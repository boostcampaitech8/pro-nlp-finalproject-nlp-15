from omegaconf import DictConfig
from core.llm import send_llmapi

class BullAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bull_system 

    async def argue(self, schema: dict, news_content: str) -> str:
        """뉴스 데이터를 바탕으로 상승 논리를 자연스러운 구어체로 주장합니다."""
        user_prompt = self.cfg.prompts.bull_argue_user.format(
            schema=schema,
            news_content=news_content
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater", # 4090 활용
            task_type="debate",
            system_prompt=self.system_prompt
        )

    async def simplify(self, original_text: str, n_count: int = 1) -> str:
        """사용자가 이해하지 못할수록 더 쉬운 비유(치킨집 등)를 사용하여 설명합니다."""
        # n_count가 2이상이면 'easy' 버전을, 1이면 일반 'simplify' 버전을 사용.
        prompt_key = "bull_simplify_user" if n_count == 1 else "bull_simplify_easy_user"
        template = getattr(self.cfg.prompts, prompt_key)
        
        user_prompt = template.format(original_text=original_text, n_count=n_count)
        
        return await send_llmapi(
            prompt=user_prompt, 
            cfg=self.cfg, 
            role="debater", 
            task_type="analysis",
            system_prompt=self.system_prompt,
            temp_override=0.8 # 비유의 창의성을 위해 온도를 약간 높임
        )