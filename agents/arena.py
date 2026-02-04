import asyncio
from omegaconf import DictConfig
from .bull import BullAgent
from .bear import BearAgent
from core.initial_bias import determine_initial_bias

async def run_automated_arena(schema: dict, news_content: str, cfg: DictConfig, max_turns: int = 2) -> list[dict]:
    bull = BullAgent(cfg)
    bear = BearAgent(cfg)
    debate_log = []
    
    # 1. 초기 편향(Initial Bias) 결정 및 선공 정하기
    bias = determine_initial_bias(schema)
    print(f"\n{'='*20} [{bias.upper()} 선공] 적대적 토론 시작 {'='*20}")

    # 2. 첫 번째 발언 (기조 연설)
    if bias == "bull":
        print("\n[Bull Agent] 📈 상승 시나리오를 바탕으로 기조 연설을 시작합니다...")
        # 첫 턴이므로 opponent_arg와 history_context는 빈 값 전달
        first_msg = await bull.argue(schema, news_content, opponent_arg="", history_context="")
        print(f"\n[BULL]: {first_msg}") # 콘솔 출력 추가
        debate_log.append({"role": "bull", "content": first_msg})
    else:
        print("\n[Bear Agent] 📉 하락 리스크를 바탕으로 경고를 시작합니다...")
        first_msg = await bear.initial_warning(schema, news_content)
        print(f"\n[BEAR]: {first_msg}") # 콘솔 출력 추가
        debate_log.append({"role": "bear", "content": first_msg})
    
    current_rebuttal_target = first_msg

    # 3. 다회차 교차 토론 루프
    for turn in range(1, max_turns + 1):
        print(f"\n{'-'*15} 제 {turn} 라운드 공방 {'-'*15}")
        
        # 매번 현재까지의 로그를 갱신하여 에이전트에게 전달
        history_text = "\n".join([f"{m['role'].upper()}: {m['content'][:150]}..." for m in debate_log])
        
        if bias == "bull":
            # [라운드 A] Bear 반박
            print(f"\n[Bear Agent] Bull의 논리적 허점을 공격 중...")
            bear_msg = await bear.counter_argue(schema, news_content, current_rebuttal_target, history_text)
            print(f"\n[BEAR]: {bear_msg}")
            debate_log.append({"role": "bear", "content": bear_msg})
            
            # [라운드 B] Bull 재반박
            print(f"\n[Bull Agent] Bear의 공격을 방어하고 추가 호재를 제시 중...")
            bull_msg = await bull.argue(schema, news_content, bear_msg, history_text)
            print(f"\n[BULL]: {bull_msg}")
            debate_log.append({"role": "bull", "content": bull_msg})
            current_rebuttal_target = bull_msg
            
        else:
            # [라운드 A] Bull 반박
            print(f"\n[Bull Agent] Bear의 경고에 대해 반등 가능성을 제시 중...")
            bull_msg = await bull.argue(schema, news_content, current_rebuttal_target, history_text)
            print(f"\n[BULL]: {bull_msg}")
            debate_log.append({"role": "bull", "content": bull_msg})
            
            # [라운드 B] Bear 재반박
            print(f"\n[Bear Agent] Bull의 낙관론이 위험한 이유를 재반박 중...")
            bear_msg = await bear.counter_argue(schema, news_content, bull_msg, history_text)
            print(f"\n[BEAR]: {bear_msg}")
            debate_log.append({"role": "bear", "content": bear_msg})
            current_rebuttal_target = bear_msg

    print(f"\n{'='*20} 토론 종료 (총 {len(debate_log)}개 메시지 생성) {'='*20}\n")
    return debate_log