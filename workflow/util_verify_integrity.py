import sys
import argparse
import yaml
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_engine
from preprocess.db_verifier import DatabaseVerifier

def main():
    parser = argparse.ArgumentParser(description="Utility: Verify SQLite database contents and integrity")
    args = parser.parse_args()

    # Load config
    config_path = PROJECT_ROOT / "config" / "chatbot.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    db_path = config['data']['db_path']
    db_cfg = config.get('database', {})
    
    print(f"🔍 Connecting to database at {db_path}...")
    engine = get_engine(
        db_path,
        timeout=db_cfg.get('timeout', 30),
        journal_mode=db_cfg.get('journal_mode', 'WAL'),
        synchronous=db_cfg.get('synchronous', 'NORMAL')
    )

    verifier = DatabaseVerifier(engine)
    stats = verifier.get_stats()

    print("\n--- 📊 Database Verification Report ---")
    print(f"Total Unique Articles: {stats['total_articles']}")
    print(f"Total Unique Events:   {stats['total_events']}")
    
    print("\nAsset Distribution:")
    for a in stats['assets']:
        print(f"  - {a['symbol']}: {a['prices']} prices, {a['events']} linked events")
    
    print(f"\nLinkage Integrity (Event -> Article): {'✅ PASSED' if stats['linkage_verified'] else '❌ FAILED'}")
    print("----------------------------------------\n")

if __name__ == "__main__":
    main()
