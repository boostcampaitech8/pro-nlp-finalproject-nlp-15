"""CSV/JSONL 파일 기반 데이터 로더"""

import json
from pathlib import Path
from typing import Iterator

import pandas as pd


class ArticleLoader:
    """CSV 파일에서 기사 로드 (lazy loading)"""
    
    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self._df: pd.DataFrame | None = None
    
    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = pd.read_csv(self.csv_path)
            self._df = self._df.set_index('id')
        return self._df
    
    def get_article(self, article_id: str) -> dict | None:
        try:
            return self.df.loc[article_id].to_dict()
        except KeyError:
            return None
    
    def get_articles(self, article_ids: list[str]) -> list[dict]:
        unique_ids = list(dict.fromkeys(article_ids))
        articles = []
        for aid in unique_ids:
            article = self.get_article(aid)
            if article:
                articles.append({'id': aid, **article})
        return articles
    
    def get_article_content(self, article_id: str) -> str:
        article = self.get_article(article_id)
        return article.get('description', '') if article else ''


class EventLoader:
    """JSONL 파일에서 이벤트 로드"""
    
    def __init__(self, jsonl_path: str | Path):
        self.jsonl_path = Path(jsonl_path)
    
    def load_all(self) -> list[dict]:
        events = []
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
    
    def iter_events(self) -> Iterator[dict]:
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    
    def get_event_count(self) -> int:
        count = 0
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count


def get_commodity_name(file_path: str | Path) -> str:
    """파일 경로에서 원자재 이름 추출 (예: gold_future.jsonl → gold_future)"""
    return Path(file_path).stem
