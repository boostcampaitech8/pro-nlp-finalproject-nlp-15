from __future__ import annotations

import json
import time
import pandas as pd
import datetime as dt
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Iterable

from extract.llm_client import WindowEventExtractor

logger = logging.getLogger(__name__)

@dataclass
class Stats:
    keyword_file: str
    output_jsonl: str
    processed_windows: int = 0
    extracted_events: int = 0
    errors: int = 0

class WindowEventExtractorEngine:
    def __init__(self, extractor: WindowEventExtractor):
        self.extractor = extractor

    def run_extraction(
        self, 
        csv_path: Path, 
        output_dir: Path, 
        args
    ) -> Stats:
        result_dir = output_dir / "result"
        state_dir = output_dir / ".state"

        for d in [result_dir, state_dir]:
            d.mkdir(parents=True, exist_ok=True)

        stem = csv_path.stem
        out_jsonl = result_dir / f"{stem}.jsonl"
        state_path = state_dir / f"{stem}.json"
        
        last_window = self._load_state(state_path) if getattr(args, 'resume', False) else None
        if last_window:
            logger.info(f"[{stem}] Resuming after: {last_window}")

        st = Stats(keyword_file=csv_path.name, output_jsonl=str(out_jsonl))
        window_to_items = self.build_window_to_items(csv_path, args)
        window_starts = sorted(window_to_items.keys())

        with out_jsonl.open("a", encoding="utf-8") as f_out:
            for w_key in window_starts:
                if last_window and w_key <= last_window:
                    continue

                items = window_to_items[w_key]
                if not items:
                    continue

                w_start_dt = dt.date.fromisoformat(w_key)
                w_end_dt = w_start_dt + dt.timedelta(days=getattr(args, 'window_size', 1) - 1)
                context_str = f"{w_key} ~ {w_end_dt.isoformat()}"

                start_time = time.time()

                try:
                    events = self.extractor.extract_window_events(
                        window_context=context_str, 
                        items=items,
                        output_dir=output_dir
                    )
                    
                    unique_events = {} 
                    for ev in events:
                        eid = ev["event_id"]
                        if eid in unique_events:
                            unique_events[eid]["source"] = sorted(list(set(unique_events[eid]["source"] + ev["source"])))
                        else:
                            unique_events[eid] = ev

                    for ev in sorted(unique_events.values(), key=lambda x: x["start_date"]):
                        ev["window_start"] = w_key
                        f_out.write(json.dumps(ev, ensure_ascii=False) + "\n")
                        st.extracted_events += 1
                    
                    self._save_state(state_path, w_key)
                    st.processed_windows += 1
                    
                    elapsed = time.time() - start_time
                    logger.info(f"[{stem}] {context_str} | Articles: {len(items)} | Events: {len(unique_events)} | {elapsed:.2f}s")
                    
                except Exception as e:
                    logger.error(f"[{stem}] {context_str} | Failed | {str(e)}")
                    st.errors += 1

        return st

    def build_window_to_items(self, csv_path: Path, args) -> Dict[str, List[Dict[str, str]]]:
        window_items = {}
        max_articles = getattr(args, 'max_articles_per_window', 50)
        window_size = getattr(args, 'window_size', 1)
        epoch = dt.date(1970, 1, 5)
        
        d_start = dt.date.fromisoformat(args.date_start) if getattr(args, 'date_start', None) else None
        d_end = dt.date.fromisoformat(args.date_end) if getattr(args, 'date_end', None) else None

        for ch in self._iter_chunks(csv_path, chunk_size=getattr(args, 'chunk_size', 50000)):
            dtv = pd.to_datetime(ch["publish_date"], errors="coerce")
            ch = ch.assign(date=dtv.dt.date)
            ch = ch[ch["date"].notna()]
            if d_start and d_end:
                ch = ch[(ch["date"] >= d_start) & (ch["date"] <= d_end)]
            
            for _, r in ch.iterrows():
                diff = (r["date"] - epoch).days
                w_key = (r["date"] - dt.timedelta(days=diff % window_size)).isoformat()
                bucket = window_items.setdefault(w_key, [])
                if len(bucket) < max_articles:
                    bucket.append({
                        "id": str(r["id"]), 
                        "title": str(r.get("title") or "").strip(), 
                        "description": str(r.get("description") or "").strip(), 
                        "publish_date": r["date"].isoformat() 
                    })
        return window_items

    def _iter_chunks(self, csv_path: Path, chunk_size: int) -> Iterable[pd.DataFrame]:
        usecols = ["id", "title", "description", "publish_date"]
        return pd.read_csv(csv_path, usecols=usecols, chunksize=chunk_size, low_memory=False)

    def _load_state(self, state_path: Path) -> Optional[str]:
        if state_path.exists():
            try:
                with state_path.open("r", encoding="utf-8") as f:
                    return json.load(f).get("last_processed_window")
            except Exception:
                pass
        return None

    def _save_state(self, state_path: Path, window_key: str):
        with state_path.open("w", encoding="utf-8") as f:
            json.dump({
                "last_processed_window": window_key,
                "updated_at": dt.datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)