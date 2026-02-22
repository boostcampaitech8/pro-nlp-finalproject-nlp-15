"""
Pipeline: Knowledge Base Vector Indexing (Chunks to Qdrant)

This script embeds pre-processed text chunks and uploads them to the Vector DB.
It should be run after reviewing the output from run_kb_chunking.py.

Usage:
    uv run python workflow/run_kb_indexing.py --resource-id [ID] [--create-collection]
"""

import hydra
import sys
from omegaconf import DictConfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vector_db.vector_store import VectorStore
from vector_db.resource_manager import ResourceManager
from preprocess.embed_and_upsert import DocumentUploader


@hydra.main(version_base=None, config_path="../config", config_name="kb_indexing")
def main(cfg: DictConfig):
    # Determine resource_id from overrides or arguments
    # Note: Hydra uses dot notation or key=value for overrides
    # e.g. python run_kb_indexing.py resource_id=my_id
    resource_id = cfg.get("resource_id")
    create_collection = cfg.get("create_collection", False)
    force_recreate = cfg.get("force_recreate", False)
    batch_size = cfg.get("batch_size", 100)
    
    if not resource_id:
        print("❌ Error: resource_id must be provided (e.g., resource_id=some_id)")
        return

    # Initialize components
    print(f"🚀 Initializing Qdrant uploader...")
    print(f"  Vector DB: {cfg.rag.vector_db.url}")
    print(f"  Collection: {cfg.rag.vector_db.knowledge_base_collection}")
    print(f"  Dense Model: {cfg.rag.embedding.dense_model}")
    print(f"  Sparse Model: {cfg.rag.embedding.sparse_model}")
    
    vector_store = VectorStore(
        qdrant_url=cfg.rag.vector_db.url,
        dense_model_name=cfg.rag.embedding.dense_model,
        sparse_model_name=cfg.rag.embedding.sparse_model
    )
    
    manifest_path = PROJECT_ROOT / cfg.data.manifest_path
    resource_manager = ResourceManager(manifest_path=manifest_path, rag_config=cfg.rag)
    uploader = DocumentUploader(
        vector_store,
        resource_manager
    )
    
    collection_name = cfg.rag.vector_db.knowledge_base_collection
    
    # Ensure indexes (if collection exists)
    if vector_store.collection_exists(collection_name):
        vector_store.create_payload_index(collection_name, "publication_date")

    # Find chunks file
    chunks_dir = PROJECT_ROOT / cfg.data.chunks_dir
    chunks_path = chunks_dir / f"{resource_id}_chunks.json"
    if not chunks_path.exists():
        print(f"❌ Chunks file not found: {chunks_path}")
        print(f"   You must run chunking first: uv run python workflow/run_kb_chunking.py resource_id={resource_id}")
        return
    
    # Upload
    print(f"\n📤 Uploading resource: {resource_id}")
    print(f"  🧠 Generating and uploading points... (this may take a while)")
    
    result = uploader.upload_chunks(
        resource_id=resource_id,
        chunks_path=chunks_path,
        collection_name=collection_name,
        batch_size=batch_size,
        force_recreate=force_recreate
    )
    
    # Ensure indexes after upload
    vector_store.create_payload_index(collection_name, "publication_date")
    
    print(f"\n✅ Uploaded {result['chunks_count']} chunks to Qdrant.")
    print(f"  Resource: {result['resource_id']}")
    print(f"  Chunks: {result['chunks_count']}")
    print(f"  Uploaded: {result['vectors_uploaded']} vectors")
    print(f"  Collection: {result['collection']}")
    print(f"\n✅ Done!")


if __name__ == "__main__":
    main()
