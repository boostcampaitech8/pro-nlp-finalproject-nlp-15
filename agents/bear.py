from omegaconf import DictConfig
from core.llm import send_llmapi

class BearAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bear_system

    async def counter_argue(self, schema: dict, news_content: str, bull_argument: str, history_context: str = "") -> str:
        hist_text = history_context if history_context else "이전 대화 기록 없음"

        user_prompt = self.cfg.prompts.bear_counter_user.format(
            schema=schema,
            news_content=news_content,
            bull_argument=bull_argument,
            history_context=hist_text
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater",
            task_type="debate",
            system_prompt=self.system_prompt
        )

    async def initial_warning(self, schema: dict, news_content: str) -> str:
        """하락 뉴스가 많을 때 Bear가 먼저 포문을 여는 메서드"""
        user_prompt = f"사건 데이터({news_content})와 스키마({schema})를 볼 때, 시장의 붕괴나 하락이 우려됩니다. 당신의 경고를 들려주세요."
        return await send_llmapi(prompt=user_prompt, cfg=self.cfg, role="debater", task_type="debate", system_prompt=self.system_prompt)