"""
Pipeline: Event Interpretation (Summarize & Predict)

이벤트에 대해 summarize와 is_up(가격 방향 예측)을 생성합니다.
NULL인 값만 처리하거나, --all 옵션으로 전체를 재처리할 수 있습니다.

Usage:
    # NULL인 것만 처리 (기본)
    uv run python workflow/run_interpret.py
    
    # 모든 이벤트 재처리
    uv run python workflow/run_interpret.py all=true
    
    # 처리 개수 제한
    uv run python workflow/run_interpret.py limit=10
"""

import hydra
import sys
from omegaconf import DictConfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from interpret.pipeline import run_batch_interpret


@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig):
    process_all = cfg.get("all", False)
    limit = cfg.get("limit", None)
    
    mode_str = "전체 재처리" if process_all else "NULL만 처리"
    limit_str = f", 제한: {limit}개" if limit else ""
    
    print(f"🚀 이벤트 해석 파이프라인 시작")
    print(f"  모드: {mode_str}{limit_str}")
    print(f"  DB: {cfg.db.host}:{cfg.db.port}/{cfg.db.database}")
    
    success_count = run_batch_interpret(cfg, limit=limit, process_all=process_all)
    
    print(f"\n✅ 완료! 처리된 이벤트: {success_count}개")


if __name__ == "__main__":
    main()
