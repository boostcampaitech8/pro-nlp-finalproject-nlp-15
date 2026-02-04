import pandas as pd
import os
import streamlit as st
from datetime import date

class StockAPI:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def get_all_files(self) -> list[str]:
        """Returns list of available price CSV files."""
        if not os.path.exists(self.data_dir): return []
        return [f for f in os.listdir(self.data_dir) if f.endswith("_price.csv")]

    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_price_data(_self, asset_name: str) -> pd.DataFrame:
        """
        Loads price data for a given asset from a CSV file.
        Returns a DataFrame with a 'time' column converted to datetime.
        Note: _self prefix prevents caching issues with instance methods.
        """
        file_path = os.path.join(_self.data_dir, f"{asset_name}_price.csv")
        if not os.path.exists(file_path):
            return pd.DataFrame()
        
        df = pd.read_csv(file_path)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
        return df

    def get_price_summary(self, asset_name: str, start_date: date, end_date: date) -> str:
        """
        Returns a statistical summary of the asset price within a specific period.
        """
        df = self.get_price_data(asset_name)
        if df.empty:
            return "No data available."

        mask = (df['time'].dt.date >= start_date) & (df['time'].dt.date <= end_date)
        period_df = df.loc[mask]

        if period_df.empty:
            return "No data in the specified range."

        start_p = period_df.iloc[0]['close']
        end_p = period_df.iloc[-1]['close']
        ret = ((end_p - start_p) / start_p) * 100
        vol = period_df['close'].pct_change().std() * (252**0.5) * 100

        return f"""
### Market Statistics: {asset_name}
- Period: {start_date} ~ {end_date}
- Return: {ret:.2f}% ({start_p:,.2f} -> {end_p:,.2f})
- Volatility (Ann.): {vol:.2f}%
"""
