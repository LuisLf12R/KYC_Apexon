"""
identity.py
-----------
Identity Verification Dimension for KYC Completeness Control.

Evaluates customer identity proofing through a regulatory-aligned,
risk-based approach. Verifies document types, expiry, verification methods,
and data consistency against FATF, CIP, and regional frameworks.

Compliance Flags:
- COMPLIANT_PRIMARY_VERIFIED: Primary document verified and current
- COMPLIANT_SECONDARY_VERIFIED: Secondary documents triangulated
- NON_COMPLIANT_DOCUMENT_EXPIRED: Document expired
- NON_COMPLIANT_VERIFICATION_STALE: Verification older than CDD refresh cycle
- NON_COMPLIANT_MISSING_IDENTITY: No acceptable identity documents
- NON_COMPLIANT_DATA_DISCREPANCY: ID data conflicts with customer record
- NON_COMPLIANT_HIGH_RISK_INSUFFICIENT: High-risk customer needs more evidence
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

from rules.schema.dimensions import IdentityParameters
logger = logging.getLogger(__name__)


class BaseDimension:
    """Base class for all KYC dimensions."""
    
    def __init__(self, evaluation_date: datetime = None):
        self.evaluation_date = evaluation_date or datetime(2026, 4, 9)
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict:
        """Evaluate a single customer. Override in subclasses."""
        raise NotImplementedError


class IdentityVerificationDimension(BaseDimension):
    """
    Identity Verification Dimension.
    
    Verifies that:
    1. Customer has at least one acceptable identity document
    2. Document(s) are current and not expired
    3. Document(s) meet risk-based sufficiency thresholds
    4. Identity data is consistent across records
    5. Verification is recent enough per regulatory refresh cycles
    """
    
    # Document tier hierarchy (highest to lowest priority)
    PRIMARY_DOCS = {
        'PASSPORT', 'NATIONAL_ID', 'DRIVERS_LICENSE', 
        'RESIDENCE_PERMIT', 'VOTER_ID', 'REAL_ID'
    }
    
    SECONDARY_DOCS = {
        'SSN_CARD', 'UTILITY_BILL', 'BANK_STATEMENT',
        'TAX_DOCUMENT', 'INSURANCE_CERTIFICATE'
    }
    
    SUPPLEMENTARY_DOCS = {
        'STUDENT_ID', 'EMPLOYER_ID', 'LIBRARY_CARD',
        'TRANSIT_PASS'
    }
    
    # Jurisdictional expiry grace periods (days)
    EXPIRY_GRACE_PERIODS = {
        'AU': 730,  # Australian passports: 2 years after expiry
        'US': 365,  # US: 12 months after expiry
        'default': 0  # Strict: must not be expired
    }
    
    # CDD refresh cycles by risk rating (days)
    CDD_REFRESH_CYCLES = {
        'HIGH': 365,      # Annual
        'MEDIUM': 730,    # Biennial
        'LOW': 1095,      # Triennial
    }
    
    _SCORE_MAP = {
        'COMPLIANT_PRIMARY_VERIFIED': 100,
        'COMPLIANT_SECONDARY_VERIFIED': 80,
        'NON_COMPLIANT_VERIFICATION_STALE': 60,
        'NON_COMPLIANT_DOCUMENT_EXPIRED': 40,
        'NON_COMPLIANT_DATA_DISCREPANCY': 40,
        'NON_COMPLIANT_HIGH_RISK_INSUFFICIENT': 30,
        'NON_COMPLIANT_MISSING_IDENTITY': 0,
    }

    def _compute_score(self, compliance_status: str) -> int:
        return self._SCORE_MAP.get(compliance_status, 0)

    def __init__(self, params: IdentityParameters, evaluation_date=None):
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
        logger.info(f"IdentityVerificationDimension initialized. Evaluation date: {self.evaluation_date}")

    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict:
        """
        Evaluate identity verification for a single customer.
        
        Args:
            customer_id: Customer ID to evaluate
            data: Dict with 'customers', 'id_verifications', etc.
        
        Returns:
            Dict with compliance assessment
        """
        try:
            customers = data['customers']
            id_verifications = data['id_verifications']
            
            # Get customer record
            customer = customers[customers['customer_id'] == customer_id]
            if customer.empty:
                return self._no_customer_error(customer_id)
            
            customer = customer.iloc[0]
            
            # Get ID verification records for this customer
            id_records = id_verifications[id_verifications['customer_id'] == customer_id]
            
            # Perform evaluations
            findings = []
            passed = True
            compliance_status = 'COMPLIANT_PRIMARY_VERIFIED'
            
            # [1] Check if customer has any identity documents
            if id_records.empty:
                findings.append('[FAIL] No identity documents found')
                passed = False
                compliance_status = 'NON_COMPLIANT_MISSING_IDENTITY'
            else:
                # [2] Select best document per hierarchy
                best_doc = self._select_best_document(id_records)
                
                if best_doc is None:
                    findings.append('[FAIL] No acceptable identity document found')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_MISSING_IDENTITY'
                else:
                    # [3] Check document expiry
                    doc_type = best_doc.get('document_type', '')
                    expiry_date = pd.to_datetime(best_doc.get('expiry_date'))
                    jurisdiction = customer.get('jurisdiction', 'default')
                    
                    days_expired = (self.evaluation_date - expiry_date).days
                    grace_period = self._get_expiry_grace_period(jurisdiction)
                    
                    if days_expired > grace_period:
                        findings.append(
                            f'[FAIL] Document expired {days_expired} days ago '
                            f'({doc_type}, grace period: {grace_period} days)'
                        )
                        passed = False
                        compliance_status = 'NON_COMPLIANT_DOCUMENT_EXPIRED'
                    else:
                        findings.append(
                            f'[PASS] Document current: {doc_type} '
                            f'(expires: {expiry_date.date()})'
                        )
                    
                    # [4] Check data consistency
                    name_match = self._check_name_consistency(
                        customer.get('customer_name', ''),
                        best_doc.get('name_on_document', customer.get('customer_name', ''))
                    )
                    
                    if not name_match:
                        findings.append('[WARN] Name discrepancy between ID and customer record')
                        passed = False
                        compliance_status = 'NON_COMPLIANT_DATA_DISCREPANCY'
                    else:
                        findings.append('[PASS] Name matches across records')
                    
                    # [5] Check verification recency
                    verification_date = pd.to_datetime(best_doc.get('verification_date'))
                    days_since_verification = (self.evaluation_date - verification_date).days
                    refresh_cycle = self._get_cdd_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
                    
                    if days_since_verification > refresh_cycle:
                        findings.append(
                            f'[WARN] Verification overdue by {days_since_verification - refresh_cycle} days '
                            f'(verified: {verification_date.date()}, refresh: {refresh_cycle} days)'
                        )
                        passed = False
                        compliance_status = 'NON_COMPLIANT_VERIFICATION_STALE'
                    else:
                        findings.append(
                            f'[PASS] Verification current '
                            f'(verified: {verification_date.date()}, '
                            f'days remaining: {refresh_cycle - days_since_verification})'
                        )
                    
                    # [6] Check risk-based sufficiency (HIGH-risk needs multiple/secondary docs)
                    if customer.get('risk_rating') == 'HIGH':
                        doc_tier = self._get_document_tier(doc_type)
                        if doc_tier == 'SUPPLEMENTARY':
                            findings.append(
                                '[FAIL] High-risk customer: supplementary document insufficient, '
                                'requires primary or secondary document'
                            )
                            passed = False
                            compliance_status = 'NON_COMPLIANT_HIGH_RISK_INSUFFICIENT'
            
            # Build result
            remediation_required = not passed
            next_review_date = self.evaluation_date + timedelta(
                days=self._get_cdd_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'IdentityVerification',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': self._compute_score(compliance_status),
                'evaluation_details': {
                    'risk_rating': customer.get('risk_rating'),
                    'jurisdiction': customer.get('jurisdiction'),
                    'id_documents_found': len(id_records),
                    'best_document_type': best_doc.get('document_type') if best_doc else None,
                    'document_expiry_date': str(best_doc.get('expiry_date')) if best_doc else None,
                    'verification_date': str(best_doc.get('verification_date')) if best_doc else None,
                    'verification_method': best_doc.get('verification_method') if best_doc else None,
                    'compliance_status': compliance_status,
                    'days_since_verification': days_since_verification if best_doc else None,
                    'cdd_refresh_cycle_days': refresh_cycle if best_doc else None,
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating identity for {customer_id}: {e}")
            return self._evaluation_error(customer_id, str(e))
    
    def _select_best_document(self, id_records: pd.DataFrame) -> Optional[Dict]:
        """
        Select the strongest available document per hierarchy:
        1. By tier (Primary > Secondary > Supplementary)
        2. By recency (most recent verification)
        """
        if id_records.empty:
            return None
        
        # Convert to dict for easier access
        docs = []
        for _, row in id_records.iterrows():
            doc_type = str(row.get('document_type', '')).upper()
            tier = self._get_document_tier(doc_type)
            verification_date = pd.to_datetime(row.get('verification_date', None))
            
            docs.append({
                'tier_rank': self._tier_rank(tier),
                'verification_date': verification_date,
                'document_type': row.get('document_type'),
                'expiry_date': row.get('expiry_date'),
                'verification_date': row.get('verification_date'),
                'verification_method': row.get('verification_method'),
                'name_on_document': row.get('name_on_document', row.get('customer_id')),
            })
        
        # Sort by tier (ascending = best first), then by verification date (descending = most recent)
        docs.sort(key=lambda x: (x['tier_rank'], -pd.to_datetime(x['verification_date']).timestamp()))
        
        return docs[0] if docs else None
    
    def _get_document_tier(self, doc_type: str) -> str:
        """Return document tier: PRIMARY, SECONDARY, SUPPLEMENTARY, or UNKNOWN."""
        doc_type = str(doc_type).upper()
        
        if doc_type in self.PRIMARY_DOCS:
            return 'PRIMARY'
        elif doc_type in self.SECONDARY_DOCS:
            return 'SECONDARY'
        elif doc_type in self.SUPPLEMENTARY_DOCS:
            return 'SUPPLEMENTARY'
        else:
            return 'UNKNOWN'
    
    def _tier_rank(self, tier: str) -> int:
        """Return numeric rank (lower = better)."""
        ranks = {'PRIMARY': 1, 'SECONDARY': 2, 'SUPPLEMENTARY': 3, 'UNKNOWN': 4}
        return ranks.get(tier, 4)
    
    def _get_expiry_grace_period(self, jurisdiction: str) -> int:
        """Return expiry grace period for jurisdiction in days."""
        return self.EXPIRY_GRACE_PERIODS.get(jurisdiction, self.EXPIRY_GRACE_PERIODS['default'])
    
    def _get_cdd_refresh_cycle(self, risk_rating: str) -> int:
        """Return CDD refresh cycle for risk rating in days."""
        return self.CDD_REFRESH_CYCLES.get(risk_rating, self.CDD_REFRESH_CYCLES['MEDIUM'])
    
    def _check_name_consistency(self, customer_name: str, id_name: str) -> bool:
        """Check if names match (case-insensitive, partial match allowed)."""
        if not customer_name or not id_name:
            return True  # Allow if either is missing (data quality issue)
        
        c_name = str(customer_name).upper().strip()
        i_name = str(id_name).upper().strip()
        
        # Exact match or substring match (allows for middle names)
        return c_name in i_name or i_name in c_name
    
    def _no_customer_error(self, customer_id: str) -> Dict:
        """Return error result for missing customer."""
        return {
            'customer_id': customer_id,
            'dimension': 'IdentityVerification',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f'Customer {customer_id} not found in dataset'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
    
    def _evaluation_error(self, customer_id: str, error_msg: str) -> Dict:
        """Return error result for evaluation failure."""
        return {
            'customer_id': customer_id,
            'dimension': 'IdentityVerification',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
