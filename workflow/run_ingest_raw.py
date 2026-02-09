import hydra
import os
import sys
from omegaconf import DictConfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.database import init_db
from preprocess.sqlite_ingestor import SQLiteIngestor


@hydra.main(version_base=None, config_path="../config", config_name="ingest_raw")
def main(cfg: DictConfig):
    rebuild = cfg.get("rebuild", False)
    # Function to resolve absolute path relative to project root if needed
    def resolve_path(p):
        if not os.path.isabs(p):
            return str(PROJECT_ROOT / p)
        return p

    db_path = resolve_path(cfg.data.db_path)
    if rebuild and os.path.exists(db_path):
        print(f"🗑️ Rebuilding database: Deleting {db_path}")
        os.remove(db_path)

    # Initialize DB engine and schema
    from omegaconf import OmegaConf
    from typing import cast
    db_cfg = cast(dict, OmegaConf.to_container(cfg.database, resolve=True))
    db_type = db_cfg.get('type', 'sqlite')
    print(f"🏗️ Initializing database ({db_type})...")
    engine = init_db(db_cfg)

    ingestor = SQLiteIngestor(engine, assets_list=cfg.assets.assets)

    # 1. Sync Assets
    print("🔄 Synchronizing assets from config...")
    asset_count = ingestor.synchronize_assets()
    print(f"   ✅ {asset_count} assets synchronized.")

    # Function to resolve absolute path relative to project root if needed
    def resolve_path(p):
        if not os.path.isabs(p):
            return str(PROJECT_ROOT / p)
        return p

    prices_dir = resolve_path(cfg.data.prices_dir)
    print(f"📈 Ingesting prices from {prices_dir}...")
    ingested_symbols = ingestor.ingest_prices(prices_dir)
    print(f"   ✅ Ingested prices for: {', '.join(ingested_symbols)}")

    # 3. Ingest Articles
    articles_dir = resolve_path(cfg.data.articles_dir)
    print(f"📰 Ingesting articles from {articles_dir}...")
    article_id_map, art_count = ingestor.ingest_articles(articles_dir)
    print(f"   ✅ {art_count} new articles ingested.")

    # 4. Ingest Events
    events_dir = resolve_path(cfg.data.events_dir)
    print(f"📅 Ingesting events from {events_dir}...")
    ev_count = ingestor.ingest_events(events_dir, article_id_map)
    print(f"   ✅ {ev_count} new events ingested.")

    print("\n🚀 Raw data ingestion pipeline completed successfully!")


if __name__ == "__main__":
    main()
