import asyncio
import hydra
import logging
from omegaconf import DictConfig
from core.jsonl__loader import load_event_from_jsonl
from core.schema import extract_schema_and_narrative
from core.reasoning import ReasoningEngine
from agents.arena import run_automated_arena
from agents.analyst import AnalystAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test_pipeline(event_id: str, cfg: DictConfig):
    print("\n" + "="*50)
    print(f"[Test Mode] Event ID {event_id} 하이브리드 분석 시작")
    print("="*50 + "\n")

    try:
        # 데이터 로드
        event_data = await load_event_from_jsonl(event_id, cfg)
        news_text = event_data["content"]
        event_title = event_data["title"]
        print(f"📁 대상 사건: {event_title}\n")
    except Exception as e:
        logger.error(f"데이터 로드 실패: {e}")
        return

    # --- Phase 1: 70B 사실 관계 확정 ---
    # 낮은 온도로 객관적 스키마 추출 (0.1~0.2)
    print("🔍 [Phase 1] 70B 모델: 사건 스키마 및 초기 서사 추출 중...")
    initial_analysis = await extract_schema_and_narrative(news_text, cfg)
    schema = initial_analysis["schema"]
    
    print(f"✅ 추출된 스키마: {schema}")
    print(f"📖 초기 요약: {initial_analysis['narrative']}\n")

    # --- Phase 2: 32B 적대적 아레나 ---
    # 높은 온도로 창의적/공격적 토론 (0.7~0.8)
    # initial_bias 로직에 따라 Bull/Bear 선공이 자동 결정됨
    print("[Phase 2] 32B 에이전트: 자율 적대적 토론 진행 중 (RTX 4090 활용)")
    debate_log = await run_automated_arena(schema, news_text, cfg, max_turns=2)

    # --- Phase 3: 70B 최종 판결 및 서사 통합 ---
    print("\n[Phase 3] 70B 모델: 최종 판결 및 리포트 생성 중...")
    
    # 1. 3단 추론(Verdict) 실행
    reasoning_engine = ReasoningEngine(cfg)
    # 토론 로그를 기반으로 최종 승패 판정 (온도 0.3)
    verdict_text = await reasoning_engine.perform_3step_reasoning(schema, debate_log)
    
    # 2. 투자 도슨트 리포트 요약
    analyst = AnalystAgent(cfg)
    final_report = await analyst.summarize_verdict(
        schema=schema, 
        debate_log=debate_log, 
        reasoning_result={
            "offense": "스키마 팩트 체크 완료",
            "unlawfulness": "상호 반박 논리 검토 완료",
            "culpability": verdict_text # 70B의 최종 판결문 주입
        }
    )

    print("\n" + "🏁" * 30)
    print(f"📋 [최종 분석 리포트 - {event_title}]")
    print(final_report)
    print("🏁" * 30 + "\n")

@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig):
    # 테스트 타겟 설정
    target_event_id = "9f75d53eba53" 
    asyncio.run(run_test_pipeline(target_event_id, cfg))

if __name__ == "__main__":
    main()