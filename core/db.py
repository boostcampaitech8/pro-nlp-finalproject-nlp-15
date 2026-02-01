"""
미정
"""
import asyncio
from omegaconf import DictConfig
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# DB 연결 엔진 유지를 위한 전역 변수
_ENGINE = None
_ASYNC_SESSION = None

def get_db_session(cfg: DictConfig):
    global _ENGINE, _ASYNC_SESSION
    if _ENGINE is None:
        # cfg.db.url 예: "mysql+asyncmy://user:pass@host:port/dbname"
        _ENGINE = create_async_engine(cfg.db.url, echo=False)
        _ASYNC_SESSION = sessionmaker(
            _ENGINE, expire_on_commit=False, class_=AsyncSession
        )
    return _ASYNC_SESSION

async def get_news(news_id: int, cfg: DictConfig) -> str:
    async_session = get_db_session(cfg)
    
    async with async_session() as session:
        # 뉴스 테이블 및 컬럼명은 팀의 실제 스키마에 맞게 조정 필요
        query = text("SELECT content FROM news_table WHERE id = :news_id")
        result = await session.execute(query, {"news_id": news_id})
        row = result.fetchone()
        
        if row:
            return row[0]
        else:
            raise ValueError(f"News ID {news_id}를 찾을 수 없습니다.")

async def get_price_data(subject: str, target_date: str, cfg: DictConfig):
    async_session = get_db_session(cfg)
    async with async_session() as session:
        query = text("""
            SELECT price, volume 
            FROM price_history 
            WHERE ticker = :subject AND date <= :target_date
            ORDER BY date DESC LIMIT 5
        """)
        result = await session.execute(query, {"subject": subject, "target_date": target_date})
        return result.all()

class VectorDBConnector:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # Pinecone, Milvus, 혹은 Chroma 연결 로직이 여기에 위치합니다.

    async def search_similar_cases(self, query_vector: list, top_k: int = 3):
        """과거의 유사한 시장 충격 사례를 검색합니다."""
        # TODO: Vector DB 클라이언트 라이브러리 연동
        pass