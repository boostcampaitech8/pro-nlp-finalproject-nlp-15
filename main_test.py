import asyncio
import hydra
import logging
from omegaconf import DictConfig
from core.jsonl__loader import load_event_from_jsonl
from core.schema import extract_schema_and_narrative
from core.reasoning import ReasoningEngine
from agents.arena import run_interactive_arena
from agents.analyst import AnalystAgent

# 로그 설정 (실행 과정을 추적하기 위함)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test_pipeline(event_id: str, cfg: DictConfig):
    """
    JSONL 파일의 특정 사건(Event)을 기반으로 한 70B-7.8B-70B 테스트 워크플로우
    """
    print("\n" + "="*50)
    print(f"[Test Mode] Event ID {event_id} 분석을 시작합니다.")
    print("="*50 + "\n")

    try:
        event_data = await load_event_from_jsonl(event_id, cfg)
        news_text = event_data["content"] # 'description' 필드
        event_title = event_data["title"]
        print(f"📁 분석 대상 사건: {event_title} (ID: {event_id})")
    except Exception as e:
        logger.error(f"데이터 로드 실패: {e}")
        return

    # --- Phase 1: 사실 관계 확정 ---
    # 가이드라인: '과거 도슨트' 온도 0.1~0.2 적용
    print("\n🔍 [Phase 1] 70B 모델이 사건 요약(Description)에서 스키마를 추출 중입니다...")
    initial_analysis = await extract_schema_and_narrative(news_text, cfg)
    schema = initial_analysis["schema"]
    
    print(f"추출된 스키마: {schema}")
    print(f"초기 도슨트 요약: {initial_analysis['narrative']}\n")

    # --- Phase 2: 적대적 아레나 ---
    # 가이드라인: '미래 토론자' 온도 0.7~0.8 적용
    print("[Phase 2] 7.8B 에이전트들의 적대적 토론을 시작합니다. (RTX 4090 활용)")
    debate_log = await run_interactive_arena(schema, news_text, cfg)

    # --- Phase 3: 최종 판결 및 서사 ---
    print("\n[Phase 3] 70B 모델이 3단 추론을 통해 최종 판결을 내리는 중입니다...")
    
    # 1. 3단 추론 실행 (Offense -> Unlawfulness -> Culpability)
    reasoning_engine = ReasoningEngine(cfg)
    # 가이드라인: '최종 분석가' 온도 0.3~0.4 적용
    verdict_text = await reasoning_engine.perform_3step_reasoning(schema, debate_log)
    
    # 2. 최종 분석가 서사 요약 및 리포트 생성
    analyst = AnalystAgent(cfg)
    # 추론 결과를 분석가가 이해하기 쉬운 딕셔너리 형태로 전달
    final_report = await analyst.summarize_verdict(
        schema=schema, 
        debate_log=debate_log, 
        reasoning_result={
            "offense": "추출된 스키마 기반 검증 완료",
            "unlawfulness": "적대적 토론 기반 반박 검토 완료",
            "culpability": verdict_text
        }
    )

    print("\n" + "🏁" * 30)
    print(f"📋 [최종 분석 리포트 - Event {event_id}]")
    print(final_report)
    print("🏁" * 30 + "\n")

@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig):
    target_event_id = "9f75d53eba53" 
    asyncio.run(run_test_pipeline(target_event_id, cfg))

if __name__ == "__main__":
    main()