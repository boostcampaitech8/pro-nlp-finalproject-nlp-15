from langchain_core.tools import tool
from datetime import date
from typing import List, Optional
import pandas as pd

# Module-level variables for dependency injection
_news_repo = None
_stock_api = None
_target_files = None

def set_dependencies(news_repo, stock_api, target_files=None):
    """Set the dependencies for the tool to use."""
    global _news_repo, _stock_api, _target_files
    _news_repo = news_repo
    _stock_api = stock_api
    _target_files = target_files

@tool
def search_volatility_events(
    asset_name: str, 
    start_date: str, 
    end_date: str, 
    top_k: int = 10
) -> str:
    """
    Find major news events that occurred on high volatility trading days.
    
    Use this tool when the user asks about:
    - Why the price moved significantly ("Why did it drop?")
    - Major events or news in a specific period
    - What happened on a particular date
    - Market catalysts, drivers, or reasons for price changes
    - Correlation between news and price movements
    
    Examples of queries:
    - "Why did the price crash in March 2020?"
    - "What events caused the volatility?"
    - "Tell me about major news in this period"
    
    Args:
        asset_name: Name of the asset (e.g., "copper")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        top_k: Number of top events to return (default: 10)
        
    Returns:
        Markdown-formatted events with dates, closing prices, titles, and descriptions,
        filtered to only include events on the most volatile trading days
    """
    if _news_repo is None or _stock_api is None:
        return "Error: Dependencies not initialized"
    
    # Parse dates
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    
    # 1. Get Price Data & Calculate Volatility
    df = _stock_api.get_price_data(asset_name)
    if df.empty:
        return "No price data available for volatility analysis."
        
    mask = (df['time'].dt.date >= s_date) & (df['time'].dt.date <= e_date)
    period_df = df.loc[mask].copy()
    
    if period_df.empty:
        return "No price data in the specified period."

    # Calculate absolute daily change
    period_df['abs_change'] = period_df['close'].pct_change().abs()
    # Sort by change descending to find most volatile days
    top_vol_days = period_df.sort_values(by='abs_change', ascending=False).head(top_k * 2) 
    target_dates = set(top_vol_days['time'].dt.date)

    # Pre-index price data for fast lookup
    price_map = period_df.set_index(period_df['time'].dt.date)['close'].to_dict()

    # 2. Get All Events
    all_events = _news_repo.get_events(s_date, e_date, target_files=_target_files)
    
    # 3. Filter Events by Target Dates (high volatility days)
    filtered_events = []
    for ev in all_events:
        d_str = ev.get('start_date') or ev.get('date')
        try:
            ev_date = pd.to_datetime(d_str[:10]).date()
            if ev_date in target_dates:
                ev['parsed_date'] = ev_date
                filtered_events.append(ev)
        except: 
            continue
        
    if not filtered_events:
         return "No events found on high volatility days in this period."

    # 4. Sort by Date and Limit
    filtered_events.sort(key=lambda x: x.get('parsed_date', date.min))
    filtered_events = filtered_events[:top_k]

    result = [f"## Top Market Events on High Volatility Days ({start_date} ~ {end_date})"]
    for ev in filtered_events:
        d = ev.get('parsed_date')
        t = ev.get('title', 'No Title')
        desc = ev.get('description', 'No description available.')
        price = price_map.get(d)
        price_str = f" (Close: {price:,.2f})" if price else ""
        
        result.append(f"### {d}{price_str}\n- **Title**: {t}\n- **Description**: {desc}\n")
        
    return "\n".join(result)
