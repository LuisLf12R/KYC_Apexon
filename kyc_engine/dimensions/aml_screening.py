"""
AML Screening Dimension
-----------------------
Validates AML/sanctions screening compliance across jurisdictions.

Core Logic:
1. NO_HIT → Compliant for last screening, schedule next based on risk tier
2. HIT (unresolved/under_review) → Non-compliant, needs manual review
3. HIT (resolved) → Status depends on resolution type (approved/blocked/false_positive)
4. Overdue screenings → Flag regardless of hit status
5. Risk-based re-screening: HIGH=90d, MEDIUM=180d, LOW=365d
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import logging

from src.data.contracts import get_contract

logger = logging.getLogger(__name__)


class AMLScreeningDimension:
    """
    AML Screening Compliance Validator.
    
    Evaluates customer AML screening status against:
    - Hit management (resolution timeliness, decision logic)
    - Re-screening frequency (risk-based intervals)
    - Jurisdictional compliance (extensible for jurisdiction-specific rules)
    """
    
    # Risk-based re-screening intervals (days)
    SCREENING_INTERVALS = {
        'HIGH': 90,      # Quarterly
        'MEDIUM': 180,   # Semi-annual
        'LOW': 365,      # Annual
    }
    
    # Maximum acceptable resolution times (days) by match severity
    RESOLUTION_SLAS = {
        'EXACT_MATCH': 7,          # 7 days for exact matches
        'FUZZY_MATCH': 14,         # 14 days for fuzzy matches
        'POTENTIAL_MATCH': 30,     # 30 days for potential matches
    }
    
    # Resolved statuses that indicate case closure
    RESOLVED_STATUSES = {'FALSE_POSITIVE', 'RESOLVED_APPROVED', 'RESOLVED_BLOCKED'}
    UNRESOLVED_STATUSES = {'UNRESOLVED', 'UNDER_REVIEW'}
    
    def __init__(self, evaluation_date: datetime = None):
        """
        Initialize AML Screening Dimension.
        
        Args:
            evaluation_date: Fixed date for compliance evaluation (default: 2026-04-09)
        """
        self.evaluation_date = evaluation_date or datetime(2026, 4, 9)
        logger.info(f"AMLScreeningDimension initialized. Evaluation date: {self.evaluation_date.date()}")
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate AML screening compliance for a single customer.
        
        Args:
            customer_id: Customer identifier
            data: Dict with 'customers' and 'screenings' DataFrames
        
        Returns:
            Dict with compliance status, findings, and remediation guidance
        """
        try:
            customers_df = data['customers']
            screenings_df = data['screenings']
            
            # Get customer record
            customer = customers_df[customers_df['customer_id'] == customer_id]
            if customer.empty:
                return self._error_result(customer_id, f"Customer {customer_id} not found")
            
            customer = customer.iloc[0]
            risk_rating = customer['risk_rating']
            jurisdiction = customer.get('jurisdiction', 'UNKNOWN')
            
            # Get customer's screening records
            customer_screenings = screenings_df[screenings_df['customer_id'] == customer_id].copy()
            
            if customer_screenings.empty:
                return self._missing_screenings_result(customer_id, risk_rating, jurisdiction)
            
            # Sort by date descending to get most recent
            customer_screenings['screening_date'] = pd.to_datetime(customer_screenings['screening_date'])
            customer_screenings = customer_screenings.sort_values('screening_date', ascending=False)
            
            # Most recent screening
            last_screening = customer_screenings.iloc[0]
            last_screening_date = last_screening['screening_date']
            screening_result = last_screening['screening_result']
            
            # Evaluate screening status
            screening_evaluation = self._evaluate_screening_result(last_screening)
            
            # Evaluate re-screening due date
            rescreening_evaluation = self._evaluate_rescreening_status(
                last_screening_date, risk_rating
            )
            
            # Evaluate hit resolution (if applicable)
            hit_evaluation = self._evaluate_hit_resolution(last_screening) if screening_result != 'NO_HIT' else None
            
            # Determine overall compliance
            overall_passed = self._determine_compliance(
                screening_evaluation, rescreening_evaluation, hit_evaluation
            )
            
            # Compile findings
            findings = self._compile_findings(
                screening_evaluation, rescreening_evaluation, hit_evaluation, risk_rating
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'AML Screening',
                'passed': overall_passed,
                'status': 'Compliant' if overall_passed else 'Non-Compliant',
                
                'evaluation_details': {
                    'risk_rating': risk_rating,
                    'jurisdiction': jurisdiction,
                    
                    'screening_evaluation': screening_evaluation,
                    'rescreening_evaluation': rescreening_evaluation,
                    'hit_evaluation': hit_evaluation,
                    
                    'last_screening_date': last_screening_date.date().isoformat(),
                    'days_since_last_screening': rescreening_evaluation['days_since_last_screening'],
                    'next_screening_due': rescreening_evaluation['next_screening_due'].isoformat(),
                    'screening_overdue': rescreening_evaluation['overdue'],
                },
                
                'findings': findings,
                'remediation_required': not overall_passed,
                'next_review_date': (self.evaluation_date + timedelta(days=90)).date().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating customer {customer_id}: {e}")
            return self._error_result(customer_id, str(e))
    
    def _evaluate_screening_result(self, screening_record: pd.Series) -> Dict[str, Any]:
        """
        Evaluate the screening result (hit vs no-hit).
        
        Returns:
            Dict with screening status and details
        """
        screening_result = screening_record['screening_result']
        
        if screening_result == 'NO_HIT':
            return {
                'screening_result': 'NO_HIT',
                'screening_status': 'NO_HIT',
                'compliance_status': 'COMPLIANT_LAST_SCREENING',
                'hit_severity': None,
                'match_name': None,
                'match_score': None,
                'list_reference': screening_record.get('list_reference'),
            }
        
        # Hit detected
        return {
            'screening_result': screening_result,
            'screening_status': 'HIT_DETECTED',
            'hit_severity': screening_result,  # EXACT_MATCH, FUZZY_MATCH, POTENTIAL_MATCH
            'match_name': screening_record.get('match_name'),
            'match_score': screening_record.get('match_score'),
            'list_reference': screening_record.get('list_reference'),
        }
    
    def _evaluate_rescreening_status(self, last_screening_date: datetime, risk_rating: str) -> Dict[str, Any]:
        """
        Evaluate re-screening due date and overdue status.
        
        Returns:
            Dict with rescreening schedule and overdue flag
        """
        allowed_interval = self.SCREENING_INTERVALS.get(risk_rating, 365)
        
        days_since = (self.evaluation_date - last_screening_date).days
        next_screening_due = last_screening_date + timedelta(days=allowed_interval)
        overdue = days_since > allowed_interval
        
        return {
            'risk_rating': risk_rating,
            'allowed_interval_days': allowed_interval,
            'days_since_last_screening': days_since,
            'next_screening_due': next_screening_due,
            'overdue': overdue,
            'days_overdue': max(0, days_since - allowed_interval),
        }
    
    def _evaluate_hit_resolution(self, screening_record: pd.Series) -> Dict[str, Any]:
        """
        Evaluate hit resolution status, timeliness, and compliance outcome.
        
        Returns:
            Dict with hit resolution details
        """
        resolution_status = screening_record.get('resolution_status')
        resolution_date = screening_record.get('resolution_date')
        screening_date = screening_record['screening_date']
        hit_severity = screening_record['screening_result']
        
        # Convert dates
        screening_date = pd.to_datetime(screening_date)
        if resolution_date:
            resolution_date = pd.to_datetime(resolution_date)
        
        # Determine compliance based on resolution status
        if resolution_status in self.UNRESOLVED_STATUSES:
            compliance_status = 'NON_COMPLIANT_PENDING_REVIEW'
            needs_manual_review = True
            days_to_resolution = None
            sla_breached = None
        else:
            needs_manual_review = False
            days_to_resolution = (resolution_date - screening_date).days if resolution_date else None
            
            # Check SLA
            sla_limit = self.RESOLUTION_SLAS.get(hit_severity, 30)
            sla_breached = days_to_resolution > sla_limit if days_to_resolution else False
            
            # Map resolution status to compliance status
            if resolution_status == 'FALSE_POSITIVE':
                compliance_status = 'COMPLIANT_FALSE_POSITIVE'
            elif resolution_status == 'RESOLVED_APPROVED':
                compliance_status = 'COMPLIANT_APPROVED_HIT'
            elif resolution_status == 'RESOLVED_BLOCKED':
                compliance_status = 'NON_COMPLIANT_BLOCKED_RELATIONSHIP'
            else:
                compliance_status = 'UNKNOWN'
        
        return {
            'resolution_status': resolution_status,
            'compliance_status': compliance_status,
            'needs_manual_review': needs_manual_review,
            'hit_severity': hit_severity,
            'resolution_date': resolution_date.date().isoformat() if resolution_date else None,
            'days_to_resolution': days_to_resolution,
            'sla_limit_days': self.RESOLUTION_SLAS.get(hit_severity),
            'sla_breached': sla_breached,
        }
    
    def _determine_compliance(self, screening_eval: Dict, rescreening_eval: Dict, hit_eval: Dict) -> bool:
        """
        Determine overall compliance based on all three evaluations.
        
        Returns:
            True if compliant, False otherwise
        """
        # Fail if screening is overdue
        if rescreening_eval['overdue']:
            return False
        
        # Fail if no-hit but there's a hit evaluation (contradiction)
        if screening_eval['screening_status'] == 'NO_HIT':
            return True  # No-hit is compliant (assuming next screening scheduled)
        
        # For hits: only compliant if properly resolved
        if hit_eval:
            compliance_status = hit_eval['compliance_status']
            
            # Non-compliant statuses
            if compliance_status in {'NON_COMPLIANT_PENDING_REVIEW', 'NON_COMPLIANT_BLOCKED_RELATIONSHIP'}:
                return False
            
            # Check if SLA breached (warning, but still compliant)
            if hit_eval['sla_breached']:
                logger.warning(f"SLA breached for hit resolution")
            
            return True  # Other resolved statuses are compliant
        
        return True
    
    def _compile_findings(self, screening_eval: Dict, rescreening_eval: Dict, hit_eval: Dict, risk_rating: str) -> List[str]:
        """
        Compile human-readable findings from all evaluations.
        
        Returns:
            List of finding strings
        """
        findings = []
        
        # Screening findings
        if screening_eval['screening_status'] == 'NO_HIT':
            findings.append(f" Last screening ({screening_eval['list_reference']}) returned NO_HIT")
        else:
            findings.append(f" Hit detected: {screening_eval['hit_severity']} on {screening_eval['list_reference']}")
            if screening_eval['match_name']:
                findings.append(f"  Matched name: {screening_eval['match_name']} (score: {screening_eval['match_score']})")
        
        # Rescreening findings
        if rescreening_eval['overdue']:
            findings.append(
                f" Screening OVERDUE: Last screening was {rescreening_eval['days_since_last_screening']} days ago "
                f"({rescreening_eval['days_overdue']} days past {risk_rating}-risk interval of {rescreening_eval['allowed_interval_days']} days)"
            )
        else:
            findings.append(
                f"✓ On schedule: {rescreening_eval['days_since_last_screening']} days since last screening "
                f"(next due: {rescreening_eval['next_screening_due'].date()})"
            )
        
        # Hit resolution findings
        if hit_eval:
            if hit_eval['needs_manual_review']:
                findings.append(
                    f" Hit requires manual review: Status is {hit_eval['resolution_status']}"
                )
            else:
                findings.append(
                    f" Hit resolved as {hit_eval['resolution_status']} in {hit_eval['days_to_resolution']} days"
                )
                if hit_eval['sla_breached']:
                    findings.append(
                        f" SLA breached: {hit_eval['days_to_resolution']} days (limit: {hit_eval['sla_limit_days']})"
                    )
        
        return findings
    
    def _missing_screenings_result(self, customer_id: str, risk_rating: str, jurisdiction: str) -> Dict[str, Any]:
        """Generate result for customer with no screening records."""
        return {
            'customer_id': customer_id,
            'dimension': 'AML Screening',
            'passed': False,
            'status': 'Non-Compliant',
            'evaluation_details': {
                'risk_rating': risk_rating,
                'jurisdiction': jurisdiction,
                'screening_evaluation': None,
                'rescreening_evaluation': None,
                'hit_evaluation': None,
            },
            'findings': ['✗ No AML screening records found for customer'],
            'remediation_required': True,
            'next_review_date': self.evaluation_date.date().isoformat(),
        }
    
    def _error_result(self, customer_id: str, error_msg: str) -> Dict[str, Any]:
        """Generate error result."""
        return {
            'customer_id': customer_id,
            'dimension': 'AML Screening',
            'passed': False,
            'status': 'Error',
            'findings': [f"Error: {error_msg}"],
            'remediation_required': True,
        }


# For testing
if __name__ == "__main__":
    from src.logging_config import setup_logging
    from src.config import Config
    from src.data_loader import DataLoader
    
    setup_logging("INFO")
    
    config = Config()
    loader = DataLoader(config)
    
    try:
        data = loader.load_all()
        dimension = AMLScreeningDimension()
        
        # Test on first customer
        result = dimension.evaluate('C001', data)
        
        print("\n" + "="*70)
        print("AML SCREENING DIMENSION TEST RESULT")
        print("="*70)
        print(f"\nCustomer: {result['customer_id']}")
        print(f"Status: {result['status']}")
        print(f"\nFindings:")
        for finding in result['findings']:
            print(f"  {finding}")
        
    except Exception as e:
        print(f"Test failed: {e}")