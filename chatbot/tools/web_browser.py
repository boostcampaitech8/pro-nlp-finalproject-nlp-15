import re
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
from bs4 import BeautifulSoup
from langchain_core.tools import tool

def clean_text(text: str) -> str:
    """Clean the extracted text by removing extra whitespaces and newlines."""
    # Remove script and style elements (backup regex)
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL)
    
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@tool
def extract_url_content(url: str) -> str:
    """
    Fetch and extract the main text content from a given URL using a headless browser.
    
    Use this tool when you have a URL (e.g., from an article's metadata) and 
    need to read the full body text for analysis. This tool can handle 
    JavaScript-heavy sites and common bot protections.
    
    Args:
        url: The full web URL to fetch.
        
    Returns:
        A string containing the extracted text content or an error message.
    """
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            
            # Create a context with a realistic user agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            context = browser.new_context(user_agent=user_agent)
            
            # Create a page and apply stealth
            page = context.new_page()
            stealth(page)
            
            # Navigate to the URL
            # wait_until="networkidle" ensures most JS content is loaded
            # Use a reasonable timeout (30 seconds)
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response:
                return "Error: No response received from the server. The URL might be invalid or the site is down."
            
            if response.status >= 400:
                return f"HTTP Error: {response.status} - Could not access the URL."

            # Optional: Wait a bit more for dynamic content if needed
            # time.sleep(2) 

            # Get the fully rendered content
            html_content = page.content()
            browser.close()
            
            # Use BeautifulSoup to parse the rendered HTML for text extraction
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()
                
            # Strategy: Look for common article containers
            article_content = ""
            
            # Try finding <article> tag first
            article_tag = soup.find("article")
            if article_tag:
                article_content = article_tag.get_text(separator="\n")
            else:
                # Fallback: Look for divs with common article-related classes/ids
                content_selectors = [
                     {"class": re.compile(r"article-body|post-content|main-content|entry-content|story-content", re.I)},
                     {"id": re.compile(r"article-body|main-content|story-body", re.I)}
                ]
                for selector in content_selectors:
                    match = soup.find("div", selector)
                    if match:
                        article_content = match.get_text(separator="\n")
                        break
                
                # Last resort: just get everything from <body>
                if not article_content:
                    body = soup.find("body")
                    if body:
                        article_content = body.get_text(separator="\n")
                    else:
                        article_content = soup.get_text(separator="\n")
            
            cleaned = clean_text(article_content)
            
            # Limit length to avoid blowing up LLM context if it's too huge
            if len(cleaned) > 20000:
                cleaned = cleaned[:20000] + "... [Content Truncated]"
                
            if not cleaned or len(cleaned) < 100:
                # Check for "Enable Javascript" or common bot block messages
                if "javascript" in cleaned.lower() and "enable" in cleaned.lower():
                    return "Error: The site requires JavaScript or detected the bot, preventing content extraction."
                return "Error: Could not extract meaningful text from the URL. The page might be protected or paywalled."
                
            return cleaned

    except Exception as e:
        # Check for common Playwright errors
        error_msg = str(e)
        if "Timeout" in error_msg:
             return f"Timeout Error: The page took too long to load ({url})."
        return f"Unexpected Scraper Error: {error_msg}"

if __name__ == "__main__":
    # Test with a known URL
    test_url = "https://www.google.com"
    print(f"Testing with: {test_url}")
    print(extract_url_content.run(test_url))
