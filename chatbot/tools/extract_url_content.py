# re, requests, bs4 are standard/minimal
import re
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

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
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth
        except ImportError:
            return "Note: Playwright is not installed. Deep scraping skipped. (Legacy extraction failed or returned too little content)."

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
