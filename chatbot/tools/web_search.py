import os
from typing import Optional, Literal
from langchain_core.tools import tool
from tavily import TavilyClient


@tool
def web_search(
    query: str, 
    max_results: int = 5, 
    start_date: str | None = None, 
    end_date: str | None = None,
    time_range: Optional[Literal['day', 'week', 'month', 'year']] = None
) -> str:
    """
    Search the web for supplementary information or context that is missing from the internal news database.
    
    CRITICAL USAGE RULES:
    1. USE ONLY AS A LAST RESORT: Always try `get_period_overview`, `search_events_by_keyword`, and `search_knowledge_base` first.
    2. SUPPLEMENTARY ONLY: Use this tool ONLY if the internal database fails to provide sufficient information.
    3. NO RECENT DATA: If the user asks for data beyond the project scope, inform them you cannot provide that information instead of overusing web search.
    
    Args:
        query: The search query (e.g., "Corn ethanol demand shift details 2021", "Specifics of 2012 drought impact on ZC").
        max_results: The number of search results to retrieve (default: 5).
        start_date: The start date for filtering (YYYY-MM-DD). Use this to align with the historical period being analyzed.
        end_date: The end date for filtering (YYYY-MM-DD).
        time_range: Use this ONLY for very recent news ('day', 'week', 'month', 'year').
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not found in environment variables."
        
    try:
        client = TavilyClient(api_key=api_key)
        
        search_depth: Literal["advanced", "basic"] = "advanced"
        search_params = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth
        }
        
        # Optional filters
        if start_date: search_params["start_date"] = start_date
        if end_date: search_params["end_date"] = end_date
        if time_range: search_params["time_range"] = time_range
        
        response = client.search(**search_params)
        
        results = response.get("results", [])
        if not results:
            filter_info = f" with filters {start_date}~{end_date}" if start_date else ""
            return f"No search results found for query: '{query}'{filter_info}"
            
        output = [f"## Web Search Results for: '{query}'"]
        if start_date or end_date:
            output.append(f"*(Filter: {start_date or 'Begin'} ~ {end_date or 'End'})*\n")
            
        for i, res in enumerate(results, 1):
            title = res.get("title", "No Title")
            url = res.get("url", "No URL")
            content = res.get("content", "No snippet available")
            score = res.get("score", 0)
            
            output.append(f"\n### {i}. {title} (Relevance: {score:.2f})")
            output.append(f"- **URL**: {url}")
            output.append(f"- **Summary**: {content}")
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Tavily Search Error: {str(e)}"
