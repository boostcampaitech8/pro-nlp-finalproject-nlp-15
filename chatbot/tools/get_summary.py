from langchain_core.tools import tool
from datetime import date

# Module-level variable for dependency injection
_stock_api = None

def set_stock_api(stock_api):
    """Set the StockAPI instance for the tool to use."""
    global _stock_api
    _stock_api = stock_api

@tool
def get_price_summary(asset_name: str, start_date: str, end_date: str) -> str:
    """
    Retrieve statistical summary of asset price movements for analysis baseline.
    
    📌 WHEN TO USE (Priority: HIGH - Use this FIRST in most analyses):
    - User asks about price trends, returns, or volatility
    - Before investigating WHY prices moved (establish WHAT happened first)
    - Comparative analysis between different time periods
    
    📌 EXPECTED OUTPUT:
    - Period return (%)
    - Annualized volatility
    - Starting/ending prices
    - Date range confirmation
    
    🔍 Example Queries:
    - "What was the return in August 2020?"
    - "How volatile was gold this quarter?"
    - "Show me price statistics for last year"
    
    Args:
        asset_name: Asset identifier (e.g., "copper", "silver", "gold_future")
        start_date: Period start in YYYY-MM-DD format
        end_date: Period end in YYYY-MM-DD format
        
    Returns:
        Markdown-formatted statistics including return, volatility, and price levels
    """
    if _stock_api is None:
        return "Error: StockAPI not initialized"
    
    # Parse dates
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    
    return _stock_api.get_price_summary(asset_name, s_date, e_date)
