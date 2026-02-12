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
    top_k: int = 20
) -> str:
    """
    Provide a comprehensive overview of price trends, statistics, and major market events for a specific period.
    Use this tool when the user asks for a general market summary or "what happened" during a timeframe 
    without specifying exact keywords or events.
    
    Args:
        asset_symbol: The ticker symbol for the asset (e.g., "ZC" for Corn, "HG" for Copper, "SI" for Silver, "GC" for Gold, "W" for Wheat, "S" for Soybean).
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
    
    # Calculate daily change
    period_df['pct_change'] = period_df['close'].pct_change()
    period_df['abs_change'] = period_df['pct_change'].abs()
    
    # --- Stratified Sampling: Divide period into top_k bins ---
    period_df = period_df.sort_values('time')
    
    # Calculate how many bins to use (up to top_k)
    num_bins = min(len(period_df), top_k)
    if num_bins > 0:
        import numpy as np
        n = len(period_df)
        bin_size = max(1, n // num_bins)
        target_dates = set()
        for i in range(0, n, bin_size):
            chunk_item = period_df.iloc[i : i + bin_size]
            if chunk_item.empty:
                continue
            # Find the most volatile day in this specific segment
            max_idx = chunk_item["abs_change"].idxmax()
            target_dates.add(chunk_item.loc[max_idx, "time"].date())
    else:
        target_dates = set()
    
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
        ev_desc = ev.get('description', 'No description available.')
        change = change_map.get(d)
        
        # Format signed change %
        if change is not None:
            sign = "+" if change > 0 else ""
            change_str = f" [Daily Change: **{sign}{change*100:.2f}%**]"
        else:
            change_str = ""
        
        output.append(f"### {d} - {t}{change_str}")
        output.append(f"- **Summary**: {ev_desc}")
        
        # Related Articles and Primary Body
        articles = ev.get('articles', [])
        primary_body = ""
        
        if articles:
            output.append("- **Related Articles**:")
            for idx, a in enumerate(articles[:5]):
                url = a.get('url', '#')
                title_art = a.get('title', 'Link')
                output.append(f"  - [{title_art}]({url})")
                
                if idx == 0:
                    # description in EventRepository's article_map is the body
                    body = a.get('description', '')
                    if body:
                        limit = 3000
                        primary_body = body[:limit] + ("..." if len(body) > limit else "")
        
        if len(primary_body) > 0:
            output.append(f"- **Description**: {primary_body}")
        
        output.append("") # Newline
    
    return "\n".join(output)

__all__ = ['get_period_overview', 'set_dependencies']
