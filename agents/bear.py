import json
from omegaconf import DictConfig
from core.llm import send_llmapi
from core.fact_book_utils import schema_for_prompt

class BearAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bear.system

    async def counter_argue(self, fact_book: str | dict, bull_argument: str) -> str:
        """
        상승 논리의 허점을 데이터로 반박합니다.
        """
        # 이미 문자열(JSON)인 경우와 딕셔너리인 경우를 모두 처리
        fact_str = fact_book if isinstance(fact_book, str) else json.dumps(fact_book, ensure_ascii=False, indent=2)
        
        user_prompt = self.cfg.prompts.bear.counter_user.format(
            fact_book=fact_str,
            bull_argument=bull_argument
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater",
            task_type="debate", # 0.7의 높은 온도 적용
            system_prompt=self.system_prompt
        )
