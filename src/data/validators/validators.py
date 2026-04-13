"""
validators.py - ENHANCED
Report data quality issues without masking them.

Philosophy: Transparency over convenience.
- Report ALL issues
- Don't auto-fix
- Audit trail visible
- Compliance-friendly
"""

import pandas as pd
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def validate_dataset(
    dataset: pd.DataFrame,
    contract: Dict[str, Any],
    strict: bool = False
) -> Dict[str, Any]:
    """
    Validate dataset against schema contract.
    
    Reports issues without fixing them.
    
    Args:
        dataset: DataFrame to validate
        contract: Schema contract from contracts.py
        strict: If True, fail on any issue. If False, warn and continue.
    
    Returns:
        {
            'valid': bool,
            'issues': [list of issues found],
            'null_counts': {field: count},
            'affected_rows': int
        }
    """
    
    issues = []
    null_counts = {}
    affected_rows = set()
    
    # Get required and optional fields
    required_fields = contract.get('required_fields', [])
    optional_fields = contract.get('optional_fields', [])
    all_fields = required_fields + optional_fields
    
    # [1] Check required fields for nulls
    for field in required_fields:
        if field not in dataset.columns:
            issues.append(f"[CRITICAL] Required field missing: {field}")
            continue
        
        null_count = dataset[field].isna().sum()
        if null_count > 0:
            null_counts[field] = null_count
            affected_rows.update(dataset[dataset[field].isna()].index.tolist())
            pct = null_count / len(dataset) * 100
            issues.append(
                f"[WARN] Required field has nulls: {field} "
                f"({null_count}/{len(dataset)} = {pct:.1f}%)"
            )
    
    # [2] Check optional fields for nulls (info only)
    for field in optional_fields:
        if field not in dataset.columns:
            continue
        
        null_count = dataset[field].isna().sum()
        if null_count > 0 and null_count > len(dataset) * 0.1:
            null_counts[field] = null_count
            pct = null_count / len(dataset) * 100
            issues.append(
                f"[INFO] Optional field has high nulls: {field} "
                f"({null_count}/{len(dataset)} = {pct:.1f}%)"
            )
    
    # [3] Check for unexpected columns
    extra_columns = set(dataset.columns) - set(all_fields)
    if extra_columns:
        issues.append(f"[INFO] Extra columns (not in contract): {', '.join(extra_columns)}")
    
    # [4] Missing expected columns
    missing_columns = set(all_fields) - set(dataset.columns)
    if missing_columns:
        issues.append(f"[WARN] Expected columns missing: {', '.join(missing_columns)}")
    
    # Determine validity
    critical_issues = [i for i in issues if '[CRITICAL]' in i]
    valid = len(critical_issues) == 0
    
    result = {
        'valid': valid,
        'issues': issues,
        'null_counts': null_counts,
        'affected_rows': len(affected_rows),
        'total_rows': len(dataset),
    }
    
    # Log results
    logger.info(f"\nDataset: {contract.get('name', 'Unknown')}")
    logger.info(f"  Valid: {valid}")
    logger.info(f"  Affected rows: {len(affected_rows)}/{len(dataset)}")
    
    for issue in issues:
        if '[CRITICAL]' in issue:
            logger.error(f"  {issue}")
        elif '[WARN]' in issue:
            logger.warning(f"  {issue}")
        else:
            logger.info(f"  {issue}")
    
    if strict and not valid:
        raise ValueError(f"Dataset validation failed: {contract.get('name', 'Unknown')}")
    
    return result


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: List[str] = None,
    strict: bool = False
) -> Dict[str, Any]:
    """
    Quick validation for a DataFrame.
    
    Args:
        df: DataFrame to validate
        required_columns: List of column names that must not be null
        strict: Fail if validation fails
    
    Returns:
        Validation result dict
    """
    
    if df is None or df.empty:
        return {
            'valid': False,
            'issues': ['DataFrame is empty or None'],
            'null_counts': {},
            'affected_rows': 0,
        }
    
    issues = []
    null_counts = {}
    affected_rows = set()
    
    if required_columns:
        for col in required_columns:
            if col not in df.columns:
                issues.append(f"[CRITICAL] Required column missing: {col}")
                continue
            
            null_count = df[col].isna().sum()
            if null_count > 0:
                null_counts[col] = null_count
                affected_rows.update(df[df[col].isna()].index.tolist())
                issues.append(
                    f"[WARN] Column has nulls: {col} ({null_count}/{len(df)})"
                )
    
    valid = not any('[CRITICAL]' in i for i in issues)
    
    result = {
        'valid': valid,
        'issues': issues,
        'null_counts': null_counts,
        'affected_rows': len(affected_rows),
    }
    
    if strict and not valid:
        raise ValueError(f"DataFrame validation failed: {issues}")
    
    return result


def validate_list_of_dicts(
    data: List[Dict],
    required_keys: List[str] = None,
    strict: bool = False
) -> Dict[str, Any]:
    """
    Validate a list of dictionaries (e.g., UBO records).
    
    Args:
        data: List of dicts to validate
        required_keys: Keys that must exist in each dict
        strict: Fail if validation fails
    
    Returns:
        Validation result dict
    """
    
    if not data:
        return {
            'valid': False,
            'issues': ['Data list is empty'],
            'records_affected': 0,
        }
    
    issues = []
    records_with_missing_keys = []
    
    if required_keys:
        for i, record in enumerate(data):
            missing = [k for k in required_keys if k not in record or pd.isna(record.get(k))]
            if missing:
                records_with_missing_keys.append((i, missing))
                issues.append(
                    f"[WARN] Record {i} missing keys: {', '.join(missing)}"
                )
    
    valid = not any('[CRITICAL]' in i for i in issues)
    
    result = {
        'valid': valid,
        'issues': issues,
        'records_affected': len(records_with_missing_keys),
        'total_records': len(data),
    }
    
    if strict and not valid:
        raise ValueError(f"List validation failed: {issues}")
    
    return result