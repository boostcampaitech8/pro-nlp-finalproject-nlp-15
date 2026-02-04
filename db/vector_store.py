import os
from typing import Any
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
        self.client = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
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
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self):
        """Ensure that necessary payload indexes exist for date filtering."""
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
