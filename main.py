import asyncio
import hydra
from omegaconf import DictConfig
from interpret.core.db import get_news
from interpret.core.schema import extract_schema_and_narrative
from interpret.core.reasoning import ReasoningEngine
from interpret.agents.arena import run_interactive_arena
from interpret.agents.analyst import AnalystAgent

async def run_pipeline(cfg: DictConfig):
    """
    비동기 방식으로 실행되는 70B-7.8B-70B 샌드위치 아키텍처 워크플로우
    """
    print("\n" + "="*50)
    print("AI 투자 도슨트 시스템을 가동합니다 (Async Mode)")
    print("="*50 + "\n")

    # 0. 데이터 로드 (2번 팀 뉴스 데이터)
    news_id = 45939 
    try:
        news_text = get_news(news_id, cfg)
    except NotImplementedError:
        news_text = "India’s Food Ministry favours lifting ban on wheat products export, moots 1 mt cap."

    # --- Phase 1: 사실 관계 확정 ---
    # 가이드라인: '과거 도슨트' 온도 0.1~0.2 적용
    print("[Phase 1] 70B 모델이 뉴스 원문에서 구성요건을 추출 중입니다...")
    initial_analysis = await extract_schema_and_narrative(news_text, cfg)
    schema = initial_analysis["schema"]
    
    print(f"\n추출된 스키마: {schema}")
    print(f"초기 도슨트 요약: {initial_analysis['narrative']}\n")

    # --- Phase 2: 적대적 아레나 ---
    # 가이드라인: '미래 토론자' 온도 0.7~0.8 적용
    print("⚔️ [Phase 2] 7.8B 에이전트들의 적대적 토론을 시작합니다.")
    debate_log = await run_interactive_arena(schema, news_text, cfg)

    # --- Phase 3: 최종 판결 및 서사 ---
    print("[Phase 3] 70B 모델이 3단 추론을 통해 판결을 내리는 중입니다...")
    
    # 1. 3단 추론 실행 (Offense -> Unlawfulness -> Culpability)
    reasoning_engine = ReasoningEngine(cfg)
    # 가이드라인: '최종 분석가' 온도 0.3~0.4 적용
    verdict_text = await reasoning_engine.perform_3step_reasoning(schema, debate_log)
    
    # 2. 최종 분석가 서사 요약 및 전달
    analyst = AnalystAgent(cfg)
    final_report = await analyst.summarize_verdict(
        schema=schema, 
        debate_log=debate_log, 
        reasoning_result={"full_verdict": verdict_text}
    )

    print("\n" + "🏁" * 30)
    print("[최종 분석 리포트]")
    print(final_report)
    print("🏁" * 30 + "\n")

@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 비동기 루프 실행
    asyncio.run(run_pipeline(cfg))

if __name__ == "__main__":
    main()