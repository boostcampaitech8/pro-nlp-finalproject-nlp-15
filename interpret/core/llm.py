"""LLM API 요청 모듈 - Hydra config를 통해 관리"""

from openai import OpenAI
from omegaconf import DictConfig


def send_llmapi(
    prompt: str,
    cfg: DictConfig,
    system_prompt: str | None = None,
) -> str:
    """
    LLM API에 요청을 보내고 응답을 반환합니다.
    
    Args:
        prompt: 사용자 프롬프트 (string)
        cfg: Hydra config 객체
        system_prompt: 시스템 프롬프트 (optional)
    
    Returns:
        LLM 응답 문자열
    """
    client = OpenAI(
        api_key=cfg.llm.api_key,
        base_url=cfg.llm.base_url,
    )
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model=cfg.llm.model,
        messages=messages,
        temperature=cfg.llm.temperature,
        max_tokens=cfg.llm.max_tokens,
    )
    
    return response.choices[0].message.content
