import os
import sys
from datetime import date
from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra

# Add root to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from db.database import get_engine
from db.event_repo import EventRepository

def test_repo():
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize(version_base=None, config_path="../config"):
        cfg = compose(config_name="chatbot")
    
    engine = get_engine(cfg.database)
    repo = EventRepository(engine)
    
    start = date(2020, 1, 1)
    end = date(2025, 1, 1)
    asset = None # Search all assets
    
    print(f"Testing search_events from {start} to {end}...")
    
    # Test Count
    total = repo.count_events(start, end, asset_symbol=asset)
    print(f"Total events: {total}")
    
    # Test Pagination
    limit = 5
    events = repo.search_events(start, end, asset_symbol=asset, limit=limit, offset=0, sort_order="desc")
    print(f"Fetched {len(events)} events (limit={limit}, sort=desc):")
    for e in events:
        print(f" - {e['start_date']} | {e['title']}")
    
    # Test Search
    if total > 0:
        keyword = events[0]['title'].split()[0] # Take first word of first event
        print(f"\nSearching for keyword: '{keyword}'...")
        searched = repo.search_events(start, end, asset_symbol=asset, keyword=keyword, limit=limit)
        print(f"Found {len(searched)} matches.")
        for e in searched:
            print(f" - {e['start_date']} | {e['title']}")

if __name__ == "__main__":
    test_repo()
