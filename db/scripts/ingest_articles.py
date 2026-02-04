import os
import uuid
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from typing import List, Dict, Any, Optional
import torch
import time
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForMaskedLM, AutoTokenizer
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException

load_dotenv()

class ArticleIngestor:
    def __init__(
        self, 
        dense_model_name: str = "telepix/PIXIE-Rune-Preview",
        sparse_model_name: str = "telepix/PIXIE-Splade-Preview",
        qdrant_url: str = "http://lori2mai11ya.asuscomm.com:6333",
        collection_name: str = "articles"
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        api_key = os.getenv("QDRANT_API_KEY")
        self.client = QdrantClient(url=qdrant_url, api_key=api_key, timeout=60)
        self.collection_name = collection_name
        
        print(f"Loading dense model: {dense_model_name}")
        self.dense_model = SentenceTransformer(dense_model_name, device=self.device)
        
        print(f"Loading sparse model: {sparse_model_name}")
        self.sparse_tokenizer = AutoTokenizer.from_pretrained(sparse_model_name)
        self.sparse_model = AutoModelForMaskedLM.from_pretrained(sparse_model_name, trust_remote_code=True).to(self.device)
        self.sparse_model.eval()

    def create_collection(self, dense_dim: int = 1024):
        """Creates collection if it doesn't exist."""
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "default": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse-text": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=True))
                }
            )
            print(f"Collection {self.collection_name} created.")
        else:
            print(f"Collection {self.collection_name} already exists.")

    def _get_sparse_vectors(self, texts: List[str]) -> List[models.SparseVector]:
        inputs = self.sparse_tokenizer(texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            outputs = self.sparse_model(**inputs)
            logits = outputs.logits
            weights = torch.log(1 + torch.relu(logits))
            weights = weights * inputs['attention_mask'].unsqueeze(-1)
            sparse_vecs_pt, _ = torch.max(weights, dim=1)
            
            results = []
            for i in range(sparse_vecs_pt.shape[0]):
                nonzero_indices = torch.nonzero(sparse_vecs_pt[i]).flatten()
                indices = nonzero_indices.tolist()
                values = sparse_vecs_pt[i][nonzero_indices].tolist()
                results.append(models.SparseVector(indices=indices, values=values))
            return results

    def _get_point_id(self, hex_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(hex_id)))

    def filter_existing_ids(self, ids: List[str]) -> List[int]:
        """Returns indices of IDs that DO NOT exist in Qdrant."""
        try:
            point_ids = [self._get_point_id(h) for h in ids]
            # Check existence in Qdrant
            # Qdrant client retrieve is fast for small sets
            existing_points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=point_ids,
                with_payload=False,
                with_vectors=False
            )
            existing_set = {p.id for p in existing_points}
            return [i for i, pid in enumerate(point_ids) if pid not in existing_set]
        except Exception as e:
            print(f"Error checking existing IDs: {e}. Assuming all need processing.")
            return list(range(len(ids)))

    def ingest_csv(self, file_path: Path, batch_size: int = 16, resume=True):
        df = pd.read_csv(file_path)
        print(f"Processing {file_path.name} ({len(df)} rows)")
        
        for i in tqdm(range(0, len(df), batch_size)):
            batch_df = df.iloc[i : i + batch_size]
            
            # Step 1: Check existence if resume is enabled
            if resume:
                needed_indices = self.filter_existing_ids(batch_df['id'].tolist())
                if not needed_indices:
                    continue
                batch_df = batch_df.iloc[needed_indices]
            
            if batch_df.empty:
                continue

            batch_texts = (batch_df['title'].fillna('') + " " + batch_df['description'].fillna('')).tolist()
            
            # Step 2: Generate Vectors with Retries
            tries = 0
            while tries < 3:
                try:
                    dense_vecs = self.dense_model.encode(batch_texts)
                    sparse_vecs = self._get_sparse_vectors(batch_texts)
                    
                    points = []
                    for idx, (_, row) in enumerate(batch_df.iterrows()):
                        point_id = self._get_point_id(row['id'])
                        points.append(models.PointStruct(
                            id=point_id,
                            vector={"default": dense_vecs[idx].tolist(), "sparse-text": sparse_vecs[idx]},
                            payload={
                                "id_hex": row['id'], "title": row.get('title'),
                                "description": row.get('description'), "publish_date": row.get('publish_date'),
                                "doc_url": row.get('doc_url'), "meta_site_name": row.get('meta_site_name'),
                                "category": file_path.stem
                            }
                        ))
                    
                    self.client.upsert(collection_name=self.collection_name, points=points)
                    break # Success
                except (UnexpectedResponse, ResponseHandlingException) as e:
                    tries += 1
                    print(f"\nError during upsert (try {tries}/3): {e}. Sleeping 5s...")
                    time.sleep(5)
                except Exception as e:
                    print(f"\nFatal error: {e}")
                    raise e

    def ingest_all(self, data_dir: str):
        self.create_collection()
        path = Path(data_dir)
        # Sort files to ensure deterministic order if resumed
        csv_files = sorted(list(path.glob("*.csv")))
        for csv_file in csv_files:
            self.ingest_csv(csv_file)

if __name__ == "__main__":
    ingestor = ArticleIngestor()
    # ingestor.create_collection()
    ingestor.ingest_all("data/articles")
