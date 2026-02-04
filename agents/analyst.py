# interpret/agents/analyst.py
from omegaconf import DictConfig
from core.llm import send_llmapi

class AnalystAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.system_prompt = cfg.prompts.analyst_system

    async def summarize_verdict(self, schema: dict, debate_log: list, reasoning_result: dict) -> str:
        # 1. 토론 로그를 텍스트로 변환 (안 그러면 에러 나거나 지저분하게 들어갑니다)
        debate_str = "\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in debate_log])
        
        # 2. 3단 추론 결과 매핑
        offense = reasoning_result.get("offense", "분석 불가")
        unlawfulness = reasoning_result.get("unlawfulness", "분석 불가")
        culpability = reasoning_result.get("culpability", "판단 보류")
        
        # 3. 프롬프트 구성 (KeyError 방지를 위해 변수명 확인 필수)
        user_prompt = self.cfg.prompts.analyst_summary_user.format(
            schema=schema,
            debate_log=debate_str,
            offense_check=offense,
            unlawfulness_check=unlawfulness,
            final_culpability=culpability
        )
        
        # 4. 7.8B 또는 70B 모델 호출
        response = await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="master",
            task_type="analysis",
            system_prompt=self.system_prompt,
        )
        return response