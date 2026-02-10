"""
Event extraction metrics: coherence, intra/inter similarity, fragmentation, merging error.
"""

from __future__ import annotations

import numpy as np


# -----------------------------------------------------------------------------
# Helpers: normalized embeddings and centroids (shared by inter + frag_by_similarity)
# -----------------------------------------------------------------------------


def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """L2-normalize embeddings per row. Returns (n, dim)."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return embeddings / norms


def _compute_centroids(
    events_doc_indices: list[list[int]],
    emb: np.ndarray,
) -> np.ndarray:
    """Compute per-event centroid from normalized embeddings. Returns (n_events, dim)."""
    centroids = []
    for indices in events_doc_indices:
        c = emb[indices].mean(axis=0)
        c = c / (np.linalg.norm(c) + 1e-12)
        centroids.append(c)
    return np.array(centroids)


# -----------------------------------------------------------------------------
# Coherence: C_V
# -----------------------------------------------------------------------------


def coherence_cv(
    top_words_per_event: list[list[str]],
    model_name: str = "all-MiniLM-L6-v2",
) -> list[float]:
    """Per-event C_V = mean over top words of cos(v_w, centroid)."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    coherences = []
    for top_words in top_words_per_event:
        top_words = [w for w in top_words if w.strip()]
        if len(top_words) < 2:
            coherences.append(np.nan)
            continue
        vecs = np.array(model.encode(top_words, show_progress_bar=False))
        centroid = vecs.mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-12)
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)
        cosines = vecs @ centroid
        coherences.append(float(np.mean(cosines)))
    return coherences


# -----------------------------------------------------------------------------
# Intra-event similarity
# -----------------------------------------------------------------------------


def intra_event_similarity(
    events_doc_indices: list[list[int]],
    embeddings: np.ndarray,
) -> list[float]:
    """Per-event mean pairwise cosine similarity (singleton = 1.0)."""
    emb = _normalize_embeddings(embeddings)
    result = []
    for indices in events_doc_indices:
        if len(indices) == 1:
            result.append(1.0)
            continue
        sub = emb[indices]
        n = len(indices)
        sim = (sub @ sub.T).sum() - n
        sim /= max(n * (n - 1), 1)
        result.append(float(sim))
    return result


# -----------------------------------------------------------------------------
# Inter-event similarity
# -----------------------------------------------------------------------------


def inter_event_similarity(
    events_doc_indices: list[list[int]],
    embeddings: np.ndarray,
) -> list[float]:
    """Per-event mean cosine similarity to other events' centroids."""
    emb = _normalize_embeddings(embeddings)
    centroids = _compute_centroids(events_doc_indices, emb)
    n_events = len(centroids)
    if n_events <= 1:
        return [np.nan] * n_events
    result = []
    for i in range(n_events):
        others = [j for j in range(n_events) if j != i]
        sims = centroids[i] @ centroids[others].T
        result.append(float(np.mean(sims)))
    return result


# -----------------------------------------------------------------------------
# Fragmentation
# -----------------------------------------------------------------------------


def fragmentation_rate_per_event(events: list[dict]) -> list[float]:
    """Per-event: 1 if singleton (only 1 article), else 0."""
    return [1.0 if len(list({str(s) for s in (ev.get("source") or [])})) == 1 else 0.0 for ev in events]


def fragmentation_by_similarity_per_event(
    events_doc_indices: list[list[int]],
    embeddings: np.ndarray,
    threshold: float = 0.85,
) -> list[float]:
    """Per-event: 1 if has another event with centroid similarity >= threshold, else 0."""
    emb = _normalize_embeddings(embeddings)
    centroids = _compute_centroids(events_doc_indices, emb)
    n = len(centroids)
    if n <= 1:
        return [0.0] * n
    sim_matrix = centroids @ centroids.T
    np.fill_diagonal(sim_matrix, -1)
    max_sim_to_other = np.max(sim_matrix, axis=1)
    return [1.0 if float(m) >= threshold else 0.0 for m in max_sim_to_other]


# -----------------------------------------------------------------------------
# Merging error
# -----------------------------------------------------------------------------


def merging_error_per_event(
    intra_similarities: list[float],
    threshold: float | None = None,
    percentile: float | None = 25.0,
) -> list[float]:
    """Per-event: 1 if intra < threshold (or below percentile), else 0."""
    arr = np.array(intra_similarities)
    valid = np.isfinite(arr)
    if threshold is None and percentile is not None:
        if valid.sum() > 0:
            threshold = np.nanpercentile(arr[valid], percentile)
        else:
            threshold = 0.0
    if threshold is None:
        threshold = 0.4
    return [1.0 if s < threshold else 0.0 for s in intra_similarities]
