"""
Workflow: Chunk Financial Documents for RAG.

This is the entry point script for chunking PDFs.
Handles path resolution, config loading, and execution orchestration only.

Usage:
    uv run python workflow/chunk_financial_documents.py --resource-id commodity_markets_2022
    uv run python workflow/chunk_financial_documents.py --all
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.resource_manager import ResourceManager
from preprocess.chunk_financial_documents import FinancialDocumentChunker


def main():
    """Main execution entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Chunk financial documents for RAG")
    parser.add_argument(
        "--resource-id",
        type=str,
        help="Process specific resource by ID"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all RAG-enabled resources"
    )
    args = parser.parse_args()
    
    if not args.resource_id and not args.all:
        parser.error("Must specify either --resource-id or --all")
    
    # Initialize paths and configs
    manifest_path = PROJECT_ROOT / "data" / "resources" / "manifest.json"
    rag_config_path = PROJECT_ROOT / "config" / "rag.yaml"
    output_dir = PROJECT_ROOT / "data" / "chunks"
    output_dir.mkdir(exist_ok=True)
    
    # Load manager
    manager = ResourceManager(
        manifest_path=str(manifest_path),
        rag_config_path=str(rag_config_path)
    )
    
    # Initialize chunker
    chunker = FinancialDocumentChunker(manager)
    
    # Determine resources to process
    if args.resource_id:
        resource_ids = [args.resource_id]
    else:
        rag_resources = manager.get_rag_enabled_resources()
        resource_ids = [r["id"] for r in rag_resources]
    
    print(f"🚀 Processing {len(resource_ids)} resource(s)")
    
    # Process each resource
    for resource_id in resource_ids:
        try:
            chunker.chunk_resource(resource_id, output_dir)
            print(f"\n✅ Done! Review preview before uploading to Qdrant.\n")
        except Exception as e:
            print(f"❌ Error processing {resource_id}: {e}")
            continue


if __name__ == "__main__":
    main()
