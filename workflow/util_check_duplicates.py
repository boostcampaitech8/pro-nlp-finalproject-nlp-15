import sys
import argparse
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from preprocess.duplicate_checker import DuplicateChecker

def main():
    parser = argparse.ArgumentParser(description="Utility: Scan raw data files for duplicate IDs")
    args = parser.parse_args()

    base_data_path = PROJECT_ROOT / "data"
    checker = DuplicateChecker()

    # 1. Articles
    articles_dir = base_data_path / "articles"
    print(f"📄 Scanning articles in {articles_dir}...")
    art_res = checker.check_articles(str(articles_dir))
    print(f"   Total scanned: {art_res['total_scanned']}")
    print(f"   Unique IDs:    {art_res['unique_count']}")
    print(f"   Duplicates:    {art_res['duplicate_count']}")
    if art_res['top_duplicates']:
        print("   Top duplicates (id: count):")
        for id, count in art_res['top_duplicates']:
            print(f"     {id}: {count}")

    # 2. Events
    events_dir = base_data_path / "events"
    print(f"\n📅 Scanning events in {events_dir}...")
    ev_res = checker.check_events(str(events_dir))
    print(f"   Total scanned: {ev_res['total_scanned']}")
    print(f"   Unique IDs:    {ev_res['unique_count']}")
    print(f"   Duplicates:    {ev_res['duplicate_count']}")
    if ev_res['top_duplicates']:
        print("   Top duplicates (id: count):")
        for id, count in ev_res['top_duplicates']:
            print(f"     {id}: {count}")

if __name__ == "__main__":
    main()
