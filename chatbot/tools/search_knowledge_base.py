from langchain_core.tools import tool
from typing import Optional

# Module-level variable for dependency injection
_vector_store = None
_collection_name = "knowledge_base" # Default

def set_vector_store(vector_store, collection_name="knowledge_base"):
    """Set the VectorStore instance for the tool to use."""
    global _vector_store, _collection_name
    _vector_store = vector_store
    _collection_name = collection_name

@tool
def search_knowledge_base(
    query: str, 
    top_k: int = 5, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> str:
    """
    Search the Knowledge Base for deep-dive financial reports, expert analysts' insights, and conceptual definitions.
    Use this tool for research-oriented questions about macro trends, long-term outlooks, or expert financial commentary.
    
    Args:
        query: The research topic or expert query (e.g., "Silver market 2024 forecast", "Historical impact of inflation").
        top_k: The number of relevant document chunks to retrieve (default: 5).
        start_date: Start of the publication period (YYYY-MM-DD, optional).
        end_date: End of the publication period (YYYY-MM-DD, optional).
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    # Collection and date field are defined at the agent level, but for the tool
    # we'll use defaults compatible with the knowledge base schema
    results = _vector_store.search(
        query=query, 
        collection_name=_collection_name, 
        date_field="publication_date", # Fixed from publish_date
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if results is None or not results:
        return f"No relevant financial documents found for query: '{query}'"
    
    output = [f"## Financial Research on: '{query}'"]
    for i, hit in enumerate(results, 1):
        score = hit.score
        payload = hit.payload or {}
        title = payload.get('title', 'No Title')
        
        # Get chunk text from payload
        text = payload.get('chunk_text', payload.get('description', 'No content'))
        pub_date = payload.get('publication_date', 'Unknown date') # Fixed from publish_date
        
        output.append(f"\n### {i}. {title} (Relevance: {score:.2f})")
        output.append(f"- **Published**: {pub_date}")
        output.append(f"- **Body**: {text or 'No content'}") # Changed label to Body
    
    return "\n".join(output)

__all__ = ['search_knowledge_base', 'set_vector_store']
