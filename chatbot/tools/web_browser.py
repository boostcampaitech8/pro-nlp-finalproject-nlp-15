import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
import re

def clean_text(text: str) -> str:
    """Clean the extracted text by removing extra whitespaces and newlines."""
    # Remove script and style elements
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL)
    
    # Remove other HTML tags (if any were missed by soup.get_text())
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@tool
def extract_url_content(url: str) -> str:
    """
    Fetch and extract the main text content from a given URL.
    
    Use this tool when you have a URL (e.g., from an article's metadata) and 
    need to read the full body text for analysis.
    
    Args:
        url: The full web URL to fetch.
        
    Returns:
        A string containing the extracted text content or an error message.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
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
        # But keep it generous enough for long articles
        if len(cleaned) > 20000:
            cleaned = cleaned[:20000] + "... [Content Truncated]"
            
        if not cleaned or len(cleaned) < 50:
            return "Error: Could not extract meaningful text from the URL. The page might be protected or use dynamic loading."
            
        return cleaned

    except requests.exceptions.HTTPError as e:
        return f"HTTP Error: {e.response.status_code} - Could not access the URL."
    except requests.exceptions.RequestException as e:
        return f"Network Error: {str(e)} - Please check the URL or try again later."
    except Exception as e:
        return f"Unexpected Error: {str(e)}"

if __name__ == "__main__":
    # Test with a known URL
    test_url = "https://www.google.com"
    print(f"Testing with: {test_url}")
    print(extract_url_content.run(test_url))
