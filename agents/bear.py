from omegaconf import DictConfig
from core.llm import send_llmapi

class BearAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bear_system

    async def counter_argue(self, schema: dict, news_content: str, bull_argument: str) -> str:
        """Bull의 주장에 대해 지시문 복창 없이 날카로운 반박 대사를 생성합니다."""
        user_prompt = self.cfg.prompts.bear_counter_user.format(
            schema=schema,
            news_content=news_content,
            bull_argument=bull_argument
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater",
            task_type="debate",
            system_prompt=self.system_prompt
        )
        
    async def explain_context(self, bear_arg: str, news_content: str, n_count: int = 1):
        """이해도가 낮을수록 일상적인 사례(중고거래 등)를 들어 반박의 이유를 설명합니다."""
        prompt_key = "bear_explain_context_user" if n_count == 1 else "bear_explain_easy_user"
        template = getattr(self.cfg.prompts, prompt_key)
        
        user_prompt = template.format(
            bear_arg=bear_arg, 
            news_content=news_content,
            n_count=n_count
        )

        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater",
            task_type="analysis",
            system_prompt=self.system_prompt
        )