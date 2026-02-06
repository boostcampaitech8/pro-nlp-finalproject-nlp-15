"""
Reasoning Engine: 내일 가격 예측을 위한 멀티에이전트 제어기
Analyst(선별) -> Arena(3턴 토론) -> Verdict(예측 리포트) 순으로 수행합니다.
"""
import json
import asyncio
from omegaconf import DictConfig
from .llm import send_llmapi
from agents.analyst import AnalystAgent
from agents.bull import BullAgent
from agents.bear import BearAgent

class ReasoningEngine:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # 1. 하위 에이전트 초기화
        self.analyst = AnalystAgent(cfg)
        self.bull = BullAgent(cfg)
        self.bear = BearAgent(cfg)
        
        # 2. 판사 시스템 프롬프트 로드 (verdict.yaml의 계층 구조 반영)
        self.system_prompt = cfg.prompts.verdict.system

    async def predict_tomorrow(self, commodity: str, base_date: str):
        """
        [1단계: Analyst] 팩트북 생성 (선별 + 요약)
        """
        print(f"🔍 [Analyst] '{commodity}' 시장 최신 데이터 및 10년 추세 분석 중...")
        # db.py 로직을 포함한 고농축 팩트북 생성 (AnalystAgent 내부에서 수행)
        fact_book = await self.analyst.create_enriched_fact_book(commodity, "2016-01-01", base_date)
        events = fact_book.get('events', [])
        
        if not events:
            return "💡 현재 분석할 유의미한 시장 사건이 발견되지 않았습니다."

        # [2단계: Arena] 3턴 핵심 토론 (Bull -> Bear -> Bull)
        debate_log = []
        for idx, event in enumerate(events):
            print(f"\n⚔️ [사건 {idx+1}] '{event['event_core']['title']}' 3턴 토론 시작")
            
            # Turn 1: Bull의 기조 발언
            bull_turn1 = await self.bull.argue(fact_book=event, opponent_arg="상승 시나리오를 제시하십시오.")
            print(f"[Bull]: {bull_turn1}...")

            # Turn 2: Bear의 반격
            bear_turn2 = await self.bear.counter_argue(fact_book=event, bull_argument=bull_turn1)
            print(f"[Bear]: {bear_turn2}...")

            # Turn 3: Bull의 최종 재반론 (최소화된 토론의 마침표)
            bull_turn3 = await self.bull.argue(fact_book=event, opponent_arg=f"상대의 하락 리스크({bear_turn2[:50]}...)를 팩트로 반박하십시오.")
            print(f"[Bull Final]: {bull_turn3}...")
            
            debate_log.append({
                "event_title": event['event_core']['title'],
                "log": f"Bull: {bull_turn1}\nBear: {bear_turn2}\nBull(Final): {bull_turn3}"
            })

        # [3단계: Verdict] 최종 방향성 예측 및 리포트 작성
        print("\n⚖️ [Verdict] 모든 토론을 종합하여 내일의 가격을 예측합니다...")
        return await self._generate_prediction_report(fact_book, debate_log, base_date)

    async def _generate_prediction_report(self, fact_book: dict, debate_log: list, base_date: str):
        """팩트북과 토론 로그를 결합하여 최종 예측 리포트를 생성합니다."""
        
        # 토론 로그 통합 텍스트화
        debate_str = "\n".join([f"### {d['event_title']}\n{d['log']}" for d in debate_log])
        
        # YAML의 judge_user 템플릿에 데이터 주입
        user_prompt = self.cfg.prompts.verdict.judge_user.format(
            end_date=base_date,
            fact_book=json.dumps(fact_book, indent=2, ensure_ascii=False),
            debate_results=debate_str
        )
        
        # 32B 모델의 신중한 추론 (verdict 온도 0.3 적용)
        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="master", 
            task_type="verdict", # local.yaml의 verdict(0.3) 온도 사용
            system_prompt=self.system_prompt
        )