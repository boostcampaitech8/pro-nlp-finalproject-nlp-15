from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from db.article_repo import get_article_by_id

class ArticleQuery(BaseModel):
    """Schema for article lookup query."""
    article_id: str = Field(..., description="The 16-character hex ID of the article to retrieve.")

def get_original_article(article_id: str) -> Dict[str, Any]:
    """Retrieves the original article title and description by its hex ID.

    This tool searches through the article database (CSV files in data/articles) 
    to find the article metadata using the provided hex ID.

    Args:
        article_id: The 16-character hex ID associated with the article.
            Found in the 'source' list of an event.

    Returns:
        dict: A dictionary containing the article's title and description, 
              or an error message if not found.
    """
    article = get_article_by_id(article_id)
    
    if not article:
        return {"error": f"Article with ID {article_id} not found."}
    
    # Return requested fields: title + description
    return {
        "id": article.get("id"),
        "title": article.get("title"),
        "description": article.get("description"),
        "publish_date": article.get("publish_date"),
        "meta_site_name": article.get("meta_site_name"),
        "authors": article.get("authors"),
        "doc_url": article.get("doc_url")
    }

if __name__ == "__main__":
    # Test with a known ID from gold_future.csv
    import json
    result = get_original_article("f1d13285ba7ebd67")
    print(json.dumps(result, indent=2, ensure_ascii=False))
