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
    Perform semantic search across ALL historical events regardless of date.
    
    📌 WHEN TO USE (Priority: MEDIUM - For thematic deep dives):
    - User asks about a specific THEME or KEYWORD (not a date range)
    - Looking for historical precedents or patterns
    - Comparative analysis: "Has this happened before?"
    - Research questions requiring topical clustering
    
    📌 KEY DIFFERENCE from search_volatility_events:
    - search_volatility_events: DATE-BOUND, finds news on volatile DAYS
    - search_similar_events: DATE-AGNOSTIC, finds semantically similar TOPICS
    
    📌 EXPECTED OUTPUT:
    - Events ranked by semantic similarity score (0.0 to 1.0)
    - Each includes: Title, Date, Description, Similarity Score
    - Can span multiple years if thematically related
    
    🔍 Example Queries:
    - "Find all events about trade wars"
    - "Historical supply chain disruptions"
    - "Similar situations to the current inflation"
    
    Args:
        query: Natural language description of topic/theme to search
        top_k: Number of most similar results (default: 5, max: 20)
        
    Returns:
        Ranked list of semantically similar events with scores
    
    ⚠️ CURRENT STATUS:
    Vector store is under development. Returns error if not initialized.
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
