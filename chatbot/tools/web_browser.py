import os
import re
import time
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from tavily import TavilyClient
from dotenv import load_dotenv

# .env 로드 (API 키 확보)
load_dotenv()

def clean_text(text: str) -> str:
    """Clean the extracted text by removing extra whitespaces and newlines."""
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _extract_legacy(url: str) -> str | None:
    """Fast extraction using requests + BeautifulSoup (Legacy method)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        for script_or_style in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            script_or_style.decompose()
            
        text = soup.get_text(separator='\n')
        cleaned = clean_text(text)
        
        # Success threshold: 200 characters of meaningful text
        if len(cleaned) > 200:
            return cleaned
        return None
    except Exception:
        return None

@tool
def extract_url_content(url: str) -> str:
    """
    Extract the main body text from a provided URL using a hybrid approach (Requests + Playwright).
    Use this tool when the user provides a specific news URL or when historical event metadata 
    contains source links that require deeper context analysis.
    
    Args:
        url: The full web URL of the article or report to extract.
    """
    # 1. Try Legacy Method First (Faster)
    legacy_result = _extract_legacy(url)
    if legacy_result:
        return legacy_result

    # 2. Fallback to Playwright (Modern/Robust)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            context = browser.new_context(user_agent=user_agent)
            Stealth().apply_stealth_sync(context)
            page = context.new_page()
            
            # Navigate to the URL
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Briefly wait for network to settle
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            if not response:
                browser.close()
                return "Error: No response received from the server."
            
            if response.status >= 400:
                browser.close()
                return f"HTTP Error: {response.status} - Could not access the URL."

            html_content = page.content()
            browser.close()
            
            try:
                soup = BeautifulSoup(html_content, "html.parser")
            except Exception:
                soup = BeautifulSoup(html_content, "html.parser") # Fallback
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()
                
            # Content Extraction Logic
            article_tag = soup.find("article")
            if article_tag:
                article_content = article_tag.get_text(separator="\n")
            else:
                # Use plain strings or simple filters to avoid complex overload issues if possible
                # But regex is better. I'll use a more standard search approach.
                article_content = ""
                main_div = soup.find("main") or soup.find("div", role="main")
                if main_div:
                    article_content = main_div.get_text(separator="\n")
                
                if not article_content:
                    body = soup.find("body")
                    article_content = body.get_text(separator="\n") if body else soup.get_text(separator="\n")
            
            cleaned = clean_text(article_content)
            
            # Limit length
            if len(cleaned) > 20000:
                cleaned = cleaned[:20000] + "... [Content Truncated]"
                
            if not cleaned or len(cleaned) < 100:
                return "Error: Could not extract meaningful text from the URL. The page might be protected or paywalled."
                
            return cleaned

    except Exception as e:
        error_msg = str(e)
        if "Timeout" in error_msg:
             return f"Timeout Error: The page took too long to load ({url})."
        return f"Unexpected Scraper Error: {error_msg}"

@tool
def web_search(
    query: str, 
    max_results: int = 5, 
    start_date: str | None = None, 
    end_date: str | None = None,
    time_range: str | None = None
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
        
        # 1. 태빌리 검색 수행
        search_params = {
            "query": query,
            "max_results": max_results,
            # Explicitly use literal values to satisfy type checkers
            "search_depth": "advanced" 
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

if __name__ == "__main__":
    # Test with a known URL
    test_url = "https://www.google.com"
    print(f"Testing Hybrid Scraper with: {test_url}")
    print(extract_url_content.run(test_url)[:500])
