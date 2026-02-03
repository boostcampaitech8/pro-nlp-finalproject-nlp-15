"""CSV 기반 뉴스/이벤트 데이터 로더 모듈"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd


class ArticleLoader:
    """CSV 파일에서 기사 데이터를 로드하는 클래스"""
    
    def __init__(self, csv_path: str | Path):
        """
        Args:
            csv_path: 기사 CSV 파일 경로
        """
        self.csv_path = Path(csv_path)
        self._df: pd.DataFrame | None = None
    
    @property
    def df(self) -> pd.DataFrame:
        """Lazy loading of DataFrame"""
        if self._df is None:
            self._df = pd.read_csv(self.csv_path)
            self._df = self._df.set_index('id')
        return self._df
    
    def get_article(self, article_id: str) -> dict | None:
        """
        ID로 단일 기사 조회
        
        Args:
            article_id: 기사 ID (hex string)
            
        Returns:
            기사 dict 또는 None
        """
        try:
            row = self.df.loc[article_id]
            return row.to_dict()
        except KeyError:
            return None
    
    def get_articles(self, article_ids: list[str]) -> list[dict]:
        """
        여러 ID로 기사들 조회
        
        Args:
            article_ids: 기사 ID 리스트
            
        Returns:
            기사 dict 리스트 (존재하는 것만)
        """
        articles = []
        # 중복 제거
        unique_ids = list(dict.fromkeys(article_ids))
        for aid in unique_ids:
            article = self.get_article(aid)
            if article:
                articles.append({'id': aid, **article})
        return articles
    
    def get_article_content(self, article_id: str) -> str:
        """
        기사 ID로 본문(description) 조회
        
        Args:
            article_id: 기사 ID
            
        Returns:
            기사 description 또는 빈 문자열
        """
        article = self.get_article(article_id)
        if article:
            return article.get('description', '')
        return ''


class EventLoader:
    """JSONL 파일에서 이벤트 데이터를 로드하는 클래스"""
    
    def __init__(self, jsonl_path: str | Path):
        """
        Args:
            jsonl_path: 이벤트 JSONL 파일 경로
        """
        self.jsonl_path = Path(jsonl_path)
    
    def load_all(self) -> list[dict]:
        """모든 이벤트 로드"""
        events = []
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
    
    def iter_events(self) -> Iterator[dict]:
        """이벤트를 하나씩 yield (메모리 효율적)"""
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    
    def get_event_count(self) -> int:
        """이벤트 총 개수 반환"""
        count = 0
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count


def get_commodity_name(file_path: str | Path) -> str:
    """
    파일 경로에서 원자재 이름 추출
    
    Args:
        file_path: 파일 경로 (예: data/events/gold_future.jsonl)
        
    Returns:
        원자재 이름 (예: gold_future)
    """
    path = Path(file_path)
    return path.stem
