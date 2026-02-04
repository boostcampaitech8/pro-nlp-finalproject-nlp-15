from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from db.vector_store import VectorStore
import os

class RelativeArticlesQuery(BaseModel):
    """Schema for relative articles semantic search."""
    query: str = Field(..., description="The semantic search query (e.g., 'interest rate impact on gold')")
    top_k: int = Field(5, description="Number of relevant articles to retrieve.")
    start_date: Optional[str] = Field(None, description="Start date for filtering in YYYY-MM-DD format (inclusive).")
    end_date: Optional[str] = Field(None, description="End date for filtering in YYYY-MM-DD format (inclusive).")

def search_relative_articles(
    query: str, 
    top_k: int = 5, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs a semantic search to find news articles related to the query.
    Supports optional date range filtering.

    Args:
        query: The user's question or keywords.
        top_k: The number of top results to return.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        dict: A list of relevant articles with their titles, descriptions, and publish dates.
    """
    try:
        vs = VectorStore()
        results = vs.search_similar_articles(
            query, 
            top_k=top_k, 
            start_date=start_date, 
            end_date=end_date
        )
        
        if not results:
            return {"message": "No relevant articles found for the given query and date range."}
            
        return {"articles": results}
    except Exception as e:
        return {"error": f"Article search failed: {str(e)}"}

if __name__ == "__main__":
    print("search_relative_articles tool ready.")
