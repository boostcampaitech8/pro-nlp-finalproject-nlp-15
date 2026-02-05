import os
from typing import List, Dict, Optional
import torch
from sentence_transformers import SentenceTransformer
from datetime import datetime, date
from transformers import AutoModelForMaskedLM, AutoTokenizer
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv

load_dotenv()

class VectorStore:
    def __init__(
        self, 
        qdrant_url: str = "http://lori2mai11ya.asuscomm.com:6333",
        collection_name: str = "articles",
        dense_model_name: str = "telepix/PIXIE-Rune-Preview",
        sparse_model_name: str = "telepix/PIXIE-Splade-Preview"
    ):
        # Initialize Qdrant client with timeout
        try:
            self.client = QdrantClient(
                url=qdrant_url, 
                api_key=os.getenv("QDRANT_API_KEY"),
                timeout=10  # 10 second timeout
            )
            # Test connection
            self.client.get_collections()
            print(f"✅ Connected to Qdrant: {qdrant_url}")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            print(f"   URL: {qdrant_url}")
            print(f"   Tip: Check server status or use local Qdrant instance")
            self.client = None  # Mark as unavailable
        
        self.collection_name = collection_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize Dense Model
        self.dense_model = SentenceTransformer(dense_model_name, device=self.device)
        
        # Initialize Sparse Model
        if sparse_model_name:
            self.sparse_tokenizer = AutoTokenizer.from_pretrained(sparse_model_name)
            self.sparse_model = AutoModelForMaskedLM.from_pretrained(sparse_model_name, trust_remote_code=True).to(self.device)
            self.sparse_model.eval()
            
        # Ensure payload indexes for date filtering
        if self.client:  # Only if connected
            self._ensure_payload_indexes()

    def _ensure_payload_indexes(self):
        """Ensure that necessary payload indexes exist for date filtering."""
        try:
            # Articles collection
            if self.client.collection_exists("articles"):
                self.client.create_payload_index(
                    collection_name="articles",
                    field_name="publish_date",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
            # Events collection
            if self.client.collection_exists("events"):
                self.client.create_payload_index(
                    collection_name="events",
                    field_name="start_date",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
                self.client.create_payload_index(
                    collection_name="events",
                    field_name="end_date",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
        except Exception as e:
            # Silently skip if collections don't exist yet or API key issue
            # Indexes will be created when collections are created
            pass

    def _get_sparse_vector(self, text: str) -> models.SparseVector:
        """Generates a sparse vector for a single query text using SPLADE pooling."""
        inputs = self.sparse_tokenizer([text], return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            outputs = self.sparse_model(**inputs)
            logits = outputs.logits
            
            # SPLADE transformation
            weights = torch.log(1 + torch.relu(logits))
            # No need to mask for single text usually, but for consistency:
            weights = weights * inputs['attention_mask'].unsqueeze(-1)
            sparse_vec_pt, _ = torch.max(weights, dim=1)
            
            nonzero_indices = torch.nonzero(sparse_vec_pt[0]).flatten()
            return models.SparseVector(
                indices=nonzero_indices.tolist(),
                values=sparse_vec_pt[0][nonzero_indices].tolist()
            )

    def _parse_date(self, date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).date()
        except ValueError:
            try:
                # Try simple YYYY-MM-DD
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                return None

    def search_similar_articles(
        self, 
        query: str, 
        top_k: int = 5, 
        start_date: str | None = None, 
        end_date: str | None = None
    ) -> list[dict]:
        """
        Performs a hybrid search for articles with optional date filtering.
        """
        dense_vec = self.dense_model.encode(query).tolist()
        sparse_vec = self._get_sparse_vector(query) # Changed from compute_sparse_vector to _get_sparse_vector as per existing method name
        
        # Build Filter
        query_filter = None
        if start_date or end_date:
            range_filter = {}
            if start_date:
                range_filter["gte"] = self._parse_date(start_date)
            if end_date:
                range_filter["lte"] = self._parse_date(end_date)
            
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="publish_date",
                        range=models.DatetimeRange(**range_filter)
                    )
                ]
            )

        results = self.client.query_points(
            collection_name="articles",
            prefetch=[
                models.Prefetch(
                    query=dense_vec,
                    using="default",
                    limit=top_k * 2,
                    filter=query_filter
                ),
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse-text",
                    limit=top_k * 2,
                    filter=query_filter
                )
            ],
            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),
            limit=top_k,
            with_payload=True
        )

        return [
            {
                "score": hit.score,
                "title": (hit.payload or {}).get("title"),
                "description": (hit.payload or {}).get("description"),
                "date": (hit.payload or {}).get("publish_date"),
                "url": (hit.payload or {}).get("doc_url"),
                "id_hex": (hit.payload or {}).get("id_hex"),
                "category": (hit.payload or {}).get("category")
            }
            for hit in results.points
        ]

    def search_similar_events(
        self, 
        query: str, 
        top_k: int = 5, 
        start_date: str | None = None, 
        end_date: str | None = None
    ) -> list[dict]:
        """
        Performs a hybrid search for events with optional date filtering.
        """
        dense_vec = self.dense_model.encode(query).tolist()
        sparse_vec = self._get_sparse_vector(query)
        
        # Build Filter for events (using start_date of the event)
        query_filter = None
        if start_date or end_date:
            range_filter = {}
            if start_date:
                range_filter["gte"] = self._parse_date(start_date)
            if end_date:
                range_filter["lte"] = self._parse_date(end_date)
            
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="start_date",
                        range=models.DatetimeRange(**range_filter)
                    )
                ]
            )

        results = self.client.query_points(
            collection_name="events",
            prefetch=[
                models.Prefetch(
                    query=dense_vec,
                    using="default",
                    limit=top_k * 2,
                    filter=query_filter
                ),
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse-text",
                    limit=top_k * 2,
                    filter=query_filter
                )
            ],
            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),
            limit=top_k,
            with_payload=True
        )

        return [
            {
                "score": hit.score,
                "title": (hit.payload or {}).get("title"),
                "description": (hit.payload or {}).get("description"),
                "start_date": (hit.payload or {}).get("start_date"),
                "end_date": (hit.payload or {}).get("end_date"),
                "id": (hit.payload or {}).get("event_id"),
                "source": (hit.payload or {}).get("source"),
                "category": (hit.payload or {}).get("category")
            }
            for hit in results.points
        ]
    
    def collection_exists(self, collection_name: str | None = None) -> bool:
        """Check if collection exists."""
        name = collection_name or self.collection_name
        try:
            self.client.get_collection(name)
            return True
        except Exception:
            return False
    
    def create_collection(
        self,
        collection_name: str | None = None,
        dense_vector_size: int = 1024,
        force_recreate: bool = False
    ) -> bool:
        """
        Create a Qdrant collection with hybrid (dense + sparse) vectors.
        
        Args:
            collection_name: Collection name (defaults to self.collection_name)
            dense_vector_size: Dense vector dimension (default 1024 for PIXIE-Rune)
            force_recreate: If True, delete and recreate collection
            
        Returns:
            True if created successfully
        """
        name = collection_name or self.collection_name
        
        # Delete if exists and force_recreate
        if force_recreate and self.collection_exists(name):
            self.client.delete_collection(name)
            print(f"🗑️  Deleted existing collection: {name}")
        
        # Skip if exists
        if self.collection_exists(name):
            print(f"✅ Collection already exists: {name}")
            return True
        
        # Create collection with hybrid vectors
        self.client.create_collection(
            collection_name=name,
            vectors_config={
                "default": models.VectorParams(
                    size=dense_vector_size,
                    distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse-text": models.SparseVectorParams()
            }
        )
        
        print(f"✅ Created collection: {name}")
        return True
    
    def batch_upsert(
        self,
        points: List[models.PointStruct],
        collection_name: str | None = None,
        batch_size: int = 100
    ) -> int:
        """
        Upsert points to Qdrant in batches.
        
        Args:
            points: List of PointStruct objects
            collection_name: Target collection (defaults to self.collection_name)
            batch_size: Number of points per batch
            
        Returns:
            Total number of points uploaded
        """
        name = collection_name or self.collection_name
        
        if not self.collection_exists(name):
            raise ValueError(f"Collection '{name}' does not exist. Create it first.")
        
        total = len(points)
        uploaded = 0
        
        for i in range(0, total, batch_size):
            batch = points[i:i+batch_size]
            self.client.upsert(
                collection_name=name,
                points=batch
            )
            uploaded += len(batch)
            print(f"  📤 Uploaded {uploaded}/{total} points ({uploaded/total*100:.1f}%)")
        
        return uploaded
    
    def embed_batch_dense(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a batch of texts."""
        return self.dense_model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
    
    def embed_batch_sparse(self, texts: List[str]) -> List[models.SparseVector]:
        """Generate sparse embeddings for a batch of texts."""
        sparse_vectors = []
        
        # Process in smaller batches to avoid OOM
        for text in texts:
            sparse_vectors.append(self._get_sparse_vector(text))
        
        return sparse_vectors
