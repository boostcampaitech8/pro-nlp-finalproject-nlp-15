"""
Arena: 적대적 데이터 토론장
최소화된 3턴 공방(Bull-Bear-Bull)을 통해 데이터의 다각적 해석을 이끌어냅니다.
"""
import asyncio
import json
from omegaconf import DictConfig
from .bull import BullAgent
from .bear import BearAgent

async def run_automated_arena(fact_book: dict, cfg: DictConfig) -> list[dict]:
    """
    팩트북 데이터를 기반으로 3턴 내에 내일 가격에 대한 토론을 종결합니다.
    """
    bull = BullAgent(cfg)
    bear = BearAgent(cfg)
    debate_log = []
    
    # 팩트북 문자열화 (LLM에게 전달할 컨텍스트)
    fact_str = json.dumps(fact_book, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*20} 🎯 내일 가격 예측: 3턴 핵심 토론 {'='*20}")

    # --- [Turn 1] Bull: 상승 시나리오 전개 ---
    print("\n[Bull Agent] 📈 내일 상승 요인 분석 중...")
    # arena.yaml의 bull.argue_user 템플릿에 맞춤
    bull_1 = await bull.argue(
        fact_book=fact_str, 
        opponent_arg="내일의 시장 상승 시나리오를 데이터 기반으로 제시하십시오."
    )
    print(f"[BULL]: {bull_1}")
    debate_log.append({"role": "bull", "content": bull_1})

    # --- [Turn 2] Bear: 하락 리스크 및 Bull 논리 반박 ---
    print("\n[Bear Agent] 📉 상승 논리 허점 및 하락 리스크 포착 중...")
    # arena.yaml의 bear.counter_user 템플릿에 맞춤
    bear_2 = await bear.counter_argue(
        fact_book=fact_str, 
        bull_argument=bull_1
    )
    print(f"[BEAR]: {bear_2}")
    debate_log.append({"role": "bear", "content": bear_2})

    # --- [Turn 3] Bull: Bear의 리스크 반박 및 최종 확신 ---
    print("\n[Bull Agent] 🛡️ Bear의 하락 공격에 대한 최종 재반론 중...")
    # Bear의 논리를 무력화하고 상승 시나리오를 강화
    bull_3 = await bull.argue(
        fact_book=fact_str, 
        opponent_arg=f"상대의 하락 리스크({bear_2[:50]}...)를 팩트로 반박하고 상승 가능성을 확정하십시오."
    )
    print(f"[BULL FINAL]: {bull_3}")
    debate_log.append({"role": "bull_final", "content": bull_3})

    print(f"\n{'='*20} 토론 종료 (3턴 데이터 공방 완료) {'='*20}\n")
    return debate_log