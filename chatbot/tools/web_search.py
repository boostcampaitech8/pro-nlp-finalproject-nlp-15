import os
from typing import Optional, Literal
from langchain_core.tools import tool
from tavily import TavilyClient
from dotenv import load_dotenv

# load_dotenv() is typically called in the entry point, but kept here for tool independence
load_dotenv()

@tool
def web_search(
    query: str, 
    max_results: int = 5, 
    start_date: str | None = None, 
    end_date: str | None = None,
    time_range: Optional[Literal['day', 'week', 'month', 'year']] = None
) -> str:
    """
    Search the web for real-time or historical information using Tavily API.
    
    📌 WHEN TO USE:
    - User asks for latest news or specific past events not in local DB.
    - Need to find external URLs for deep analysis.
    
    📌 DATE FILTERING:
    - If user specifies a year (e.g., 2022), MUST use start_date='2022-01-01' and end_date='2022-12-31'.
    - For recent news, use time_range='day', 'week', 'month', or 'year'.
    
    Args:
        query: Search query string.
        max_results: Number of results (default 5).
        start_date: Optional. Filter results from this date (YYYY-MM-DD).
        end_date: Optional. Filter results until this date (YYYY-MM-DD).
        time_range: Optional. Relative time range ('day', 'week', 'month', 'year').
        
    Returns:
        Structured string with search results.
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
