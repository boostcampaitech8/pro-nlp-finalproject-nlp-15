"""
Analyst Agent (최종 분석가): 70B 서버 모델 기반
3단 추론 결과와 토론 로그를 종합하여 사용자 친화적인 최종 리포트를 작성합니다.
"""
from omegaconf import DictConfig
from core.llm import send_llmapi

class AnalystAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # analyst_agent.yaml에 정의된 도슨트 페르소나 로드
        self.system_prompt = cfg.prompts.analyst_system

    async def summarize_verdict(self, schema: dict, debate_log: list, reasoning_result: dict) -> str:
        """
        기술적인 3단 추론 결과를 일반 사용자가 이해하기 쉬운 서사로 변환합니다.
        비동기 호출을 통해 70B 마스터 모델의 지능을 활용합니다.
        """
        # 1. 3단 추론 단계별 결과 추출 (reasoning.py 결과와 연동)
        offense = reasoning_result.get("offense", "분석 불가")
        unlawfulness = reasoning_result.get("unlawfulness", "분석 불가")
        culpability = reasoning_result.get("culpability", "판단 보류")
        
        # 2. 프롬프트 구성
        user_prompt = self.cfg.prompts.analyst_summary_user.format(
            schema=schema,
            debate_log=debate_log,
            offense_check=offense,
            unlawfulness_check=unlawfulness,
            final_culpability=culpability
        )
        
        # 3. 서버 70B 호출 (role="master")
        # task_type="analysis"를 지정하여 가이드라인 온도(0.3~0.4)를 적용.
        # 마스터 모델 설정을 통해 긴 토큰(Max Tokens)이 적용.
        response = await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="master",
            task_type="analysis",
            system_prompt=self.system_prompt
        )
        
        return response