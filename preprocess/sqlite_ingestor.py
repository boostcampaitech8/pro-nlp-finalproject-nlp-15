import os
import glob
import pandas as pd
import json
import uuid
from tqdm import tqdm
from datetime import datetime
from sqlalchemy.orm import Session
from db.database import Asset, Price, Event, Article, init_db
import yaml

class SQLiteIngestor:
    """Pure logic for ingesting financial data into SQLite."""
    
    def __init__(self, engine, assets_list=None, assets_config_path=None):
        self.engine = engine
        self.assets_list = assets_list
        # Fallback to old path if nothing provided
        self.assets_config_path = assets_config_path or "config/assets/default.yaml"

    def load_assets_config(self):
        # If assets_list was passed directly (from Hydra), use it
        if self.assets_list is not None:
            return self.assets_list
            
        # Otherwise load from file
        with open(self.assets_config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get('assets', [])

    def parse_date(self, date_str):
        if not date_str or pd.isna(date_str):
            return None
        try:
            return pd.to_datetime(date_str).to_pydatetime()
        except:
            return None

    def synchronize_assets(self):
        assets_config = self.load_assets_config()
        with Session(self.engine) as session:
            for a_cfg in assets_config:
                # Use 'code' instead of 'symbol'
                existing = session.query(Asset).filter(Asset.code == a_cfg['symbol']).first()
                keywords_str = ",".join(a_cfg.get('keywords', []))
                if existing:
                    existing.name_ko = a_cfg['name']
                else:
                    asset = Asset(
                        code=a_cfg['symbol'],
                        name_ko=a_cfg['name']
                    )
                    session.add(asset)
            session.commit()
        return len(assets_config)

    def ingest_prices(self, prices_dir):
        price_files = glob.glob(os.path.join(prices_dir, "*_price.csv"))
        ingested_symbols = []
        
        with Session(self.engine) as session:
            assets_map = {str(a.code): a for a in session.query(Asset).all()}
            for file_path in tqdm(price_files, desc="Processing price files"):
                filename = os.path.basename(file_path)
                symbol = filename.replace("_future_price.csv", "").replace("_price.csv", "").upper()
                if symbol not in assets_map: continue
                
                asset = assets_map[symbol]
                df = pd.read_csv(file_path)
                
                # Bulk fetch existing dates for this asset to avoid N queries
                existing_dates = {
                    r[0] for r in session.query(Price.time).filter(Price.asset_id == asset.id).all()
                }
                
                new_prices = []
                for _, row in df.iterrows():
                    dt = self.parse_date(row['time'])
                    if not dt: continue
                    p_date = dt.date()
                    if p_date in existing_dates: continue
                    
                    new_prices.append({
                        "asset_id": asset.id, # Changed from commodity_id to asset_id
                        "time": p_date,
                        "close": row['close'],
                        "volume": row.get('Volume')
                    })
                    existing_dates.add(p_date)
                
                if new_prices:
                    session.bulk_insert_mappings(Price.__mapper__, new_prices)
                    session.commit()
                    
                ingested_symbols.append(symbol)
        return ingested_symbols

    def ingest_articles(self, articles_dir):
        article_files = glob.glob(os.path.join(articles_dir, "*.csv"))
        article_id_map = {} # id -> id (for consistency with events)
        new_total = 0
        
        # Determine asset map for column 'commodity_id' in article table
        with Session(self.engine) as session:
            assets_map = {str(a.code): a.id for a in session.query(Asset).all()}
            # Pre-fetch existing IDs to avoid DB checks per row
            existing_ids = {r[0] for r in session.query(Article.id).all()}

            file_pbar = tqdm(article_files, desc="Processing article files")
            for file_path in file_pbar:
                try:
                    fname = os.path.basename(file_path).upper()
                    target_asset_id = None
                    # Map based on code or part of the name
                    for code, aid in assets_map.items():
                        if code in fname:
                            target_asset_id = aid
                            break
                    
                    if not target_asset_id:
                        # Fallback to name match if code doesn't work (e.g. Copper vs HG)
                        pass 

                    reader = pd.read_csv(file_path, chunksize=2000)
                    for chunk in tqdm(reader, desc=f"Ingesting {os.path.basename(file_path)}", leave=False):
                        new_articles = []
                        for _, row in chunk.iterrows():
                            if 'id' not in row: continue
                            art_id = str(row['id'])
                            if art_id in existing_ids:
                                article_id_map[art_id] = art_id
                                continue
                            
                            pub_date_str = str(row.get('publish_date')) 
                            
                            article_data = {
                                "id": art_id,
                                "publish_date": pub_date_str,
                                "title": str(row.get('title', 'Unknown')),
                                "description": str(row.get('description', '')),
                                "doc_url": str(row.get('doc_url', '')),
                                "meta_site_name": str(row.get('meta_site_name', '')),
                                "authors": str(row.get('authors', '')),
                                "key_word": str(row.get('key_word', '')),
                                "asset_id": target_asset_id # Maps to 'commodity_id' column
                            }
                            new_articles.append(article_data)
                            existing_ids.add(art_id)
                            article_id_map[art_id] = art_id
                            new_total += 1
                        
                        if new_articles:
                            session.bulk_insert_mappings(Article.__mapper__, new_articles)
                            session.commit()
                except Exception as e:
                    print(f"  Error processing {file_path}: {e}")
        return article_id_map, new_total

    def ingest_events(self, events_dir, article_id_map):
        event_files = glob.glob(os.path.join(events_dir, "*.jsonl"))
        new_count_total = 0
        
        with Session(self.engine) as session:
            assets = session.query(Asset).all()
            assets_map = {a.code.lower(): a for a in assets}
            
            # Pre-fetch existing event keys
            existing_events = {
                (r[0], r[1]) for r in session.query(Event.title, Event.date).all()
            }

            for file_path in tqdm(event_files, desc="Processing event files"):
                filename_base = os.path.basename(file_path).lower()
                
                # Robust asset detection
                primary_asset = None
                for code, asset in assets_map.items():
                    if code in filename_base:
                        primary_asset = asset
                        break
                
                # Fallback: check parts of the code
                if not primary_asset:
                    for code, asset in assets_map.items():
                        if code.split('_')[0] in filename_base:
                            primary_asset = asset
                            break

                new_events = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        data = json.loads(line)
                        title = data.get('title', '')
                        dt = self.parse_date(data.get('start_date'))
                        if not dt: continue
                        ev_date = dt.date()
                        
                        event_key = (title, ev_date)
                        if event_key in existing_events: continue
                        
                        orig_article_ids = data.get('source', [])
                        # Ensure string conversion for mapping
                        mapped_article_ids = [article_id_map[str(sid)] for sid in orig_article_ids if str(sid) in article_id_map]
                        
                        event_data = {
                            "original_source_id": str(data.get('event_id')) if data.get('event_id') else str(uuid.uuid4())[:16],
                            "title": title,
                            "description": data.get('description', ''),
                            "date": ev_date, # Maps to 'start_date' column
                            "source_article_ids": ",".join(mapped_article_ids), # Maps to 'source' column
                            "asset_id": primary_asset.id if primary_asset else None # Maps to 'commodity_id' column
                        }
                        new_events.append(event_data)
                        existing_events.add(event_key)
                        new_count_total += 1
                
                if new_events:
                    session.bulk_insert_mappings(Event.__mapper__, new_events)
                    session.commit()
                    
        return new_count_total
