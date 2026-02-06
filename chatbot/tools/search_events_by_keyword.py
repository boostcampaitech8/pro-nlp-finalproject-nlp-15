from langchain_core.tools import tool
from typing import Optional

# Module-level variables for dependency injection
_vector_store = None
_article_repo = None
_collection_name = "events" # Default

def set_dependencies(vector_store, article_repo=None, collection_name="events"):
    """Set the dependencies for this tool to use."""
    global _vector_store, _article_repo, _collection_name
    _vector_store = vector_store
    _article_repo = article_repo
    _collection_name = collection_name

@tool
def search_events_by_keyword(
    query: str, 
    top_k: int = 10, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> str:
    """
    Search for specific market events, historical episodes, or topics in the news database.
    This tool performs a hybrid semantic search to find significant market-moving events and 
    returns summaries along with source article bodies for deep context analysis.
    
    Args:
        query: The market event or topic to investigate (e.g., "Crude oil supply shock", "Gold price spike origins").
        top_k: The number of historical events to retrieve (default: 10).
        start_date: Start of the search range (YYYY-MM-DD, optional).
        end_date: End of the search range (YYYY-MM-DD, optional).
    """
    if _vector_store is None:
        return "Error: Vector store not initialized."
    
    # Search in events collection
    results = _vector_store.search(
        query=query, 
        collection_name=_collection_name, 
        date_field="start_date",
        top_k=top_k, 
        start_date=start_date, 
        end_date=end_date
    )
    
    if not results:
        return f"No events found matching query: '{query}'"
    
    # Sort results by date (ascending)
    results.sort(key=lambda hit: (hit.payload or {}).get('start_date', '') or '')
    
    output = [f"## Event Search Results for: '{query}'"]
    for i, hit in enumerate(results, 1):
        payload = hit.payload or {}
        title = payload.get('title', 'No Title')
        description = payload.get('description', 'No description available')
        start = payload.get('start_date', 'Unknown')
        end = payload.get('end_date', start)
        
        output.append(f"\n### {i}. {title}")
        output.append(f"- **Summary**: {description}")
        
        # Related Articles and Primary Body
        article_ids = payload.get('article_ids', [])
        related_links = []
        primary_body = ""
        
        if _article_repo and article_ids:
            for idx, aid in enumerate(article_ids):
                art_data = _article_repo.get_article(aid)
                if art_data:
                    title_art = art_data.get('title', 'Link')
                    url_art = art_data.get('url', '#')
                    related_links.append(f"[{title_art}]({url_art})")
                    
                    if idx == 0: # First article as primary body
                        body = art_data.get('content', '') or art_data.get('description', '')
                        if body:
                            limit = 3000
                            primary_body = body[:limit] + ("..." if len(body) > limit else "")

        if related_links:
            output.append("- **Related Articles**:")
            for link in related_links[:5]: # Limit to top 5
                output.append(f"  - {link}")
        
        if len(primary_body) > 0:
            output.append(f"- **Description**: {primary_body}")
        elif article_ids and not _article_repo:
            output.append(f"- **Related Articles**: {len(article_ids)} items (Article Repository required for details)")
    
    return "\n".join(output)

__all__ = ['search_events_by_keyword', 'set_dependencies']
