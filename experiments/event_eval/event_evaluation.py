from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CFG_PATH = Path(__file__).with_name("event_evaluate.yaml")
with open(CFG_PATH, "r", encoding="utf-8") as f:
    _RAW_CFG = yaml.safe_load(f) or {}

DEFAULT_EMBEDDING_MODEL = _RAW_CFG.get("embedding_model", "all-MiniLM-L6-v2")
DEFAULT_TOPK_WORDS = int(_RAW_CFG.get("topk_words", 15))
DEFAULT_MERGING_THRESHOLD = _RAW_CFG.get("merging_threshold", 0.4)
DEFAULT_MERGING_PERCENTILE = _RAW_CFG.get("merging_percentile", None)
DEFAULT_FRAG_SIM_THRESHOLD = _RAW_CFG.get("fragmentation_similarity_threshold", 0.85)
DEFAULT_DATASET = _RAW_CFG.get("dataset")
DEFAULT_OUTPUT_PATH = _RAW_CFG.get("output_path")
DEFAULT_INCLUDE_OVERALL_ROW = bool(_RAW_CFG.get("include_overall_row", True))

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


def run_evaluation(
    events_path: Path,
    articles_path: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    topk_words: int = DEFAULT_TOPK_WORDS,
    merging_threshold: float | None = DEFAULT_MERGING_THRESHOLD,
    merging_percentile: float | None = DEFAULT_MERGING_PERCENTILE,
    fragmentation_similarity_threshold: float = DEFAULT_FRAG_SIM_THRESHOLD,
) -> dict:

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
    include_overall: bool = True,
) -> None:
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
    pairs = []
    for jpath in events_dir.glob("*.jsonl"):
        name = jpath.stem
        cpath = articles_dir / f"{name}.csv"
        if cpath.exists():
            pairs.append((jpath, cpath))
    return sorted(pairs)


def main() -> None:
    root = PROJECT_ROOT
    events_dir = root / "data" / "events"
    articles_dir = root / "data" / "articles"

    dataset = DEFAULT_DATASET
    output_conf = DEFAULT_OUTPUT_PATH
    include_overall_row = DEFAULT_INCLUDE_OVERALL_ROW

    if dataset:
        jpath = events_dir / f"{dataset}.jsonl"
        cpath = articles_dir / f"{dataset}.csv"
        if not jpath.exists() or not cpath.exists():
            print(f"Missing: {jpath} or {cpath}")
            return
        pairs = [(jpath, cpath)]
    else:
        pairs = discover_pairs(events_dir, articles_dir)
        if not pairs:
            print("No matching event JSONL and article CSV pairs found.")
            return

    output_path = None
    if output_conf is not None:
        output_path = Path(output_conf)
    if output_path is not None:
        output_path = output_path if output_path.is_absolute() else root / output_path

    for jpath, cpath in pairs:
        name = jpath.stem
        results = run_evaluation(
            jpath,
            cpath,
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
                include_overall=include_overall_row,
            )


if __name__ == "__main__":
    main()
