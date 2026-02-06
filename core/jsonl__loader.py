import json
import os
import glob
import logging
from omegaconf import DictConfig

logger = logging.getLogger(__name__)

# 우선 시도할 파일명 (없으면 raw_path 안 다른 .jsonl 사용)
PREFERRED_JSONL = [
    "soybean_production.jsonl",
    "national_agricultural_statistics_service.jsonl",
    "gold_future.jsonl",
    "soybean_and_price_or_demand_or_supply_or_inventory.jsonl",
]


def _list_jsonl_files(raw_path: str) -> list[str]:
    """raw_path에서 사용 가능한 .jsonl 파일 목록 (우선순위 반영)."""
    existing = []
    for name in PREFERRED_JSONL:
        p = os.path.join(raw_path, name)
        if os.path.isfile(p):
            existing.append(p)
    rest = glob.glob(os.path.join(raw_path, "*.jsonl"))
    for p in sorted(rest):
        if p not in existing:
            existing.append(p)
    return existing


async def load_event_from_jsonl(event_id: str, cfg: DictConfig) -> dict:
    """
    JSONL 파일에서 event_id에 해당하는 데이터를 찾아 반환합니다.
    soybean_production.jsonl이 없어도 raw_path 내 다른 .jsonl을 사용하고,
    event_id가 없으면 첫 번째 이벤트로 테스트용 반환합니다.
    """
    raw_path = os.path.abspath(cfg.data.raw_path)
    if not os.path.isdir(raw_path):
        raise FileNotFoundError(f"데이터 디렉터리가 없습니다: {raw_path}")

    jsonl_files = _list_jsonl_files(raw_path)
    if not jsonl_files:
        raise FileNotFoundError(f".jsonl 파일이 없습니다: {raw_path}")

    print(f"[Debug] JSONL 후보: {[os.path.basename(p) for p in jsonl_files]}")

    def _find_event_in_file(path: str, eid: str):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if str(data.get("event_id", "")).strip() == str(eid).strip():
                        return data
                except json.JSONDecodeError:
                    continue
        return None

    def _first_event_in_file(path: str):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data and data.get("event_id") is not None:
                        return data
                except json.JSONDecodeError:
                    continue
        return None

    event_data = None
    for path in jsonl_files:
        event_data = _find_event_in_file(path, event_id)
        if event_data:
            break

    if not event_data:
        # 테스트용: 첫 번째 이벤트 사용
        for path in jsonl_files:
            event_data = _first_event_in_file(path)
            if event_data:
                logger.warning(
                    "Event ID %s not found; using first event from %s (id=%s) for test.",
                    event_id,
                    os.path.basename(path),
                    event_data.get("event_id"),
                )
                break

    if not event_data:
        raise ValueError(f"Event ID {event_id} not found and no valid event in any .jsonl under {raw_path}")

    return {
        "content": event_data.get("description", ""),
        "date": event_data.get("start_date", ""),
        "title": event_data.get("title", ""),
        "raw": event_data,
    }