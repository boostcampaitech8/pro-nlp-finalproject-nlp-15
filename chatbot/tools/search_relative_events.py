from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from db.vector_store import VectorStore
import os

class RelativeEventsQuery(BaseModel):
    """Schema for relative events semantic search."""
    query: str = Field(..., description="The semantic search query (e.g., 'interest rate impact on gold')")
    top_k: int = Field(5, description="Number of relevant events to retrieve.")

def search_relative_events(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Performs a semantic search to find articles/events related to the query.
    Uses a hybrid (Dense + Sparse) search strategy for high accuracy.

    Args:
        query: The user's question or keywords.
        top_k: The number of top results to return.

    Returns:
        dict: A list of relevant events with their titles, descriptions, and dates.
    """
    # Initialize VectorStore (Using environment variables default)
    # Note: In a production app, we might want to singleton this.
    try:
        vs = VectorStore()
        results = vs.search_similar_events(query, top_k=top_k)
        
        if not results:
            return {"message": "No relevant events found for the given query."}
            
        return {"events": results}
    except Exception as e:
        return {"error": f"Semantic search failed: {str(e)}"}

if __name__ == "__main__":
    # Internal Test
    import json
    # result = search_relative_events("FED interest rate hike impact")
    # print(json.dumps(result, indent=2, ensure_ascii=False))
    print("search_relative_events tool ready.")
