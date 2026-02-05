import aiohttp
from omegaconf import DictConfig

# config에 master/debater가 있으면 역할별 설정, 없으면 cfg.llm 자체를 API 설정으로 사용
def _get_llm_cfg(cfg: DictConfig, role: str):
    if hasattr(cfg.llm, "master") and hasattr(cfg.llm, "debater"):
        return cfg.llm.master if role == "master" else cfg.llm.debater
    return cfg.llm


async def send_llmapi(
    prompt: str,
    cfg: DictConfig,
    role: str = "master",      # "master" 또는 "debater"
    task_type: str = "debate", # "schema", "debate", "analysis"
    system_prompt: str | None = None,
    temp_override: float | None = None
) -> str:
    """
    config/llm (예: local.yaml)에 정의된 API로 요청합니다.
    역할 및 태스크 타입에 따라 온도와 토큰 수를 적용합니다.
    """
    target_cfg = _get_llm_cfg(cfg, role)
    temp = (
        temp_override
        if temp_override is not None
        else getattr(cfg.llm, "temperatures", {}).get(task_type, getattr(target_cfg, "temperature", 0.7))
    )
    max_tokens = getattr(target_cfg, "max_tokens", 2048)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": target_cfg.model,
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tokens,
        "stream": False,
    }
    api_key = getattr(target_cfg, "api_key", "EMPTY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    base_url = target_cfg.base_url.rstrip("/")
    full_url = f"{base_url}/chat/completions"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(full_url, json=payload, headers=headers, timeout=30) as response:
                if response.status != 200:
                    err_text = await response.text()
                    return f"Error: Status {response.status} - {err_text}"
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Server API Error: {str(e)} (Check base_url: {target_cfg.base_url})"