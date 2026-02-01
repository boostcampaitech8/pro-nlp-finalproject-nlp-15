"""
Interactive Arena: 사용자의 이해도에 따라 점진적으로 쉬워지는 도슨트 로직 적용
"""
import asyncio
from omegaconf import DictConfig
from .bull import BullAgent
from .bear import BearAgent

async def run_interactive_arena(schema: dict, news_content: str, cfg: DictConfig) -> list[dict]:
    bull = BullAgent(cfg)
    bear = BearAgent(cfg)
    debate_log = []

    print("\n" + "="*20 + " 에이전트 적대적 토론 시작 " + "="*20)
    await asyncio.sleep(1)

    # --- Turn 1: Bull의 입장 선포 ---
    print("\n[Bull Agent] 시장 상승 가능성을 분석 중입니다...")
    bull_arg = await bull.argue(schema, news_content)
    print(f"\nBull 주장 전문:\n{bull_arg}")
    debate_log.append({"role": "bull", "content": bull_arg})

    # [이해도 체크 1] 단계별 강화 로직 적용
    n_count = 0
    while True:
        understand = input("\nBull의 주장이 충분히 이해되셨나요? (y/n): ").lower().strip()
        if understand == 'y':
            print("이해 완료. 다음 단계로 진행합니다.")
            break
        elif understand == 'n':
            n_count += 1
            # n_count에 따라 도슨트의 태도를 변경.
            level_msg = [
                "쉽게 풀어서 설명", 
                "초등학생도 이해할 수 있는 비유 사용", 
                "일상 생활의 예시를 들어 아주 천천히 설명"
            ]
            current_level = level_msg[min(n_count-1, len(level_msg)-1)]
            
            print(f"\n💡 [Docent] 사용자가 {n_count}번 이해하지 못했습니다. {current_level} 중...")
            
            # Agent의 simplify 메서드에 n_count 정보를 함께 전달.
            explanation = await bull.simplify(bull_arg, n_count=n_count)
            print(f"\n📖 Bull 보충설명 (Level {n_count}):\n{explanation}")
        else:
            print("⚠️ 'y' 또는 'n'으로 입력해주세요.")

    # --- Turn 2: Bear의 적대적 반박 ---
    print("\n[Bear Agent] 상대방 논리의 허점을 찾는 중입니다... (OBJECTION!)")
    bear_arg = await bear.counter_argue(schema, news_content, bull_arg)
    print(f"\nBear 반박 전문:\n{bear_arg}")
    debate_log.append({"role": "bear", "content": bear_arg})

    # [이해도 체크 2] 단계별 강화 로직 적용
    n_count = 0
    while True:
        understand = input("\nBear의 반박 내용과 쟁점이 이해되셨나요? (y/n): ").lower().strip()
        if understand == 'y':
            print("이해 완료. 최종 판결 단계로 이동합니다.")
            break
        elif understand == 'n':
            n_count += 1
            print(f"\n💡 [Docent] Bear가 더욱 직관적인 근거를 보충 중입니다... (시도 {n_count}회)")
            
            explanation = await bear.explain_context(bear_arg, news_content, n_count=n_count)
            print(f"\n📖 Bear 보충설명 (Level {n_count}):\n{explanation}")
        else:
            print("'y' 또는 'n'으로 입력해주세요.")

    print("\n" + "="*20 + " 토론 종료. 최종 판결로 이동합니다. " + "="*20 + "\n")
    return debate_log