
from sqlalchemy import text
from db.database import get_engine
from hydra import initialize, compose
from dotenv import load_dotenv

load_dotenv()
initialize(version_base=None, config_path="config")
cfg = compose(config_name="chatbot")
engine = get_engine(cfg.database)

print("🛠️ Fixing Article and Event indexes...")

with engine.connect() as conn:
    # 1. Fix Article table
    print(" - Optimizing article table...")
    try:
        # Change id to VARCHAR to allow indexing
        conn.execute(text("ALTER TABLE article MODIFY id VARCHAR(50)"))
    except Exception as e:
        print(f"   (Article id modify skipped: {e})")

    try:
        # Add index on id if not already there
        conn.execute(text("CREATE INDEX idx_article_id ON article (id)"))
    except Exception as e:
        print(f"   (Article id index skipped: {e})")

    # 2. Re-verify Event indexes (just in case they were missed)
    print(" - Optimizing event table...")
    try:
        conn.execute(text("CREATE INDEX idx_event_date ON event (start_date)"))
    except Exception as e:
        print(f"   (Event date index skipped: {e})")
    
    try:
        conn.execute(text("CREATE INDEX idx_event_commodity ON event (commodity_id)"))
    except Exception as e:
        print(f"   (Event commodity index skipped: {e})")

    conn.commit()

print("✅ Index optimization attempt complete.")
