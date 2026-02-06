---
description: Chunk and upsert resources to Qdrant vector DB
---

# Resource Upserting Workflow

This workflow chunks documents and uploads them to Qdrant for RAG.

## Prerequisites

- Resource registered in `data/resources/manifest.json`
- RAG config in `config/infra/rag.yaml`
- Qdrant environment variables configured

## Step 1: Chunking (Review Mode)

Before uploading, chunks are generated and saved locally for review.

```bash
# Chunk specific resource
uv run python workflow/run_kb_chunking.py resource_id=commodity_markets_2022
```

**Output**:
- `data/chunks/{resource_id}_chunks.json` - Full chunk data for indexing
- `data/chunks/{resource_id}_preview.md` - Human-readable preview for quality check

## Step 2: Review Chunks

Check the generated preview file to ensure chunk quality.

```bash
# View preview
cat data/chunks/commodity_markets_2022_preview.md
```

**Check for**:
- ✅ Chunks are coherent
- ✅ Overlap is sufficient for context
- ✅ Metadata extraction is accurate

## Step 3: Vector Indexing (Upsert)

Once chunks are verified, upload them to the Vector DB.

```bash
# After confirming chunks are good
uv run python workflow/run_kb_indexing.py resource_id=commodity_markets_2022
```

**Key Features**:
- **Auto-Collection**: The script will automatically create the Qdrant collection if it doesn't exist.
- **Hybrid Embeddings**: Generates both Dense (Rune) and Sparse (Splade) vectors.
- **Manifest Tracking**: Automatically updates the `manifest.json` with processing status and vector counts.

## Step 4: Verification

Verify the integrity of the database and indexes.

```bash
uv run python workflow/util_verify_integrity.py
```

## Troubleshooting

**Chunks not found**:
- Ensure you ran `run_kb_chunking.py` first.
- Check that `resource_id` matches the manifest.

**Qdrant Collection Error**:
- The latest `VectorStore` handles creation automatically, but ensure the Qdrant URL in `rag.yaml` is accessible.
