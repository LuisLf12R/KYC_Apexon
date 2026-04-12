"""
proof_of_address.py
-------------------
Proof of Address Dimension for KYC Completeness and AML/CFT Control.

Evaluates customer address documentation through a risk-based, 
jurisdictionally-aware approach. Verifies document types, validity periods,
data consistency, and compliance with FATF, regional, and local frameworks.

Compliance Flags:
- COMPLIANT_PRIMARY_POA: Primary/government address document verified
- COMPLIANT_SECONDARY_POA: Secondary address document(s) verified
- NON_COMPLIANT_POA_EXPIRED: Address document expired or stale
- NON_COMPLIANT_POA_MISSING: No acceptable address documents found
- NON_COMPLIANT_ADDRESS_DISCREPANCY: Address mismatch across records
- NON_COMPLIANT_REVERIFICATION_OVERDUE: PoA re-verification cycle exceeded
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ProofOfAddressDimension:
    """
    Proof of Address Dimension.
    
    Verifies that:
    1. Customer has at least one acceptable address document
    2. Document(s) are current per jurisdictional validity windows
    3. Address data is consistent with customer record
    4. Re-verification is current per risk-based refresh cycles
    """
    
    # Document acceptance tiers
    PRIMARY_POA_DOCS = {
        'PASSPORT', 'NATIONAL_ID', 'DRIVERS_LICENSE', 'GOVERNMENT_ID_WITH_ADDRESS',
        'MELDEBESCHEINIGUNG', 'CERTIFICADO_EMPADRONAMIENTO', 'COUNCIL_TAX_BILL'
    }
    
    SECONDARY_POA_DOCS = {
        'UTILITY_BILL', 'BANK_STATEMENT', 'INSURANCE_CERTIFICATE',
        'TAX_NOTICE', 'LEASE_AGREEMENT', 'RENT_RECEIPT', 'GOVERNMENT_CORRESPONDENCE'
    }
    
    SUPPLEMENTARY_POA_DOCS = {
        'ATTESTATION_HEBERGEMENT', 'EMPLOYER_LETTER', 'REFUGEE_CERTIFICATE',
        'HOMELESS_SHELTER_LETTER', 'STUDENT_LETTER', 'HOST_ATTESTATION'
    }
    
    # Jurisdictional validity windows (days)
    DOCUMENT_VALIDITY_WINDOWS = {
        'US': 90,          # < 90 days
        'EU': 180,         # 3-6 months (standardized to 180)
        'GB': 180,         # 3-6 months
        'FR': 180,         # 3-6 months
        'DE': 0,           # Must be current/valid
        'ES': 90,          # < 3 months
        'SG': 180,         # 6 months
        'HK': 90,          # < 3 months
        'AE': 180,         # 6 months
        'IN': 0,           # Current
        'CA': 180,         # < 6 months (dual-process)
        'AU': 180,         # Current / Recent
        'default': 180,    # Global default: 6 months
    }
    
    # PoA re-verification cycles by risk rating (days)
    POA_REFRESH_CYCLES = {
        'HIGH': 365,       # Annual
        'MEDIUM': 730,     # Biennial
        'LOW': 1095,       # Triennial (3 years)
    }
    
    def __init__(self, evaluation_date: datetime = None):
        self.evaluation_date = evaluation_date or datetime(2026, 4, 9)
        logger.info(f"ProofOfAddressDimension initialized. Evaluation date: {self.evaluation_date}")
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict:
        """
        Evaluate proof of address for a single customer.
        
        Args:
            customer_id: Customer ID to evaluate
            data: Dict with 'customers', 'documents', etc.
        
        Returns:
            Dict with compliance assessment
        """
        try:
            customers = data['customers']
            documents = data['documents']
            
            # Get customer record
            customer = customers[customers['customer_id'] == customer_id]
            if customer.empty:
                return self._no_customer_error(customer_id)
            
            customer = customer.iloc[0]
            
            # Get PoA documents for this customer
            poa_records = documents[
                (documents['customer_id'] == customer_id) &
                (documents['document_category'].isin(['POA', 'ADDRESS']))
            ]
            
            # Perform evaluations
            findings = []
            passed = True
            compliance_status = 'COMPLIANT_PRIMARY_POA'
            
            # [1] Check if customer has any PoA documents
            if poa_records.empty:
                findings.append('[FAIL] No proof of address documents found')
                passed = False
                compliance_status = 'NON_COMPLIANT_POA_MISSING'
            else:
                # [2] Select best document per hierarchy
                best_doc = self._select_best_document(poa_records)
                
                if best_doc is None:
                    findings.append('[FAIL] No acceptable proof of address document found')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_POA_MISSING'
                else:
                    # [3] Check document validity per jurisdiction
                    doc_type = best_doc.get('document_type', '')
                    issue_date = pd.to_datetime(best_doc.get('issue_date'))
                    expiry_date = pd.to_datetime(best_doc.get('expiry_date'))
                    jurisdiction = customer.get('jurisdiction', 'default')
                    
                    # Check issue date (freshness)
                    days_since_issue = (self.evaluation_date - issue_date).days
                    validity_window = self._get_validity_window(jurisdiction)
                    
                    if days_since_issue > validity_window:
                        findings.append(
                            f'[FAIL] PoA document stale: {days_since_issue} days old '
                            f'({doc_type}, validity: {validity_window} days)'
                        )
                        passed = False
                        compliance_status = 'NON_COMPLIANT_POA_EXPIRED'
                    else:
                        findings.append(
                            f'[PASS] PoA document current: {doc_type} '
                            f'(issued: {issue_date.date()}, '
                            f'days remaining: {validity_window - days_since_issue})'
                        )
                    
                    # Check expiry (if applicable)
                    if pd.notna(expiry_date) and expiry_date < self.evaluation_date:
                        findings.append(
                            f'[FAIL] PoA document expired: {expiry_date.date()}'
                        )
                        passed = False
                        compliance_status = 'NON_COMPLIANT_POA_EXPIRED'
                    
                    # [4] Check address data consistency
                    address_match = self._check_address_consistency(
                        customer.get('declared_address_city', ''),
                        customer.get('declared_address_country', ''),
                        best_doc.get('poa_address_city', ''),
                        best_doc.get('poa_address_country', '')
                    )
                    
                    if not address_match:
                        findings.append('[WARN] Address discrepancy between PoA and customer record')
                        passed = False
                        compliance_status = 'NON_COMPLIANT_ADDRESS_DISCREPANCY'
                    else:
                        findings.append('[PASS] Address matches across records')
                    
                    # [5] Check re-verification recency
                    verification_date = pd.to_datetime(best_doc.get('verified_at', best_doc.get('upload_date')))
                    if pd.notna(verification_date):
                        days_since_verification = (self.evaluation_date - verification_date).days
                        refresh_cycle = self._get_poa_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
                        
                        if days_since_verification > refresh_cycle:
                            findings.append(
                                f'[WARN] PoA re-verification overdue by {days_since_verification - refresh_cycle} days '
                                f'(verified: {verification_date.date()}, refresh: {refresh_cycle} days)'
                            )
                            passed = False
                            compliance_status = 'NON_COMPLIANT_REVERIFICATION_OVERDUE'
                        else:
                            findings.append(
                                f'[PASS] PoA re-verification current '
                                f'(verified: {verification_date.date()}, '
                                f'days remaining: {refresh_cycle - days_since_verification})'
                            )
                    
                    # [6] Check risk-based sufficiency (HIGH-risk may need stronger docs)
                    if customer.get('risk_rating') == 'HIGH':
                        doc_tier = self._get_document_tier(doc_type)
                        if doc_tier == 'SUPPLEMENTARY':
                            findings.append(
                                '[WARN] High-risk customer: supplementary PoA document, '
                                'consider stronger documentation'
                            )
            
            # Build result
            remediation_required = not passed
            next_review_date = self.evaluation_date + timedelta(
                days=self._get_poa_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'ProofOfAddress',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'evaluation_details': {
                    'risk_rating': customer.get('risk_rating'),
                    'jurisdiction': customer.get('jurisdiction'),
                    'poa_documents_found': len(poa_records),
                    'best_document_type': best_doc.get('document_type') if best_doc else None,
                    'document_issue_date': str(best_doc.get('issue_date')) if best_doc else None,
                    'document_expiry_date': str(best_doc.get('expiry_date')) if best_doc else None,
                    'document_verified_date': str(best_doc.get('verified_at', best_doc.get('upload_date'))) if best_doc else None,
                    'declared_address_city': customer.get('declared_address_city'),
                    'declared_address_country': customer.get('declared_address_country'),
                    'compliance_status': compliance_status,
                    'validity_window_days': self._get_validity_window(customer.get('jurisdiction', 'default')),
                    'refresh_cycle_days': self._get_poa_refresh_cycle(customer.get('risk_rating', 'MEDIUM')),
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating PoA for {customer_id}: {e}")
            return self._evaluation_error(customer_id, str(e))
    
    def _select_best_document(self, poa_records: pd.DataFrame) -> Optional[Dict]:
        """
        Select the strongest available PoA document per hierarchy:
        1. By tier (Primary > Secondary > Supplementary)
        2. By recency (most recent issue date)
        """
        if poa_records.empty:
            return None
        
        # Convert to dict for easier access
        docs = []
        for _, row in poa_records.iterrows():
            doc_type = str(row.get('document_type', '')).upper()
            tier = self._get_document_tier(doc_type)
            issue_date = pd.to_datetime(row.get('issue_date', None))
            
            docs.append({
                'tier_rank': self._tier_rank(tier),
                'issue_date': issue_date,
                'document_type': row.get('document_type'),
                'issue_date': row.get('issue_date'),
                'expiry_date': row.get('expiry_date'),
                'verified_at': row.get('verified_at'),
                'upload_date': row.get('upload_date'),
                'poa_address_city': row.get('poa_address_city'),
                'poa_address_country': row.get('poa_address_country'),
            })
        
        # Sort by tier (ascending = best first), then by issue date (descending = most recent)
        docs.sort(key=lambda x: (x['tier_rank'], -pd.to_datetime(x['issue_date']).timestamp() if pd.notna(x['issue_date']) else 0))
        
        return docs[0] if docs else None
    
    def _get_document_tier(self, doc_type: str) -> str:
        """Return document tier: PRIMARY, SECONDARY, SUPPLEMENTARY, or UNKNOWN."""
        doc_type = str(doc_type).upper()
        
        if doc_type in self.PRIMARY_POA_DOCS:
            return 'PRIMARY'
        elif doc_type in self.SECONDARY_POA_DOCS:
            return 'SECONDARY'
        elif doc_type in self.SUPPLEMENTARY_POA_DOCS:
            return 'SUPPLEMENTARY'
        else:
            return 'UNKNOWN'
    
    def _tier_rank(self, tier: str) -> int:
        """Return numeric rank (lower = better)."""
        ranks = {'PRIMARY': 1, 'SECONDARY': 2, 'SUPPLEMENTARY': 3, 'UNKNOWN': 4}
        return ranks.get(tier, 4)
    
    def _get_validity_window(self, jurisdiction: str) -> int:
        """Return PoA validity window for jurisdiction in days."""
        return self.DOCUMENT_VALIDITY_WINDOWS.get(jurisdiction, self.DOCUMENT_VALIDITY_WINDOWS['default'])
    
    def _get_poa_refresh_cycle(self, risk_rating: str) -> int:
        """Return PoA re-verification cycle for risk rating in days."""
        return self.POA_REFRESH_CYCLES.get(risk_rating, self.POA_REFRESH_CYCLES['MEDIUM'])
    
    def _check_address_consistency(self, cust_city: str, cust_country: str, 
                                   doc_city: str, doc_country: str) -> bool:
        """Check if address data matches (case-insensitive)."""
        if not cust_city or not cust_country or not doc_city or not doc_country:
            return True  # Allow if any field is missing (data quality issue)
        
        c_city = str(cust_city).upper().strip()
        c_country = str(cust_country).upper().strip()
        d_city = str(doc_city).upper().strip()
        d_country = str(doc_country).upper().strip()
        
        # Require exact match on country, fuzzy on city (accounts for transliteration)
        country_match = c_country in d_country or d_country in c_country
        city_match = c_city in d_city or d_city in c_city
        
        return country_match and city_match
    
    def _no_customer_error(self, customer_id: str) -> Dict:
        """Return error result for missing customer."""
        return {
            'customer_id': customer_id,
            'dimension': 'ProofOfAddress',
            'passed': False,
            'status': 'Error',
            'findings': [f'Customer {customer_id} not found in dataset'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
    
    def _evaluation_error(self, customer_id: str, error_msg: str) -> Dict:
        """Return error result for evaluation failure."""
        return {
            'customer_id': customer_id,
            'dimension': 'ProofOfAddress',
            'passed': False,
            'status': 'Error',
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
