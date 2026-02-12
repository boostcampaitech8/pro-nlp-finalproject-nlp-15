"""MySQL 데이터베이스 연동 모듈"""

import threading
from contextlib import contextmanager
from typing import Iterator

import pymysql
from pymysql.cursors import DictCursor
from omegaconf import DictConfig


class DatabaseConnection:
    """스레드 안전한 MySQL 연결 관리"""
    
    _thread_local = threading.local()
    
    @classmethod
    def get_connection_params(cls, cfg: DictConfig) -> dict:
        return {
            'host': cfg.db.host,
            'port': int(cfg.db.port),
            'database': cfg.db.database,
            'user': cfg.db.user,
            'password': cfg.db.password,
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
        }
    
    @classmethod
    def get_connection(cls, cfg: DictConfig) -> pymysql.Connection:
        conn = getattr(cls._thread_local, 'connection', None)
        if conn is None or not conn.open:
            conn = pymysql.connect(**cls.get_connection_params(cfg))
            cls._thread_local.connection = conn
        return conn
    
    @classmethod
    def close_pool(cls) -> None:
        conn = getattr(cls._thread_local, 'connection', None)
        if conn and conn.open:
            conn.close()
            cls._thread_local.connection = None
    
    @classmethod
    @contextmanager
    def get_cursor(cls, cfg: DictConfig):
        conn = cls.get_connection(cfg)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def ensure_event_columns(cfg: DictConfig) -> bool:
    """event 테이블에 summarize, is_up 컬럼 추가 (없으면)"""
    table_name = cfg.db.tables.get('events', 'event')
    database = cfg.db.database
    
    with DatabaseConnection.get_cursor(cfg) as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME IN ('summarize', 'is_up')
        """, (database, table_name))
        
        existing_columns = {row['COLUMN_NAME'] for row in cursor.fetchall()}
        migrated = False
        
        if 'summarize' not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN summarize TEXT DEFAULT NULL")
            print(f"  [Migration] Added 'summarize' column to {table_name}")
            migrated = True
        
        if 'is_up' not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN is_up BOOLEAN DEFAULT NULL")
            print(f"  [Migration] Added 'is_up' column to {table_name}")
            migrated = True
        
        return migrated


def get_article_by_id(article_id: str, cfg: DictConfig) -> dict | None:
    table_name = cfg.db.tables.get('articles', 'article')
    with DatabaseConnection.get_cursor(cfg) as cursor:
        cursor.execute(
            f"SELECT id, title, description, publish_date, authors, key_word, doc_url, commodity_id "
            f"FROM {table_name} WHERE id = %s",
            (str(article_id),)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_articles_by_ids(article_ids: list[str], cfg: DictConfig) -> list[dict]:
    if not article_ids:
        return []
    
    table_name = cfg.db.tables.get('articles', 'article')
    unique_ids = list(dict.fromkeys([str(aid) for aid in article_ids]))
    
    with DatabaseConnection.get_cursor(cfg) as cursor:
        placeholders = ','.join(['%s'] * len(unique_ids))
        cursor.execute(
            f"SELECT id, title, description, publish_date, authors, key_word, doc_url, commodity_id "
            f"FROM {table_name} WHERE id IN ({placeholders})",
            unique_ids
        )
        return [dict(row) for row in cursor.fetchall()]


def get_events(cfg: DictConfig, limit: int | None = None) -> list[dict]:
    table_name = cfg.db.tables.get('events', 'event')
    with DatabaseConnection.get_cursor(cfg) as cursor:
        query = f"SELECT * FROM {table_name} ORDER BY start_date"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def get_events_pending_interpret(cfg: DictConfig, limit: int | None = None) -> list[dict]:
    """summarize 또는 is_up이 NULL인 이벤트 조회"""
    table_name = cfg.db.tables.get('events', 'event')
    with DatabaseConnection.get_cursor(cfg) as cursor:
        query = f"SELECT * FROM {table_name} WHERE summarize IS NULL OR is_up IS NULL ORDER BY start_date"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def get_events_pending_count(cfg: DictConfig) -> int:
    table_name = cfg.db.tables.get('events', 'event')
    with DatabaseConnection.get_cursor(cfg) as cursor:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name} WHERE summarize IS NULL OR is_up IS NULL")
        result = cursor.fetchone()
        return result['cnt'] if result else 0


def update_event_interpret(event_pk: int, summarize: str, is_up: bool, cfg: DictConfig) -> bool:
    table_name = cfg.db.tables.get('events', 'event')
    with DatabaseConnection.get_cursor(cfg) as cursor:
        cursor.execute(
            f"UPDATE {table_name} SET summarize = %s, is_up = %s WHERE id = %s",
            (summarize, is_up, event_pk)
        )
        return cursor.rowcount > 0


class SQLArticleLoader:
    """SQL 기반 기사 로더 (캐싱 지원)"""
    
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self._cache: dict[str, dict] = {}
    
    def get_article(self, article_id: str) -> dict | None:
        article_id = str(article_id)
        if article_id in self._cache:
            return self._cache[article_id]
        
        article = get_article_by_id(article_id, self.cfg)
        if article:
            self._cache[article_id] = article
        return article
    
    def get_articles(self, article_ids: list[str]) -> list[dict]:
        article_ids = [str(aid) for aid in article_ids]
        uncached_ids = [aid for aid in article_ids if aid not in self._cache]
        
        if uncached_ids:
            for article in get_articles_by_ids(uncached_ids, self.cfg):
                aid = str(article.get('id'))
                if aid:
                    self._cache[aid] = article
        
        return [self._cache[aid] for aid in article_ids if aid in self._cache]
    
    def get_article_content(self, article_id: str) -> str:
        article = self.get_article(str(article_id))
        return article.get('description', '') if article else ''


class SQLEventLoader:
    """SQL 기반 이벤트 로더"""
    
    def __init__(self, cfg: DictConfig, pending_only: bool = False):
        self.cfg = cfg
        self.pending_only = pending_only
    
    def load_all(self, limit: int | None = None) -> list[dict]:
        if self.pending_only:
            return get_events_pending_interpret(self.cfg, limit=limit)
        return get_events(self.cfg, limit=limit)
    
    def iter_events(self, limit: int | None = None) -> Iterator[dict]:
        for event in self.load_all(limit=limit):
            yield event
    
    def get_event_count(self) -> int:
        if self.pending_only:
            return get_events_pending_count(self.cfg)
        
        table_name = self.cfg.db.tables.get('events', 'event')
        with DatabaseConnection.get_cursor(self.cfg) as cursor:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            result = cursor.fetchone()
            return result['cnt'] if result else 0
