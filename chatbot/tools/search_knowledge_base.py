from langchain_core.tools import tool
from typing import Optional

# Module-level variable for dependency injection
_vector_store = None

def set_vector_store(vector_store):
    """Set the VectorStore instance for the tool to use."""
    global _vector_store
    _vector_store = vector_store

@tool
def search_knowledge_base(
    query: str, 
    top_k: int = 5, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> str:
    """
    시장 인사이트, 거시적/장기적 동향, 또는 금융 지식(개념 설명)을 검색합니다.
    유저가 특정 주제에 대한 깊이 있는 분석, 전문가 의견, 또는 금융 용어의 정의를 물을 때 사용합니다.
    
    Args:
        query: 검색할 분석 주제나 질문 (예: "선물 거래 원리", "금리 인상의 거시적 영향")
        top_k: 반환할 검색 결과 개수
        start_date: 문서 발행 시작일 (선택 사항)
        end_date: 문서 발행 종료일 (선택 사항)
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    # Use the search method directly - VectorStore can handle different collections
    # We'll search in the default collection and filter/enhance results
    # For now, we search articles but this will be updated when financial_documents is populated
    results = _vector_store.search_similar_articles(
        query, 
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if not results:
        return f"No relevant financial documents found for query: '{query}'"
    
    output = [f"## Financial Research on: '{query}'"]
    for i, doc in enumerate(results, 1):
        score = doc.get('score', 0)
        title = doc.get('title', 'No Title')
        
        # Get chunk text from payload
        text = doc.get('chunk_text', doc.get('description', 'No content'))
        source = doc.get('source_id', 'Unknown source')
        pub_date = doc.get('publication_date', 'Unknown date')
        
        output.append(f"\n### {i}. {title} (Relevance: {score:.2f})")
        output.append(f"- **Source**: {source}")
        output.append(f"- **Published**: {pub_date}")
        output.append(f"- **Excerpt**: {text[:300]}...")
    
    return "\n".join(output)

__all__ = ['search_knowledge_base', 'set_vector_store']
