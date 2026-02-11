from __future__ import annotations

import json
import re
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd


def load_articles(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for col in ("id", "title", "description"):
        if col not in df.columns:
            raise ValueError(f"CSV must have column '{col}': {csv_path}")
    df["id"] = df["id"].astype(str)
    df["text"] = df["title"].fillna("") + " " + df["description"].fillna("")
    return df


def load_events(jsonl_path: Path) -> list[dict]:
    events = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def align_events_articles(
    events: list[dict],
    articles: pd.DataFrame,
) -> tuple[list[dict], list[list[int]]]:

    id_to_idx = {aid: i for i, aid in enumerate(articles["id"].tolist())}
    events_used = []
    indices_per_event = []

    for ev in events:
        source = ev.get("source") or []
        if isinstance(source, str):
            source = [source]
        ids = list({str(s) for s in source})
        idxs = [id_to_idx[aid] for aid in ids if aid in id_to_idx]
        if not idxs:
            continue
        events_used.append(ev)
        indices_per_event.append(idxs)

    return events_used, indices_per_event


def get_article_embeddings(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    return np.array(model.encode(texts, show_progress_bar=len(texts) > 50))


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]{2,}", text)
    return tokens


def get_top_words_per_event(
    events_doc_indices: list[list[int]],
    doc_tokens: list[list[str]],
    topk: int = 15,
    min_df: int = 1,
) -> list[list[str]]:

    top_words_per_event = []
    for indices in events_doc_indices:
        all_tokens: list[str] = []
        for i in indices:
            all_tokens.extend(doc_tokens[i])
        if not all_tokens:
            top_words_per_event.append([])
            continue
        cnt = Counter(all_tokens)
        doc_sets = [set(doc_tokens[i]) for i in indices]
        if min_df > 1:
            doc_freq = {}
            for w in cnt:
                doc_freq[w] = sum(1 for s in doc_sets if w in s)
            words = [w for w, c in cnt.most_common(topk * 2) if doc_freq.get(w, 0) >= min_df][:topk]
        else:
            words = [w for w, _ in cnt.most_common(topk)]
        top_words_per_event.append(words)
    return top_words_per_event
