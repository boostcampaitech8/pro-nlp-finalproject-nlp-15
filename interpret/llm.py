"""LLM API 호출 모듈"""

from openai import OpenAI
from omegaconf import DictConfig


def send_llmapi(prompt: str, cfg: DictConfig, system_prompt: str | None = None) -> str:
    """OpenAI 호환 API로 LLM 호출"""
    client = OpenAI(api_key=cfg.llm.api_key, base_url=cfg.llm.base_url)
    
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
