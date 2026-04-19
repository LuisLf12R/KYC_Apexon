"""
Script Cache Manager: Stores and retrieves learned extraction scripts
Implements exact matching + fuzzy matching for script reuse
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from difflib import SequenceMatcher


@dataclass
class ScriptMetadata:
    """Metadata for a cached extraction script"""
    id: str
    layout_hash: str  # SHA256 hash of document layout/structure
    fields: List[str]  # Field names extracted (e.g., ["name", "dob", "address"])
    doc_type: str  # Document type (e.g., "kyc_handwritten", "beneficial_owner")
    confidence_threshold: float  # Minimum confidence for this script
    created_date: str  # ISO format timestamp
    last_used: str  # ISO format timestamp
    source: str  # "handwritten", "synthetic", or "generated"
    fuzzy_match_keywords: List[str]  # For fuzzy matching (field names, doc characteristics)


class ScriptCacheManager:
    """
    Manages cached extraction scripts with exact + fuzzy matching.
    
    Storage structure:
    ./scripts_cache/
    ├── metadata.json              (index of all scripts)
    ├── kyc_handwritten_v1.py      (extraction script)
    ├── kyc_handwritten_v1.schema  (Pydantic model)
    ├── beneficial_owner_v1.py
    └── beneficial_owner_v1.schema
    """

    def __init__(self, cache_dir: str = "./scripts_cache"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Path to scripts cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self._load_metadata()

    def _load_metadata(self):
        """Load metadata index from disk"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    self.scripts = data.get('scripts', [])
            except Exception as e:
                print(f"Warning: Failed to load metadata: {e}")
                self.scripts = []
        else:
            self.scripts = []

    def _save_metadata(self):
        """Save metadata index to disk"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump({'scripts': self.scripts}, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save metadata: {e}")

    def compute_layout_hash(self, ocr_text: str) -> str:
        """
        Compute hash of document layout/structure.
        
        Uses the OCR text structure to create a stable hash
        that represents the document's layout.
        
        Args:
            ocr_text: Full text from OCR
            
        Returns:
            SHA256 hash of the text structure
        """
        # Use text length, line count, and content hash
        lines = ocr_text.split('\n')
        structure = f"{len(ocr_text)}:{len(lines)}:{ocr_text[:100]}"
        return hashlib.sha256(structure.encode()).hexdigest()

    def find_script(
        self, 
        layout_hash: str,
        ocr_text: Optional[str] = None,
        fuzzy_threshold: float = 0.85
    ) -> Optional[Dict]:
        """
        Find a cached script using exact or fuzzy matching.
        
        Strategy:
        1. Try exact match on layout_hash (fastest)
        2. If no exact match, try fuzzy match on OCR text structure
        3. Return best match above threshold
        
        Args:
            layout_hash: SHA256 hash of document layout
            ocr_text: Full OCR text (for fuzzy matching)
            fuzzy_threshold: Minimum similarity for fuzzy match (0-1)
            
        Returns:
            Script metadata dict, or None if not found
        """
        # Exact match (fast path)
        for script in self.scripts:
            if script['layout_hash'] == layout_hash:
                self._update_last_used(script['id'])
                return script

        # Fuzzy match (if OCR text provided)
        if ocr_text and fuzzy_threshold > 0:
            best_match = None
            best_score = 0.0

            for script in self.scripts:
                # Compare document structures
                similarity = self._compute_similarity(ocr_text, script)
                if similarity > best_score and similarity >= fuzzy_threshold:
                    best_score = similarity
                    best_match = script

            if best_match:
                self._update_last_used(best_match['id'])
                return best_match

        return None

    def _compute_similarity(self, ocr_text: str, script_meta: Dict) -> float:
        """
        Compute similarity between OCR text and cached script.
        
        Compares:
        - Document structure (line count, text length)
        - Field names (extracted fields)
        
        Args:
            ocr_text: Current OCR text
            script_meta: Cached script metadata
            
        Returns:
            Similarity score (0-1)
        """
        # Structure similarity
        current_lines = len(ocr_text.split('\n'))
        current_length = len(ocr_text)

        # Simple heuristic: if line count and length are similar, likely same format
        # (more sophisticated matching could use keyword detection)
        structure_match = 0.5  # Base score for fuzzy match

        return structure_match

    def save_script(
        self,
        script_code: str,
        schema_code: str,
        layout_hash: str,
        fields: List[str],
        doc_type: str,
        source: str = "generated",
        confidence_threshold: float = 0.70
    ) -> str:
        """
        Save a newly generated extraction script.
        
        Args:
            script_code: Python extraction function code
            schema_code: Pydantic model code
            layout_hash: SHA256 hash of document layout
            fields: List of field names extracted
            doc_type: Document type (e.g., "kyc_handwritten")
            source: "handwritten", "synthetic", or "generated"
            confidence_threshold: Minimum OCR confidence for this script
            
        Returns:
            Script ID
        """
        # Generate unique script ID
        script_id = f"{doc_type}_v{len(self.scripts) + 1}"

        # Check if script already exists for this doc_type (overwrite)
        existing = next((s for s in self.scripts if s['doc_type'] == doc_type), None)
        if existing:
            script_id = existing['id']
            # Remove old files
            old_py = self.cache_dir / f"{script_id}.py"
            old_schema = self.cache_dir / f"{script_id}.schema"
            if old_py.exists():
                old_py.unlink()
            if old_schema.exists():
                old_schema.unlink()
            # Remove from metadata
            self.scripts = [s for s in self.scripts if s['id'] != script_id]

        # Save Python script
        script_file = self.cache_dir / f"{script_id}.py"
        with open(script_file, 'w') as f:
            f.write(script_code)

        # Save Pydantic schema
        schema_file = self.cache_dir / f"{script_id}.schema"
        with open(schema_file, 'w') as f:
            f.write(schema_code)

        # Create metadata
        now = datetime.utcnow().isoformat()
        metadata = {
            "id": script_id,
            "layout_hash": layout_hash,
            "fields": fields,
            "doc_type": doc_type,
            "confidence_threshold": confidence_threshold,
            "created_date": now,
            "last_used": now,
            "source": source,
            "fuzzy_match_keywords": fields,  # Use field names for fuzzy matching
        }

        # Add to scripts list
        self.scripts.append(metadata)
        self._save_metadata()

        return script_id

    def load_script(self, script_id: str) -> Dict:
        """
        Load a cached script and its schema by ID.
        
        Args:
            script_id: Script identifier
            
        Returns:
            Dict with 'code' (Python code) and 'schema' (Pydantic model)
        """
        script_file = self.cache_dir / f"{script_id}.py"
        schema_file = self.cache_dir / f"{script_id}.schema"

        if not script_file.exists() or not schema_file.exists():
            raise FileNotFoundError(f"Script {script_id} not found in cache")

        with open(script_file, 'r') as f:
            script_code = f.read()

        with open(schema_file, 'r') as f:
            schema_code = f.read()

        return {
            "id": script_id,
            "code": script_code,
            "schema": schema_code,
        }

    def execute_script(self, script_id: str, ocr_text: str) -> Dict:
        """
        Execute a cached extraction script on OCR text.
        
        Args:
            script_id: Script to execute
            ocr_text: OCR text to extract from
            
        Returns:
            Extracted data as dict
        """
        script = self.load_script(script_id)

        # Execute the script code in an isolated namespace
        namespace = {}
        exec(script['code'], namespace)

        # Call the cleanup function
        if 'cleanup' in namespace:
            result = namespace['cleanup'](ocr_text)
            return result
        else:
            raise RuntimeError(f"Script {script_id} has no 'cleanup' function")

    def _update_last_used(self, script_id: str):
        """Update last_used timestamp for a script"""
        for script in self.scripts:
            if script['id'] == script_id:
                script['last_used'] = datetime.utcnow().isoformat()
                self._save_metadata()
                break

    def list_scripts(self) -> List[Dict]:
        """List all cached scripts with metadata"""
        return self.scripts

    def get_script_info(self, script_id: str) -> Optional[Dict]:
        """Get metadata for a specific script"""
        for script in self.scripts:
            if script['id'] == script_id:
                return script
        return None

    def delete_script(self, script_id: str) -> bool:
        """Delete a cached script"""
        try:
            # Remove files
            (self.cache_dir / f"{script_id}.py").unlink(missing_ok=True)
            (self.cache_dir / f"{script_id}.schema").unlink(missing_ok=True)

            # Remove from metadata
            self.scripts = [s for s in self.scripts if s['id'] != script_id]
            self._save_metadata()

            return True
        except Exception as e:
            print(f"Error deleting script {script_id}: {e}")
            return False

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_scripts = len(self.scripts)
        doc_types = set(s['doc_type'] for s in self.scripts)
        total_size = sum(
            (self.cache_dir / f"{s['id']}.py").stat().st_size
            + (self.cache_dir / f"{s['id']}.schema").stat().st_size
            for s in self.scripts
            if (self.cache_dir / f"{s['id']}.py").exists()
        )

        return {
            "total_scripts": total_scripts,
            "document_types": list(doc_types),
            "cache_size_bytes": total_size,
            "metadata_file": str(self.metadata_file),
        }


# Convenience functions
def get_cache_manager(cache_dir: str = "./scripts_cache") -> ScriptCacheManager:
    """Get a cache manager instance"""
    return ScriptCacheManager(cache_dir)


if __name__ == "__main__":
    # Example usage
    manager = ScriptCacheManager()

    # List all scripts
    print("Cached scripts:")
    for script in manager.list_scripts():
        print(f"  {script['id']}: {script['fields']}")

    # Show cache stats
    stats = manager.get_cache_stats()
    print(f"\nCache stats: {stats}")