"""event 테이블 마이그레이션 스크립트"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hydra import compose, initialize_config_dir
from interpret.db import DatabaseConnection, ensure_event_columns


MIGRATION_SQL = """
ALTER TABLE event ADD COLUMN summarize TEXT DEFAULT NULL;
ALTER TABLE event ADD COLUMN is_up BOOLEAN DEFAULT NULL;
CREATE INDEX idx_event_is_up ON event(is_up);
"""


def run_migration(dry_run: bool = False):
    if dry_run:
        print("=== 마이그레이션 SQL (dry-run) ===")
        print(MIGRATION_SQL)
        return
    
    config_path = PROJECT_ROOT / "config"
    with initialize_config_dir(version_base=None, config_dir=str(config_path)):
        cfg = compose(config_name="config")
    
    print("=== Event 테이블 마이그레이션 ===")
    print(f"DB: {cfg.db.host}:{cfg.db.port}/{cfg.db.database}")
    print(f"테이블: {cfg.db.tables.get('events', 'event')}")
    print()
    
    try:
        migrated = ensure_event_columns(cfg)
        
        if migrated:
            print("\n✓ 마이그레이션 완료")
        else:
            print("\n✓ 컬럼이 이미 존재합니다")
        
        # 현재 상태 확인
        table_name = cfg.db.tables.get('events', 'event')
        database = cfg.db.database
        
        with DatabaseConnection.get_cursor(cfg) as cursor:
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s 
                AND COLUMN_NAME IN ('summarize', 'is_up')
            """, (database, table_name))
            
            columns = cursor.fetchall()
            if columns:
                print(f"\n{table_name} 테이블 컬럼:")
                for col in columns:
                    print(f"  - {col['COLUMN_NAME']}: {col['DATA_TYPE']} (nullable={col['IS_NULLABLE']})")
            
            cursor.execute(f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN summarize IS NULL OR is_up IS NULL THEN 1 ELSE 0 END) as pending
                FROM {table_name}
            """)
            
            stats = cursor.fetchone()
            if stats:
                print(f"\n이벤트: 전체 {stats['total']}개, 대기 {stats['pending']}개")
        
    except Exception as e:
        print(f"\n✗ 실패: {e}")
        raise
    finally:
        DatabaseConnection.close_pool()


def main():
    parser = argparse.ArgumentParser(description='Event 테이블 마이그레이션')
    parser.add_argument('--dry-run', action='store_true', help='SQL만 출력')
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
