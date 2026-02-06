# agents/bull.py
import json
from omegaconf import DictConfig
from core.llm import send_llmapi

class BullAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bull.system

    async def argue(self, fact_book: str | dict, opponent_arg: str = "") -> str:
        """
        팩트북 기반의 상승 시나리오를 전개하거나 Bear의 반격에 재반론합니다.
        """
        fact_str = fact_book if isinstance(fact_book, str) else json.dumps(fact_book, ensure_ascii=False, indent=2)
        opp_text = opponent_arg if opponent_arg else "내일의 시장 상승 시나리오를 데이터 기반으로 제시하십시오."
        
        user_prompt = self.cfg.prompts.bull.argue_user.format(
            fact_book=fact_str,
            opponent_arg=opp_text
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater",
            task_type="debate", # 0.7의 높은 온도 적용
            system_prompt=self.system_prompt
        )