# Event Extraction Evaluation Metrics — Design

## Data Setup
- **Events**: `data/events/{name}.jsonl` — each line is an event with `event_id`, `source` (list of article ids), etc.
- **Articles**: `data/article/{name}.csv` — same `{name}`; columns include `id`, `title`, `description` (English).
- **Mapping**: Event `source` ids are matched to article `id`. `event_id` is treated as **cluster label**; each event = one cluster of articles.

## Text Used
- Article text = `title + " " + description` (English only).

## Embeddings
- Sentence-transformer model (e.g. `all-MiniLM-L6-v2`) to compute one embedding per article (and, for C_V, per word).

---

## 1. Event-level topic coherence (C_V or NPMI)

**Goal**: How coherent is the “topic” of each event (i.e. do the top terms of that event form one consistent theme?).

### 1.1 NPMI (Normalized Pointwise Mutual Information)
- **Corpus**: All articles in the current CSV (document-level).
- **Per event**:
  1. Take the set of documents (articles) in that event.
  2. Tokenize all corpus documents; get **top-k words** for this event (e.g. by TF or TF-IDF over event docs only).
  3. For each pair of top words \((w_i, w_j)\), compute NPMI over the **full corpus**:
     - \(P(w) = \frac{\#\text{docs containing } w}{N}\), \(P(w_i, w_j) = \frac{\#\text{docs containing both}}{N}\).
     - \(\mathrm{PMI}(w_i, w_j) = \log \frac{P(w_i, w_j)}{P(w_i)P(w_j)}\).
     - \(\mathrm{NPMI}(w_i, w_j) = \frac{\mathrm{PMI}(w_i, w_j)}{-\log P(w_i, w_j)}\) (range \([-1, 1]\)).
  4. **Event NPMI** = mean over all pairs of top-k words (or over a single-set segmentation).
- **Output**: Per-event coherence; overall = mean over events (skip events with &lt; 2 top words or no pairs).

### 1.2 C_V (embedding-based)
- **Per event**:
  1. Same top-k words from event documents (TF or TF-IDF within event).
  2. Embed each word with the sentence-transformer (each word as a one-word sentence).
  3. **C_V** = mean over top words of \(\cos(\mathbf{v}_w, \bar{\mathbf{v}})\), where \(\bar{\mathbf{v}}\) is the centroid of all top-word embeddings for this event.
- **Output**: Per-event C_V; overall = mean over events.

---

## 2. Intra-event similarity

**Goal**: How similar are articles **inside** the same event (cluster cohesion)?

- For each event: take embeddings of all its articles (deduplicated by article id).
- **Per event**: \(\mathrm{intra}(e) = \frac{1}{|\mathcal{P}|} \sum_{(i,j) \in \mathcal{P}} \cos(\mathbf{e}_i, \mathbf{e}_j)\), where \(\mathcal{P}\) is the set of unordered pairs of distinct articles in the event.
- **Singleton events** (only one article): define \(\mathrm{intra}(e) = 1.0\) (perfect cohesion).
- **Output**: Per-event intra similarity; overall = mean over events.

---

## 3. Inter-event similarity

**Goal**: How similar are **events** to each other (lower = better separation)?

- For each event: **centroid** = mean of its article embeddings.
- **Per event** \(e_i\): \(\mathrm{inter}(e_i) = \frac{1}{|\mathcal{E}|-1} \sum_{j \neq i} \cos(\bar{\mathbf{e}}_i, \bar{\mathbf{e}}_j)\) (mean similarity to other event centroids).
- **Single-event dataset**: define inter = NaN and skip in overall.
- **Output**: Per-event inter similarity; overall = mean over events (excluding NaN).

---

## 4. Fragmentation rate

**Goal**: Rate of events that are “fragments” (single-article events).

- **Per event**: \(\mathrm{frag}(e) = 1\) if \(|\mathrm{source}(e)| = 1\), else \(0\).
- **Overall**: \(\mathrm{fragmentation\_rate} = \frac{1}{|\mathcal{E}|} \sum_e \mathrm{frag}(e)\).
- **Output**: Per-event binary; overall = proportion of singleton events.

---

## 5. Merging error rate

**Goal**: Rate of events that look like they **merge** distinct topics (low internal cohesion).

- **Per event**: \(\mathrm{merge}(e) = 1\) if \(\mathrm{intra}(e) < \theta\), else \(0\). Use a fixed threshold \(\theta\) (e.g. 0.4) or percentile (e.g. bottom 25% of intra).
- **Singleton events**: \(\mathrm{intra}=1.0\) → never counted as merging error.
- **Overall**: \(\mathrm{merging\_error\_rate} = \frac{1}{|\mathcal{E}|} \sum_e \mathrm{merge}(e)\).
- **Output**: Per-event binary; overall = proportion of low-cohesion events.

---

## Output Format
- Each metric: **per-event** (list/Series keyed by event_id) and **overall** (single number).
- Print/save: event-level table and one-row overall summary.
