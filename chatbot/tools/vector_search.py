from langchain_core.tools import tool
from typing import List, Dict

# Module-level variable for dependency injection
_vector_store = None

def set_vector_store(vector_store):
    """Set the VectorStore instance for the tool to use."""
    global _vector_store
    _vector_store = vector_store

@tool
def search_similar_events(query: str, top_k: int = 5) -> str:
    """
    Search for events semantically similar to a given query or topic.
    
    Use this tool when the user asks about:
    - Specific topics, themes, or keywords (e.g., "tariffs", "strikes", "supply chain")
    - Historical precedents ("Has this happened before?", "Similar situations")
    - Comparative analysis across different time periods
    - Thematic research (e.g., "All news about China demand")
    
    Examples of queries:
    - "Find events about trade wars"
    - "Show me similar supply disruptions"
    - "What happened with tariffs historically?"
    
    Args:
        query: Search query in natural language describing the topic or theme
        top_k: Number of most similar events to return (default: 5)
        
    Returns:
        List of relevant events with similarity scores, titles, descriptions, and dates
    """
    if _vector_store is None:
        return "Error: Vector store not initialized. Semantic search is not available yet."
    
    results = _vector_store.search_similar_events(query, top_k)
    
    if not results:
        return f"No similar events found for query: '{query}'"
    
    output = [f"## Events similar to: '{query}'"]
    for i, event in enumerate(results, 1):
        score = event.get('score', 0)
        title = event.get('title', 'No Title')
        desc = event.get('description', 'No description')
        date = event.get('date', 'Unknown date')
        
        output.append(f"\n### {i}. {title} (Similarity: {score:.2f})")
        output.append(f"- **Date**: {date}")
        output.append(f"- **Description**: {desc}")
    
    return "\n".join(output)
