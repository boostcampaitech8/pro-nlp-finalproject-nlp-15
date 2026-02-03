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
    Get statistical summary of asset price for a given period.
    
    Use this tool when the user asks about:
    - Price movements (returns, gains, losses)
    - Volatility or risk metrics
    - Overall market performance in a specific period
    - Price statistics or quantitative analysis
    
    Examples of queries:
    - "What was the return in August 2020?"
    - "How volatile was the market?"
    - "Show me the price statistics"
    
    Args:
        asset_name: Name of the asset (e.g., "copper", "silver")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Markdown-formatted price statistics including return and volatility
    """
    if _stock_api is None:
        return "Error: StockAPI not initialized"
    
    # Parse dates
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    
    return _stock_api.get_price_summary(asset_name, s_date, e_date)
