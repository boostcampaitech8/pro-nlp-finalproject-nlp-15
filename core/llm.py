import os
import torch
import aiohttp
import asyncio
import json
from omegaconf import DictConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

_LOCAL_MODEL = None
_LOCAL_TOKENIZER = None

def get_local_model(cfg: DictConfig):
    global _LOCAL_MODEL, _LOCAL_TOKENIZER
    if _LOCAL_MODEL is None:
        raw_path = cfg.llm.debater.model_path
        model_path = os.path.abspath(raw_path)
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 
        )
        
        print(f"Loading local model from: {model_path}")
        
        _LOCAL_TOKENIZER = AutoTokenizer.from_pretrained(
            model_path, 
            local_files_only=True,
            trust_remote_code=True
        )
        _LOCAL_MODEL = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True
        )
        print("Local model loaded successfully.")
    return _LOCAL_MODEL, _LOCAL_TOKENIZER

async def send_llmapi(
    prompt: str,
    cfg: DictConfig,
    role: str = "master",      # "master" 또는 "debater"
    task_type: str = "debate", # "schema", "debate", "analysis"
    system_prompt: str | None = None,
    temp_override: float | None = None
) -> str:
    """
    역할 및 태스크 타입에 따라 온도와 토큰 수를 최적화하여 호출합니다.
    """
    actual_role = "debater"
    # 1. 태스크별 설정 로드
    target_cfg = cfg.llm.master if role == "master" else cfg.llm.debater
    
    # 가이드라인 온도 참조 (schema: 0.1 / debate: 0.7 / analysis: 0.4)
    temp = temp_override if temp_override is not None else cfg.llm.temperatures.get(task_type, 0.7)
    
    # --- [Role: Master] 석진님 서버 API 호출 (비동기 방식) ---
    if actual_role == "master" and role == "master":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_cfg.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": target_cfg.max_tokens,
            "stream": False 
        }
        headers = {"Authorization": f"Bearer {target_cfg.api_key}", "Content-Type": "application/json"}

        try:
            # URL 끝에 /v1이 중복되지 않도록 처리
            base_url = target_cfg.base_url.rstrip('/')
            full_url = f"{base_url}/chat/completions"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(full_url, json=payload, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        return f"Error: Status {response.status} - {err_text}"
                    
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            # 타임아웃이나 연결 실패 시 상세 메시지 출력
            return f"Server API Error: {str(e)} (Check if IP {target_cfg.base_url} is correct)"

    else:
        model, tokenizer = get_local_model(cfg)
        print(f"[Local 7.8B] {task_type} 작업을 수행 중입니다...")
        # EXAONE 스타일 프롬프트 구성 (시스템 프롬프트 명시)
        formatted_prompt = f"[[SYSTEM]]: {system_prompt}\n\n[[USER]]: {prompt}\n[[ASSISTANT]]:" if system_prompt else f"[[USER]]: {prompt}\n[[ASSISTANT]]:"
        
        inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
        
        loop = asyncio.get_event_loop()
        outputs = await loop.run_in_executor(None, lambda: model.generate(
            **inputs,
            max_new_tokens=target_cfg.max_tokens,
            temperature=temp,
            do_sample=True if temp > 0 else False,
            pad_token_id=tokenizer.eos_token_id
        ))
        
        return tokenizer.decode(outputs[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True).strip()