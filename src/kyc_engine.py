"""
kyc_engine.py
KYC Compliance Engine - Unified orchestration of 6 compliance dimensions.

Orchestrates:
- AML Screening (25%)
- Identity Verification (20%)
- Account Activity (15%)
- Proof of Address (15%)
- Beneficial Ownership (15%)
- Data Quality (10%)

Returns composite compliance scores and status.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional


class KYCComplianceEngine:
    """
    Unified KYC compliance evaluation engine.
    
    Evaluates customers across 6 dimensions and returns composite scores.
    """
    
    # Dimension weights (must sum to 100%)
    DIMENSION_WEIGHTS = {
        'aml_screening': 0.25,
        'identity_verification': 0.20,
        'account_activity': 0.15,
        'proof_of_address': 0.15,
        'beneficial_ownership': 0.15,
        'data_quality': 0.10
    }
    
    # Score thresholds
    SCORE_THRESHOLDS = {
        'compliant': 90,
        'minor_gaps': 70,
        'non_compliant': 0
    }
    
    def __init__(self, data_clean_dir: Path = None):
        """
        Initialize KYC engine with data.
        
        Args:
            data_clean_dir: Path to Data Clean directory with CSV files
        """
        self.data_clean_dir = data_clean_dir or Path.cwd() / 'Data Clean'
        
        # Load all datasets
        self.customers = self._load_dataframe('customers_clean.csv')
        self.screenings = self._load_dataframe('screenings_clean.csv')
        self.id_verifications = self._load_dataframe('id_verifications_clean.csv')
        self.transactions = self._load_dataframe('transactions_clean.csv')
        self.beneficial_owners = self._load_dataframe('beneficial_ownership_clean.csv')
    
    def _load_dataframe(self, filename: str) -> pd.DataFrame:
        """Load CSV file into DataFrame, return empty if not found."""
        filepath = self.data_clean_dir / filename
        try:
            return pd.read_csv(filepath)
        except FileNotFoundError:
            return pd.DataFrame()
    
    # =========================================================================
    # DIMENSION 1: AML SCREENING (25%)
    # =========================================================================
    
    def evaluate_aml_screening(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate AML Screening dimension.
        
        Checks: Sanctions list matches, screening recency, hit status
        
        Scoring:
        - No match + recent screening: 100
        - No match + old screening: 80
        - False positive match: 70
        - Confirmed match: 0
        - No screening record: 30
        """
        
        if self.customers is None or customer_id not in self.customers['customer_id'].values:
            return 0, {'error': 'Customer not found'}
        
        if self.screenings is None or len(self.screenings) == 0:
            return 30, {
                'status': 'no_screening_data',
                'finding': 'No screening records available'
            }
        
        # Get screening record
        screening = self.screenings[
            self.screenings['customer_id'] == customer_id
        ]
        
        if len(screening) == 0:
            return 30, {'status': 'no_screening_record'}
        
        screening = screening.iloc[0]
        result = screening['screening_result']
        hit_status = screening.get('hit_status')
        
        # Score based on result
        if result == 'NO_MATCH':
            # Check screening date recency
            try:
                screening_date = pd.to_datetime(screening['screening_date'])
                days_ago = (datetime.now() - screening_date).days
                
                if days_ago <= 90:
                    score = 100
                elif days_ago <= 180:
                    score = 85
                else:
                    score = 70  # Stale screening
            except:
                score = 80
            
            return score, {
                'status': 'no_match',
                'list_reference': screening.get('list_reference', 'N/A'),
                'finding': 'Customer not on sanctions lists'
            }
        
        elif result == 'MATCH':
            if hit_status == 'FALSE_POSITIVE':
                return 70, {
                    'status': 'false_positive',
                    'match_name': screening.get('match_name'),
                    'list_reference': screening.get('list_reference'),
                    'finding': 'Match is false positive (similar name)'
                }
            elif hit_status == 'CONFIRMED':
                return 0, {
                    'status': 'confirmed_match',
                    'match_name': screening.get('match_name'),
                    'list_reference': screening.get('list_reference'),
                    'finding': 'Customer confirmed on sanctions list - HIGH RISK'
                }
            else:
                return 50, {
                    'status': 'match_requires_review',
                    'match_name': screening.get('match_name'),
                    'finding': 'Match requires manual review'
                }
        
        return 30, {'status': 'unknown_screening_result'}
    
    # =========================================================================
    # DIMENSION 2: IDENTITY VERIFICATION (20%)
    # =========================================================================
    
    def evaluate_identity_verification(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate Identity Verification dimension.
        
        Checks: Document presence, status (VERIFIED/EXPIRED/PENDING), document types
        
        Scoring:
        - At least 1 VERIFIED document: 100
        - VERIFIED + EXPIRED: 80
        - Only PENDING documents: 40
        - Only EXPIRED documents: 20
        - No documents: 0
        """
        
        if self.id_verifications is None or len(self.id_verifications) == 0:
            return 0, {'status': 'no_id_data', 'finding': 'No identity documents available'}
        
        # Get ID records for customer
        ids = self.id_verifications[
            self.id_verifications['customer_id'] == customer_id
        ]
        
        if len(ids) == 0:
            return 0, {'status': 'no_documents', 'finding': 'No identity documents on file'}
        
        # Analyze document statuses
        statuses = ids['document_status'].value_counts().to_dict()
        doc_types = ids['document_type'].unique().tolist()
        
        verified_count = statuses.get('VERIFIED', 0)
        expired_count = statuses.get('EXPIRED', 0)
        pending_count = statuses.get('PENDING', 0)
        rejected_count = statuses.get('REJECTED', 0)
        
        # Scoring logic
        if verified_count > 0:
            if expired_count > 0:
                score = 80  # Has verified but also expired (minor gap)
            else:
                score = 100  # Clean verification
            
            finding = f'{verified_count} verified document(s)'
        elif pending_count > 0:
            score = 40
            finding = f'Verification pending on {pending_count} document(s)'
        elif expired_count > 0:
            score = 20
            finding = f'All documents expired ({expired_count})'
        else:
            score = 0
            finding = 'All documents rejected or invalid'
        
        return score, {
            'status': 'identity_documents',
            'verified': verified_count,
            'expired': expired_count,
            'pending': pending_count,
            'rejected': rejected_count,
            'document_types': doc_types,
            'finding': finding
        }
    
    # =========================================================================
    # DIMENSION 3: ACCOUNT ACTIVITY (15%)
    # =========================================================================
    
    def evaluate_account_activity(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate Account Activity dimension.
        
        Checks: Transaction patterns, frequency, volume consistency
        
        Scoring:
        - REGULAR pattern: 100
        - IRREGULAR pattern: 70
        - SUSPICIOUS pattern: 20
        - No transactions: 30
        """
        
        if self.transactions is None or len(self.transactions) == 0:
            return 30, {'status': 'no_transaction_data'}
        
        # Get transaction record
        txn = self.transactions[
            self.transactions['customer_id'] == customer_id
        ]
        
        if len(txn) == 0:
            return 30, {
                'status': 'no_transactions',
                'finding': 'No transaction activity on record'
            }
        
        txn = txn.iloc[0]
        pattern = txn.get('transaction_pattern', 'UNKNOWN')
        frequency = txn.get('transaction_frequency', 'N/A')
        
        # Score based on pattern
        if pattern == 'REGULAR':
            score = 100
            finding = 'Regular, predictable transaction patterns'
        elif pattern == 'IRREGULAR':
            score = 70
            finding = 'Irregular transaction patterns - requires monitoring'
        elif pattern == 'SUSPICIOUS':
            score = 20
            finding = 'Suspicious patterns detected (structuring, unusual amounts)'
        else:
            score = 50
            finding = 'Unknown transaction pattern'
        
        return score, {
            'status': 'transaction_analysis',
            'pattern': pattern,
            'frequency': frequency,
            'txn_count': int(txn.get('txn_count', 0)),
            'total_volume': float(txn.get('total_volume', 0)),
            'average_size': float(txn.get('average_txn_size', 0)),
            'finding': finding
        }
    
    # =========================================================================
    # DIMENSION 4: PROOF OF ADDRESS (15%)
    # =========================================================================
    
    def evaluate_proof_of_address(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate Proof of Address dimension.
        
        Checks: Presence of address verification documents, recency
        
        Note: Currently uses id_verifications as proxy for POA
        
        Scoring:
        - Recent verified POA document: 100
        - Old but verified POA: 70
        - Pending POA: 40
        - No POA: 0
        """
        
        # For now, use ID verifications as proxy for POA
        # In production, would use dedicated POA documents (utility bills, etc.)
        
        if self.id_verifications is None or len(self.id_verifications) == 0:
            return 30, {'status': 'no_poa_data', 'finding': 'No proof of address available'}
        
        # Get address verification records (for now, any ID serves as proxy)
        poa = self.id_verifications[
            self.id_verifications['customer_id'] == customer_id
        ]
        
        if len(poa) == 0:
            return 0, {'status': 'no_address_verification'}
        
        # Check for verified documents
        verified = poa[poa['document_status'] == 'VERIFIED']
        
        if len(verified) > 0:
            try:
                verify_date = pd.to_datetime(verified.iloc[0]['verification_date'])
                days_ago = (datetime.now() - verify_date).days
                
                if days_ago <= 365:
                    score = 100
                else:
                    score = 70
            except:
                score = 80
            
            finding = 'Proof of address verified'
        else:
            pending = poa[poa['document_status'] == 'PENDING']
            if len(pending) > 0:
                score = 40
                finding = 'Proof of address verification pending'
            else:
                score = 20
                finding = 'Address verification stale or expired'
        
        return score, {
            'status': 'address_verification',
            'documents_on_file': len(poa),
            'verified_documents': len(verified),
            'finding': finding
        }
    
    # =========================================================================
    # DIMENSION 5: BENEFICIAL OWNERSHIP (15%)
    # =========================================================================
    
    def evaluate_beneficial_ownership(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate Beneficial Ownership dimension.
        
        Checks: For corporates/partnerships, presence of UBO records, PEP status
        
        Scoring:
        - INDIVIDUAL (not applicable): 100
        - Corporate with UBOs documented, no PEPs: 100
        - Corporate with UBOs, has LOW_PEP: 80
        - Corporate with UBOs, has MEDIUM/HIGH_PEP: 40
        - Corporate with missing UBOs: 20
        """
        
        if self.customers is None or customer_id not in self.customers['customer_id'].values:
            return 0, {'error': 'Customer not found'}
        
        customer = self.customers[
            self.customers['customer_id'] == customer_id
        ].iloc[0]
        
        entity_type = customer.get('entity_type', 'UNKNOWN')
        
        # INDIVIDUAL entities don't require UBOs
        if entity_type == 'INDIVIDUAL':
            return 100, {
                'status': 'not_applicable',
                'entity_type': entity_type,
                'finding': 'Individual customers do not require beneficial ownership documentation'
            }
        
        # Corporate/Partnership - check for UBOs
        if self.beneficial_owners is None or len(self.beneficial_owners) == 0:
            return 20, {
                'status': 'no_ubo_data',
                'entity_type': entity_type,
                'finding': 'No beneficial ownership data available'
            }
        
        ubos = self.beneficial_owners[
            self.beneficial_owners['customer_id'] == customer_id
        ]
        
        if len(ubos) == 0:
            return 20, {
                'status': 'no_ubos_documented',
                'entity_type': entity_type,
                'finding': 'Corporate entity missing beneficial ownership documentation'
            }
        
        # Analyze UBO risk
        pep_statuses = ubos['pep_status'].value_counts().to_dict()
        has_high_pep = pep_statuses.get('HIGH_PEP', 0) > 0
        has_medium_pep = pep_statuses.get('MEDIUM_PEP', 0) > 0
        has_low_pep = pep_statuses.get('LOW_PEP', 0) > 0
        
        sanctioned = ubos[ubos['sanctioned_jurisdiction'] == 'YES']
        
        if has_high_pep or len(sanctioned) > 0:
            score = 40
            finding = 'UBOs documented but includes PEPs or sanctioned jurisdictions'
        elif has_medium_pep:
            score = 70
            finding = 'UBOs documented with medium-risk PEPs'
        elif has_low_pep:
            score = 85
            finding = 'UBOs documented with low-risk associates'
        else:
            score = 100
            finding = 'UBOs fully documented, no PEP concerns'
        
        return score, {
            'status': 'beneficial_ownership',
            'entity_type': entity_type,
            'ubo_count': len(ubos),
            'high_peps': pep_statuses.get('HIGH_PEP', 0),
            'medium_peps': pep_statuses.get('MEDIUM_PEP', 0),
            'low_peps': pep_statuses.get('LOW_PEP', 0),
            'sanctioned_ubos': len(sanctioned),
            'finding': finding
        }
    
    # =========================================================================
    # DIMENSION 6: DATA QUALITY (10%)
    # =========================================================================
    
    def evaluate_data_quality(self, customer_id: str) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate Data Quality dimension.
        
        Checks: Completeness, consistency, age of data
        
        Scoring:
        - Complete recent data: 100
        - Complete but older data: 80
        - Incomplete or missing fields: 50
        - Significant gaps: 20
        """
        
        if self.customers is None or customer_id not in self.customers['customer_id'].values:
            return 0, {'error': 'Customer not found'}
        
        customer = self.customers[
            self.customers['customer_id'] == customer_id
        ].iloc[0]
        
        # Check for null values in critical fields
        null_count = customer.isnull().sum()
        total_fields = len(customer)
        
        # Check data age
        try:
            review_date = pd.to_datetime(customer['last_kyc_review_date'])
            days_since_review = (datetime.now() - review_date).days
        except:
            days_since_review = 999
        
        # Scoring logic
        if null_count == 0:
            if days_since_review <= 365:
                score = 100
            elif days_since_review <= 730:
                score = 80
            else:
                score = 60
            quality_rating = 'Excellent'
        elif null_count <= 2:
            score = 70
            quality_rating = 'Good'
        elif null_count <= 4:
            score = 40
            quality_rating = 'Fair'
        else:
            score = 20
            quality_rating = 'Poor'
        
        return score, {
            'status': 'data_quality',
            'quality_rating': quality_rating,
            'null_fields': int(null_count),
            'total_fields': int(total_fields),
            'days_since_review': int(days_since_review),
            'finding': f'Data quality {quality_rating.lower()} - {null_count} missing fields, last reviewed {days_since_review} days ago'
        }
    
    # =========================================================================
    # COMPOSITE SCORING & REPORTING
    # =========================================================================
    
    def evaluate_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Evaluate a single customer across all 6 dimensions.
        
        Returns comprehensive compliance profile.
        """
        
        # Evaluate each dimension
        aml_score, aml_details = self.evaluate_aml_screening(customer_id)
        id_score, id_details = self.evaluate_identity_verification(customer_id)
        activity_score, activity_details = self.evaluate_account_activity(customer_id)
        poa_score, poa_details = self.evaluate_proof_of_address(customer_id)
        ubo_score, ubo_details = self.evaluate_beneficial_ownership(customer_id)
        dq_score, dq_details = self.evaluate_data_quality(customer_id)
        
        # Calculate weighted overall score
        overall_score = (
            aml_score * self.DIMENSION_WEIGHTS['aml_screening'] +
            id_score * self.DIMENSION_WEIGHTS['identity_verification'] +
            activity_score * self.DIMENSION_WEIGHTS['account_activity'] +
            poa_score * self.DIMENSION_WEIGHTS['proof_of_address'] +
            ubo_score * self.DIMENSION_WEIGHTS['beneficial_ownership'] +
            dq_score * self.DIMENSION_WEIGHTS['data_quality']
        )
        
        # Determine status
        if overall_score >= self.SCORE_THRESHOLDS['compliant']:
            status = 'Compliant'
        elif overall_score >= self.SCORE_THRESHOLDS['minor_gaps']:
            status = 'Compliant with Minor Gaps'
        else:
            status = 'Non-Compliant'
        
        return {
            'customer_id': customer_id,
            'aml_screening_score': round(aml_score, 1),
            'aml_screening_details': aml_details,
            'identity_verification_score': round(id_score, 1),
            'identity_verification_details': id_details,
            'account_activity_score': round(activity_score, 1),
            'account_activity_details': activity_details,
            'proof_of_address_score': round(poa_score, 1),
            'proof_of_address_details': poa_details,
            'beneficial_ownership_score': round(ubo_score, 1),
            'beneficial_ownership_details': ubo_details,
            'data_quality_score': round(dq_score, 1),
            'data_quality_details': dq_details,
            'overall_score': round(overall_score, 1),
            'overall_status': status,
            'evaluation_date': datetime.now().isoformat()
        }
    
    def evaluate_batch(self, customer_ids: List[str]) -> pd.DataFrame:
        """
        Evaluate multiple customers and return DataFrame with results.
        
        Args:
            customer_ids: List of customer IDs to evaluate
            
        Returns:
            DataFrame with compliance scores
        """
        results = []
        
        for customer_id in customer_ids:
            result = self.evaluate_customer(customer_id)
            results.append(result)
        
        # Convert to DataFrame, selecting only numeric scores
        df = pd.DataFrame(results)
        
        # Reorder columns for readability
        score_cols = [
            'customer_id',
            'aml_screening_score',
            'identity_verification_score',
            'account_activity_score',
            'proof_of_address_score',
            'beneficial_ownership_score',
            'data_quality_score',
            'overall_score',
            'overall_status'
        ]
        
        return df[[col for col in score_cols if col in df.columns]]
    
    def generate_compliance_report(self, customer_ids: List[str]) -> str:
        """
        Generate human-readable compliance report.
        
        Args:
            customer_ids: List of customer IDs
            
        Returns:
            Formatted report string
        """
        results = self.evaluate_batch(customer_ids)
        
        compliant = len(results[results['overall_status'] == 'Compliant'])
        minor_gaps = len(results[results['overall_status'] == 'Compliant with Minor Gaps'])
        non_compliant = len(results[results['overall_status'] == 'Non-Compliant'])
        
        report = f"""
KYC COMPLIANCE EVALUATION REPORT
{'='*70}

Evaluation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Customers Evaluated: {len(results)}

COMPLIANCE SUMMARY
{'='*70}
Compliant: {compliant} ({compliant/len(results)*100:.1f}%)
Compliant with Minor Gaps: {minor_gaps} ({minor_gaps/len(results)*100:.1f}%)
Non-Compliant: {non_compliant} ({non_compliant/len(results)*100:.1f}%)

DIMENSION BREAKDOWN
{'='*70}
Average Scores:
  AML Screening:              {results['aml_screening_score'].mean():.1f}/100 (25% weight)
  Identity Verification:      {results['identity_verification_score'].mean():.1f}/100 (20% weight)
  Account Activity:           {results['account_activity_score'].mean():.1f}/100 (15% weight)
  Proof of Address:           {results['proof_of_address_score'].mean():.1f}/100 (15% weight)
  Beneficial Ownership:       {results['beneficial_ownership_score'].mean():.1f}/100 (15% weight)
  Data Quality:               {results['data_quality_score'].mean():.1f}/100 (10% weight)

OVERALL AVERAGE SCORE: {results['overall_score'].mean():.1f}/100

TOP PERFORMERS (Highest Compliance)
{'='*70}
"""
        top_performers = results.nlargest(5, 'overall_score')
        for idx, row in top_performers.iterrows():
            report += f"{row['customer_id']}: {row['overall_score']:.1f} - {row['overall_status']}\n"
        
        report += f"\nRISK AREAS (Lowest Compliance)\n{'='*70}\n"
        risk_areas = results.nsmallest(5, 'overall_score')
        for idx, row in risk_areas.iterrows():
            report += f"{row['customer_id']}: {row['overall_score']:.1f} - {row['overall_status']}\n"
        
        return report


def main():
    """Demo the KYC engine."""
    print("[*] Initializing KYC Compliance Engine...")
    
    engine = KYCComplianceEngine()
    
    print("[OK] Engine initialized with 6 dimensions")
    print(f"    Customers: {len(engine.customers)}")
    print(f"    Screenings: {len(engine.screenings)}")
    print(f"    ID Verifications: {len(engine.id_verifications)}")
    print(f"    Transactions: {len(engine.transactions)}")
    print(f"    Beneficial Owners: {len(engine.beneficial_owners)}\n")
    
    if len(engine.customers) > 0:
        # Evaluate first customer
        first_customer = engine.customers.iloc[0]['customer_id']
        print(f"[*] Evaluating sample customer: {first_customer}\n")
        
        result = engine.evaluate_customer(first_customer)
        
        print(f"Overall Score: {result['overall_score']}/100")
        print(f"Status: {result['overall_status']}\n")
        
        print("Dimension Scores:")
        print(f"  AML Screening: {result['aml_screening_score']}/100")
        print(f"  Identity Verification: {result['identity_verification_score']}/100")
        print(f"  Account Activity: {result['account_activity_score']}/100")
        print(f"  Proof of Address: {result['proof_of_address_score']}/100")
        print(f"  Beneficial Ownership: {result['beneficial_ownership_score']}/100")
        print(f"  Data Quality: {result['data_quality_score']}/100\n")
        
        print("[SUCCESS] KYC Engine operational!")


if __name__ == '__main__':
    main()
