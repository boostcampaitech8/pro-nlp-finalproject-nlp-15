from langchain_core.tools import tool
from datetime import date
from typing import Optional
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
def get_period_overview(
    asset_name: str, 
    start_date: str, 
    end_date: str, 
    top_k: int = 8
) -> str:
    """
    특정 기간에 대한 가격 흐름, 통계, 주요사건 요약. 
    유저가 특정 기간이나 사건, 키워드를 명시하지 않고 전반적인 시장 상황을 설명해달라고 할 때 사용합니다.
    
    Args:
        asset_name: 자산 이름 (예: "silver_future", "copper")
        start_date: 분석 시작일 (YYYY-MM-DD)
        end_date: 분석 종료일 (YYYY-MM-DD)
        top_k: 반환할 주요 이벤트 최대 개수
    """
    if _news_repo is None or _stock_api is None:
        return "Error: Dependencies not initialized"
    
    # Parse dates
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    
    output = [f"# {asset_name} Analysis: {start_date} ~ {end_date}\n"]
    
    # ======= PART 1: PRICE SUMMARY =======
    output.append("## Price Summary\n")
    try:
        price_summary = _stock_api.get_price_summary(asset_name, s_date, e_date)
        output.append(price_summary)
    except Exception as e:
        output.append(f"Price data retrieval failed: {str(e)}")
    
    output.append("\n---\n")
    
    # ======= PART 2: MAJOR EVENTS (VOLATILITY-DRIVEN) =======
    output.append("## Major Events (High Volatility)\n")
    
    # Get price data for volatility analysis
    df = _stock_api.get_price_data(asset_name)
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
    
    # Get events
    all_events = _news_repo.get_events(s_date, e_date, target_files=_target_files)
    
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
        output.append(f"{desc}\n")
    
    return "\n".join(output)

__all__ = ['get_period_overview', 'set_dependencies']
