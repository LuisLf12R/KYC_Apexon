"""
kyc_input_orchestrator.py - REFACTORED
Flexible input pipeline that uses integrated document processing.

Uses:
- document_processor: Wraps execution_engine for KYC
- Handles structured CSV + unstructured documents
- Merges multiple data sources
- Feeds to KYC engine
"""

from pathlib import Path
from typing import Dict, List, Any, Union
import sys
import pandas as pd
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KYCInputOrchestrator:
    """
    Flexible input orchestrator for KYC engine.
    
    Pipeline:
    1. Accept unstructured documents OR structured data
    2. Process documents using integrated document_processor
    3. Merge with existing structured data
    4. Validate and normalize
    5. Feed to KYC engine
    """
    
    def __init__(self, 
                 project_root: Path = None,
                 cache_dir: str = './scripts_cache'):
        """
        Initialize orchestrator.
        
        Args:
            project_root: Root directory (default: current working directory)
            cache_dir: Path to script cache directory
        """
        self.project_root = project_root or Path.cwd()
        self.data_root = self.project_root / 'Data Clean'
        self.cache_dir = cache_dir
        
        self.processed_data = {}
        self.merged_data = {}

        try:
            src_path = str(self.project_root / 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)

            from document_processor import DocumentProcessor
            self.document_processor = DocumentProcessor(cache_dir=cache_dir)
            logger.info(f"KYCInputOrchestrator initialized (cache: {cache_dir})")
        except ImportError as e:
            logger.warning(
                f"DocumentProcessor not available ({e}). "
                "Document folder processing disabled; manifest transform still works."
            )
            self.document_processor = None
    
    def process_input_folder(self, 
                            input_folder: Union[str, Path],
                            doc_type_mapping: Dict[str, str] = None,
                            merge_with_existing: bool = True) -> Dict[str, Any]:
        """
        Process all documents in a folder using integrated extraction pipeline.
        
        Args:
            input_folder: Path to folder with unstructured documents
            doc_type_mapping: Map filename patterns to doc types
            merge_with_existing: Merge with existing Data Clean/ files
        
        Returns:
            Dict with structured data for each document type
        """
        
        input_folder = Path(input_folder)
        
        if not input_folder.exists():
            logger.error(f"Input folder not found: {input_folder}")
            return {}
        
        logger.info(f"[*] Processing documents from {input_folder.name}...")
        
        processed_df = self.document_processor.process_directory(
            input_folder, 
            doc_type_mapping=doc_type_mapping
        )
        
        if processed_df.empty:
            logger.warning(f"No documents processed from {input_folder.name}")
            return {}
        
        exports = self.document_processor.export_to_kyc_format(self.data_root)
        
        self.processed_data = {
            'source': str(input_folder),
            'timestamp': datetime.now().isoformat(),
            'exports': exports,
            'cache_stats': self.document_processor.get_cache_stats(),
        }
        
        if merge_with_existing:
            self._merge_with_existing_data()
        
        return exports
    
    def load_structured_input(self, csv_or_json_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load pre-structured CSV or JSON file directly.
        
        Args:
            csv_or_json_path: Path to CSV or JSON file
        
        Returns:
            DataFrame with loaded data
        """
        
        path = Path(csv_or_json_path)
        
        if not path.exists():
            logger.error(f"File not found: {path}")
            return pd.DataFrame()
        
        logger.info(f"[*] Loading structured data from {path.name}...")
        
        try:
            if path.suffix.lower() == '.csv':
                df = pd.read_csv(path)
            elif path.suffix.lower() == '.jsonl':
                df = pd.read_json(path, lines=True)
            elif path.suffix.lower() == '.json':
                df = pd.read_json(path)
            else:
                logger.error(f"Unsupported format: {path.suffix}")
                return pd.DataFrame()
            
            logger.info(f"[OK] Loaded {len(df)} records from {path.name}")
            return df
        
        except Exception as e:
            logger.error(f"Error loading {path.name}: {e}")
            return pd.DataFrame()
    
    def merge_multiple_sources(self, 
                              documents_folder: Union[str, Path] = None,
                              doc_type_mapping: Dict[str, str] = None,
                              customers_csv: Union[str, Path] = None,
                              screenings_csv: Union[str, Path] = None,
                              transactions_csv: Union[str, Path] = None,
                              ubo_json: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Merge data from multiple sources (documents + CSVs + JSON).
        
        Flexible: Any source can be None - only processes what's provided.
        
        Args:
            documents_folder: Folder with unstructured documents
            doc_type_mapping: Map filename patterns to doc types
            customers_csv: Path to customers CSV
            screenings_csv: Path to screenings CSV
            transactions_csv: Path to transactions CSV
            ubo_json: Path to UBO JSON
        
        Returns:
            Merged data dict ready for KYC engine
        """
        
        logger.info("[*] Merging multiple data sources...")
        
        merged = {}
        
        if documents_folder:
            doc_exports = self.process_input_folder(
                documents_folder, 
                doc_type_mapping=doc_type_mapping,
                merge_with_existing=False
            )
            for doc_type, file_path in doc_exports.items():
                df = pd.read_csv(file_path)
                merged[doc_type] = df
                logger.info(f"Merged {len(df)} {doc_type} records")
        
        if customers_csv:
            df = self.load_structured_input(customers_csv)
            if not df.empty:
                merged['customers'] = df
                logger.info(f"Merged {len(df)} customer records")
        
        if screenings_csv:
            df = self.load_structured_input(screenings_csv)
            if not df.empty:
                merged['screenings'] = df
                logger.info(f"Merged {len(df)} screening records")
        
        if transactions_csv:
            df = self.load_structured_input(transactions_csv)
            if not df.empty:
                merged['transactions'] = df
                logger.info(f"Merged {len(df)} transaction records")
        
        if ubo_json:
            data = self.load_structured_input(ubo_json)
            if isinstance(data, pd.DataFrame):
                merged['ubo'] = data.to_dict('records')
            else:
                merged['ubo'] = data
            logger.info(f"Merged UBO records")
        
        self.merged_data = merged
        
        logger.info(f"[OK] Merged {len(merged)} data sources")
        
        return merged
    
    def feed_to_kyc_engine(self, data: Dict[str, Any] = None):
        """
        Feed merged data to KYC compliance engine.
        
        Args:
            data: Dict with structured data. If None, uses self.merged_data
        
        Returns:
            KYCComplianceEngine instance ready to evaluate
        """
        
        if data is None:
            data = self.merged_data
        
        if not data:
            logger.error("No data to feed to KYC engine")
            return None
        
        try:
            import sys
            src_path = str(self.project_root / 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            
            from kyc_engine import KYCComplianceEngine
        except ImportError:
            logger.error("KYCComplianceEngine not found. Ensure kyc_engine.py is in src/")
            return None
        
        engine = KYCComplianceEngine(self.project_root)
        
        engine.data = self._convert_to_engine_format(data)
        
        logger.info(f"[OK] Data fed to KYC engine")
        
        return engine
    
    def auto_pipeline(self, 
                     input_path: Union[str, Path],
                     doc_type_mapping: Dict[str, str] = None,
                     evaluate: bool = True) -> Dict[str, Any]:
        """
        Full automated pipeline: Input -> Process -> Merge -> Evaluate.
        
        Detects input type and runs complete workflow.
        
        Args:
            input_path: Can be folder (documents) or file (CSV/JSON)
            doc_type_mapping: Map filename patterns to doc types
            evaluate: Also run KYC evaluation if True
        
        Returns:
            Results dict with processed data and evaluation
        """
        
        input_path = Path(input_path)
        
        logger.info("[*] Starting automated KYC input pipeline...")
        
        if input_path.is_dir():
            logger.info(f"Detected folder input: {input_path.name}")
            data = self.process_input_folder(
                input_path, 
                doc_type_mapping=doc_type_mapping,
                merge_with_existing=True
            )
        else:
            logger.info(f"Detected file input: {input_path.name}")
            df = self.load_structured_input(input_path)
            data = {input_path.stem: df}
        
        if not data:
            logger.error("Pipeline failed: No data processed")
            return {
                'pipeline_status': 'FAILED',
                'error': 'No data processed',
            }
        
        engine = self.feed_to_kyc_engine()
        
        results = {
            'pipeline_status': 'SUCCESS',
            'timestamp': datetime.now().isoformat(),
            'processed_data': data,
            'engine_ready': engine is not None,
            'cache_stats': self.document_processor.get_cache_stats(),
        }
        
        if evaluate and engine and engine.data:
            logger.info("[*] Running KYC evaluation...")
            try:
                customers = engine.data.get('customers', pd.DataFrame())
                if not customers.empty:
                    sample_ids = customers['customer_id'].values[:10]
                    report = engine.generate_compliance_report(sample_ids)
                    results['evaluation_report'] = {
                        'customers_evaluated': report['customers_evaluated'],
                        'compliance_rate': report['summary']['overall_compliance_rate'],
                        'avg_score': report['avg_compliance_score'],
                        'dimension_rates': report['dimension_pass_rates'],
                    }
                    logger.info(f"[OK] Evaluated {report['customers_evaluated']} customers")
            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
        
        return results
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics from document extraction."""
        return self.document_processor.get_cache_stats()
    
    def list_cached_scripts(self) -> List[Dict]:
        """List cached extraction scripts."""
        return self.document_processor.list_cached_scripts()
    
    def _is_scenario_manifest(self, df: pd.DataFrame) -> bool:
        """Return True if the DataFrame looks like a generated scenario manifest."""
        return "scenario_id" in df.columns or "archetype_id" in df.columns

    def _normalize_scenario_manifest(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Transform a flat scenario manifest DataFrame into engine-ready tables.
        Routes through ExecutionEngine → Claude generates/caches transform script.
        Returns {table_name: DataFrame}.
        """
        TARGET_SCHEMA = {
            "customers": [
                "customer_id", "entity_type", "jurisdiction",
                "risk_rating", "account_open_date", "last_kyc_review_date",
            ],
            "screenings": [
                "customer_id", "screening_date", "screening_result",
                "match_name", "list_reference", "hit_status",
            ],
            "id_verifications": [
                "customer_id", "document_type", "document_number",
                "issue_date", "expiry_date", "verification_date", "document_status",
            ],
            "documents": [
                "customer_id", "document_type", "issue_date",
                "expiry_date", "document_category",
            ],
        }

        rows = df.to_dict(orient="records")

        # Import lazily to avoid circular imports and OCR dependency at import time
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        from llm_integration.execution_engine import ExecutionEngine

        engine = ExecutionEngine(cache_dir=self.cache_dir)
        result = engine.transform_structured_data(
            rows=rows,
            doc_type="scenario_manifest_to_kyc_tables",
            target_schema=TARGET_SCHEMA,
        )

        logger.info("Schema transform returned tables: %s", list(result.keys()))
        return {
            table: pd.DataFrame(table_rows)
            for table, table_rows in result.items()
            if table_rows
        }

    def _convert_to_engine_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert merged data to KYC engine format.
        Detects scenario manifests and normalises them via the LLM transform pipeline.
        """
        engine_data = {}

        for key, value in data.items():
            if isinstance(value, pd.DataFrame) and self._is_scenario_manifest(value):
                logger.info(
                    "Detected scenario manifest in '%s' — normalising via LLM pipeline", key
                )
                normalized = self._normalize_scenario_manifest(value)
                engine_data.update(normalized)
            elif isinstance(value, str) and Path(value).exists():
                engine_data[key] = pd.read_csv(value)
            elif isinstance(value, (pd.DataFrame, list)):
                engine_data[key] = value

        return engine_data

    def _merge_with_existing_data(self):
        """
        Merge processed document data with existing Data Clean/ files.
        """
        
        logger.info("[*] Merging with existing structured data...")
        
        for csv_file in self.data_root.glob('*.csv'):
            if 'extracted' not in csv_file.name:
                df = pd.read_csv(csv_file)
                key = csv_file.stem
                self.merged_data[key] = df
                logger.info(f"Merged existing: {key} ({len(df)} records)")
    
    def export_summary(self, output_file: Union[str, Path] = None) -> str:
        """
        Export orchestration summary for audit.
        
        Args:
            output_file: Path to save summary JSON
        
        Returns:
            Summary as JSON string
        """
        
        summary = {
            'orchestration_timestamp': datetime.now().isoformat(),
            'processed_data': self.processed_data,
            'merged_sources': {k: len(v) if isinstance(v, (pd.DataFrame, list)) else 'unknown' 
                              for k, v in self.merged_data.items()},
            'cache_stats': self.get_extraction_stats(),
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Summary exported to {output_file}")
        
        return json.dumps(summary, indent=2)
