"""
RDB 연결 및 쿼리 테스트 스크립트.

실행 예시 (프로젝트 루트에서):

    uv run python scripts/test_db.py
    # 또는
    python scripts/test_db.py

config/config.yaml 의 `db: ...` 설정과
`config/db/` 아래 rdb 설정이 올바른지 확인한 뒤 사용하세요.
"""

import asyncio
import os
import sys

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig

# 프로젝트 루트를 PYTHONPATH에 추가해서 `core`, `agents` 등을 import 가능하게 함
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.db import DBManager


async def main() -> None:
    # 프로젝트 루트 기준 config 디렉터리
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(project_root, "config")

    # Hydra로 config 로드
    with initialize_config_dir(config_dir=config_dir, version_base=None):
        cfg: DictConfig = compose(config_name="config")

    if not hasattr(cfg, "db"):
        print("[ERROR] cfg.db 설정을 찾을 수 없습니다. config/config.yaml 의 defaults 에 db 항목을 확인하세요.")
        sys.exit(1)

    print(f"[INFO] DB 설정 로딩 완료: {cfg.db}")

    # DBManager 초기화 및 간단한 팩트북 조회
    try:
        manager = DBManager(cfg)
    except Exception as e:
        print(f"[ERROR] DB 연결 실패: {e}")
        sys.exit(1)

    # 테스트용 파라미터 (필요시 종목/기간 수정)
    commodity_name = "은"  # 예시: DB에 존재하는 name_ko 값으로 변경 가능
    start_date = "2026-01-01"
    end_date = "2026-01-15"

    print(f"[INFO] get_batch_fact_book 호출: 종목={commodity_name}, 기간={start_date}~{end_date}")

    # 함수 자체는 동기식이지만, 상위 파이프라인과 맞추기 위해 async main에서 실행
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: manager.get_batch_fact_book(commodity_name, start_date, end_date),
    )

    if not result or "events" not in result:
        print("[WARN] 결과가 비어 있거나 events 키가 없습니다. 쿼리 조건 또는 DB 데이터를 확인하세요.")
        return

    events = result.get("events", [])
    meta = result.get("analysis_metadata", {})

    print("\n[RESULT] DB 팩트북 조회 결과 요약")
    print(f"- total_events_found: {meta.get('total_events_found', len(events))}")
    print(f"- commodity: {meta.get('commodity')}")
    print(f"- period: {meta.get('period')}")

    if events:
        first = events[0]
        core = first.get("event_core", {})
        meta_ev = first.get("event_metadata", {})
        print("\n[RESULT] 첫 번째 이벤트 예시:")
        print(f"- event_id: {meta_ev.get('event_id')}")
        print(f"- title: {core.get('title')}")
        print(f"- news_count: {core.get('news_count')}")
    else:
        print("\n[RESULT] 조건에 맞는 이벤트가 없습니다.")

    # 결과 JSON 파일로 저장
    output_dir = os.path.join(project_root, "data", "fact_books")
    file_name = f"fact_book_{commodity_name}_{start_date}_{end_date}.json"
    output_path = os.path.join(output_dir, file_name)

    manager.save_fact_book(result, output_path)
    print(f"\n[RESULT] 팩트북 JSON 저장 완료: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())

