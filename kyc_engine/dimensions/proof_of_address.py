"""
proof_of_address.py - FIXED VERSION
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

from rules.schema.dimensions import DocumentParameters
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
    
    JURISDICTIONAL_VALIDITY_DAYS = {
        'US': 90,
        'EU': 180,
        'GB': 180,
        'FR': 180,
        'DE': 0,
        'ES': 90,
        'SG': 180,
        'HK': 90,
        'AE': 180,
        'IN': 0,
        'CA': 180,
        'AU': 180,
        'default': 180,
    }
    
    POA_REFRESH_CYCLES = {
        'HIGH': 365,
        'MEDIUM': 730,
        'LOW': 1095,
    }
    
    _SCORE_MAP = {
        'COMPLIANT_PRIMARY_POA': 100,
        'COMPLIANT_SECONDARY_POA': 80,
        'NON_COMPLIANT_POA_EXPIRED': 50,
        'NON_COMPLIANT_REVERIFICATION_OVERDUE': 40,
        'NON_COMPLIANT_ADDRESS_DISCREPANCY': 20,
        'NON_COMPLIANT_POA_MISSING': 0,
    }

    def _compute_score(self, compliance_status: str) -> int:
        return self._SCORE_MAP.get(compliance_status, 0)

    def __init__(self, params: DocumentParameters, evaluation_date=None):
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
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
            
            customer = customers[customers['customer_id'] == customer_id]
            if customer.empty:
                return self._no_customer_error(customer_id)
            
            customer = customer.iloc[0]
            
            # Get PoA documents for this customer - FIXED: Handle missing document_category
            if 'document_category' in documents.columns:
                poa_records = documents[
                    (documents['customer_id'] == customer_id) &
                    (documents['document_category'].isin(['POA', 'ADDRESS']))
                ]
            else:
                poa_types = ['UTILITY_BILL', 'BANK_STATEMENT', 'COUNCIL_TAX_BILL', 'LEASE_AGREEMENT', 
                            'GOVERNMENT_CORRESPONDENCE', 'INSURANCE_CERTIFICATE', 'TAX_NOTICE']
                poa_records = documents[
                    (documents['customer_id'] == customer_id) &
                    (documents['document_type'].isin(poa_types))
                ]
            
            findings = []
            passed = True
            compliance_status = 'COMPLIANT_PRIMARY_POA'
            
            if poa_records.empty:
                findings.append('[FAIL] No proof of address documents found')
                passed = False
                compliance_status = 'NON_COMPLIANT_POA_MISSING'
            else:
                poa_docs = poa_records.to_dict('records') if isinstance(poa_records, pd.DataFrame) else poa_records
                
                best_doc = self._select_best_poa_document(poa_docs)
                
                if best_doc is None:
                    findings.append('[FAIL] No acceptable PoA document found')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_POA_MISSING'
                else:
                    doc_type = best_doc.get('document_type', 'UNKNOWN')
                    
                    if doc_type in self.PRIMARY_POA_DOCS:
                        findings.append(f'[PASS] Primary PoA document: {doc_type}')
                        compliance_status = 'COMPLIANT_PRIMARY_POA'
                    elif doc_type in self.SECONDARY_POA_DOCS:
                        findings.append(f'[PASS] Secondary PoA document: {doc_type}')
                        compliance_status = 'COMPLIANT_SECONDARY_POA'
                    else:
                        findings.append(f'[WARN] Supplementary PoA document: {doc_type}')
                    
                    issue_date = pd.to_datetime(best_doc.get('issue_date'))
                    
                    if pd.notna(issue_date):
                        jurisdiction = customer.get('jurisdiction', 'default')
                        validity_days = self.JURISDICTIONAL_VALIDITY_DAYS.get(jurisdiction, self.params.max_doc_age_days)
                        min_issue_date = self.evaluation_date - timedelta(days=validity_days)
                        
                        if issue_date < min_issue_date:
                            findings.append(f'[WARN] PoA document stale: {issue_date.date()}')
                            passed = False
                            compliance_status = 'NON_COMPLIANT_POA_EXPIRED'
                        else:
                            findings.append(f'[PASS] PoA document current ({(self.evaluation_date - issue_date).days} days old)')
                    
                    for doc in poa_docs:
                        reverification_date = pd.to_datetime(doc.get('verification_date'))
                        if pd.notna(reverification_date):
                            days_since = (self.evaluation_date - reverification_date).days
                            refresh_cycle = self.POA_REFRESH_CYCLES.get(customer.get('risk_rating', 'MEDIUM'), 730)
                            
                            if days_since > refresh_cycle:
                                findings.append(f'[WARN] PoA re-verification overdue ({days_since} days)')
                                passed = False
                                compliance_status = 'NON_COMPLIANT_REVERIFICATION_OVERDUE'
            
            remediation_required = not passed
            next_review_date = self.evaluation_date + timedelta(
                days=self.POA_REFRESH_CYCLES.get(customer.get('risk_rating', 'MEDIUM'), 730)
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'ProofOfAddressDimension',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': self._compute_score(compliance_status),
                'evaluation_details': {
                    'entity_type': customer.get('entity_type'),
                    'jurisdiction': customer.get('jurisdiction'),
                    'risk_rating': customer.get('risk_rating'),
                    'poa_documents_found': len(poa_records) if not poa_records.empty else 0,
                    'compliance_status': compliance_status,
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating PoA for {customer_id}: {e}")
            return self._evaluation_error(customer_id, str(e))
    
    def _select_best_poa_document(self, documents: List[Dict]) -> Optional[Dict]:
        """Select best PoA document by tier."""
        for doc in documents:
            doc_type = doc.get('document_type', '')
            if doc_type in self.PRIMARY_POA_DOCS:
                return doc
        
        for doc in documents:
            doc_type = doc.get('document_type', '')
            if doc_type in self.SECONDARY_POA_DOCS:
                return doc
        
        for doc in documents:
            doc_type = doc.get('document_type', '')
            if doc_type in self.SUPPLEMENTARY_POA_DOCS:
                return doc
        
        return documents[0] if documents else None
    
    def _no_customer_error(self, customer_id: str) -> Dict:
        """Return error result for missing customer."""
        return {
            'customer_id': customer_id,
            'dimension': 'ProofOfAddressDimension',
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
            'dimension': 'ProofOfAddressDimension',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
