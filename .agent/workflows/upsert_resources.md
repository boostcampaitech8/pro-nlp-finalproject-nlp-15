---
description: Chunk and upsert resources to Qdrant vector DB
---

# Resource Upserting Workflow

This workflow chunks PDF documents and uploads them to Qdrant for RAG.

## Prerequisites

- PDF files in `data/resources/`
- Resource registered in `data/resources/manifest.json`
- RAG config in `config/rag.yaml`

## Step 1: Install Dependencies

```bash
uv add pymupdf qdrant-client
```

## Step 2: Chunk PDF (Preview)

```bash
# Chunk specific resource
uv run python workflow/chunk_financial_documents.py --resource-id commodity_markets_2022

# Or chunk all RAG-enabled resources
uv run python workflow/chunk_financial_documents.py --all
```

**Output**:
- `data/chunks/{resource_id}_chunks.json` - Full chunk data
- `data/chunks/{resource_id}_preview.md` - Human-readable preview

## Step 3: Review Chunks

```bash
# View preview
cat data/chunks/commodity_markets_2022_preview.md

# Or open in editor
code data/chunks/commodity_markets_2022_preview.md
```

**Check for**:
- ✅ Chunks are coherent (not cutting mid-sentence)
- ✅ Chunk size is appropriate
- ✅ Metadata is correct (page numbers, authors, etc.)

## Step 4: Adjust Config (If Needed)

If chunks look wrong, adjust `config/rag.yaml`:

```yaml
overrides:
  textbook:
    chunk_size: 2000  # Increase if chunks too small
```

Then re-run Step 2.

## Step 5: Upsert to Qdrant (TODO)

```bash
# After confirming chunks are good
uv run python workflow/upsert_to_qdrant.py --resource-id commodity_markets_2022
```

This will:
1. Load chunks from `data/chunks/{resource_id}_chunks.json`
2. Generate embeddings (dense + sparse)
3. Upload to Qdrant
4. Update manifest with processing status

## Troubleshooting

**PDF parsing failed**:
- Check PDF is not encrypted
- Ensure PyMuPDF installed: `uv add pymupdf`

**Chunks too large/small**:
- Adjust `chunk_size` in `config/rag.yaml`
- Re-run chunking

**Qdrant connection failed**:
- Check `config/rag.yaml` has correct URL
- Verify Qdrant is running at the URL
