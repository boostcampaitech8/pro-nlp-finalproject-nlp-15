import os
import json
from typing import List, Dict, Optional
from datetime import date

class NewsRepository:
    def __init__(self, event_dir: str):
        self.event_dir = event_dir

    def get_all_files(self) -> List[str]:
        """Returns list of available event files (json/jsonl)."""
        if not os.path.exists(self.event_dir): return []
        return [f for f in os.listdir(self.event_dir) if f.endswith((".json", ".jsonl"))]

    def get_events(self, start_date: date, end_date: date, keywords: Optional[List[str]] = None, target_files: Optional[List[str]] = None) -> List[Dict]:
        """
        Loads event data from JSON files and filters by date and optional keywords.
        """
        events = []
        if not os.path.exists(self.event_dir):
            return events

        # Assuming event files are named like 'events.json' or structured by asset
        # For prototype, we iterate all json files or specific ones if logic exists
        # Here simplified: verify path exists and iterate
        
        if target_files is not None:
            # If user explicitly provided a list (even empty), respect it
            files_to_read = [f for f in target_files if os.path.exists(os.path.join(self.event_dir, f))]
        else:
            files_to_read = [f for f in os.listdir(self.event_dir) if f.endswith((".json", ".jsonl"))]
        
        for filename in files_to_read:
            if filename.endswith(".json") or filename.endswith(".jsonl"):
                filepath = os.path.join(self.event_dir, filename)
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
                                        events.append(item)
                                else:
                                    events.append(item)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
        
        # Sort by date
        events.sort(key=lambda x: x.get('start_date', ''))
        return events
