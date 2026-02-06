import pandas as pd
import json
import glob
import os
from collections import Counter

class DuplicateChecker:
    """Pure logic for checking duplicate IDs in raw data files."""
    
    def check_articles(self, article_dir):
        all_ids = []
        files = glob.glob(os.path.join(article_dir, "*.csv"))
        for f in files:
            try:
                df = pd.read_csv(f)
                if 'id' in df.columns:
                    all_ids.extend(df['id'].astype(str).tolist())
            except:
                continue
        
        counts = Counter(all_ids)
        duplicates = {id: count for id, count in counts.items() if count > 1}
        return {
            "total_scanned": len(all_ids),
            "unique_count": len(counts),
            "duplicate_count": len(duplicates),
            "top_duplicates": sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    def check_events(self, event_dir):
        all_ids = []
        files = glob.glob(os.path.join(event_dir, "*.jsonl"))
        for f in files:
            with open(f, 'r', encoding='utf-8') as file:
                for line in file:
                    try:
                        data = json.loads(line)
                        if 'event_id' in data:
                            all_ids.append(str(data['event_id']))
                    except:
                        continue
        
        counts = Counter(all_ids)
        duplicates = {id: count for id, count in counts.items() if count > 1}
        return {
            "total_scanned": len(all_ids),
            "unique_count": len(counts),
            "duplicate_count": len(duplicates),
            "top_duplicates": sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]
        }
