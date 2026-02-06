"""
Arena: 적대적 데이터 토론장
선공은 initial_bias로 정하고, 3라운드(Bull↔Bear 또는 Bear↔Bull) 반복.
"""
from omegaconf import DictConfig
from .bull import BullAgent
from .bear import BearAgent
from core.fact_book_utils import fact_book_to_arena_input
from core.initial_bias import determine_initial_bias

ARENA_MAX_CONTEXT_CHARS = 30_000
NUM_ROUNDS = 3


async def run_automated_arena(fact_book: dict, cfg: DictConfig) -> list[dict]:
    """
    팩트북 기반으로 3라운드 토론 (한 라운드 = 선공 1발언 + 후공 1발언).
    선공은 determine_initial_bias(schema)로 결정.
    """
    bull = BullAgent(cfg)
    bear = BearAgent(cfg)
    debate_log = []

    schema, news_content = fact_book_to_arena_input(
        fact_book,
        max_events=15,
        max_context_chars=ARENA_MAX_CONTEXT_CHARS,
    )
    fact_str = news_content
    if len(fact_str) > ARENA_MAX_CONTEXT_CHARS:
        fact_str = fact_str[:ARENA_MAX_CONTEXT_CHARS] + "\n\n... (맥락 길이 제한)"

    first_speaker = determine_initial_bias(schema)
    second_speaker = "bear" if first_speaker == "bull" else "bull"
    print(f"\n{'='*20} [{first_speaker.upper()} 선공] {NUM_ROUNDS}라운드 토론 {'='*20}")

    for round_no in range(1, NUM_ROUNDS + 1):
        print(f"\n--- 라운드 {round_no}/{NUM_ROUNDS} ---")

        if first_speaker == "bull":
            # Bull 발언
            if round_no == 1:
                opp_arg = "내일의 시장 상승 시나리오를 데이터 기반으로 제시하십시오."
            else:
                prev = debate_log[-1]["content"]
                opp_arg = f"상대 발언: {prev[:200]}..." if len(prev) > 200 else prev
            print("\n[Bull Agent] 📈 발언 중...")
            msg = await bull.argue(fact_book=fact_str, opponent_arg=opp_arg)
            print(f"[BULL]: {msg}")
            debate_log.append({"role": "bull", "content": msg})

            # Bear 발언
            print("\n[Bear Agent] 📉 반박 중...")
            msg = await bear.counter_argue(fact_book=fact_str, bull_argument=debate_log[-1]["content"])
            print(f"[BEAR]: {msg}")
            debate_log.append({"role": "bear", "content": msg})
        else:
            # Bear 선공
            if round_no == 1:
                print("\n[Bear Agent] 📉 선공 경고 중...")
                msg = await bear.initial_warning(fact_str)
            else:
                prev = debate_log[-1]["content"]
                print("\n[Bear Agent] 📉 반박 중...")
                msg = await bear.counter_argue(fact_book=fact_str, bull_argument=prev)
            print(f"[BEAR]: {msg}")
            debate_log.append({"role": "bear", "content": msg})

            # Bull 발언
            opp_arg = debate_log[-1]["content"][:200] + "..." if len(debate_log[-1]["content"]) > 200 else debate_log[-1]["content"]
            print("\n[Bull Agent] 📈 반박 중...")
            msg = await bull.argue(fact_book=fact_str, opponent_arg=opp_arg)
            print(f"[BULL]: {msg}")
            debate_log.append({"role": "bull", "content": msg})

    print(f"\n{'='*20} 토론 종료 (총 {len(debate_log)}개 메시지) {'='*20}\n")
    return debate_log
