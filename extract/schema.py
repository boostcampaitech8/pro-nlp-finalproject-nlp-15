from __future__ import annotations
import datetime as dt
from typing import Any, Dict, List, Optional
import hashlib
from pydantic import BaseModel

class DailyEvent(BaseModel):
    event_id: str
    title: str
    description: str
    start_date: str
    end_date: Optional[str] = None
    source: List[str]  # int에서 str 리스트로 변경 (최종 해시 ID 저장용)

def _pydantic_validate(model: type[BaseModel], obj: Dict[str, Any]) -> Dict[str, Any]:
    if hasattr(model, "model_validate"):
        inst = model.model_validate(obj)
        return inst.model_dump()
    inst = model.parse_obj(obj)
    return inst.dict()

def normalize_event(
    raw: Dict[str, Any],
    article_db: Dict[int, Dict[str, Any]],
    id_map: Dict[int, str]
) -> Dict[str, Any]:
    # 1. source 처리 및 원래 해시 ID로 복원
    raw_source = raw.get("source") or []
    integer_sources = sorted(list(set(
        int(s) for s in raw_source if str(s).isdigit()
    )))
    original_id_sources = [id_map[s] for s in integer_sources if s in id_map]

    # 2. Rule-based 날짜 결정 (기사 중 최소/최대 발행일)
    publish_dates = []
    for s in integer_sources:
        article = article_db.get(s)
        if article and article.get("publish_date"):
            publish_dates.append(str(article["publish_date"]))
    
    if publish_dates:
        s_date = min(publish_dates)
        e_date = max(publish_dates)
    else:
        s_date = raw.get("start_date")
        e_date = raw.get("end_date")

    # 3. 텍스트 정제 및 ID 생성
    title = (raw.get("title") or "").strip()
    description = (raw.get("description") or "").strip()
    id_seed = f"{''.join(title.split())}_{s_date}"
    event_id = hashlib.sha256(id_seed.encode('utf-8')).hexdigest()[:16]

    obj = {
        "event_id": event_id,
        "title": title,
        "description": description,
        "start_date": s_date,
        "end_date": e_date,
        "source": original_id_sources,
    }
    return _pydantic_validate(DailyEvent, obj)