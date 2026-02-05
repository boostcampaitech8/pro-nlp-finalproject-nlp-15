from langchain_core.tools import tool
from typing import Optional

# Module-level variable for dependency injection
_vector_store = None

def set_vector_store(vector_store):
    """Set the VectorStore instance for this tool to use."""
    global _vector_store
    _vector_store = vector_store

@tool
def search_events_by_keyword(
    query: str, 
    top_k: int = 10, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> str:
    """
    특정 주제나 키워드에 관한 실제 사건들을 검색하여 리스트로 제공합니다.
    자료가 충분하지 않다면 top_k를 늘려 더 많은 결과를 요청할 수 있습니다.
    
    Args:
        query: 검색할 주제나 키워드 (예: "코로나", "우크라이나 전쟁")
        top_k: 반환할 검색 결과 개수 (기본값: 10)
        start_date: 검색 기간 시작일 (선택 사항)
        end_date: 검색 기간 종료일 (선택 사항)
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    # Search in events collection
    results = _vector_store.search_similar_events(
        query, 
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if not results:
        return f"No events found matching query: '{query}'"
    
    # Sort results by date (ascending)
    # Most events have 'start_date'. Fallback to empty string for sorting.
    results.sort(key=lambda x: x.get('start_date', '') or '')
    
    output = [f"## 관련 이벤트 검색 결과: '{query}'"]
    for i, ev in enumerate(results, 1):
        title = ev.get('title', 'No Title')
        description = ev.get('description', 'No description available')
        start = ev.get('start_date', 'Unknown')
        end = ev.get('end_date', start)
        
        output.append(f"\n### {i}. {title}")
        output.append(f"- **Period**: {start} ~ {end}")
        output.append(f"- **Summary**: {description}")
        
        # Optionally include article references if available
        article_ids = ev.get('article_ids', [])
        if article_ids:
            output.append(f"- **Related Articles**: {len(article_ids)} items")
    
    return "\n".join(output)

__all__ = ['search_events_by_keyword', 'set_vector_store']
