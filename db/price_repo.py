import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.database import Asset, Price

class PriceRepository:
    def __init__(self, engine):
        self.engine = engine

    def list_assets(_self) -> dict[str, str]:
        """Returns mapping of {name_ko: code} for assets in the database."""
        with Session(_self.engine) as session:
            return {str(a.name_ko): str(a.code) for a in session.query(Asset).all()}

    def get_prices(_self, asset_symbol: str) -> pd.DataFrame:
        """
        Loads price data for a given asset from SQLite.
        Returns a DataFrame with a 'time' column converted to datetime.
        """
        with Session(_self.engine) as session:
            asset = session.query(Asset).filter(Asset.code == asset_symbol.upper()).first()
            if not asset:
                return pd.DataFrame()
            
            prices = session.query(Price).filter(Price.asset_id == asset.id).order_by(Price.time).all()
            if not prices:
                return pd.DataFrame()
            
            df = pd.DataFrame([{
                'time': p.time,
                'close': p.close,
                'volume': p.volume
            } for p in prices])
            
            # Ensure time is datetime for .dt accessors
            df['time'] = pd.to_datetime(df['time'])
            
            return df

    def get_summary(self, asset_symbol: str, start_date: date, end_date: date) -> str:
        """
        Returns a statistical summary of the asset price within a specific period.
        Includes a 'Price Flow' trend to help LLM understand the chart shape.
        """
        df = self.get_prices(asset_symbol)
        if df.empty:
            return "No data available."

        # Filter by date range
        mask = (df['time'].dt.date >= start_date) & (df['time'].dt.date <= end_date)
        period_df = df.loc[mask].reset_index(drop=True)

        if period_df.empty:
            return "No data in the specified range."

        start_p = period_df.iloc[0]['close']
        end_p = period_df.iloc[-1]['close']
        ret = ((end_p - start_p) / start_p) * 100
        
        # Calculate volatility if enough data points
        if len(period_df) > 1:
            vol = period_df['close'].pct_change().std() * (252**0.5) * 100
        else:
            vol = 0.0

        # Calculate Min/Max stats
        min_price = period_df['close'].min()
        min_date = period_df.loc[period_df['close'].idxmin(), 'time'].strftime('%Y-%m-%d')
        max_price = period_df['close'].max()
        max_date = period_df.loc[period_df['close'].idxmax(), 'time'].strftime('%Y-%m-%d')

        # Create Price Flow (7 representative points + Min/Max)
        # We want to capture the shape, so we check local extrema or just equidistant points
        # For simplicity and robust shape, let's use 5 equidistant + min + max, sorted by time
        important_indices = {0, len(period_df)-1}
        important_indices.add(int(period_df['close'].idxmin()))
        important_indices.add(int(period_df['close'].idxmax()))
        # Add simpler 25/50/75 quantiles indices
        n = len(period_df)
        important_indices.update([int(n*0.25), int(n*0.5), int(n*0.75)])
        
        sorted_indices = sorted([i for i in important_indices if 0 <= i < n])
        
        flow_points = []
        for i in sorted_indices:
            p = period_df.iloc[i]
            val = p['close']
            date_str = p['time'].strftime('%y-%m')
            flow_points.append(f"{val:,.2f}({date_str})")
            
        price_flow = " -> ".join(flow_points)

        return f"""
### Market Statistics: {asset_symbol}
- Period: {start_date} ~ {end_date}
- Price Flow: [{price_flow}]
- Key Levels: Low {min_price:,.2f} ({min_date}) | High {max_price:,.2f} ({max_date})
- Return: {ret:.2f}% ({start_p:,.2f} -> {end_p:,.2f})
- Volatility (Ann.): {vol:.2f}%
"""
