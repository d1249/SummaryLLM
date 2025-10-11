"""
JSON output assembler for digest data.
"""
import json
from pathlib import Path
from typing import Dict, Any
import structlog

from digest_core.llm.schemas import Digest

logger = structlog.get_logger()


class JSONAssembler:
    """Assemble digest data into JSON output."""
    
    def __init__(self):
        self.indent = 2
        self.ensure_ascii = False
    
    def write_digest(self, digest_data: Digest, output_path: Path) -> None:
        """Write digest data to JSON file."""
        logger.info("Writing JSON digest", output_path=str(output_path))
        
        try:
            # Convert to dict for JSON serialization
            digest_dict = self._digest_to_dict(digest_data)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(digest_dict, f, indent=self.indent, ensure_ascii=self.ensure_ascii)
            
            logger.info("JSON digest written successfully", 
                       output_path=str(output_path),
                       sections_count=len(digest_data.sections))
            
        except Exception as e:
            logger.error("Failed to write JSON digest", 
                        output_path=str(output_path),
                        error=str(e))
            raise
    
    def _digest_to_dict(self, digest_data: Digest) -> Dict[str, Any]:
        """Convert Digest object to dictionary."""
        return {
            "schema_version": digest_data.schema_version,
            "prompt_version": digest_data.prompt_version,
            "digest_date": digest_data.digest_date,
            "trace_id": digest_data.trace_id,
            "sections": [
                {
                    "title": section.title,
                    "items": [
                        {
                            "title": item.title,
                            "owners_masked": item.owners_masked,
                            "due": item.due,
                            "evidence_id": item.evidence_id,
                            "confidence": item.confidence,
                            "source_ref": item.source_ref
                        }
                        for item in section.items
                    ]
                }
                for section in digest_data.sections
            ]
        }
    
    def read_digest(self, input_path: Path) -> Digest:
        """Read digest data from JSON file."""
        logger.info("Reading JSON digest", input_path=str(input_path))
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                digest_dict = json.load(f)
            
            # Convert to Digest object
            digest_data = self._dict_to_digest(digest_dict)
            
            logger.info("JSON digest read successfully", 
                       input_path=str(input_path),
                       sections_count=len(digest_data.sections))
            
            return digest_data
            
        except Exception as e:
            logger.error("Failed to read JSON digest", 
                        input_path=str(input_path),
                        error=str(e))
            raise
    
    def _dict_to_digest(self, digest_dict: Dict[str, Any]) -> Digest:
        """Convert dictionary to Digest object."""
        from digest_core.llm.schemas import Section, Item
        
        sections = []
        for section_dict in digest_dict.get("sections", []):
            items = []
            for item_dict in section_dict.get("items", []):
                item = Item(
                    title=item_dict["title"],
                    owners_masked=item_dict.get("owners_masked", []),
                    due=item_dict.get("due"),
                    evidence_id=item_dict["evidence_id"],
                    confidence=item_dict["confidence"],
                    source_ref=item_dict["source_ref"]
                )
                items.append(item)
            
            section = Section(
                title=section_dict["title"],
                items=items
            )
            sections.append(section)
        
        return Digest(
            schema_version=digest_dict.get("schema_version", "1.0"),
            prompt_version=digest_dict.get("prompt_version", "extract_actions.v1"),
            digest_date=digest_dict["digest_date"],
            trace_id=digest_dict["trace_id"],
            sections=sections
        )
    
    def validate_digest(self, digest_data: Digest) -> bool:
        """Validate digest data structure."""
        try:
            # Check required fields
            if not digest_data.digest_date or not digest_data.trace_id:
                return False
            
            # Check sections
            for section in digest_data.sections:
                if not section.title or not isinstance(section.items, list):
                    return False
                
                # Check items
                for item in section.items:
                    if not item.title or not item.evidence_id:
                        return False
                    
                    if not isinstance(item.confidence, (int, float)) or not (0 <= item.confidence <= 1):
                        return False
                    
                    if not isinstance(item.source_ref, dict) or "type" not in item.source_ref:
                        return False
            
            return True
            
        except Exception as e:
            logger.warning("Digest validation failed", error=str(e))
            return False
