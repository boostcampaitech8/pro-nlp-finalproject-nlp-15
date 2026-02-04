import os
import json
import uuid
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from typing import Any
import torch
import time
from datetime import datetime
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams, PointStruct, SparseVectorParams, OptimizersConfigDiff
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForMaskedLM, AutoTokenizer

# Load environment variables
load_dotenv()

class EventIngestor:
    def __init__(self, collection_name: str = "events"):
        self.collection_name = collection_name
        qdrant_url = os.getenv("QDRANT_URL", "http://lori2mai11ya.asuscomm.com:6333")
        api_key = os.getenv("QDRANT_API_KEY")
        
        # Initialize Qdrant client
        # Note: If using a remote server with API key over HTTP, it might warn about insecure connection
        self.client = QdrantClient(url=qdrant_url, api_key=api_key)
        
        # Initialize PIXIE models
        print("Loading dense model: telepix/PIXIE-Rune-Preview")
        self.dense_model = SentenceTransformer("telepix/PIXIE-Rune-Preview", device="cuda" if torch.cuda.is_available() else "cpu")
        
        print("Loading sparse model: telepix/PIXIE-Splade-Preview")
        self.sparse_tokenizer = AutoTokenizer.from_pretrained("telepix/PIXIE-Splade-Preview")
        self.sparse_model = AutoModelForMaskedLM.from_pretrained("telepix/PIXIE-Splade-Preview", trust_remote_code=True)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sparse_model.to(self.device)
        self.sparse_model.eval()

    def create_collection(self, overwrite: bool = False):
        if self.client.collection_exists(self.collection_name):
            if overwrite:
                print(f"Collection {self.collection_name} exists. Overwriting...")
                self.client.delete_collection(self.collection_name)
            else:
                print(f"Collection {self.collection_name} already exists.")
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "default": VectorParams(
                    size=1024,  # PIXIE-Rune size
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse-text": models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=True,
                    )
                )
            }
        )
        
        # Create Payload Indexes for date filtering
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="start_date",
            field_schema=models.PayloadSchemaType.DATETIME
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="end_date",
            field_schema=models.PayloadSchemaType.DATETIME
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="category",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        
        print(f"Collection {self.collection_name} created with payload indexes.")

    def get_existing_ids(self) -> set[str]:
        """Returns a set of all point IDs currently in the collection."""
        existing_ids = set()
        offset = None
        while True:
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=False,
                with_vectors=False,
                offset=offset
            )
            points, next_page_offset = scroll_result
            for point in points:
                existing_ids.add(point.id)
            if next_page_offset is None:
                break
            offset = next_page_offset
        return existing_ids

    def compute_sparse_vector(self, text: str) -> models.SparseVector:
        """Compute sparse vector using PIXIE-Splade."""
        inputs = self.sparse_tokenizer([text], return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.sparse_model(**inputs)
            logits = outputs.logits
            
            # SPLADE pooling: log(1 + relu(logits))
            weights = torch.log(1 + torch.relu(logits))
            # Masking
            weights = weights * inputs['attention_mask'].unsqueeze(-1)
            sparse_vec_pt, _ = torch.max(weights, dim=1)
            
            nonzero_indices = torch.nonzero(sparse_vec_pt[0]).flatten()
            return models.SparseVector(
                indices=nonzero_indices.tolist(),
                values=sparse_vec_pt[0][nonzero_indices].tolist()
            )

    def process_jsonl(self, file_path: Path):
        category = file_path.stem
        print(f"Processing {file_path.name} (Category: {category})")
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        num_lines = len(lines)
        batch_size = 16
        
        # Check existing IDs to resume
        existing_ids = self.get_existing_ids()
        print(f"Found {len(existing_ids)} existing points in collection.")

        for i in tqdm(range(0, num_lines, batch_size)):
            batch_lines = lines[i:i + batch_size]
            points = []
            
            for line in batch_lines:
                try:
                    data = json.loads(line)
                    event_id = data.get("event_id")
                    
                    # Ensure event_id is a valid UUID or integer
                    def is_valid_uuid(val):
                        try:
                            uuid.UUID(str(val))
                            return True
                        except ValueError:
                            return False
                            
                    if not is_valid_uuid(event_id) and not isinstance(event_id, int):
                        # Generate deterministic UUID
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(event_id)))
                    else:
                        point_id = str(event_id)
                    
                    if point_id in existing_ids:
                        continue
                        
                    text_to_encode = f"{data.get('title', '')} {data.get('description', '')}"
                    
                    # Convert dates to ISO 8601 strings if they aren't already
                    # Most are YYYY-MM-DD which is fine for Qdrant's datetime
                    start_date = data.get("start_date")
                    end_date = data.get("end_date")
                    
                    # Add category to payload
                    payload = data.copy()
                    payload["category"] = category
                    
                    # Compute vectors
                    dense_vec = self.dense_model.encode(text_to_encode).tolist()
                    sparse_vec = self.compute_sparse_vector(text_to_encode)
                    
                    points.append(PointStruct(
                        id=point_id,
                        vector={
                            "default": dense_vec,
                            "sparse-text": sparse_vec
                        },
                        payload=payload
                    ))
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue
            
            if points:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points
                        )
                        break
                    except Exception as e:
                        print(f"Upsert failed (attempt {attempt+1}/{max_retries}): {e}")
                        time.sleep(2 * (attempt + 1))

def main():
    ingestor = EventIngestor(collection_name="events")
    ingestor.create_collection(overwrite=True) # Re-create with correct dimension
    
    events_dir = Path("data/events")
    jsonl_files = list(events_dir.glob("*.jsonl"))
    
    for jsonl_file in jsonl_files:
        ingestor.process_jsonl(jsonl_file)

if __name__ == "__main__":
    main()
