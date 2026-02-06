import hydra
import sys
from omegaconf import DictConfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vector_db.vector_store import VectorStore
from db.database import get_engine
from preprocess.embed_and_upsert import EventUploader


@hydra.main(version_base=None, config_path="../config", config_name="index_events")
def main(cfg: DictConfig):
    recreate_collection = cfg.get("recreate_collection", False)
    batch_size = cfg.get("batch_size", 100)
    
    # Initialize components
    print(f"🚀 Initializing Event uploader...")
    
    rag_config = cfg.rag.vector_db
    collection_name = rag_config.event_collection
    
    vector_store = VectorStore(
        qdrant_url=rag_config.url,
        dense_model_name=cfg.rag.embedding.dense_model,
        sparse_model_name=cfg.rag.embedding.sparse_model
    )
    
    # Pass the database config as a dictionary
    from omegaconf import OmegaConf
    from typing import cast
    db_cfg = cast(dict, OmegaConf.to_container(cfg.database, resolve=True))
    engine = get_engine(db_cfg)
    uploader = EventUploader(vector_store, engine)
    
    # Ensure indexes (if collection exists)
    if vector_store.collection_exists(collection_name):
        vector_store.create_payload_index(collection_name, "start_date")
        vector_store.create_payload_index(collection_name, "end_date")
    
    # Ensure indexes
    vector_store.create_payload_index(collection_name, "start_date")
    vector_store.create_payload_index(collection_name, "end_date")
    
    # Upload
    print(f"\n📤 Syncing events from SQLite to Qdrant...")
    result = uploader.upload_events(
        batch_size=batch_size,
        collection_name=collection_name,
        force_recreate=recreate_collection
    )
    
    # Ensure indexes after upload
    vector_store.create_payload_index(collection_name, "start_date")
    vector_store.create_payload_index(collection_name, "end_date")
    
    print(f"\n✅ Done!")
    print(f"  Events Found: {result['events_count']}")
    print(f"  Points Uploaded: {result['vectors_uploaded']}")
    print(f"  Collection: {result['collection']}")


if __name__ == "__main__":
    main()
