from db.news_repo import NewsRepository
from db.stock_api import StockAPI
from datetime import date, timedelta
from typing import List
import pandas as pd

class SearchEventsTool:
    def __init__(self, news_repo: NewsRepository, stock_api: StockAPI):
        self.news_repo = news_repo
        self.stock_api = stock_api

    def run(self, asset_name: str, start_date: date, end_date: date, target_files: List[str] = None, top_k: int = 20) -> str:
        """
        Tool function to get events filtered by high volatility dates, including price context and full descriptions.
        """
        # 1. Get Price Data & Calculate Volatility
        df = self.stock_api.get_price_data(asset_name)
        if df.empty:
            return "No price data for volatility analysis."
            
        mask = (df['time'].dt.date >= start_date) & (df['time'].dt.date <= end_date)
        period_df = df.loc[mask].copy()
        
        if period_df.empty:
            return "No price data in this period."

        # Calculate absolute daily change
        period_df['abs_change'] = period_df['close'].pct_change().abs()
        # Sort by change descending to find most volatile days
        top_vol_days = period_df.sort_values(by='abs_change', ascending=False).head(top_k * 2) 
        target_dates = set(top_vol_days['time'].dt.date)

        # Pre-index price data for fast lookup
        price_map = period_df.set_index(period_df['time'].dt.date)['close'].to_dict()

        # 2. Get All Events
        all_events = self.news_repo.get_events(start_date, end_date, target_files=target_files)
        
        # 3. Filter Events by Target Dates
        filtered_events = []
        for ev in all_events:
            d_str = ev.get('start_date') or ev.get('date')
            try:
                ev_date = pd.to_datetime(d_str[:10]).date()
                if ev_date in target_dates:
                    ev['parsed_date'] = ev_date # For sorting and price lookup
                    filtered_events.append(ev)
            except: continue
            
        if not filtered_events:
             return "No events found on high volatility days in this period."

        # 4. Sort by Date and Limit
        filtered_events.sort(key=lambda x: x.get('parsed_date', date.min))
        filtered_events = filtered_events[:top_k]

        result = [f"## [Top Market Events & Price Correlation] ({start_date} ~ {end_date})"]
        for ev in filtered_events:
            d = ev.get('parsed_date')
            t = ev.get('title', 'No Title')
            desc = ev.get('description', 'No description available.')
            price = price_map.get(d)
            price_str = f" (Close Price: {price:,.2f})" if price else ""
            
            result.append(f"### Date: {d}{price_str}\n- **Title**: {t}\n- **Description**: {desc}\n")
            
        return "\n".join(result)
