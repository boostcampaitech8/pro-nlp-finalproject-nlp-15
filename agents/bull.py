from omegaconf import DictConfig
from core.llm import send_llmapi

class BullAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.bull_system

    async def argue(self, schema: dict, news_content: str, opponent_arg: str = "", history_context: str = "") -> str:
        # KeyError 방지를 위한 기본값 설정
        opp_text = opponent_arg if opponent_arg else "상대방의 반박이 아직 없는 초기 제안 단계입니다."
        hist_text = history_context if history_context else "이전 대화 기록 없음"

        user_prompt = self.cfg.prompts.bull_argue_user.format(
            schema=schema,
            news_content=news_content,
            opponent_arg=opp_text,
            history_context=hist_text
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="debater", # 32B 서버 모델 활용
            task_type="debate",
            system_prompt=self.system_prompt
        )