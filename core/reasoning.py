"""
Trichotomous Reasoning Engine: 70B 서버 모델 기반
Offense -> Unlawfulness -> Culpability 3단 검증을 비동기로 수행합니다.
"""
from omegaconf import DictConfig
from .llm import send_llmapi
from .fact_book_utils import schema_for_prompt

class ReasoningEngine:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # verdict.yaml에 정의된 판사(Judge) 시스템 프롬프트 로드
        self.system_prompt = cfg.prompts.verdict_system

    async def perform_3step_reasoning(self, schema, debate_log: list):
        # 리스트 형태의 로그를 텍스트로 병합
        debate_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in debate_log])
        schema_str = schema_for_prompt(schema)

        # YAML에 정의한 verdict_user 키와 변수명을 일치시킵니다.
        user_prompt = self.cfg.prompts.verdict_user.format(
            schema=schema_str,
            debate_log=debate_str
        )
        
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="analyst", # 7.8B 로컬 모델 활용
            task_type="verdict",
            system_prompt=self.cfg.prompts.verdict_system
        )

    def check_moot(self, verdict: str) -> bool:
        """
        구성요건 미달(Moot) 여부를 판단합니다.
        1단계(Offense)에서 사건의 실체가 없다고 판단되면 이후 과정을 생략할 수 있습니다.
        """
        # 판결문 내 특정 키워드를 통해 조기 종료 여부 확인
        moot_keywords = ["Moot", "요건 미달", "실체적 요건 결여", "No Offense"]
        return any(keyword in verdict for keyword in moot_keywords)