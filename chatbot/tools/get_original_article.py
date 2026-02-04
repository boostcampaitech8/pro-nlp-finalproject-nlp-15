from langchain_core.tools import tool
from typing import Any
from pydantic import BaseModel, Field
from db.article_repo import get_article_by_id

class ArticleQuery(BaseModel):
    """Schema for article lookup query."""
    article_id: str = Field(..., description="The 16-character hex ID of the article to retrieve.")

def _get_article_metadata(article_id: str) -> dict[str, Any]:
    """Internal function for retrieving article metadata."""
    article = get_article_by_id(article_id)
    
    if not article:
        return {"error": f"Article with ID {article_id} not found."}
    
    return {
        "id": article.get("id"),
        "title": article.get("title"),
        "description": article.get("description"),
        "publish_date": article.get("publish_date"),
        "meta_site_name": article.get("meta_site_name"),
        "authors": article.get("authors"),
        "doc_url": article.get("doc_url")
    }

@tool
def get_original_article(article_id: str) -> dict[str, Any]:
    """
    Retrieve full metadata and description of a specific news article by ID.
    
    📌 WHEN TO USE (Priority: LOW - Verification only):
    - User asks for MORE DETAILS about a specific event mentioned earlier
    - Need to verify exact wording or author of a source
    - Providing direct URL link for user to read full article
    
    📌 DO NOT USE if:
    - User is asking a general question (use search tools instead)
    - You don't have an article ID from previous tool results
    
    📌 EXPECTED OUTPUT:
    Dictionary containing:
    - id: 16-character hex identifier
    - title: Article headline
    - description: Full article description/summary
    - publish_date: Publication date
    - doc_url: Link to original source
    - meta_site_name: Publisher name
    
    🔍 Example Scenario:
    After showing event summary: "2024-03-15: 중국 수요 감소 (ID: f1d13285ba7ebd67)"
    User asks: "Tell me more about that China demand article"
    → Call get_original_article("f1d13285ba7ebd67")
    
    Args:
        article_id: 16-character hexadecimal ID from event source list
        
    Returns:
        Dictionary with article metadata, or {"error": "..."} if not found
    """
    return _get_article_metadata(article_id)

if __name__ == "__main__":
    # Test with a known ID from gold_future.csv
    import json
    result = _get_article_metadata("f1d13285ba7ebd67")
    print(json.dumps(result, indent=2, ensure_ascii=False))
