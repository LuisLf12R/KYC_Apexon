"""
document_processor.py - REFACTORED
Bridges unstructured documents to KYC engine.

Uses:
- llm_integration.execution_engine: Full OCR -> Cache -> Generate -> Execute pipeline
- Converts extracted data to KYC-compatible CSV/JSON

Philosophy: Leverage existing extraction pipeline, add KYC-specific logic
"""

from pathlib import Path
from typing import Dict, List, Any, Union
import pandas as pd
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Document processor for KYC compliance.
    
    Pipeline:
    1. Accept unstructured documents (PDF, images, etc)
    2. Use execution_engine for OCR + LLM extraction
    3. Map extracted fields to KYC schemas
    4. Validate against KYC requirements
    5. Output to KYC-compatible CSV/JSON
    """
    
    SUPPORTED_FORMATS = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.docx', '.txt']
    
    # Map document types to KYC schemas
    DOCUMENT_TYPE_MAPPINGS = {
        'identity_document': 'id_verifications',
        'kyc_handwritten': 'id_verifications',
        'passport': 'id_verifications',
        'drivers_license': 'id_verifications',
        'national_id': 'id_verifications',
        'proof_of_address': 'proof_of_address',
        'bank_statement': 'proof_of_address',
        'utility_bill': 'proof_of_address',
        'corporate_document': 'corporate_docs',
        'beneficial_owner': 'beneficial_owners',
        'ubo_declaration': 'beneficial_owners',
    }
    
    # KYC output schemas
    KYC_SCHEMAS = {
        'id_verifications': {
            'customer_id': str,
            'document_type': str,
            'document_number': str,
            'name': str,
            'dob': str,
            'issue_date': str,
            'expiry_date': str,
            'nationality': str,
        },
        'proof_of_address': {
            'customer_id': str,
            'document_type': str,
            'customer_name': str,
            'address': str,
            'city': str,
            'postal_code': str,
            'country': str,
            'issue_date': str,
        },
        'beneficial_owners': {
            'customer_id': str,
            'ubo_name': str,
            'ownership_percentage': float,
            'nationality': str,
            'date_identified': str,
        },
    }
    
    def __init__(self, 
                 cache_dir: str = './scripts_cache',
                 use_cache: bool = True):
        """
        Initialize document processor.
        
        Args:
            cache_dir: Path to script cache directory
            use_cache: Use cached extraction scripts if available
        """
        try:
            import sys
            from pathlib import Path
            
            project_root = Path(__file__).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from llm_integration.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(cache_dir=cache_dir)
            self.use_cache = use_cache
            self.processed_documents = []
            logger.info(f"DocumentProcessor initialized (cache_dir: {cache_dir})")
        except ImportError as e:
            logger.error(f"Failed to import execution_engine: {e}")
            raise RuntimeError("llm_integration module required. Ensure it's in your project root.")
    
    def process_file(self, 
                    file_path: Union[str, Path], 
                    doc_type: str = None,
                    customer_id: str = None) -> Dict[str, Any]:
        """
        Process a single unstructured document.
        
        Args:
            file_path: Path to document file
            doc_type: Document type (identity_document, proof_of_address, etc)
                     If None, LLM will attempt to detect
            customer_id: Customer ID to associate with document
        
        Returns:
            Structured data dict matching KYC schema
        """
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            logger.error(f"Unsupported format: {file_path.suffix}")
            return None
        
        logger.info(f"Processing: {file_path.name} (type: {doc_type})")
        
        try:
            extraction_result = self.execution_engine.extract_from_image(
                str(file_path),
                doc_type=doc_type or 'unknown_document'
            )
            
            logger.info(f"Extraction complete (source: {extraction_result.source}, "
                       f"time: {extraction_result.execution_time_seconds:.2f}s)")
            
            extracted_data = extraction_result.extracted_data
            
            structured_data = self._map_to_kyc_schema(
                extracted_data, 
                doc_type, 
                customer_id
            )
            
            if structured_data:
                self.processed_documents.append({
                    'file': file_path.name,
                    'doc_type': doc_type or 'unknown',
                    'customer_id': customer_id,
                    'timestamp': datetime.now().isoformat(),
                    'extraction_source': extraction_result.source,
                    'script_id': extraction_result.script_id,
                    'ocr_confidence': extraction_result.ocr_confidence,
                    'script_confidence': extraction_result.script_confidence,
                    'execution_time': extraction_result.execution_time_seconds,
                    'data': structured_data,
                    'warnings': extraction_result.warnings,
                })
                
                logger.info(f"[OK] Structured data created for {file_path.name}")
                return structured_data
            else:
                logger.warning(f"Failed to structure extracted data")
                return None
        
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_directory(self, 
                         directory: Union[str, Path],
                         doc_type_mapping: Dict[str, str] = None) -> pd.DataFrame:
        """
        Process all documents in a directory.
        
        Args:
            directory: Path to directory containing documents
            doc_type_mapping: Dict mapping filename patterns to doc types
                            (e.g., {'identity_*': 'identity_document'})
        
        Returns:
            DataFrame with structured data from all documents
        """
        
        directory = Path(directory)
        results = []
        
        for file_path in sorted(directory.glob('*')):
            if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                
                detected_doc_type = None
                if doc_type_mapping:
                    for pattern, dtype in doc_type_mapping.items():
                        if pattern in file_path.name:
                            detected_doc_type = dtype
                            break
                
                result = self.process_file(file_path, doc_type=detected_doc_type)
                if result:
                    results.append(result)
        
        if results:
            df = pd.DataFrame(results)
            logger.info(f"Processed {len(results)} documents from {directory.name}")
            return df
        else:
            logger.warning(f"No documents processed from {directory.name}")
            return pd.DataFrame()
    
    def export_to_kyc_format(self, output_dir: Path = None) -> Dict[str, str]:
        """
        Export processed documents to KYC-compatible CSV/JSON.
        
        Organizes by schema type:
        - id_verifications_extracted.csv
        - proof_of_address_extracted.csv
        - beneficial_owners_extracted.csv
        
        Args:
            output_dir: Directory to save exports (default: Data Clean/)
        
        Returns:
            Dict with file paths of exports
        """
        
        if not self.processed_documents:
            logger.warning("No documents to export")
            return {}
        
        output_dir = output_dir or Path.cwd() / 'Data Clean'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exports = {}
        
        # Group by KYC schema type
        grouped = self._group_by_schema_type()
        
        for schema_type, documents in grouped.items():
            if documents:
                df = pd.DataFrame([d['data'] for d in documents])
                
                filename = f"{schema_type}_extracted.csv"
                path = output_dir / filename
                df.to_csv(path, index=False)
                exports[schema_type] = str(path)
                
                logger.info(f"Exported {len(df)} {schema_type} records to {filename}")
        
        metadata_path = output_dir / 'extraction_metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump({
                'extraction_timestamp': datetime.now().isoformat(),
                'total_documents': len(self.processed_documents),
                'exports': exports,
                'documents_processed': [
                    {
                        'file': d['file'],
                        'doc_type': d['doc_type'],
                        'extraction_source': d['extraction_source'],
                        'script_id': d['script_id'],
                        'ocr_confidence': d['ocr_confidence'],
                        'script_confidence': d['script_confidence'],
                    }
                    for d in self.processed_documents
                ]
            }, f, indent=2)
        
        logger.info(f"Metadata exported to extraction_metadata.json")
        
        return exports
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics from extraction script cache."""
        return self.execution_engine.get_cache_stats()
    
    def list_cached_scripts(self) -> List[Dict]:
        """List all cached extraction scripts."""
        return self.execution_engine.list_cached_scripts()
    
    def _map_to_kyc_schema(self, 
                         extracted_data: Dict, 
                         doc_type: str,
                         customer_id: str = None) -> Dict[str, Any]:
        """
        Map extracted fields to KYC schema.
        
        Args:
            extracted_data: Raw extracted data from LLM
            doc_type: Document type
            customer_id: Customer ID to add to output
        
        Returns:
            Data structured according to KYC schema
        """
        
        if not doc_type:
            doc_type = self._detect_doc_type(extracted_data)
        
        schema_type = self.DOCUMENT_TYPE_MAPPINGS.get(
            doc_type.lower(), 
            'unknown'
        )
        
        if schema_type == 'unknown':
            logger.warning(f"Unknown document type: {doc_type}")
            return None
        
        schema = self.KYC_SCHEMAS.get(schema_type, {})
        
        structured = {'document_type': doc_type}
        if customer_id:
            structured['customer_id'] = customer_id
        
        for field, field_type in schema.items():
            if field in ['customer_id', 'document_type']:
                continue
            
            if field in extracted_data:
                value = extracted_data[field]
                try:
                    if field_type == float:
                        structured[field] = float(value)
                    else:
                        structured[field] = str(value)
                except (ValueError, TypeError):
                    structured[field] = None
            else:
                structured[field] = None
        
        return structured
    
    def _detect_doc_type(self, extracted_data: Dict) -> str:
        """
        Detect document type from extracted fields.
        
        Simple heuristic: look for field patterns.
        """
        
        keys = set(extracted_data.keys())
        
        if {'account_number', 'bank_name', 'balance'} & keys:
            return 'bank_statement'
        
        if {'document_number', 'dob', 'nationality'} & keys:
            return 'identity_document'
        
        if {'ownership_percentage', 'ubo_name'} & keys:
            return 'beneficial_owner'
        
        if {'address', 'postal_code'} & keys:
            return 'proof_of_address'
        
        return 'unknown_document'
    
    def _group_by_schema_type(self) -> Dict[str, List]:
        """Group processed documents by KYC schema type."""
        
        grouped = {}
        
        for doc in self.processed_documents:
            doc_type = doc['doc_type']
            schema_type = self.DOCUMENT_TYPE_MAPPINGS.get(
                doc_type.lower(), 
                'unknown'
            )
            
            if schema_type not in grouped:
                grouped[schema_type] = []
            
            grouped[schema_type].append(doc)
        
        return grouped


def main():
    """Example usage."""
    
    processor = DocumentProcessor(use_cache=True)
    
    input_dir = Path.cwd() / 'Documents'
    
    if input_dir.exists():
        type_mapping = {
            'passport': 'passport',
            'statement': 'bank_statement',
            'utility': 'utility_bill',
            'ubo': 'beneficial_owner',
        }
        
        df = processor.process_directory(input_dir, doc_type_mapping=type_mapping)
        
        if not df.empty:
            exports = processor.export_to_kyc_format()
            
            print(f"\nProcessed {len(processor.processed_documents)} documents")
            print(f"Exports: {exports}")
            
            stats = processor.get_cache_stats()
            print(f"\nCache stats: {stats}")
    else:
        print(f"Documents directory not found: {input_dir}")


if __name__ == '__main__':
    main()
