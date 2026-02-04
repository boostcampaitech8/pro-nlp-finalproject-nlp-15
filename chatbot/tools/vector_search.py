from langchain_core.tools import tool
from typing import Any

# Module-level variable for dependency injection
_vector_store: Any | None = None

def set_vector_store(vector_store: Any) -> None:
    """Set the VectorStore instance for the tools to use."""
    global _vector_store
    _vector_store = vector_store

@tool
def search_similar_articles(
    query: str, 
    top_k: int = 5, 
    start_date: str | None = None, 
    end_date: str | None = None
) -> str:
    """
    Search for news articles semantically similar to a given query or topic.
    Supports optional date range filtering.
    
    Use this tool when the user asks about:
    - Specific news topics, themes, or keywords (e.g., "tariffs", "strikes", "supply chain")
    - Thematic research across news content
    
    Args:
        query: Search query in natural language
        top_k: Number of most similar articles to return (default: 5)
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
        
    Returns:
        String containing relevant articles with similarity scores, titles, descriptions, and dates
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    results = _vector_store.search_similar_articles(
        query, 
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if not results:
        return f"No similar articles found for query: '{query}' in the given date range."
    
    output = [f"## Articles similar to: '{query}'"]
    for i, article in enumerate(results, 1):
        score = article.get('score', 0)
        title = article.get('title', 'No Title')
        desc = article.get('description', 'No description')
        date = article.get('date', 'Unknown date')
        url = article.get('url', 'No URL')
        
        output.append(f"\n### {i}. {title} (Similarity: {score:.2f})")
        output.append(f"- **Date**: {date}")
        output.append(f"- **URL**: {url}")
        output.append(f"- **Description**: {desc}")
    
    return "\n".join(output)

@tool
def search_similar_events(
    query: str, 
    top_k: int = 5, 
    start_date: str | None = None, 
    end_date: str | None = None
) -> str:
    """
    Search for extracted events (summarized occurrences) semantically similar to a query.
    Supports optional date range filtering.
    
    Use this tool when the user asks about:
    - Specifically identified events or occurrences
    - Summary of a situation or event
    
    Args:
        query: Search query in natural language
        top_k: Number of most similar events to return (default: 5)
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
        
    Returns:
        String containing relevant events with similarity scores, titles, summaries, and durations
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    results = _vector_store.search_similar_events(
        query, 
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if not results:
        return f"No similar events found for query: '{query}' in the given date range."
    
    output = [f"## Events similar to: '{query}'"]
    for i, event in enumerate(results, 1):
        score = event.get('score', 0)
        title = event.get('title', 'No Title')
        desc = event.get('description', 'No description')
        start = event.get('start_date', 'Unknown')
        end = event.get('end_date', 'Unknown')
        
        output.append(f"\n### {i}. {title} (Similarity: {score:.2f})")
        output.append(f"- **Duration**: {start} to {end}")
        output.append(f"- **Summary**: {desc}")
    
    return "\n".join(output)
