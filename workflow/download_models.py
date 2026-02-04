"""
Pre-download embedding models to cache.

This script downloads models separately with progress indication,
so the main upload script can use cached models instantly.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer
from transformers import AutoModelForMaskedLM, AutoTokenizer
import torch


def download_models():
    """Download both dense and sparse embedding models."""
    
    dense_model_name = "telepix/PIXIE-Rune-Preview"
    sparse_model_name = "telepix/PIXIE-Splade-Preview"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"🚀 Downloading embedding models to cache...")
    print(f"  Device: {device}")
    
    # Download dense model
    print(f"\n📥 Downloading dense model: {dense_model_name}")
    print(f"  (This may take 1-5 minutes depending on internet speed)")
    dense_model = SentenceTransformer(dense_model_name, device=device)
    print(f"  ✅ Dense model loaded")
    print(f"  Embedding dimension: {dense_model.get_sentence_embedding_dimension()}")
    
    # Download sparse model
    print(f"\n📥 Downloading sparse model: {sparse_model_name}")
    print(f"  (This may take 2-10 minutes - larger model)")
    sparse_tokenizer = AutoTokenizer.from_pretrained(sparse_model_name)
    sparse_model = AutoModelForMaskedLM.from_pretrained(
        sparse_model_name, 
        trust_remote_code=True
    ).to(device)
    print(f"  ✅ Sparse model loaded")
    
    # Test embeddings
    print(f"\n🧪 Testing embeddings...")
    test_text = "Commodity markets and price volatility"
   
    dense_vec = dense_model.encode(test_text)
    print(f"  ✅ Dense embedding: {len(dense_vec)} dims")
    
    inputs = sparse_tokenizer([test_text], return_tensors="pt", padding=True, truncation=True).to(device)
    with torch.no_grad():
        outputs = sparse_model(**inputs)
    print(f"  ✅ Sparse embedding generated")
    
    print(f"\n✅ All models downloaded and cached!")
    print(f"\nNow you can run:")
    print(f"  uv run python workflow/upsert_to_qdrant.py --resource-id commodity_markets_2022 --create-collection")


if __name__ == "__main__":
    download_models()
