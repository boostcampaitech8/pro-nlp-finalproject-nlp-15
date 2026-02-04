"""
Event extraction evaluation: orchestration, report, CLI.

Metrics are implemented in metrics.py; data/embedding helpers in utils.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .utils import (
        load_articles,
        load_events,
        align_events_articles,
        tokenize,
        get_article_embeddings,
        get_top_words_per_event,
    )
    from .metrics import (
        coherence_cv,
        intra_event_similarity,
        inter_event_similarity,
        fragmentation_rate_per_event,
        fragmentation_by_similarity_per_event,
        merging_error_per_event,
    )
except ImportError:
    from utils import (
        load_articles,
        load_events,
        align_events_articles,
        tokenize,
        get_article_embeddings,
        get_top_words_per_event,
    )
    from metrics import (
        coherence_cv,
        intra_event_similarity,
        inter_event_similarity,
        fragmentation_rate_per_event,
        fragmentation_by_similarity_per_event,
        merging_error_per_event,
    )


def run_evaluation(
    events_path: Path,
    articles_path: Path,
    embedding_model: str = "all-MiniLM-L6-v2",
    topk_words: int = 15,
    merging_threshold: float | None = 0.4,
    merging_percentile: float | None = None,
    fragmentation_similarity_threshold: float = 0.85,
) -> dict:
    """
    Load events and articles, compute all metrics.
    Returns dict with per-event Series and overall values.
    """
    articles = load_articles(articles_path)
    events = load_events(events_path)
    events, events_doc_indices = align_events_articles(events, articles)
    if not events:
        return {"error": "No events with at least one article in CSV"}

    texts = articles["text"].tolist()
    doc_tokens = [tokenize(t) for t in texts]

    embeddings = get_article_embeddings(texts, model_name=embedding_model)
    event_ids = [str(ev.get("event_id", i)) for i, ev in enumerate(events)]

    # 1. Coherence (C_V)
    top_words_per_event = get_top_words_per_event(events_doc_indices, doc_tokens, topk=topk_words)
    coherence_values = coherence_cv(top_words_per_event, model_name=embedding_model)

    # 2. Intra-event similarity
    intra = intra_event_similarity(events_doc_indices, embeddings)

    # 3. Inter-event similarity
    inter = inter_event_similarity(events_doc_indices, embeddings)

    # 4. Fragmentation
    frag = fragmentation_rate_per_event(events)
    frag_similarity = fragmentation_by_similarity_per_event(
        events_doc_indices, embeddings, threshold=fragmentation_similarity_threshold
    )

    # 5. Merging error
    merge = merging_error_per_event(intra, threshold=merging_threshold, percentile=merging_percentile)

    def safe_mean(vals: list[float], skip_nan: bool = True) -> float:
        a = np.array(vals, dtype=float)
        if skip_nan:
            a = a[np.isfinite(a)]
        return float(np.mean(a)) if len(a) > 0 else np.nan

    return {
        "event_id": event_ids,
        "coherence": coherence_values,
        "intra_event_similarity": intra,
        "inter_event_similarity": inter,
        "fragmentation": frag,
        "fragmentation_by_similarity": frag_similarity,
        "merging_error": merge,
        "overall": {
            "coherence": safe_mean(coherence_values),
            "intra_event_similarity": safe_mean(intra),
            "inter_event_similarity": safe_mean(inter),
            "fragmentation_rate": safe_mean(frag, skip_nan=False),
            "fragmentation_by_similarity_rate": safe_mean(frag_similarity, skip_nan=False),
            "merging_error_rate": safe_mean(merge, skip_nan=False),
        },
        "n_events": len(events),
    }


def results_to_dataframe(results: dict) -> pd.DataFrame | None:
    """Build per-event metrics DataFrame from run_evaluation results. Returns None if error."""
    if "error" in results:
        return None
    return pd.DataFrame({
        "event_id": results["event_id"],
        "coherence": results["coherence"],
        "intra_sim": results["intra_event_similarity"],
        "inter_sim": results["inter_event_similarity"],
        "fragmentation": results["fragmentation"],
        "fragmentation_by_similarity": results["fragmentation_by_similarity"],
        "merging_error": results["merging_error"],
    })


def save_metrics_csv(
    results: dict,
    output_path: Path,
    dataset_name: str = "",
    include_overall: bool = True,
) -> None:
    """Save per-event metrics to CSV. If include_overall, append a row with overall means."""
    df = results_to_dataframe(results)
    if df is None:
        return
    if include_overall:
        overall = results["overall"]
        overall_row = pd.DataFrame([{
            "event_id": "_overall",
            "coherence": overall["coherence"],
            "intra_sim": overall["intra_event_similarity"],
            "inter_sim": overall["inter_event_similarity"],
            "fragmentation": overall["fragmentation_rate"],
            "fragmentation_by_similarity": overall["fragmentation_by_similarity_rate"],
            "merging_error": overall["merging_error_rate"],
        }])
        df = pd.concat([df, overall_row], ignore_index=True)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Saved: {output_path}")


def print_report(results: dict, dataset_name: str = "") -> None:
    """Print per-event table and overall summary."""
    if "error" in results:
        print(f"[{dataset_name}] Error: {results['error']}")
        return

    overall = results["overall"]
    print(f"\n{'='*60}")
    print(f"Dataset: {dataset_name} (n_events={results['n_events']})")
    print(f"{'='*60}")

    df = results_to_dataframe(results)
    if df is None:
        return
    pd.set_option("display.max_rows", 20)
    pd.set_option("display.width", 120)
    print("\nPer-event (first 20):")
    print(df.head(20).to_string(index=False))
    if len(df) > 20:
        print(f"... and {len(df) - 20} more events")

    print("\n--- Overall ---")
    print(f"  Coherence (C_V):     {overall['coherence']:.4f}")
    print(f"  Intra-event similarity:  {overall['intra_event_similarity']:.4f}")
    print(f"  Inter-event similarity:  {overall['inter_event_similarity']:.4f}")
    print(f"  Fragmentation rate (singleton): {overall['fragmentation_rate']:.4f}")
    print(f"  Fragmentation by similarity:    {overall['fragmentation_by_similarity_rate']:.4f}")
    print(f"  Merging error rate:      {overall['merging_error_rate']:.4f}")


def discover_pairs(events_dir: Path, articles_dir: Path) -> list[tuple[Path, Path]]:
    """Return list of (jsonl_path, csv_path) where base names match."""
    pairs = []
    for jpath in events_dir.glob("*.jsonl"):
        name = jpath.stem
        cpath = articles_dir / f"{name}.csv"
        if cpath.exists():
            pairs.append((jpath, cpath))
    return sorted(pairs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Event extraction evaluation")
    parser.add_argument("--events-dir", type=Path, default=Path("data/events"), help="Directory of event JSONL files")
    parser.add_argument("--articles-dir", type=Path, default=Path("data/article"), help="Directory of article CSV files")
    parser.add_argument("--dataset", type=str, default=None, help="Single dataset (stem); if set, only evaluate this one")
    parser.add_argument("--model", type=str, default="all-MiniLM-L6-v2", help="Sentence-transformer model")
    parser.add_argument("--topk", type=int, default=15, help="Top-k words per event for coherence")
    parser.add_argument("--merging-threshold", type=float, default=0.4, help="Intra similarity threshold for merging error")
    parser.add_argument("--merging-percentile", type=float, default=None, help="Use percentile instead of threshold (e.g. 25)")
    parser.add_argument("--fragmentation-similarity-threshold", type=float, default=0.85, help="Cosine threshold for fragmentation_by_similarity (event has sibling >= this)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Save per-event metrics to this CSV (or directory for multiple datasets)")
    parser.add_argument("--no-overall-row", action="store_true", help="Do not add _overall row to saved CSV")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    events_dir = root / args.events_dir if not args.events_dir.is_absolute() else args.events_dir
    articles_dir = root / args.articles_dir if not args.articles_dir.is_absolute() else args.articles_dir

    if args.dataset:
        jpath = events_dir / f"{args.dataset}.jsonl"
        cpath = articles_dir / f"{args.dataset}.csv"
        if not jpath.exists() or not cpath.exists():
            print(f"Missing: {jpath} or {cpath}")
            return
        pairs = [(jpath, cpath)]
    else:
        pairs = discover_pairs(events_dir, articles_dir)
        if not pairs:
            print("No matching event JSONL and article CSV pairs found.")
            return

    output_path = args.output
    if output_path is not None:
        output_path = output_path if output_path.is_absolute() else root / output_path

    for jpath, cpath in pairs:
        name = jpath.stem
        results = run_evaluation(
            jpath,
            cpath,
            embedding_model=args.model,
            topk_words=args.topk,
            merging_threshold=args.merging_threshold,
            merging_percentile=args.merging_percentile,
            fragmentation_similarity_threshold=args.fragmentation_similarity_threshold,
        )
        print_report(results, dataset_name=name)

        if output_path is not None and "error" not in results:
            if len(pairs) == 1 and output_path.suffix.lower() == ".csv":
                save_path = output_path
            else:
                out_dir = output_path if output_path.is_dir() else output_path.parent
                save_path = Path(out_dir) / f"{name}_event_metrics.csv"
            save_metrics_csv(
                results,
                save_path,
                dataset_name=name,
                include_overall=not args.no_overall_row,
            )


if __name__ == "__main__":
    main()
