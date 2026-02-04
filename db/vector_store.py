import os
from typing import List, Dict, Any, Optional
import torch
from sentence_transformers import SentenceTransformer
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
        self.client = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
        self.collection_name = collection_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize Dense Model
        self.dense_model = SentenceTransformer(dense_model_name, device=self.device)
        
        # Initialize Sparse Model
        self.sparse_tokenizer = AutoTokenizer.from_pretrained(sparse_model_name)
        self.sparse_model = AutoModelForMaskedLM.from_pretrained(sparse_model_name, trust_remote_code=True).to(self.device)
        self.sparse_model.eval()

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

    def search_similar_events(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Performs a hybrid (Dense + Sparse) search in Qdrant with Reciprocal Rank Fusion (RRF).
        Requires Qdrant 1.10+.
        """
        dense_vec = self.dense_model.encode(query).tolist()
        sparse_vec = self._get_sparse_vector(query)
        
        # Qdrant Hybrid Search with RRF
        # We use the 'prefetch' feature to combine results from multiple encoders
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vec,
                    using="default",
                    limit=top_k * 2,
                ),
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse-text",
                    limit=top_k * 2,
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
