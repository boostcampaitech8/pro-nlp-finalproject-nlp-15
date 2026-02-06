import hydra
import sys
from omegaconf import DictConfig
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vector_db.resource_manager import ResourceManager
from preprocess.chunk_financial_documents import FinancialDocumentChunker


@hydra.main(version_base=None, config_path="../config", config_name="kb_chunking")
def main(cfg: DictConfig):
    resource_id = cfg.get("resource_id")
    process_all = cfg.get("all", False)
    
    if not resource_id and not process_all:
        print("❌ Error: Must specify either resource_id=ID or all=true")
        return
    
    manifest_path = PROJECT_ROOT / cfg.data.manifest_path
    output_dir = PROJECT_ROOT / cfg.data.chunks_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load manager (ResourceManager still takes paths, but we get them from cfg if needed)
    # Actually ResourceManager reads config internaly, but we can pass them.
    # Note: ResourceManager.__init__ currently doesn't take DictConfig directly.
    # I'll let it use its internal logic for now or refactor it.
    # Load manager
    manager = ResourceManager(manifest_path=manifest_path, rag_config=cfg.rag)
    chunker = FinancialDocumentChunker(manager)
    
    # Determine resources to process
    if resource_id:
        resource_ids = [resource_id]
    else:
        rag_resources = manager.get_rag_enabled_resources()
        resource_ids = [r["id"] for r in rag_resources]
    
    print(f"🚀 Processing {len(resource_ids)} resource(s)")
    
    # Process each resource
    for r_id in resource_ids:
        try:
            resource = manager.get_resource(r_id)
            if not resource:
                print(f"⚠️ Resource {r_id} not found in manifest, skipping.")
                continue
                
            print(f"\n📄 Processing: {resource['title']} ({r_id})")
            result = chunker.chunk_resource(r_id, output_dir)
            
            print(f"  ✅ Created {result['total_chunks']} chunks")
            print(f"  💾 Saved JSON: {output_dir / f'{r_id}_chunks.json'}")
            print(f"  📋 Preview for review: {output_dir / f'{r_id}_preview.md'}")
            print(f"✅ Chunking complete! Please review the preview before running indexing (run_kb_indexing.py).")
        except Exception as e:
            print(f"❌ Error processing {r_id}: {e}")
            continue


if __name__ == "__main__":
    main()
