"""
Resource Manager for tracking and managing RAG documents.

This module provides utilities to:
- Load and validate resource manifest
- Query available resources by category/tags
- Track indexing status for RAG pipeline
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any


class ResourceManager:
    """Manages RAG document resources and their metadata."""
    
    def __init__(self, manifest_path: str | None = None, rag_config_path: str | None = None):
        """
        Initialize ResourceManager.
        
        Args:
            manifest_path: Path to manifest.json. Defaults to data/resources/manifest.json
            rag_config_path: Path to rag.yaml. Defaults to config/rag.yaml
        """
        if manifest_path is None:
            # Default to project root / data / resources / manifest.json
            manifest_path = Path(__file__).parent.parent / "data" / "resources" / "manifest.json"
        
        if rag_config_path is None:
            # Default to project root / config / rag.yaml
            rag_config_path = Path(__file__).parent.parent / "config" / "rag.yaml"
        
        self.manifest_path = Path(manifest_path)
        self.rag_config_path = Path(rag_config_path)
        self.manifest_data: dict[str, Any] = {}
        self.rag_config: dict[str, Any] = {}
        
        self.load_manifest()
        self.load_rag_config()
    
    def load_manifest(self) -> dict[str, Any]:
        """Load manifest.json file."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest_data = json.load(f)
        
        return self.manifest_data
    
    def load_rag_config(self) -> dict[str, Any]:
        """Load rag.yaml configuration file."""
        if not self.rag_config_path.exists():
            # Fallback to default config if file doesn't exist
            self.rag_config = {
                "default": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "embedding_model": "text-embedding-3-small",
                    "vector_collection": "financial_documents"
                }
            }
            return self.rag_config
        
        with open(self.rag_config_path, "r", encoding="utf-8") as f:
            self.rag_config = yaml.safe_load(f)
        
        return self.rag_config
    
    def get_rag_config(self, resource_id: str) -> dict[str, Any]:
        """
        Get RAG configuration for a resource.
        
        Merges global config with type-specific overrides and resource-specific overrides.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Merged RAG configuration
        """
        resource = self.get_resource(resource_id)
        if not resource:
            return {}
        
        # Start with default config
        config = self.rag_config.get("default", {}).copy()
        
        # Apply type-specific override if exists
        resource_type = resource.get("type")
        if resource_type and "overrides" in self.rag_config:
            type_override = self.rag_config["overrides"].get(resource_type, {})
            config.update(type_override)
        
        # Apply resource-specific override if exists
        resource_override = resource.get("rag_config", {})
        config.update(resource_override)
        
        return config
    
    def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        """
        Get resource by ID.
        
        Args:
            resource_id: Unique resource identifier
            
        Returns:
            Resource dict or None if not found
        """
        for resource in self.manifest_data.get("resources", []):
            if resource.get("id") == resource_id:
                return resource
        return None
    
    def list_resources(
        self, 
        category: str | None = None,
        tag: str | None = None,
        rag_enabled: bool | None = None
    ) -> list[dict[str, Any]]:
        """
        List resources with optional filters.
        
        Args:
            category: Filter by category (e.g., "economics")
            tag: Filter by tag (e.g., "commodity")
            rag_enabled: Filter by RAG enablement status
            
        Returns:
            List of matching resources
        """
        resources = self.manifest_data.get("resources", [])
        
        if category:
            resources = [r for r in resources if r.get("category") == category]
        
        if tag:
            resources = [r for r in resources if tag in r.get("tags", [])]
        
        if rag_enabled is not None:
            resources = [
                r for r in resources 
                if r.get("rag_config", {}).get("enabled") == rag_enabled
            ]
        
        return resources
    
    def get_rag_enabled_resources(self) -> list[dict[str, Any]]:
        """Get all resources with RAG enabled."""
        return self.list_resources(rag_enabled=True)
    
    def update_index_status(
        self, 
        resource_id: str, 
        indexed_at: str | None = None,
        chunk_count: int | None = None
    ) -> bool:
        """
        Update indexing status for a resource.
        
        Args:
            resource_id: Resource to update
            indexed_at: ISO timestamp of indexing
            chunk_count: Number of chunks created
            
        Returns:
            True if updated successfully, False if resource not found
        """
        resource = self.get_resource(resource_id)
        if not resource:
            return False
        
        rag_config = resource.get("rag_config", {})
        
        if indexed_at:
            rag_config["indexed_at"] = indexed_at
            rag_config["last_sync"] = datetime.now().isoformat()
        
        if chunk_count is not None:
            rag_config["chunk_count"] = chunk_count
        
        # Save back to file
        self._save_manifest()
        return True
    
    def get_vector_payload(self, resource_id: str) -> dict[str, Any] | None:
        """
        Get vector payload for a resource (metadata that goes into each vector chunk).
        
        Constructs payload from resource metadata fields.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Vector payload dict or None if not found
        """
        resource = self.get_resource(resource_id)
        if not resource:
            return None
        
        # Build payload from flat resource fields
        return {
            "source_id": resource["id"],
            "title": resource.get("title", ""),
            "source_type": resource.get("type", "unknown"),
            "authors": resource.get("authors", []),
            "publisher": resource.get("publisher", ""),
            "publication_date": resource.get("publication_date", ""),
            "language": resource.get("language", "en"),
            "url": resource.get("url", "")
        }
    
    def filter_by_date_range(
        self, 
        start_year: int | None = None, 
        end_year: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Filter resources by publication year range.
        
        Args:
            start_year: Minimum publication year (inclusive)
            end_year: Maximum publication year (inclusive)
            
        Returns:
            List of resources within date range
        """
        resources = self.manifest_data.get("resources", [])
        
        if start_year is not None:
            resources = [
                r for r in resources 
                if r.get("metadata", {}).get("publication_year", 0) >= start_year
            ]
        
        if end_year is not None:
            resources = [
                r for r in resources 
                if r.get("metadata", {}).get("publication_year", 9999) <= end_year
            ]
        
        return resources
    
    def update_preprocessing_status(
        self,
        resource_id: str,
        status: str | None = None,
        chunks_created: int | None = None,
        vectors_uploaded: int | None = None,
        error: str | None = None
    ) -> bool:
        """
        Update preprocessing status for a resource.
        
        Args:
            resource_id: Resource to update
            status: Processing status (pending|processing|completed|failed)
            chunks_created: Number of chunks created
            vectors_uploaded: Number of vectors uploaded to DB
            error: Error message if failed
            
        Returns:
            True if updated successfully
        """
        resource = self.get_resource(resource_id)
        if not resource:
            return False
        
        preprocessing = resource.get("preprocessing", {})
        
        if status:
            preprocessing["status"] = status
            preprocessing["last_run"] = datetime.now().isoformat()
        
        if chunks_created is not None:
            preprocessing["chunks_created"] = chunks_created
        
        if vectors_uploaded is not None:
            preprocessing["vectors_uploaded"] = vectors_uploaded
        
        if error:
            preprocessing["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "message": error
            })
        
        self._save_manifest()
        return True
    
    def get_resource_path(self, resource_id: str) -> Path | None:
        """
        Get absolute path to resource file.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Absolute Path object or None if not found
        """
        resource = self.get_resource(resource_id)
        if not resource:
            return None
        
        filename = resource.get("file", {}).get("path")
        if not filename:
            return None
        
        # Construct path: manifest_dir / filename
        return self.manifest_path.parent / filename
    
    def _save_manifest(self):
        """Save manifest data back to file."""
        self.manifest_data["last_updated"] = datetime.now().isoformat()
        
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Example usage
    manager = ResourceManager()
    
    print("📚 All Resources:")
    for resource in manager.manifest_data["resources"]:
        print(f"  - {resource['title']} ({resource['id']})")
    
    print("\n🔍 Economics Resources:")
    for resource in manager.list_resources(category="economics"):
        print(f"  - {resource['title']}")
    
    print("\n⚡ RAG-Enabled Resources:")
    for resource in manager.get_rag_enabled_resources():
        path = manager.get_resource_path(resource["id"])
        print(f"  - {resource['title']}")
        print(f"    Path: {path}")
        print(f"    Status: {resource['rag_config']['indexed_at'] or 'Not indexed'}")
