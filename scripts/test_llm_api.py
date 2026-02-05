"""
config/llm/local.yaml API 연결 테스트.
실행: 프로젝트 루트에서
  uv run python scripts/test_llm_api.py
또는
  python scripts/test_llm_api.py
"""
import asyncio
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig

from core.llm import send_llmapi


async def main():
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
    with initialize_config_dir(config_dir=config_dir, version_base=None):
        cfg = compose(config_name="config")
        assert hasattr(cfg, "llm"), "config에 llm이 없습니다. config/config.yaml에서 llm: local 확인."
        print(f"[Config] base_url: {cfg.llm.base_url}, model: {cfg.llm.model}\n")
        print("API 호출 중... (짧은 질문 1회)\n")
        reply = await send_llmapi(
            prompt="한 문장으로 자기소개 해줘.",
            cfg=cfg,
            role="master",
            task_type="debate",
            system_prompt="당신은 친절한 어시스턴트입니다.",
        )
        print("[모델 응답]")
        print(reply)
        if reply.startswith("Error:") or reply.startswith("Server API Error:"):
            print("\n[WARN] API connection failed. Check base_url, api_key, and network.")
            sys.exit(1)
        print("\n[OK] Got a valid reply from the API.")


if __name__ == "__main__":
    asyncio.run(main())
