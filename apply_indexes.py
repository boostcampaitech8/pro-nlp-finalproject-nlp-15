
from sqlalchemy import text
from db.database import get_engine
from hydra import initialize, compose
from dotenv import load_dotenv

load_dotenv()

# Load config
with initialize(version_base=None, config_path="config"):
    cfg = compose(config_name="chatbot")

engine = get_engine(cfg.database)

print("🚀 Applying indexes to MySQL database...")
with engine.connect() as conn:
    # Asset.code is already unique=True which creates an index.
    
    # 1. Price.time
    print(" - Indexing futures_price.time...")
    try:
        conn.execute(text("CREATE INDEX idx_price_time ON futures_price (time)"))
    except Exception as e:
        print(f"   (Skipped or already exists: {e})")
    
    # 2. Event.date
    print(" - Indexing event.start_date...")
    try:
        conn.execute(text("CREATE INDEX idx_event_date ON event (start_date)"))
    except Exception as e:
        print(f"   (Skipped or already exists: {e})")

    # 3. Event.asset_id
    print(" - Indexing event.commodity_id...")
    try:
        conn.execute(text("CREATE INDEX idx_event_commodity ON event (commodity_id)"))
    except Exception as e:
        print(f"   (Skipped or already exists: {e})")

    conn.commit()
print("✅ Indexing complete.")
