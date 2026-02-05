from langchain_core.tools import tool
from datetime import date
import pandas as pd
from typing import Any

# Module-level variables for dependency injection
_news_repo: Any | None = None
_stock_api: Any | None = None
_target_files: list[str] | None = None

def set_dependencies(news_repo: Any, stock_api: Any, target_files: list[str] | None = None) -> None:
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
    📊 VOLATILITY-DRIVEN EVENT SEARCH - Events on high price-change days
    
    ⭐ USE FOR PRICE MOVEMENT QUERIES - When user asks about price changes:
    - "무슨 일이 있었어?" (general period review)
    - "왜 가격이 올랐어/내렸어?" (explain price movements)
    - "이 기간 주요 이벤트" (get events from most volatile days)
    - "가격 변동 원인" (connect volatility to news)
    
    ❌ DON'T USE FOR:
    - "코로나가 미친 영향" → Use search_similar_events (theme-based search)
    - "우크라이나 전쟁" → Use search_similar_events (topic search)
    - Any topic/theme queries → Use search_similar_events instead
    
    💡 HOW IT WORKS:
    1. Identifies days with highest absolute price changes in period
    2. Retrieves news events published on those specific dates
    3. Returns chronologically ordered events with closing prices
    
    Args:
        asset_name: Asset identifier (e.g., "copper", "silver_future")
        start_date: Period start in YYYY-MM-DD format
        end_date: Period end in YYYY-MM-DD format
        top_k: Max number of events to return (default: 10)
        
    Returns:
        Markdown report of major events on high-volatility days with closing prices
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
