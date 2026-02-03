from db.stock_api import StockAPI
from datetime import date

class GetSummaryTool:
    def __init__(self, stock_api: StockAPI):
        self.stock_api = stock_api

    def run(self, asset_name: str, start_date: date, end_date: date) -> str:
        """
        Tool function to get market statistical summary.
        """
        return self.stock_api.get_price_summary(asset_name, start_date, end_date)
