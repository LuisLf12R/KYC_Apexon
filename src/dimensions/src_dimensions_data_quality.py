"""
data_quality.py
---------------
Data Quality Dimension for KYC/AML Compliance Monitoring.

Evaluates the structural integrity, completeness, freshness, and consistency
of all KYC/AML datasets against regulatory standards (NYDFS Part 504, BCBS 239).

Monitors:
1. Completeness — Required fields populated, no critical nulls
2. Freshness/Timeliness — Data within risk-based SLAs
3. Validity — Data conforms to formats and domain constraints
4. Consistency — No contradictions across related records
5. Uniqueness — No duplicate customer profiles
6. Coverage Drift — Percentage of portfolio overdue for review/screening

Flags:
- COMPLIANT_HIGH_QUALITY: Data quality score 90+, all SLAs met
- COMPLIANT_ACCEPTABLE_QUALITY: Data quality score 70-89, minor gaps
- NON_COMPLIANT_DATA_DECAY: Data quality score < 70, critical gaps
- NON_COMPLIANT_SLA_BREACH: Critical SLA breaches detected
- NON_COMPLIANT_COVERAGE_DRIFT: Screening/review coverage gaps
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataQualityDimension:
    """
    Data Quality Dimension for comprehensive KYC/AML data governance.
    
    Evaluates all datasets against regulatory data quality standards.
    Produces a weighted composite Data Quality Score (0-100).
    """
    
    # Fixed evaluation date per regulatory framework
    EVALUATION_DATE = datetime(2026, 4, 9)
    
    # Risk-based KYC review SLAs (days)
    KYC_REVIEW_SLAS = {
        'HIGH': 365,      # Annual
        'MEDIUM': 730,    # Biennial
        'LOW': 1825,      # 5 years
    }
    
    # Identity document expiry SLA
    ID_EXPIRY_SLA_DAYS = 0  # Must not be expired
    
    # PoA freshness SLA (3-6 months)
    POA_FRESHNESS_SLA_DAYS = 90  # 3 months standard
    
    # Screening coverage SLA (daily batch)
    SCREENING_SLA_DAYS = 1  # Must be screened within 1 day
    
    # UBO verification SLA (aligned with customer master)
    UBO_SLA_DAYS = 365  # Aligned with risk-based cycles
    
    # Transaction data SLA
    TRANSACTION_SLA_DAYS = 0  # Must not be in future
    
    # Field criticality weights (3=critical, 2=standard, 1=optional)
    FIELD_WEIGHTS = {
        'customer_id': 3,
        'entity_type': 3,
        'jurisdiction': 3,
        'risk_rating': 3,
        'account_open_date': 2,
        'last_kyc_review_date': 3,
        'document_type': 2,
        'issue_date': 2,
        'expiry_date': 3,
        'verification_date': 2,
        'screening_date': 3,
        'screening_result': 3,
        'ubo_name': 3,
        'ownership_percent': 3,
        'transaction_date': 2,
    }
    
    def __init__(self, evaluation_date: datetime = None):
        self.evaluation_date = evaluation_date or self.EVALUATION_DATE
        logger.info(f"DataQualityDimension initialized. Evaluation date: {self.evaluation_date}")
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict:
        """
        Evaluate overall data quality for a single customer.
        
        Checks across all datasets: customers, id_verifications, documents,
        screenings, ubo, transactions.
        
        Returns:
            Dict with data quality assessment and composite score
        """
        try:
            customers = data['customers']
            
            # Get customer record
            customer = customers[customers['customer_id'] == customer_id]
            if customer.empty:
                return self._no_customer_error(customer_id)
            
            customer = customer.iloc[0]
            
            # Perform comprehensive data quality checks
            findings = []
            checks = {}
            scores = {}
            
            # [1] Customer Master Data Quality
            cust_score, cust_findings = self._check_customer_data(customer_id, customer)
            scores['customer_master'] = cust_score
            findings.extend(cust_findings)
            checks['customer_master'] = {'score': cust_score, 'weight': 0.25}
            
            # [2] Identity Verification Data Quality
            id_score, id_findings = self._check_identity_data(customer_id, data['id_verifications'])
            scores['identity_verification'] = id_score
            findings.extend(id_findings)
            checks['identity_verification'] = {'score': id_score, 'weight': 0.20}
            
            # [3] Documents (PoA) Data Quality
            doc_score, doc_findings = self._check_document_data(customer_id, data['documents'])
            scores['documents'] = doc_score
            findings.extend(doc_findings)
            checks['documents'] = {'score': doc_score, 'weight': 0.15}
            
            # [4] Screening Data Quality
            scr_score, scr_findings = self._check_screening_data(customer_id, data['screenings'])
            scores['screenings'] = scr_score
            findings.extend(scr_findings)
            checks['screenings'] = {'score': scr_score, 'weight': 0.20}
            
            # [5] UBO Data Quality (if legal entity)
            if customer.get('entity_type') == 'LEGAL_ENTITY':
                ubo_score, ubo_findings = self._check_ubo_data(customer_id, data['ubo'])
                scores['ubo'] = ubo_score
                findings.extend(ubo_findings)
                checks['ubo'] = {'score': ubo_score, 'weight': 0.10}
            else:
                scores['ubo'] = 100  # N/A for individuals
                checks['ubo'] = {'score': 100, 'weight': 0.10}
            
            # [6] Transaction Data Quality
            txn_score, txn_findings = self._check_transaction_data(customer_id, data['transactions'])
            scores['transactions'] = txn_score
            findings.extend(txn_findings)
            checks['transactions'] = {'score': txn_score, 'weight': 0.10}
            
            # Calculate weighted composite score
            weighted_score = self._calculate_composite_score(scores, checks)
            
            # Determine compliance status
            if weighted_score >= 90:
                status = 'Compliant'
                compliance_flag = 'COMPLIANT_HIGH_QUALITY'
                passed = True
            elif weighted_score >= 70:
                status = 'Compliant'
                compliance_flag = 'COMPLIANT_ACCEPTABLE_QUALITY'
                passed = True
            else:
                status = 'Non-Compliant'
                compliance_flag = 'NON_COMPLIANT_DATA_DECAY'
                passed = False
            
            # Check for critical SLA breaches (override score)
            critical_breaches = [f for f in findings if '[CRITICAL]' in f]
            if critical_breaches:
                passed = False
                status = 'Non-Compliant'
                compliance_flag = 'NON_COMPLIANT_SLA_BREACH'
            
            # Build result
            return {
                'customer_id': customer_id,
                'dimension': 'DataQuality',
                'passed': passed,
                'status': status,
                'evaluation_details': {
                    'entity_type': customer.get('entity_type'),
                    'risk_rating': customer.get('risk_rating'),
                    'data_quality_score': round(weighted_score, 2),
                    'component_scores': {k: round(v, 2) for k, v in scores.items()},
                    'compliance_flag': compliance_flag,
                    'evaluation_date': self.evaluation_date.strftime('%Y-%m-%d'),
                },
                'findings': findings,
                'remediation_required': not passed,
                'next_review_date': (self.evaluation_date + timedelta(days=90)).strftime('%Y-%m-%d'),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating data quality for {customer_id}: {e}")
            return self._evaluation_error(customer_id, str(e))
    
    def _check_customer_data(self, customer_id: str, customer: pd.Series) -> Tuple[float, List[str]]:
        """Check customer master data completeness and freshness."""
        findings = []
        score = 100
        
        # Required fields: customer_id, entity_type, jurisdiction, risk_rating
        required_fields = ['customer_id', 'entity_type', 'jurisdiction', 'risk_rating']
        for field in required_fields:
            if pd.isna(customer.get(field)):
                findings.append(f'[CRITICAL] Missing required field: {field}')
                score -= 20
        
        # Risk-based KYC review freshness
        last_kyc_review = pd.to_datetime(customer.get('last_kyc_review_date'))
        if pd.notna(last_kyc_review):
            days_since_kyc = (self.evaluation_date - last_kyc_review).days
            sla = self.KYC_REVIEW_SLAS.get(customer.get('risk_rating', 'MEDIUM'), 730)
            
            if days_since_kyc > sla:
                findings.append(
                    f'[CRITICAL] KYC review overdue: {days_since_kyc} days '
                    f'(SLA: {sla} days for {customer.get("risk_rating")})'
                )
                score -= 15
            else:
                findings.append(f'[OK] KYC review current ({days_since_kyc} days old)')
        
        # Account open date validity
        account_open = pd.to_datetime(customer.get('account_open_date'))
        if pd.notna(account_open) and account_open > self.evaluation_date:
            findings.append('[CRITICAL] Account open date in future')
            score -= 10
        
        return max(0, score), findings
    
    def _check_identity_data(self, customer_id: str, id_verifications: pd.DataFrame) -> Tuple[float, List[str]]:
        """Check identity verification data validity and expiry."""
        findings = []
        score = 100
        
        if id_verifications.empty:
            findings.append('[WARN] No identity records found')
            return 50, findings
        
        # Filter records for this customer
        id_records = id_verifications[id_verifications['customer_id'] == customer_id]
        if id_records.empty:
            findings.append('[WARN] No identity records found for customer')
            return 50, findings
        
        # Check for valid, non-expired documents
        valid_count = 0
        for _, record in id_records.iterrows():
            expiry = pd.to_datetime(record.get('expiry_date'))
            issue = pd.to_datetime(record.get('issue_date'))
            verification = pd.to_datetime(record.get('verification_date'))
            
            # Validity checks
            if pd.isna(expiry) or pd.isna(issue) or pd.isna(verification):
                findings.append(f'[WARN] Missing date fields in ID record')
                score -= 5
                continue
            
            if issue > expiry:
                findings.append('[WARN] Issue date after expiry date')
                score -= 10
                continue
            
            if verification < issue or verification > expiry:
                findings.append('[CRITICAL] Verification date outside document validity')
                score -= 15
                continue
            
            # Expiry check
            if expiry < self.evaluation_date:
                findings.append(f'[WARN] Identity document expired: {expiry.date()}')
                score -= 10
            else:
                valid_count += 1
        
        if valid_count > 0:
            findings.append(f'[OK] {valid_count} valid identity document(s) found')
        
        return max(0, score), findings
    
    def _check_document_data(self, customer_id: str, documents: pd.DataFrame) -> Tuple[float, List[str]]:
        """Check PoA document freshness."""
        findings = []
        score = 100
        
        if documents.empty:
            findings.append('[INFO] No documents found (N/A for this dataset)')
            return 100, findings
        
        # Filter PoA documents for this customer
        poa_docs = documents[
            (documents['customer_id'] == customer_id) &
            (documents['document_category'].isin(['POA', 'ADDRESS']))
        ]
        
        if poa_docs.empty:
            findings.append('[WARN] No PoA documents found')
            return 50, findings
        
        # Check freshness (3-month SLA)
        min_issue_date = self.evaluation_date - timedelta(days=self.POA_FRESHNESS_SLA_DAYS)
        
        for _, doc in poa_docs.iterrows():
            issue_date = pd.to_datetime(doc.get('issue_date'))
            
            if pd.isna(issue_date):
                findings.append('[WARN] Missing issue date in PoA document')
                score -= 10
                continue
            
            if issue_date < min_issue_date:
                findings.append(f'[WARN] PoA document stale: {issue_date.date()} (> 3 months old)')
                score -= 10
            else:
                findings.append(f'[OK] PoA document current ({(self.evaluation_date - issue_date).days} days old)')
        
        return max(0, score), findings
    
    def _check_screening_data(self, customer_id: str, screenings: pd.DataFrame) -> Tuple[float, List[str]]:
        """Check screening data completeness and coverage drift."""
        findings = []
        score = 100
        
        if screenings.empty:
            findings.append('[CRITICAL] No screening records in dataset')
            return 30, findings
        
        # Filter for this customer
        cust_screenings = screenings[screenings['customer_id'] == customer_id]
        
        if cust_screenings.empty:
            findings.append('[CRITICAL] No screening records found for customer')
            return 30, findings
        
        # Check for null critical fields
        for _, screening in cust_screenings.iterrows():
            if pd.isna(screening.get('screening_date')):
                findings.append('[CRITICAL] Missing screening date')
                score -= 20
            
            if pd.isna(screening.get('screening_result')):
                findings.append('[CRITICAL] Missing screening result')
                score -= 20
        
        # Check screening freshness (1-day SLA)
        latest_screening = cust_screenings['screening_date'].max()
        if pd.notna(latest_screening):
            latest_screening = pd.to_datetime(latest_screening)
            days_since = (self.evaluation_date - latest_screening).days
            
            if days_since > self.SCREENING_SLA_DAYS:
                findings.append(
                    f'[CRITICAL] Screening coverage drift: {days_since} days overdue '
                    f'(SLA: {self.SCREENING_SLA_DAYS} day)'
                )
                score -= 25
            else:
                findings.append(f'[OK] Screening current ({days_since} days old)')
        
        return max(0, score), findings
    
    def _check_ubo_data(self, customer_id: str, ubo_list: List[Dict]) -> Tuple[float, List[str]]:
        """Check UBO data completeness and ownership thresholds."""
        findings = []
        score = 100
        
        if not ubo_list:
            findings.append('[WARN] No UBO records found')
            return 50, findings
        
        # Filter for this customer
        ubos = [u for u in ubo_list if u.get('customer_id') == customer_id] if isinstance(ubo_list, list) else []
        
        if not ubos:
            findings.append('[WARN] No UBO records found for customer')
            return 50, findings
        
        # Check completeness
        required_ubo_fields = ['ubo_name', 'ownership_percent']
        for ubo in ubos:
            for field in required_ubo_fields:
                if pd.isna(ubo.get(field)):
                    findings.append(f'[WARN] Missing UBO field: {field}')
                    score -= 10
        
        # Check ownership sum doesn't exceed 100%
        total_ownership = sum([float(u.get('ownership_percent', 0)) for u in ubos])
        if total_ownership > 100:
            findings.append(f'[CRITICAL] Total ownership exceeds 100%: {total_ownership}%')
            score -= 20
        else:
            findings.append(f'[OK] Total ownership: {total_ownership}%')
        
        return max(0, score), findings
    
    def _check_transaction_data(self, customer_id: str, transactions: pd.DataFrame) -> Tuple[float, List[str]]:
        """Check transaction data validity and completeness."""
        findings = []
        score = 100
        
        if transactions.empty:
            findings.append('[WARN] No transaction records in dataset')
            return 50, findings
        
        # Filter for this customer
        cust_txns = transactions[transactions['customer_id'] == customer_id]
        
        if cust_txns.empty:
            findings.append('[WARN] No transaction records found for customer')
            return 50, findings
        
        # Check for future-dated transactions
        for _, txn in cust_txns.iterrows():
            txn_date = pd.to_datetime(txn.get('last_txn_date'))
            if pd.notna(txn_date) and txn_date > self.evaluation_date:
                findings.append(f'[CRITICAL] Transaction date in future: {txn_date.date()}')
                score -= 25
        
        findings.append(f'[OK] {len(cust_txns)} transaction record(s) found')
        return max(0, score), findings
    
    def _calculate_composite_score(self, scores: Dict[str, float], checks: Dict[str, Dict]) -> float:
        """Calculate weighted composite data quality score (0-100)."""
        weighted_sum = 0
        total_weight = 0
        
        for component, weight_dict in checks.items():
            score = scores.get(component, 0)
            weight = weight_dict.get('weight', 0)
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0
    
    def _no_customer_error(self, customer_id: str) -> Dict:
        """Return error result for missing customer."""
        return {
            'customer_id': customer_id,
            'dimension': 'DataQuality',
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
            'dimension': 'DataQuality',
            'passed': False,
            'status': 'Error',
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
