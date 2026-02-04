"""
Workflow: Upload chunked documents to Qdrant.

Usage:
    python workflow/upsert_to_qdrant.py --resource-id commodity_markets_2022 [--create-collection]
"""

import argparse
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.vector_store import VectorStore
from db.resource_manager import ResourceManager
from preprocess.embed_and_upsert import DocumentUploader


def main():
    parser = argparse.ArgumentParser(description="Upload chunks to Qdrant")
    parser.add_argument("--resource-id", required=True, help="Resource ID to upload")
    parser.add_argument("--create-collection", action="store_true", help="Create collection if not exists")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection (DELETES DATA)")
    parser.add_argument("--batch-size", type=int, default=100, help="Upload batch size")
    
    args = parser.parse_args()
    
    # Load config
    config_path = PROJECT_ROOT / "config" / "rag.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    print(f"🚀 Initializing Qdrant uploader...")
    print(f"  Vector DB: {config['vector_db']['url']}")
    print(f"  Collection: {config['vector_db']['collection']}")
    print(f"  Dense Model: {config['embedding']['dense_model']}")
    print(f"  Sparse Model: {config['embedding']['sparse_model']}")
    
    vector_store = VectorStore(
        qdrant_url=config["vector_db"]["url"],
        collection_name=config["vector_db"]["collection"],
        dense_model_name=config["embedding"]["dense_model"],
        sparse_model_name=config["embedding"]["sparse_model"]
    )
    
    resource_manager = ResourceManager()
    uploader = DocumentUploader(vector_store, resource_manager)
    
    # Create collection if requested
    if args.create_collection or args.force_recreate:
        print(f"\n🏗️  Creating collection...")
        vector_store.create_collection(force_recreate=args.force_recreate)
    
    # Find chunks file
    chunks_path = PROJECT_ROOT / "data" / "chunks" / f"{args.resource_id}_chunks.json"
    if not chunks_path.exists():
        print(f"❌ Chunks file not found: {chunks_path}")
        print(f"   Run chunking first: python workflow/chunk_financial_documents.py --resource-id {args.resource_id}")
        sys.exit(1)
    
    # Upload
    print(f"\n📤 Uploading resource: {args.resource_id}")
    result = uploader.upload_chunks(
        resource_id=args.resource_id,
        chunks_path=chunks_path,
        batch_size=args.batch_size
    )
    
    print(f"\n✅ Done!")
    print(f"  Resource: {result['resource_id']}")
    print(f"  Chunks: {result['chunks_count']}")
    print(f"  Uploaded: {result['vectors_uploaded']} vectors")
    print(f"  Collection: {result['collection']}")


if __name__ == "__main__":
    main()
