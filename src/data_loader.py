"""
data_loader.py - ENHANCED
Load data WITH validation enabled.

Philosophy: Report all issues transparently.
- Validate every dataset
- Log all findings
- DO NOT auto-fix
- Audit trail visible
"""

from pathlib import Path
from typing import Dict, Tuple
import pandas as pd
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Data loader with ENABLED validation.
    
    Reports data quality issues without masking them.
    This ensures compliance teams see exactly what's wrong.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.data_root = self.project_root / 'Data Clean'
        self._cache = {}
        self.validation_report = {}
        logger.info(f"DataLoader initialized for {self.project_root}")
    
    def load_all(self) -> Dict:
        """Load all datasets with validation enabled."""
        
        logger.info("[*] Loading all datasets with validation...")
        
        data = {
            'customers': self.load_customers(),
            'id_verifications': self.load_id_verifications(),
            'documents': self.load_documents(),
            'screenings': self.load_screenings(),
            'transactions': self.load_transactions(),
            'ubo': self.load_ubo(),
            'regulatory_rules': self.load_regulatory_rules(),
        }
        
        # Print validation summary
        self._print_validation_summary()
        
        return data
    
    def load_customers(self) -> pd.DataFrame:
        """Load customers with validation."""
        if 'customers' in self._cache:
            return self._cache['customers']
        
        logger.info("Loading customers_clean.csv...")
        df = pd.read_csv(self.data_root / 'customers_clean.csv')
        df = self._parse_dates(df, {'account_open_date', 'last_kyc_review_date'})
        
        # VALIDATE (report, DO NOT fix)
        self._validate_and_report(
            df, 
            'customers',
            required_fields=['customer_id', 'entity_type', 'jurisdiction', 'risk_rating'],
            optional_fields=['account_open_date', 'last_kyc_review_date', 'country_of_origin']
        )
        
        self._cache['customers'] = df
        logger.info(f"[OK] Loaded {len(df):,} customer records")
        return df
    
    def load_id_verifications(self) -> pd.DataFrame:
        """Load identity verifications with validation."""
        if 'id_verifications' in self._cache:
            return self._cache['id_verifications']
        
        logger.info("Loading id_verifications_clean.csv...")
        df = pd.read_csv(self.data_root / 'id_verifications_clean.csv')
        df = self._parse_dates(df, {'issue_date', 'expiry_date', 'verification_date'})
        
        # VALIDATE (report, DO NOT fix)
        self._validate_and_report(
            df,
            'id_verifications',
            required_fields=['customer_id', 'document_type', 'issue_date', 'expiry_date'],
            optional_fields=['verification_date', 'document_status']
        )
        
        self._cache['id_verifications'] = df
        logger.info(f"[OK] Loaded {len(df):,} ID verification records")
        return df
    
    def load_documents(self) -> pd.DataFrame:
        """Load documents with validation."""
        if 'documents' in self._cache:
            return self._cache['documents']
        
        logger.info("Loading documents_clean.csv...")
        df = pd.read_csv(self.data_root / 'documents_clean.csv')
        df = self._parse_dates(df, {'issue_date', 'expiry_date'})
        
        # VALIDATE (report, DO NOT fix)
        self._validate_and_report(
            df,
            'documents',
            required_fields=['customer_id', 'document_type'],
            optional_fields=['issue_date', 'expiry_date', 'document_category']
        )
        
        self._cache['documents'] = df
        logger.info(f"[OK] Loaded {len(df):,} document records")
        return df
    
    def load_screenings(self) -> pd.DataFrame:
        """Load screening records with validation."""
        if 'screenings' in self._cache:
            return self._cache['screenings']
        
        logger.info("Loading screenings_clean.csv...")
        df = pd.read_csv(self.data_root / 'screenings_clean.csv')
        df = self._parse_dates(df, {'screening_date'})
        
        # VALIDATE (report, DO NOT fix)
        self._validate_and_report(
            df,
            'screenings',
            required_fields=['customer_id', 'screening_date', 'screening_result'],
            optional_fields=['match_name', 'list_reference', 'hit_status']
        )
        
        self._cache['screenings'] = df
        logger.info(f"[OK] Loaded {len(df):,} screening records")
        return df
    
    def load_transactions(self) -> pd.DataFrame:
        """Load transaction records with validation."""
        if 'transactions' in self._cache:
            return self._cache['transactions']
        
        logger.info("Loading transactions_clean.csv...")
        df = pd.read_csv(self.data_root / 'transactions_clean.csv')
        df = self._parse_dates(df, {'last_txn_date'})
        
        # VALIDATE (report, DO NOT fix)
        self._validate_and_report(
            df,
            'transactions',
            required_fields=['customer_id'],
            optional_fields=['last_txn_date', 'txn_count', 'total_volume']
        )
        
        self._cache['transactions'] = df
        logger.info(f"[OK] Loaded {len(df):,} transaction records")
        return df
    
    def load_ubo(self) -> list:
        """Load UBO records with validation."""
        if 'ubo' in self._cache:
            return self._cache['ubo']
        
        logger.info("Loading ubo.json...")
        with open(self.project_root / 'Data Raw' / 'ubo.json') as f:
            data = json.load(f)
        
        # VALIDATE (report, DO NOT fix)
        issues = []
        records_missing_keys = 0
        
        for i, record in enumerate(data):
            missing = [k for k in ['customer_id', 'ubo_name'] if k not in record]
            if missing:
                records_missing_keys += 1
                if records_missing_keys <= 5:
                    issues.append(f"Record {i} missing: {missing}")
        
        if records_missing_keys > 0:
            logger.warning(f"[WARN] UBO records missing required keys: {records_missing_keys} affected")
        
        self.validation_report['ubo'] = {
            'valid': records_missing_keys == 0,
            'issues': issues,
            'records_affected': records_missing_keys,
            'total_records': len(data),
        }
        
        self._cache['ubo'] = data
        logger.info(f"[OK] Loaded {len(data):,} UBO records")
        return data
    
    def load_regulatory_rules(self) -> list:
        """Load regulatory rules with validation."""
        if 'regulatory_rules' in self._cache:
            return self._cache['regulatory_rules']
        
        logger.info("Loading regulatory_rules.json...")
        with open(self.project_root / 'Data Raw' / 'regulatory_rules.json') as f:
            data = json.load(f)
        
        # VALIDATE (report, DO NOT fix)
        issues = []
        if not data:
            issues.append("Regulatory rules list is empty")
        
        self.validation_report['regulatory_rules'] = {
            'valid': len(issues) == 0,
            'issues': issues,
            'total_records': len(data),
        }
        
        self._cache['regulatory_rules'] = data
        logger.info(f"[OK] Loaded {len(data):,} regulatory rules")
        return data
    
    def _parse_dates(self, df: pd.DataFrame, date_fields: set) -> pd.DataFrame:
        """Parse date fields consistently."""
        for field in date_fields:
            if field in df.columns:
                df[field] = pd.to_datetime(df[field], errors='coerce')
        return df
    
    def _validate_and_report(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        required_fields: list = None,
        optional_fields: list = None
    ) -> Dict:
        """
        Validate dataset and report findings.
        
        Reports issues without fixing them.
        """
        
        issues = []
        null_counts = {}
        affected_rows = set()
        
        required_fields = required_fields or []
        optional_fields = optional_fields or []
        
        # Check required fields
        for field in required_fields:
            if field not in df.columns:
                issues.append(f"[CRITICAL] Required column missing: {field}")
                continue
            
            null_count = df[field].isna().sum()
            if null_count > 0:
                null_counts[field] = null_count
                affected_rows.update(df[df[field].isna()].index.tolist())
                pct = (null_count / len(df)) * 100
                issues.append(
                    f"[WARN] Required field nulls: {field} "
                    f"({null_count}/{len(df)} = {pct:.1f} percent)"
                )
        
        # Check optional fields (warn only if high null rate)
        for field in optional_fields:
            if field not in df.columns:
                continue
            
            null_count = df[field].isna().sum()
            if null_count > len(df) * 0.1:
                null_counts[field] = null_count
                pct = (null_count / len(df)) * 100
                issues.append(
                    f"[INFO] Optional field high nulls: {field} "
                    f"({null_count}/{len(df)} = {pct:.1f} percent)"
                )
        
        # Store report
        valid = not any('[CRITICAL]' in i for i in issues)
        
        self.validation_report[dataset_name] = {
            'valid': valid,
            'issues': issues,
            'null_counts': null_counts,
            'affected_rows': len(affected_rows),
            'total_rows': len(df),
        }
        
        # Log each issue
        if issues:
            logger.info(f"\n{dataset_name} Validation:")
            for issue in issues:
                if '[CRITICAL]' in issue:
                    logger.error(f"  {issue}")
                elif '[WARN]' in issue:
                    logger.warning(f"  {issue}")
                else:
                    logger.info(f"  {issue}")
    
    def _print_validation_summary(self):
        """Print validation summary for all datasets."""
        
        logger.info("\n" + "="*70)
        logger.info("DATA VALIDATION SUMMARY")
        logger.info("="*70)
        
        for dataset_name, report in self.validation_report.items():
            valid = report.get('valid', False)
            status = "PASS" if valid else "FAIL"
            issues_count = len(report.get('issues', []))
            affected = report.get('affected_rows', 0)
            total = report.get('total_rows', report.get('total_records', 0))
            
            logger.info(f"\n{dataset_name}: {status}")
            logger.info(f"  Issues: {issues_count}")
            logger.info(f"  Affected rows: {affected}/{total}")
            
            if report.get('issues'):
                for issue in report['issues'][:3]:
                    logger.info(f"    {issue}")
                
                if len(report['issues']) > 3:
                    logger.info(f"    ... and {len(report['issues']) - 3} more issues")
        
        logger.info("\n" + "="*70)
        logger.info("NOTE: Issues are REPORTED but NOT fixed.")
        logger.info("Compliance teams should review and remediate manually.")
        logger.info("="*70 + "\n")
    
    def get_validation_report(self) -> Dict:
        """Get full validation report for audit."""
        return self.validation_report
    
    def clear_cache(self):
        """Clear in-memory cache."""
        self._cache.clear()
        logger.info("Cache cleared")