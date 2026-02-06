import json
import uuid
from typing import Any, cast
from pathlib import Path
from qdrant_client.http import models
from tqdm import tqdm
from vector_db.vector_store import VectorStore
from vector_db.resource_manager import ResourceManager

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
        collection_name: str | None = None,
        force_recreate: bool = False
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
        # Resolve collection name
        target_collection: str
        if collection_name is not None:
            target_collection = collection_name
        else:
            vector_db_cfg = self.resource_manager.rag_config.get("vector_db", {})
            target = vector_db_cfg.get("knowledge_base_collection", "knowledge_base")
            target_collection = cast(str, target) if target is not None else "knowledge_base"
        # Load chunks
        with open(chunks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        chunks = data["chunks"]
        
        # Get resource metadata
        resource = self.resource_manager.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        payload_data = self.resource_manager.get_vector_payload(resource_id)
        if payload_data is None:
            vector_payload: dict[str, Any] = {}
        else:
            vector_payload = payload_data
        
        # Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        
        print(f"  🧠 Generating embeddings for {len(chunks)} chunks...")
        dense_embeddings = self.vector_store.embed_batch_dense(texts)
        sparse_embeddings = self.vector_store.embed_batch_sparse(texts)
        
        # Build Qdrant points
        points = []
        for i, chunk in enumerate(tqdm(chunks, desc="Building Points", unit="chunk", leave=False)):
            # Generate deterministic UUID from chunk_id string
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
        
        uploaded = self.vector_store.batch_upsert(
            points=points,
            collection_name=target_collection,
            batch_size=batch_size,
            force_recreate=force_recreate
        )
        
        # Update manifest status
        self.resource_manager.update_preprocessing_status(
            resource_id=resource_id,
            status="completed",
            chunks_created=len(chunks),
            vectors_uploaded=uploaded
        )
        
        return {
            "resource_id": resource_id,
            "chunks_count": len(chunks),
            "vectors_uploaded": uploaded,
            "collection": collection_name or "knowledge_base"
        }

class EventUploader:
    """Handles event fetching, embedding and upload to Qdrant."""
    
    def __init__(self, vector_store: VectorStore, engine):
        """
        Initialize uploader.
        
        Args:
            vector_store: VectorStore instance
            engine: SQLAlchemy engine
        """
        self.vector_store = vector_store
        self.engine = engine
    
    def upload_events(
        self,
        batch_size: int = 100,
        collection_name: str = "events",
        force_recreate: bool = False
    ) -> dict:
        """
        Fetch all events from SQLite and upload to Qdrant.
        
        Args:
            batch_size: Upload batch size
            collection_name: Target collection
            
        Returns:
            Upload result dict with stats
        """
        from sqlalchemy.orm import Session, selectinload
        from db.database import Event
        
        # 1. Get total count first
        with Session(self.engine) as session:
            total_events = session.query(Event).count()
        
        if total_events == 0:
            return {"events_count": 0, "vectors_uploaded": 0}
        
        # 2. Process in chunks for better memory management and progress visibility
        chunk_size = 5000
        total_uploaded = 0
        
        print(f"📦 Processing {total_events} events in chunks of {chunk_size}...")
        
        for start_idx in range(0, total_events, chunk_size):
            # Fetch events for current chunk with eager loading
            with Session(self.engine) as session:
                current_chunk = session.query(Event).options(
                    selectinload(Event.asset)
                ).offset(start_idx).limit(chunk_size).all()
            
            chunk_num = (start_idx // chunk_size) + 1
            total_chunks = (total_events + chunk_size - 1) // chunk_size
            
            print(f"\n🔹 Chunk {chunk_num}/{total_chunks} ({len(current_chunk)} events):")
            
            # Prepare texts for this chunk
            texts = [f"{e.title}\n{e.description or ''}" for e in current_chunk]
            
            # Generate embeddings
            dense_embeddings = self.vector_store.embed_batch_dense(texts)
            sparse_embeddings = self.vector_store.embed_batch_sparse(texts)
            
            # Build Qdrant points
            points = []
            for i, e in enumerate(tqdm(current_chunk, desc="Building Points", unit="event", leave=False)):
                eid = str(e.id)
                try:
                    point_id = str(uuid.UUID(eid))
                except ValueError:
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, eid))
                    
                point = models.PointStruct(
                    id=point_id,
                    vector={
                        "default": dense_embeddings[i],
                        "sparse-text": sparse_embeddings[i]
                    },
                    payload={
                        "event_id": e.id,
                        "title": e.title,
                        "description": e.description,
                        "start_date": e.date.isoformat(),
                        "assets": [e.asset.code] if e.asset else [],
                        "article_ids": e.source_article_ids.split(",") if e.source_article_ids else []
                    }
                )
                points.append(point)
            
            uploaded = self.vector_store.batch_upsert(
                points=points,
                collection_name=collection_name,
                batch_size=batch_size,
                force_recreate=force_recreate if start_idx == 0 else False # Only recreate on first batch
            )
            total_uploaded += uploaded
        
        return {
            "events_count": total_events,
            "vectors_uploaded": total_uploaded,
            "collection": collection_name
        }
