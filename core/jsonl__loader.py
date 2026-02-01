import json
import os
import logging
from omegaconf import DictConfig

logger = logging.getLogger(__name__)

async def load_event_from_jsonl(event_id: str, cfg: DictConfig) -> dict:
    """
    JSONL 파일에서 특정 event_id에 해당하는 데이터를 찾아 반환합니다.
    """

    file_name = "soybean_production.jsonl" 
    file_path = os.path.join(cfg.data.raw_path, file_name)
    
    print(f"🔍 [Debug] 파일 로드 시도: {os.path.abspath(file_path)}")

    if not os.path.exists(file_path):
        file_path = os.path.join(cfg.data.raw_path, "national_agricultural_statistics_service.jsonl")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    def _read_file_sync():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    if str(data.get("event_id")).strip() == str(event_id).strip():
                        return data
                except json.JSONDecodeError:
                    continue
        return None

    event_data = _read_file_sync()
    
    if not event_data:
        raise ValueError(f"Event ID {event_id} not found in {file_name}")
        
    # 3. 에이전트 공통 필드 매핑
    return {
        "content": event_data.get("description", ""),  # 뉴스 원문 역할
        "date": event_data.get("start_date", ""),      # 사건 발생일
        "title": event_data.get("title", ""),          # 제목/ID
        "raw": event_data                              # 원본 데이터 보존
    }