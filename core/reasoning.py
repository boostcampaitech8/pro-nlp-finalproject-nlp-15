"""
Trichotomous Reasoning Engine: 70B 서버 모델 기반
Offense -> Unlawfulness -> Culpability 3단 검증을 비동기로 수행합니다.
"""
from omegaconf import DictConfig
from .llm import send_llmapi

class ReasoningEngine:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # verdict.yaml에 정의된 판사(Judge) 시스템 프롬프트 로드
        self.system_prompt = cfg.prompts.verdict_system

    async def perform_3step_reasoning(self, schema: dict, debate_log: list) -> str:

        # 1. 토론 로그를 하나의 텍스트로 결합
        formatted_log = "\n".join([f"{log['role'].upper()}: {log['content']}" for log in debate_log])
        
        # 2. 프롬프트 구성 (verdict.yaml의 변수 매핑)
        user_prompt = self.cfg.prompts.verdict_user.format(
            schema=schema,
            debate_log=formatted_log
        )
        
        print("판사가 3단 추론을 통해 최종 판결을 검토 중입니다...")
        
        # task_type="analysis"를 지정하여 가이드라인 온도(0.3~0.4)를 적용.
        # 일관된 논리를 위해 마스터 모델의 긴 토큰 제한이 적용.
        verdict_result = await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="master",
            task_type="analysis",
            system_prompt=self.system_prompt
        )
        
        return verdict_result

    def check_moot(self, verdict: str) -> bool:
        """
        구성요건 미달(Moot) 여부를 판단합니다.
        1단계(Offense)에서 사건의 실체가 없다고 판단되면 이후 과정을 생략할 수 있습니다.
        """
        # 판결문 내 특정 키워드를 통해 조기 종료 여부 확인
        moot_keywords = ["Moot", "요건 미달", "실체적 요건 결여", "No Offense"]
        return any(keyword in verdict for keyword in moot_keywords)