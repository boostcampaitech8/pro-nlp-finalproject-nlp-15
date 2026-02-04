import os
import json
import pandas as pd
import streamlit as st
from datetime import date

class NewsRepository:
    def __init__(self, event_dir: str, article_dir: str | None = None):
        self.event_dir = event_dir
        # Default: assume articles are in a sibling directory
        self.article_dir = article_dir or os.path.join(os.path.dirname(event_dir), "articles")

    def get_all_files(self) -> list[str]:
        """Returns list of available event files (json/jsonl)."""
        if not os.path.exists(self.event_dir): return []
        return [f for f in os.listdir(self.event_dir) if f.endswith((".json", ".jsonl"))]

    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def _load_articles(_article_dir: str, target_files: list[str] | None = None) -> dict[str, dict]:
        """
        Loads article CSVs and returns a lookup dictionary: {article_id: article_dict}.
        If target_files is provided, only load matching article CSVs (based on filename stem).
        Note: Static method for better caching.
        """
        article_map = {}
        if not os.path.exists(_article_dir):
            return article_map
        
        # Determine which article files to load
        if target_files:
            # Match event file stems to article file stems (e.g., copper_silver.jsonl -> copper_silver.csv)
            stems = [os.path.splitext(f)[0] for f in target_files]
            article_files = [f"{stem}.csv" for stem in stems if os.path.exists(os.path.join(_article_dir, f"{stem}.csv"))]
        else:
            article_files = [f for f in os.listdir(_article_dir) if f.endswith(".csv")]
        
        for filename in article_files:
            filepath = os.path.join(_article_dir, filename)
            try:
                df = pd.read_csv(filepath)
                if 'id' not in df.columns:
                    continue
                for _, row in df.iterrows():
                    article_id = row['id']
                    article_map[article_id] = {
                        'title': row.get('title', 'No Title'),
                        'description': row.get('description', ''),
                        'url': row.get('doc_url', ''),
                        'publish_date': row.get('publish_date', ''),
                        'source': row.get('meta_site_name', '')
                    }
            except Exception as e:
                print(f"Error loading article file {filename}: {e}")
        
        return article_map


    @st.cache_data(ttl=3600, show_spinner="Loading events...")
    def get_events(_self, start_date: date, end_date: date, keywords: list[str] | None = None, target_files: list[str] | None = None) -> list[dict]:
        """
        Loads event data from JSON files and filters by date and optional keywords.
        Enriches events with article metadata via source IDs.
        
        NOTE: _self prefix to avoid hashing issues with st.cache_data
        """
        events = []
        if not os.path.exists(_self.event_dir):
            return events

        # Load articles first (now a static cached method)
        article_map = NewsRepository._load_articles(_self.article_dir, target_files)

        if target_files is not None:
            files_to_read = [f for f in target_files if os.path.exists(os.path.join(_self.event_dir, f))]
        else:
            files_to_read = [f for f in os.listdir(_self.event_dir) if f.endswith((".json", ".jsonl"))]
        
        for filename in files_to_read:
            if filename.endswith(".json") or filename.endswith(".jsonl"):
                filepath = os.path.join(_self.event_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        # Handle JSONL (Line-delimited JSON)
                        if filename.endswith(".jsonl"):
                            data = []
                            for line in f:
                                try:
                                    if line.strip(): data.append(json.loads(line))
                                except json.JSONDecodeError: continue
                        else:
                            # Handle standard JSON
                            data = json.load(f)

                        items = data if isinstance(data, list) else data.get('events', [])
                        
                        for item in items:
                            # Normalize date
                            evt_date_str = item.get('start_date') or item.get('date') or item.get('publish_date')
                            if not evt_date_str: continue
                            
                            try:
                                # First 10 chars usually contain YYYY-MM-DD
                                evt_date = date.fromisoformat(evt_date_str[:10])
                            except ValueError:
                                continue 

                            if start_date <= evt_date <= end_date:
                                # Keyword filtering
                                if keywords:
                                    text = (item.get('title', '') + item.get('description', '')).lower()
                                    if any(k.lower() in text for k in keywords):
                                        pass  # Continue to enrichment
                                    else:
                                        continue
                                
                                # Enrich with articles
                                source_ids = item.get('source', [])
                                if isinstance(source_ids, list):
                                    item['articles'] = [article_map[sid] for sid in source_ids if sid in article_map]
                                else:
                                    item['articles'] = []
                                
                                events.append(item)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
        
        # Sort by date
        events.sort(key=lambda x: x.get('start_date', ''))
        return events
