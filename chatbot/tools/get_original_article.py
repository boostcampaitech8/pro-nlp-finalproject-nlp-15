from langchain_core.tools import tool
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from db.article_repo import ArticleRepository

# Module-level variable for dependency injection
_article_repo: Optional[ArticleRepository] = None

def set_dependencies(article_repo: ArticleRepository):
    """Set the dependencies for the tool to use."""
    global _article_repo
    _article_repo = article_repo

@tool
def get_original_article(article_id: str) -> dict[str, Any]:
    """
    Retrieve full metadata and content of a specific news article by ID.
    
    📌 WHEN TO USE (Priority: LOW - Verification only):
    - User asks for MORE DETAILS about a specific event mentioned earlier
    - Need to verify exact wording or author of a source
    - Providing direct URL link for user to read full article
    
    Args:
        article_id: 16-character hexadecimal ID from tool results
        
    Returns:
        Dictionary with article metadata, or {"error": "..."} if not found
    """
    if _article_repo is None:
        return {"error": "Error: Article repository not initialized."}
        
    article = _article_repo.get_article(article_id)
    
    if not article:
        return {"error": f"Article with ID {article_id} not found."}
    
    # article is a dict from ArticleRepository.get_article()
    return {
        "id": article.get("id"),
        "title": article.get("title"),
        "description": article.get("content"), # Map 'content' to 'description' for consistency
        "publish_date": article.get("date"),
        "meta_site_name": article.get("source"),
        "doc_url": article.get("url")
    }

if __name__ == "__main__":
    # Test stub
    pass
