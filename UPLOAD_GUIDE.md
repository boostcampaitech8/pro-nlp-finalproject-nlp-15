# Qdrant Upload Guide (Remote Server)

## Quick Start

```bash
# 1. Pull latest code
git pull

# 2. Install dependencies
uv sync

# 3. Download models (one-time)
uv run python workflow/download_models.py

# 4. Create collection and upload
uv run python workflow/upsert_to_qdrant.py \
  --resource-id commodity_markets_2022 \
  --create-collection
```

## What Was Implemented

### Files Created/Modified
- `db/vector_store.py` - Added collection management & batch upsert
- `preprocess/embed_and_upsert.py` - Embedding generation & upload logic
- `workflow/upsert_to_qdrant.py` - CLI upload script
- `workflow/download_models.py` - Pre-download models with progress
- `db/resource_manager.py` - Simplified manifest structure

### Manifest Structure (Simplified)
```json
{
  "id": "commodity_markets_2022",
  "title": "Commodity Markets...",
  "type": "textbook",
  "authors": ["John Baffes", "Peter Nagle"],
  "publisher": "World Bank",
  "publication_date": "2022-05-12",
  "file": {
    "path": "Commodity Markets: Evolution, Challenges and Policies.pdf",
    "format": "pdf"
  },
  "content_pages": {
    "start": 19,
    "end": 289
  },
  "preprocessing": {
    "status": "pending",
    "chunks_created": null,
    "vectors_uploaded": null
  }
}
```

## Expected Timeline (Remote Server)

- Model download: 2-5 minutes (one-time)
- Embedding generation: 3-5 minutes (541 chunks)
- Upload to Qdrant: 1-2 minutes

**Total**: ~10 minutes first time, then instant for subsequent resources

## After Upload

Check manifest updates:
```bash
cat data/resources/manifest.json
# Should show:
# "status": "completed"
# "chunks_created": 541
# "vectors_uploaded": 541
```

Test search:
```python
from db.vector_store import VectorStore
vs = VectorStore()
results = vs.search_similar_events("oil price volatility", top_k=5)
```
