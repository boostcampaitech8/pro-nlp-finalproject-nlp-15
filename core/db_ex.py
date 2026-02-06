import uuid
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

from qdrant_client.http import models
from interpret.core.stock_api import StockAPI
from interpret.core.vector_store import VectorStore

class FinancialDB:
    """
    RDB/Vector DB 통합 인터페이스.
    주가 데이터(StockAPI)와 뉴스 원문(VectorStore)을 결합하여 
    3단 추론 아레나에 필요한 시계열 컨텍스트를 생성합니다.
    """

    def __init__(
        self, 
        data_dir: str = "data/prices",
        qdrant_url: str = "http://lori2mai11ya.asuscomm.com:6333",
        collection_articles: str = "articles",
        collection_events: str = "events"
    ):
        # 주가 데이터 로더 초기화
        self.stock_api = StockAPI(data_dir=data_dir)
        
        # 벡터 DB 검색 엔진 초기화
        self.vector_store = VectorStore(
            qdrant_url=qdrant_url,
            collection_name=collection_articles
        )
        self.client = self.vector_store.client
        self.collection_articles = collection_articles
        self.collection_events = collection_events

    def _get_point_id(self, hex_id: str) -> str:
        """기사 ID(hex)를 Qdrant UUID로 변환 (ingest 로직과 동일)"""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(hex_id)))

    def get_market_context(self, asset_name: str, start_date: date, end_date: date) -> str:
        """기간 내 시장 수익률 및 변동성 통계 요약 반환"""
        return self.stock_api.get_price_summary(asset_name, start_date, end_date)

    def get_timeline_articles(self, start_date: date, end_date: date, asset_name: str) -> str:
        """
        기간 내 발생한 사건들과 연결된 모든 기사 원문(Description)을 
        발행일 순으로 정렬하여 하나의 타임라인 텍스트로 통합합니다.
        """
        # 1. 기간 내 사건(Events) 검색
        # 해당 기간에 발생한 모든 사건을 가져오기 위해 range 필터 사용
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="start_date",
                    range=models.DatetimeRange(
                        gte=start_date.isoformat(),
                        lte=end_date.isoformat()
                    )
                ),
                models.FieldCondition(
                    key="category",
                    match=models.MatchValue(value=asset_name)
                )
            ]
        )

        # 넉넉하게 상위 50개 사건 검색
        events_result = self.client.scroll(
            collection_name=self.collection_events,
            scroll_filter=query_filter,
            limit=50,
            with_payload=True
        )[0]

        # 2. 모든 관련 기사 ID(source) 추출 및 중복 제거
        article_hex_ids = set()
        for evt in events_result:
            source = evt.payload.get("source", [])
            if isinstance(source, list):
                article_hex_ids.update(source)

        if not article_hex_ids:
            return "해당 기간에 관련된 뉴스 기사가 없습니다."

        # 3. Qdrant에서 기사 원문(Payload) 벌크 로드
        point_ids = [self._get_point_id(hid) for hid in article_hex_ids]
        articles_payload = self.client.retrieve(
            collection_name=self.collection_articles,
            ids=point_ids,
            with_payload=True
        )

        # 4. 발행일 순으로 정렬 (ISO 8601 기반)
        valid_articles = [a.payload for a in articles_payload if a.payload]
        valid_articles.sort(key=lambda x: x.get("publish_date", ""))

        # 5. 타임라인 텍스트 구성 (Analyst/Lawyer 에이전트 입력용)
        timeline_lines = []
        for a in valid_articles:
            p_date = a.get("publish_date", "Unknown Date")
            title = a.get("title", "No Title")
            desc = a.get("description", "") # '원문'으로 사용하는 필드
            timeline_lines.append(f"[{p_date}] {title}\n- 요약: {desc}\n")

        return "\n".join(timeline_lines)

    def get_arena_context(self, start_date: date, end_date: date, asset_name: str) -> Dict[str, Any]:
        """
        3단 추론 아레나(Analyst, Lawyer, Verdict)에 필요한 
        통합 데이터 패키지를 생성합니다.
        """
        market_stats = self.get_market_context(asset_name, start_date, end_date)
        news_timeline = self.get_timeline_articles(start_date, end_date, asset_name)
        
        # 예측 대상일 (end_date 다음날) 정보 추가
        target_date = end_date # 실제 로직에서는 휴장일 등을 고려한 logic 필요
        
        return {
            "asset_name": asset_name,
            "period": f"{start_date} ~ {end_date}",
            "market_summary": market_stats,
            "news_context": news_timeline,
            "target_date_context": f"{end_date} 이후의 가격 방향성을 예측하세요."
        }

if __name__ == "__main__":
    # 테스트 코드
    db = FinancialDB()
    test_start = date(2024, 1, 1)
    test_end = date(2024, 1, 10)
    
    context = db.get_arena_context(test_start, test_end, "gold_future")
    print(f"--- Market Summary ---\n{context['market_summary']}")
    print(f"\n--- News Timeline ---\n{context['news_context'][:500]}...")