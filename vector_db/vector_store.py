import os
import requests
from typing import List, Dict, Optional, Any, cast
import torch
from sentence_transformers import SentenceTransformer
from datetime import datetime, date
from transformers import AutoModelForMaskedLM, AutoTokenizer
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

class VectorStore:
    client: Optional[QdrantClient] = None
    dense_model: Optional[SentenceTransformer] = None
    sparse_model: Optional[AutoModelForMaskedLM] = None
    sparse_tokenizer: Optional[AutoTokenizer] = None
    
    # Class-level cache for models to prevent repeated loads
    _model_cache: Dict[str, Any] = {}

    def __init__(
        self, 
        qdrant_url: str,
        embedding_cfg: Optional[Any] = None,
        dense_model_name: str = "telepix/PIXIE-Rune-Preview",
        sparse_model_name: str = "telepix/PIXIE-Splade-Preview"
    ):
        """
        Initialize VectorStore. 
        If embedding_cfg is provided (Hydra), it uses it to decide between 'local' or 'api' mode.
        If not provided, it defaults to 'local' for backward compatibility.
        """
        # 1. Initialize Qdrant Client
        try:
            self.client = QdrantClient(
                url=qdrant_url, 
                api_key=os.getenv("QDRANT_API_KEY"),
                timeout=10
            )
            self.client.get_collections()
            print(f"✅ Connected to Qdrant: {qdrant_url}")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            self.client = None

        self.cfg = embedding_cfg
        self.mode = "local"
        if self.cfg and hasattr(self.cfg, "mode"):
            self.mode = self.cfg.mode

        print(f"🛠️  VectorStore Mode: {self.mode}")

        # 2. Local Model Loading (only if mode is local)
        if self.mode == "local":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
                
            # Dense Model
            if dense_model_name not in VectorStore._model_cache:
                print(f"📦 Loading Dense Model: {dense_model_name}...")
                VectorStore._model_cache[dense_model_name] = SentenceTransformer(dense_model_name, device=self.device)
            self.dense_model = VectorStore._model_cache[dense_model_name]
            
            # Sparse Model & Tokenizer
            if sparse_model_name:
                cache_key = f"sparse_{sparse_model_name}"
                if cache_key not in VectorStore._model_cache:
                    print(f"📦 Loading Sparse Model: {sparse_model_name}...")
                    tokenizer = AutoTokenizer.from_pretrained(sparse_model_name)
                    model = AutoModelForMaskedLM.from_pretrained(sparse_model_name, trust_remote_code=True).to(self.device)
                    model.eval()
                    VectorStore._model_cache[cache_key] = (tokenizer, model)
                
                self.sparse_tokenizer, self.sparse_model = VectorStore._model_cache[cache_key]
        else:
            # API Mode: No local models needed
            self.dense_model = None
            self.sparse_model = None
            self.sparse_tokenizer = None

    def create_payload_index(self, collection_name: str, field_name: str, field_type: str = "datetime"):
        """Utility to ensure payload indexes exist."""
        if not self.client or not self.client.collection_exists(collection_name):
            return
            
        schema = models.PayloadSchemaType.DATETIME if field_type == "datetime" else models.PayloadSchemaType.KEYWORD
        try:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema
            )
            print(f"✅ Index created: {collection_name}.{field_name}")
        except Exception:
            pass

    def _get_sparse_vector(self, text: str) -> models.SparseVector:
        """Generates a sparse vector using either local model or remote API."""
        if self.mode == "api":
            return self._get_sparse_vector_api(text)
            
        if not self.sparse_tokenizer:
            raise ValueError("Sparse tokenizer not initialized. Provide sparse_model_name during initialization.")
            
        inputs = self.sparse_tokenizer([text], return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            outputs = self.sparse_model(**inputs)
            logits = outputs.logits
            
            # SPLADE transformation
            weights = torch.log(1 + torch.relu(logits))
            weights = weights * inputs['attention_mask'].unsqueeze(-1)
            sparse_vec_pt, _ = torch.max(weights, dim=1)
            
            nonzero_indices = torch.nonzero(sparse_vec_pt[0]).flatten()
            return models.SparseVector(
                indices=nonzero_indices.tolist(),
                values=sparse_vec_pt[0][nonzero_indices].tolist()
            )

    def _get_sparse_vector_api(self, text: str) -> models.SparseVector:
        """Fetch sparse vector from remote API."""
        if not self.cfg or not hasattr(self.cfg, "sparse") or not hasattr(self.cfg.sparse, "api_url"):
            raise ValueError("Sparse API configuration (api_url) is missing in rag.yaml.")
            
        url = self.cfg.sparse.api_url
        response = requests.post(url, json={"text": text}, timeout=5)
        response.raise_for_status()
        data = response.json()
        vec = data["sparse_vector"]
        return models.SparseVector(
            indices=vec["indices"],
            values=vec["values"]
        )

    def _get_sparse_vectors(self, texts: List[str]) -> List[models.SparseVector]:
        """Generates multiple sparse vectors."""
        if self.mode == "api":
            # Current implementation of splade API seems to handle single text. 
            # If batching is needed, loop or update API.
            return [self._get_sparse_vector_api(t) for t in texts]
            
        if not self.sparse_tokenizer:
            raise ValueError("Sparse tokenizer not initialized.")
            
        inputs = self.sparse_tokenizer(texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            outputs = self.sparse_model(**inputs)
            logits = outputs.logits
            
            # SPLADE transformation
            weights = torch.log(1 + torch.relu(logits))
            weights = weights * inputs['attention_mask'].unsqueeze(-1)
            sparse_vecs_pt, _ = torch.max(weights, dim=1)
            
            results = []
            for i in range(sparse_vecs_pt.shape[0]):
                nonzero_indices = torch.nonzero(sparse_vecs_pt[i]).flatten()
                results.append(models.SparseVector(
                    indices=nonzero_indices.tolist(),
                    values=sparse_vecs_pt[i][nonzero_indices].tolist()
                ))
            return results

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

    def search(
        self, 
        query: str, 
        collection_name: str,
        date_field: str = "publish_date",
        top_k: int = 5, 
        start_date: str | None = None, 
        end_date: str | None = None
    ) -> list[models.ScoredPoint]:
        """
        Performs a generic hybrid search with optional date filtering.
        """
        if not self.client:
            return []
            
        dense_vec = self.embed_batch_dense([query])[0]
        sparse_vec = self._get_sparse_vector(query)
        
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
                        key=date_field,
                        range=models.DatetimeRange(**range_filter)
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=collection_name,
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

        return results.points if results and results.points else []

    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        if self.client is None:
            return False
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    def create_collection(
        self,
        collection_name: str,
        dense_vector_size: int | None = None,
        force_recreate: bool = False
    ) -> bool:
        """
        Create a Qdrant collection with hybrid (dense + sparse) vectors.
        """
        if self.client is None:
            print("❌ Cannot create collection: Qdrant client is not initialized.")
            return False

        # Use model dimension if not provided
        if dense_vector_size is not None:
            actual_size: int = dense_vector_size
        elif self.dense_model:
            actual_size = cast(int, self.dense_model.get_sentence_embedding_dimension())
        else:
            # Default for PIXIE if API mode and no size provided
            actual_size = 1024 

        # Delete if exists and force_recreate
        if force_recreate and self.collection_exists(collection_name):
            self.client.delete_collection(collection_name)
            print(f"🗑️  Deleted existing collection: {collection_name}")
        
        # Skip if exists
        if self.collection_exists(collection_name):
            print(f"✅ Collection already exists: {collection_name}")
            return True
        
        # Create collection with hybrid vectors
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "default": models.VectorParams(
                    size=actual_size,
                    distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse-text": models.SparseVectorParams()
            }
        )
        
        print(f"✅ Created collection: {collection_name}")
        return True
    
    def batch_upsert(
        self,
        points: List[models.PointStruct],
        collection_name: str,
        batch_size: int = 100,
        force_recreate: bool = False
    ) -> int:
        """
        Upsert points to Qdrant in batches.
        """
        if self.client is None:
            raise ValueError("Qdrant client is not initialized.")
            
        if force_recreate or not self.collection_exists(collection_name):
            print(f"🏗️  Setting up collection '{collection_name}' (force_recreate={force_recreate})...")
            self.create_collection(collection_name, force_recreate=force_recreate)
        
        total = len(points)
        uploaded = 0
        
        # Use tqdm for progress tracking
        with tqdm(total=total, desc=f"Upserting to {collection_name}", unit="point") as pbar:
            for i in range(0, total, batch_size):
                batch = points[i:i+batch_size]
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch
                )
                uploaded += len(batch)
                pbar.update(len(batch))
        
        return uploaded
    
    def embed_batch_dense(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a batch of texts."""
        if self.mode == "api":
            return self._get_dense_vectors_api(texts)
            
        if not self.dense_model:
            raise ValueError("Dense model not initialized.")
            
        return self.dense_model.encode(texts, batch_size=32, show_progress_bar=True).tolist()
    
    def _get_dense_vectors_api(self, texts: List[str]) -> List[List[float]]:
        """Fetch dense embeddings from remote API."""
        if not self.cfg or not hasattr(self.cfg, "dense") or not hasattr(self.cfg.dense, "api_url"):
            raise ValueError("Dense API configuration (api_url) is missing in rag.yaml.")
            
        url = self.cfg.dense.api_url
        payload = {
            "texts": texts,
            "is_query": True,
            "normalize": True
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]

    def embed_batch_sparse(self, texts: List[str], mini_batch_size: int = 32) -> List[models.SparseVector]:
        """Generate sparse embeddings for a batch of texts using controlled mini-batching."""
        if self.mode == "api":
            # API might be single or batch. We follow the local mini-batching pattern.
            sparse_vectors = []
            for i in range(0, len(texts), mini_batch_size):
                batch_texts = texts[i : i + mini_batch_size]
                # Batching via comprehension as current Splade API seems single-text
                batch_vectors = [self._get_sparse_vector_api(t) for t in batch_texts]
                sparse_vectors.extend(batch_vectors)
            return sparse_vectors

        sparse_vectors = []
        total = len(texts)
        
        # Process with progress bar and true GPU batching
        with tqdm(total=total, desc="Generating Sparse Embeddings", unit="text", leave=False) as pbar:
            for i in range(0, total, mini_batch_size):
                batch_texts = texts[i : i + mini_batch_size]
                batch_vectors = self._get_sparse_vectors(batch_texts)
                sparse_vectors.extend(batch_vectors)
                pbar.update(len(batch_texts))
        
        return sparse_vectors
