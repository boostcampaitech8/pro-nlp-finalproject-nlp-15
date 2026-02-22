import json
import re
from pathlib import Path
from typing import Any
from vector_db.resource_manager import ResourceManager

try:
    import pymupdf4llm
except ImportError:
    raise ImportError("pymupdf4llm not installed. Run: uv add pymupdf4llm")

class ContentFilter:
    """Filter to identify and skip non-content sections."""
    
    # Patterns for sections to skip
    SKIP_PATTERNS = [
        r"^Table of Contents",
        r"^Contents$",
        r"^\d+\s+Contents",  # "1  Contents"
        r"^Preface",
        r"^Foreword",
        r"^Acknowledgments?",
        r"^About the (Authors|Editors)",
        r"^References",
        r"^Bibliography",
        r"^Index$",
        r"^Appendix [A-Z]",
    ]
    
    @classmethod
    def is_main_content(cls, text: str) -> bool:
        """
        Check if text is main content (not TOC, preface, etc).
        """
        if not text or len(text.strip()) < 50:
            return False
        
        # Check for skip patterns
        for pattern in cls.SKIP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                return False
        
        # If mostly numbers and dots (likely TOC)
        words = text.split()
        if len(words) > 0:
            numeric_ratio = sum(1 for w in words if re.match(r'^\d+\.?$', w)) / len(words)
            if numeric_ratio > 0.3:  # More than 30% numeric
                return False
        
        return True

class MarkdownPDFParser:
    """PDF parser using pymupdf4llm for markdown conversion."""
    
    @staticmethod
    def parse(pdf_path: Path, page_range: dict[str, int] | None = None) -> str:
        """Parse PDF to markdown with structure preservation."""
        # Convert PDF to markdown with optional page range
        if page_range:
            start = page_range.get("start", 1) - 1  # Convert to 0-indexed
            end = page_range.get("end")
            pages = list(range(start, end)) if end else None
            md_text = pymupdf4llm.to_markdown(str(pdf_path), pages=pages)
        else:
            md_text = pymupdf4llm.to_markdown(str(pdf_path))
        
        if isinstance(md_text, list):
            # If pymupdf4llm returns chunks (list[dict]), join them
            return "\n\n".join([chunk.get("text", "") for chunk in md_text if isinstance(chunk, dict)])
            
        return str(md_text)
    
    @staticmethod
    def filter_content(md_text: str) -> str:
        """Light filtering to remove obvious non-content."""
        lines = md_text.split('\n')
        filtered_lines = [line for line in lines if line.strip()]
        return '\n'.join(filtered_lines)

class TextChunker:
    """Smart text chunking with markdown structure awareness."""
    
    @staticmethod
    def chunk(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        """Chunk markdown text respecting structure."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end < len(text):
                # Try to break at markdown header (##, ###)
                header_match = re.search(r'\n#{1,3}\s', text[start:end])
                if header_match and header_match.start() > chunk_size * 0.5:
                    end = start + header_match.start()
                else:
                    # Fall back to sentence boundary
                    last_period = text.rfind('. ', start, end)
                    last_question = text.rfind('? ', start, end)
                    last_exclaim = text.rfind('! ', start, end)
                    
                    sentence_end = max(last_period, last_question, last_exclaim)
                    if sentence_end > start + (chunk_size - 200):
                        end = sentence_end + 2
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - chunk_overlap
        
        return chunks

class FinancialDocumentChunker:
    """Main chunker for financial documents with improved parsing."""
    
    def __init__(self, resource_manager: ResourceManager):
        self.manager = resource_manager
        self.parser = MarkdownPDFParser()
        self.chunker = TextChunker()
    
    def chunk_resource(
        self, 
        resource_id: str, 
        output_dir: Path
    ) -> dict[str, Any]:
        """Chunk a financial document resource."""
        # Get resource and config
        resource = self.manager.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        rag_config = self.manager.get_rag_config(resource_id)
        if not rag_config:
            raise ValueError(f"No RAG config for: {resource_id}")
        
        pdf_path = self.manager.get_resource_path(resource_id)
        if not pdf_path or not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Get page range if specified
        page_range = resource.get("content_pages")
        
        # Parse PDF to markdown with optional page range
        md_text = self.parser.parse(pdf_path, page_range=page_range)
        
        # Filter content
        filtered_text = self.parser.filter_content(md_text)
        
        # Chunk the filtered markdown
        text_chunks = self.chunker.chunk(
            filtered_text,
            rag_config["chunk_size"],
            rag_config["chunk_overlap"]
        )
        
        # Build chunk data
        all_chunks = []
        vector_payload = self.manager.get_vector_payload(resource_id)
        
        for idx, text_content in enumerate(text_chunks):
            chunk_data = {
                "chunk_id": f"{resource_id}_chunk_{idx}",
                "chunk_index": idx,
                "text": text_content,
                "char_count": len(text_content),
                "metadata": vector_payload or {},
                "format": "markdown"
            }
            all_chunks.append(chunk_data)
        
        # Prepare output
        output_data = {
            "resource_id": resource_id,
            "title": resource["title"],
            "total_chunks": len(all_chunks),
            "config": rag_config,
            "parser": "pymupdf4llm",
            "content_filtered": True,
            "chunks": all_chunks
        }
        
        # Save JSON
        output_dir.mkdir(exist_ok=True, parents=True)
        output_json = output_dir / f"{resource_id}_chunks.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        # Save markdown preview
        self._save_preview(output_data, output_dir)
        
        return output_data
    
    def _save_preview(self, output_data: dict, output_dir: Path):
        """Save markdown preview of chunks."""
        resource_id = output_data["resource_id"]
        chunks = output_data["chunks"]
        
        output_md = output_dir / f"{resource_id}_preview.md"
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(f"# Chunking Preview: {output_data['title']}\n\n")
            f.write(f"**Resource ID**: `{resource_id}`\n")
            f.write(f"**Parser**: {output_data['parser']}\n")
            f.write(f"**Content Filtered**: {output_data['content_filtered']}\n")
            f.write(f"**Config**: chunk_size={output_data['config']['chunk_size']}, ")
            f.write(f"chunk_overlap={output_data['config']['chunk_overlap']}\n")
            f.write(f"**Total Chunks**: {len(chunks)}\n\n")
            f.write("---\n\n")
            
            # Show first 10 chunks
            preview_count = min(10, len(chunks))
            for i, chunk in enumerate(chunks[:preview_count]):
                f.write(f"## Chunk {i+1} ({chunk['char_count']} chars)\n\n")
                f.write(f"```markdown\n{chunk['text']}\n```\n\n")
                if i < preview_count - 1:
                    f.write(f"**→ Next chunk overlaps by {output_data['config']['chunk_overlap']} chars**\n\n")
                f.write("---\n\n")
            
            if len(chunks) > preview_count:
                f.write(f"\n*... and {len(chunks) - preview_count} more chunks*\n")
