"""
Embed and upsert chunked documents to Qdrant.

This module handles:
- Loading chunks from JSON
- Generating hybrid embeddings (dense + sparse)
- Building Qdrant points with metadata
- Batch uploading to Qdrant
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.vector_store import VectorStore
from db.resource_manager import ResourceManager
from qdrant_client.http import models
from tqdm import tqdm


class DocumentUploader:
    """Handles document embedding and upload to Qdrant."""
    
    def __init__(self, vector_store: VectorStore, resource_manager: ResourceManager):
        """
        Initialize uploader.
        
        Args:
            vector_store: VectorStore instance
            resource_manager: ResourceManager instance
        """
        self.vector_store = vector_store
        self.resource_manager = resource_manager
    
    def upload_chunks(
        self,
        resource_id: str,
        chunks_path: Path,
        batch_size: int = 100,
        collection_name: str | None = None
    ) -> dict:
        """
        Upload chunks from JSON to Qdrant.
        
        Args:
            resource_id: Resource identifier
            chunks_path: Path to chunks JSON file
            batch_size: Upload batch size
            collection_name: Target collection (optional)
            
        Returns:
            Upload result dict with stats
        """
        # Load chunks
        print(f"📂 Loading chunks from {chunks_path.name}...")
        with open(chunks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        chunks = data["chunks"]
        print(f"  ✅ Loaded {len(chunks)} chunks")
        
        # Get resource metadata
        resource = self.resource_manager.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        vector_payload = self.resource_manager.get_vector_payload(resource_id)
        print(f"  📋 Resource: {vector_payload['title']}")
        print(f"  📅 Publication: {vector_payload['publication_date']}")
        
        # Generate embeddings
        print(f"\n🧠 Generating embeddings...")
        texts = [chunk["text"] for chunk in chunks]
        
        print(f"  🔸 Dense embeddings...")
        dense_embeddings = self.vector_store.embed_batch_dense(texts)
        
        print(f"  🔹 Sparse embeddings...")
        sparse_embeddings = self.vector_store.embed_batch_sparse(texts)
        
        print(f"  ✅ Generated {len(dense_embeddings)} dense + {len(sparse_embeddings)} sparse embeddings")
        
        # Build Qdrant points
        print(f"\n📦 Building Qdrant points...")
        points = []
        
        for i, chunk in enumerate(chunks):
            # Generate deterministic UUID from chunk_id string
            import uuid
            chunk_id_str = chunk.get("chunk_id", f"{resource_id}_chunk_{i}")
            point_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id_str)
            
            point = models.PointStruct(
                id=str(point_uuid),  # UUID as string
                vector={
                    "default": dense_embeddings[i],
                    "sparse-text": sparse_embeddings[i]
                },
                payload={
                    # Resource metadata
                    **vector_payload,
                    
                    # Chunk-specific
                    "chunk_id": chunk_id_str,  # Store original ID in payload
                    "chunk_index": i,
                    "chunk_text": chunk["text"],
                    "char_count": chunk["char_count"]
                }
            )
            points.append(point)
        
        print(f"  ✅ Built {len(points)} points")
        
        # Upload to Qdrant
        print(f"\n📤 Uploading to Qdrant...")
        uploaded = self.vector_store.batch_upsert(
            points=points,
            collection_name=collection_name,
            batch_size=batch_size
        )
        
        # Update manifest status
        self.resource_manager.update_preprocessing_status(
            resource_id=resource_id,
            status="completed",
            chunks_created=len(chunks),
            vectors_uploaded=uploaded
        )
        
        print(f"\n✅ Upload complete!")
        print(f"  📊 Chunks: {len(chunks)}")
        print(f"  📤 Uploaded: {uploaded} vectors")
        
        return {
            "resource_id": resource_id,
            "chunks_count": len(chunks),
            "vectors_uploaded": uploaded,
            "collection": collection_name or self.vector_store.collection_name
        }


if __name__ == "__main__":
    # Example usage
    from config import rag_config
    
    vector_store = VectorStore(
        qdrant_url=rag_config["vector_db"]["url"],
        collection_name=rag_config["vector_db"]["collection"]
    )
    
    resource_manager = ResourceManager()
    uploader = DocumentUploader(vector_store, resource_manager)
    
    # Ensure collection exists
    vector_store.create_collection()
    
    # Upload example
    chunks_path = PROJECT_ROOT / "data" / "chunks" / "commodity_markets_2022_chunks.json"
    result = uploader.upload_chunks(
        resource_id="commodity_markets_2022",
        chunks_path=chunks_path
    )
    
    print(f"\n📊 Result: {result}")
