
import os
import sys
import time
from datetime import date
sys.path.append(os.getcwd())
from dotenv import load_dotenv
load_dotenv()
from hydra import initialize, compose
from db.database import get_engine
from db.event_repo import EventRepository

# Load config
with initialize(version_base=None, config_path="config"):
    cfg = compose(config_name="chatbot")

engine = get_engine(cfg.database)
repo = EventRepository(engine)

start_date = date(2017, 11, 1)
end_date = date(2025, 1, 31)
asset = "ZC" # Corn

print(f"🕵️ Testing Event Search for {asset} ({start_date} ~ {end_date})...")

# 1. Test Date Sort
print("\n--- Testing Date Sort (DESC) ---")
start_time = time.time()
events = repo.search_events(start_date, end_date, asset_symbol=asset, sort_by="date", limit=10)
dur = time.time() - start_time
print(f"Found {len(events)} events in {dur:.4f} seconds")

# 2. Test Volatility Sort
print("\n--- Testing Volatility Sort (DESC) ---")
start_time = time.time()
events_vol = repo.search_events(start_date, end_date, asset_symbol=asset, sort_by="volatility", limit=10)
dur_vol = time.time() - start_time
print(f"Found {len(events_vol)} events in {dur_vol:.4f} seconds")

if events_vol:
    print(f"Sample Event: {events_vol[0]['title']} (ID: {events_vol[0]['id']})")
else:
    print("❌ No volatility events found.")
