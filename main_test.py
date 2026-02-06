import asyncio
import json
import os
import hydra
import logging
from datetime import datetime, timedelta
from omegaconf import DictConfig
from core.db import DBManager
from core.fact_book_utils import fact_book_to_arena_input
from core.reasoning import ReasoningEngine
from agents.arena import run_automated_arena
from agents.analyst import AnalystAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Phase 1 입력: fact_book 생성/로드 파라미터 (필요 시 수정)
COMMODITY_NAME = "은"
END_DATE = "2026-01-15"
N_DAYS = 14

# 기대 파일명: fact_book_{종목}_{start}_{end}.json (이미 있으면 로드, 없으면 DB에서 생성)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FACT_BOOKS_DIR = os.path.join(PROJECT_ROOT, "data", "fact_books")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "data", "reports")


def _expected_fact_book_path(commodity: str, end_date: str, n_days: int) -> str:
    """end_date, n_days로 기간 시작일을 구해 기대 파일 경로 반환."""
    end_d = datetime.strptime(end_date, "%Y-%m-%d")
    start_d = end_d - timedelta(days=n_days - 1)
    start_s = start_d.strftime("%Y-%m-%d")
    return os.path.join(FACT_BOOKS_DIR, f"fact_book_{commodity}_{start_s}_{end_date}.json")


async def run_test_pipeline(cfg: DictConfig):
    print("\n" + "=" * 50)
    print("[Test Mode] fact_book 기반 에이전트 회의 파이프라인")
    print("=" * 50 + "\n")

    # --- Phase 1: fact_book 로드(있으면) 또는 DB에서 생성 ---
    expected_path = _expected_fact_book_path(COMMODITY_NAME, END_DATE, N_DAYS)

    if os.path.isfile(expected_path):
        print("[Phase 1] 기존 팩트북 파일 사용 중...")
        try:
            with open(expected_path, "r", encoding="utf-8") as f:
                fact_book = json.load(f)
        except Exception as e:
            logger.error(f"팩트북 파일 로드 실패: {e}")
            return
        print(f"  경로: {expected_path}")
    else:
        print("[Phase 1] DB에서 팩트북 생성 중...")
        try:
            manager = DBManager(cfg)
            fact_book = manager.get_batch_fact_book(COMMODITY_NAME, END_DATE, N_DAYS)
        except Exception as e:
            logger.error(f"팩트북 생성 실패: {e}")
            return
        if not fact_book or not fact_book.get("events"):
            logger.warning("수집된 사건이 없습니다. 종목/기간을 확인하세요.")
            return
        os.makedirs(FACT_BOOKS_DIR, exist_ok=True)
        manager.save_fact_book(fact_book, expected_path)
        print(f"  저장: {expected_path}")

    meta = fact_book.get("analysis_metadata", {})
    print(f"  종목: {meta.get('commodity')}, 기간: {meta.get('period')}, 사건 수: {len(fact_book.get('events', []))}건")

    # fact_book → 에이전트 입력 형태로 변환
    schema, news_content = fact_book_to_arena_input(fact_book)
    print(f"✅ Phase 1 완료. 스키마/맥락 생성됨.\n")

    # --- Phase 2: Bull/Bear 적대적 아레나 ---
    max_turns = 2
    print("[Phase 2] 에이전트 자율 적대적 토론 진행 중...")
    debate_log = await run_automated_arena(schema, news_content, cfg, max_turns=max_turns)

    # --- Phase 3: 최종 판결 및 서사 통합 ---
    print("\n[Phase 3] 최종 판결 및 리포트 생성 중...")
    reasoning_engine = ReasoningEngine(cfg)
    verdict_text = await reasoning_engine.perform_3step_reasoning(schema, debate_log)

    analyst = AnalystAgent(cfg)
    final_report = await analyst.summarize_verdict(
        schema=schema,
        debate_log=debate_log,
        reasoning_result={
            "offense": "스키마 팩트 체크 완료",
            "unlawfulness": "상호 반박 논리 검토 완료",
            "culpability": verdict_text,
        },
    )

    print("\n" + "🏁" * 30)
    print(f"📋 [최종 분석 리포트 - {meta.get('commodity', '')} {meta.get('period', {})}]")
    print(final_report)
    print("🏁" * 30 + "\n")
from omegaconf import DictConfig
from core.reasoning import ReasoningEngine

    # 토론 로그 + 최종 리포트를 디스크에 저장 (터미널 출력과 동일한 내용)
    period = meta.get("period", {})
    start_s = period.get("start", "start")
    end_s = period.get("end", "end")
    commodity = meta.get("commodity", "unknown")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_name = f"report_{commodity}_{start_s}_{end_s}.txt"
    report_path = os.path.join(REPORTS_DIR, report_name)

    lines = [
        "=" * 50,
        "[Test Mode] fact_book 기반 에이전트 회의 파이프라인",
        "=" * 50,
        "",
        f"종목: {commodity}, 기간: {start_s} ~ {end_s}, 사건 수: {len(fact_book.get('events', []))}건",
        "",
        "=" * 20 + " [Phase 2] Bull/Bear 토론 로그 " + "=" * 20,
        "",
    ]
    for m in debate_log:
        role = m.get("role", "").upper()
        content = m.get("content", "")
        lines.append(f"[{role}]:")
        lines.append(content)
        lines.append("")
    lines.extend([
        "=" * 20 + " [Phase 3] 최종 분석 리포트 " + "=" * 20,
        "",
        f"📋 [최종 분석 리포트 - {commodity} {period}]",
        "",
        final_report,
        "",
        "🏁" * 30,
    ])
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] 토론·리포트: {report_path}\n")

    # 백엔드 전달용 JSON (같은 base name으로 저장)
    turn_start = debate_log[0]["role"] if debate_log else "bull"
    bull_contents = [m["content"] for m in debate_log if m.get("role") == "bull"]
    bear_contents = [m["content"] for m in debate_log if m.get("role") == "bear"]
    report_json = {
        "commodity": commodity,
        "period": {
            "start": period.get("start"),
            "end": period.get("end"),
            "delta_days": period.get("delta_days"),
        },
        "events_cnt": len(fact_book.get("events", [])),
        "turn": max_turns,
        "agent": {
            "turn_start": turn_start,
            "bull": bull_contents,
            "bear": bear_contents,
        },
        "final_report": final_report,
    }
    report_json_path = os.path.join(REPORTS_DIR, report_name.replace(".txt", ".json"))
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    print(f"[저장] 백엔드용 JSON: {report_json_path}\n")


@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig):
    asyncio.run(run_test_pipeline(cfg))

#     asyncio.run(run_pipeline(cfg))

# async def run_pipeline(cfg: DictConfig):
#     print("\n" + "="*50 + "\n📈 AI 금융 분석 파이프라인 가동 (v2.1)\n" + "="*50)
    
#     target = input("👉 종목(은/구리 등): ").strip()
#     start = input("📅 시작일(YYYY-MM-DD): ").strip()
#     end = input("📅 종료일(YYYY-MM-DD): ").strip()

#     if not all([target, start, end]):
#         print("❌ 입력을 확인해주세요."); return

#     engine = ReasoningEngine(cfg)
    
#     print(f"\n🚀 {target} 시장 분석 및 토론을 시작합니다...")
#     report = await engine.run_full_analysis(target, start, end)
    
#     print(f"\n⚖️ [최종 투자 리포트]\n{report}")
#     print("\n" + "="*50 + "\n✅ 분석 완료\n" + "="*50)

if __name__ == "__main__":
    main()
