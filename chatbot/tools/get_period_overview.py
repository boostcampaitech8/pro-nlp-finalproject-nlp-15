from langchain_core.tools import tool
from datetime import date
from typing import Optional
import pandas as pd

from vector_db.resource_manager import ResourceManager
from db.price_repo import PriceRepository
from db.event_repo import EventRepository

# Module-level variables for dependency injection
_event_repo: Optional[EventRepository] = None
_price_repo: Optional[PriceRepository] = None

def set_dependencies(event_repo: EventRepository, price_repo: PriceRepository):
    """Set the dependencies for the tool to use."""
    global _event_repo, _price_repo
    _event_repo = event_repo
    _price_repo = price_repo

@tool
def get_period_overview(
    asset_symbol: str, 
    start_date: str, 
    end_date: str, 
    top_k: int = 8
) -> str:
    """
    Provide a comprehensive overview of price trends, statistics, and major market events for a specific period.
    Use this tool when the user asks for a general market summary or "what happened" during a timeframe 
    without specifying exact keywords or events.
    
    Args:
        asset_symbol: The asset identifier (e.g., "silver_future", "copper").
        start_date: The start date for analysis (YYYY-MM-DD).
        end_date: The end date for analysis (YYYY-MM-DD).
        top_k: The maximum number of high-volatility events to return.
    """
    if _event_repo is None or _price_repo is None:
        return "Error: Dependencies not initialized"
    
    # Parse dates
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    
    output = [f"# {asset_symbol} Analysis: {start_date} ~ {end_date}\n"]
    
    # ======= PART 1: PRICE SUMMARY =======
    output.append("## Price Summary\n")
    try:
        price_summary = _price_repo.get_summary(asset_symbol, s_date, e_date)
        output.append(price_summary)
    except Exception as e:
        output.append(f"Price data retrieval failed: {str(e)}")
    
    output.append("\n---\n")
    
    # ======= PART 2: MAJOR EVENTS (VOLATILITY-DRIVEN) =======
    output.append("## Major Events (High Volatility)\n")
    
    # Get price data for volatility analysis
    df = _price_repo.get_prices(asset_symbol)
    if df.empty:
        output.append("No price data available for event search.")
        return "\n".join(output)
    
    mask = (df['time'].dt.date >= s_date) & (df['time'].dt.date <= e_date)
    period_df = df.loc[mask].copy()
    
    if period_df.empty:
        output.append("No price data in the specified range.")
        return "\n".join(output)
    
    # Calculate daily change and top volatile days
    period_df['pct_change'] = period_df['close'].pct_change()
    period_df['abs_change'] = period_df['pct_change'].abs()
    top_vol_days = period_df.sort_values(by='abs_change', ascending=False).head(top_k * 2)
    target_dates = set(top_vol_days['time'].dt.date)
    
    # Change% map for displaying alongside events
    change_map = period_df.set_index(period_df['time'].dt.date)['pct_change'].to_dict()
    
    # Get events filtered by asset via many-to-many relationship
    all_events = _event_repo.search_events(s_date, e_date, asset_symbol=asset_symbol)
    
    # Filter events by high volatility dates
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
        output.append("No major events recorded on high-volatility dates.")
        return "\n".join(output)
    
    # Sort by date and limit
    filtered_events.sort(key=lambda x: x.get('parsed_date', date.min))
    filtered_events = filtered_events[:top_k]
    
    # Format events
    for ev in filtered_events:
        d = ev.get('parsed_date')
        t = ev.get('title', 'No Title')
        desc = ev.get('description', 'No description available.')
        change = change_map.get(d)
        
        # Format signed change %
        if change is not None:
            sign = "+" if change > 0 else ""
            change_str = f" | Daily Change: **{sign}{change*100:.2f}%**"
        else:
            change_str = ""
        
        output.append(f"### {d}{change_str}")
        output.append(f"**{t}**")
        output.append(f"{desc}")
        
        # Add source URLs with Titles if available
        articles = ev.get('articles', [])
        if articles:
             # articles is a list of dicts with 'url', 'title'
             for a in articles[:3]: # Limit to top 3
                 url = a.get('url')
                 if url:
                     title = a.get('title', 'Link')
                     output.append(f"- Source: [{title}]({url})")
        
        output.append("") # Newline
    
    return "\n".join(output)

__all__ = ['get_period_overview', 'set_dependencies']
