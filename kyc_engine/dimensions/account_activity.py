"""
Account Activity Dimension
---------------------------
Evaluates customer account activity status, dormancy, and behavioral anomalies.

Core Logic:
1. Activity Status: ACTIVE, INACTIVE, DORMANT based on days_since_last_txn
2. Event Triggers: Reactivation, volume spikes, anomalous patterns
3. Risk-Based Monitoring: Compliance tied to risk tier and KYC review cycles
4. Jurisdiction-Ready: Global baseline with override hooks for jurisdiction-specific rules
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import logging

from rules.schema.dimensions import TransactionParameters

logger = logging.getLogger(__name__)


class AccountActivityDimension:
    """
    Account Activity Compliance Validator.
    
    Evaluates customer account activity status against:
    - Dormancy thresholds (global + jurisdiction-overridable)
    - Risk-based activity monitoring intervals
    - Event-driven triggers (reactivation, volume spikes, anomalies)
    - Expected activity profiles
    """
    
    # Global dormancy thresholds (days)
    DORMANCY_THRESHOLDS = {
        'ACTIVE': 180,      # 0-180 days
        'INACTIVE': 365,    # 181-365 days
        'DORMANT': 365,     # 365+ days
    }
    
    # Risk-based KYC review intervals (months)
    KYC_REVIEW_INTERVALS = {
        'HIGH': 12,
        'MEDIUM': 24,
        'LOW': 36,
    }
    
    # Volume spike multiplier (3x avg = spike)
    VOLUME_SPIKE_MULTIPLIER = 3.0
    
    # Minimum transaction count for spike detection
    MIN_TXN_COUNT_FOR_SPIKE = 5
    
    def __init__(self, params: TransactionParameters, evaluation_date=None):
        """
        Initialize Account Activity Dimension.
        
        Args:
            evaluation_date: Fixed date for compliance evaluation (default: 2026-04-09)
        """
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
        logger.info(f"AccountActivityDimension initialized. Evaluation date: {self.evaluation_date.date()}")
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate account activity compliance for a single customer.
        
        Args:
            customer_id: Customer identifier
            data: Dict with 'customers' and 'transactions' DataFrames
        
        Returns:
            Dict with activity status, flags, and compliance determination
        """
        try:
            customers_df = data['customers']
            transactions_df = data['transactions']
            
            # Get customer record
            customer = customers_df[customers_df['customer_id'] == customer_id]
            if customer.empty:
                return self._error_result(customer_id, f"Customer {customer_id} not found")
            
            customer = customer.iloc[0]
            risk_rating = customer['risk_rating']
            jurisdiction = customer.get('jurisdiction', 'UNKNOWN')
            
            # Get customer's transaction records
            customer_txns = transactions_df[transactions_df['customer_id'] == customer_id].copy()
            
            if customer_txns.empty:
                return self._no_transactions_result(customer_id, risk_rating, jurisdiction)
            
            # Parse dates
            customer_txns['last_txn_date'] = pd.to_datetime(customer_txns['last_txn_date'])
            
            # Get most recent transaction
            last_txn_date = customer_txns['last_txn_date'].max()
            
            # Evaluate activity status
            activity_eval = self._evaluate_activity_status(last_txn_date, jurisdiction)
            
            # Evaluate transaction metrics
            txn_metrics = self._calculate_transaction_metrics(customer_txns)
            
            # Detect event triggers
            triggers = self._detect_event_triggers(
                activity_eval, txn_metrics, customer
            )
            
            # Evaluate KYC review alignment
            kyc_eval = self._evaluate_kyc_review_alignment(
                activity_eval['activity_status'], risk_rating
            )
            
            # Determine compliance
            compliance_flag, passed = self._determine_compliance(
                activity_eval, triggers, kyc_eval
            )
            
            # Compile findings
            findings = self._compile_findings(
                activity_eval, triggers, kyc_eval, txn_metrics
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'Account Activity',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                
                'evaluation_details': {
                    'risk_rating': risk_rating,
                    'jurisdiction': jurisdiction,
                    
                    'activity_status': activity_eval['activity_status'],
                    'days_since_last_txn': activity_eval['days_since_last_txn'],
                    'last_txn_date': last_txn_date.date().isoformat(),
                    
                    'transaction_metrics': txn_metrics,
                    
                    'event_triggers': {
                        'reactivation_flag': triggers['reactivation'],
                        'volume_spike_flag': triggers['volume_spike'],
                        'above_expected_activity': triggers['above_expected'],
                        'below_expected_activity': triggers['below_expected'],
                    },
                    
                    'kyc_review_alignment': kyc_eval,
                    
                    'activity_compliance_flag': compliance_flag,
                },
                
                'findings': findings,
                'remediation_required': not passed,
                'next_review_date': (self.evaluation_date + timedelta(days=90)).date().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating customer {customer_id}: {e}")
            return self._error_result(customer_id, str(e))
    
    def _evaluate_activity_status(self, last_txn_date: datetime, jurisdiction: str) -> Dict[str, Any]:
        """
        Determine activity status based on days since last transaction.
        
        Returns:
            Dict with activity status and days calculation
        """
        days_since = (self.evaluation_date - last_txn_date).days
        
        # Get jurisdiction-specific threshold (for now, global baseline)
        dormancy_threshold = self._get_dormancy_threshold(jurisdiction)
        
        if days_since <= 180:
            activity_status = 'ACTIVE'
        elif days_since <= dormancy_threshold:
            activity_status = 'INACTIVE'
        else:
            activity_status = 'DORMANT'
        
        return {
            'activity_status': activity_status,
            'days_since_last_txn': days_since,
            'dormancy_threshold_days': dormancy_threshold,
        }
    
    def _get_dormancy_threshold(self, jurisdiction: str) -> int:
        """
        Get dormancy threshold for jurisdiction.
        Currently returns global baseline; extensible for jurisdiction overrides.
        
        Args:
            jurisdiction: Customer jurisdiction
        
        Returns:
            Dormancy threshold in days
        """
        # Jurisdiction-specific overrides (phase 2)
        jurisdiction_overrides = {
            # 'US': 360,
            # 'UK': 450,  # 15 months
            # Add more as needed
        }
        
        return jurisdiction_overrides.get(jurisdiction, 365)
    
    def _calculate_transaction_metrics(self, txn_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate transaction volume and count metrics.
        
        Returns:
            Dict with transaction statistics
        """
        # Get dates
        min_date = txn_df['last_txn_date'].min()
        max_date = txn_df['last_txn_date'].max()
        
        # Calculate spans
        days_span = (max_date - min_date).days
        
        # Count transactions in different periods
        cutoff_30d = self.evaluation_date - timedelta(days=self.params.velocity_window_days)
        cutoff_12m = self.evaluation_date - timedelta(days=365)
        
        txn_count_30d = len(txn_df[txn_df['last_txn_date'] >= cutoff_30d])
        txn_count_12m = len(txn_df)
        
        # For demo, assume each row = 1 transaction
        # In production, would sum txn_count column if available
        
        # Calculate average monthly volume
        if days_span > 0:
            months_active = max(days_span / self.params.velocity_window_days, 1)
            avg_monthly_txn = txn_count_12m / months_active
        else:
            avg_monthly_txn = 0
        
        return {
            'txn_count_30d': txn_count_30d,
            'txn_count_12m': txn_count_12m,
            'avg_monthly_txn_count': round(avg_monthly_txn, 2),
            'days_of_history': days_span,
        }
    
    def _detect_event_triggers(self, activity_eval: Dict, txn_metrics: Dict, customer: pd.Series) -> Dict[str, bool]:
        """
        Detect event-driven review triggers.
        
        Returns:
            Dict with trigger flags
        """
        triggers = {
            'reactivation': False,
            'volume_spike': False,
            'above_expected': False,
            'below_expected': False,
        }
        
        # Trigger 1: Reactivation
        # (In v1, would require prior dormancy state; approximating here)
        # If currently ACTIVE but days_since is borderline (e.g., 170-180), flag
        if activity_eval['activity_status'] == 'ACTIVE' and activity_eval['days_since_last_txn'] >= 150:
            triggers['reactivation'] = True
        
        # Trigger 2: Volume spike
        # If recent 30d activity >> historical average
        avg_monthly = txn_metrics['avg_monthly_txn_count']
        recent_30d = txn_metrics['txn_count_30d']
        
        if avg_monthly > 0:
            recent_avg_daily = recent_30d / self.params.velocity_window_days
            historical_avg_daily = avg_monthly / self.params.velocity_window_days
            
            if (recent_30d >= self.MIN_TXN_COUNT_FOR_SPIKE and 
                recent_avg_daily > (self.VOLUME_SPIKE_MULTIPLIER * historical_avg_daily)):
                triggers['volume_spike'] = True
        
        # Trigger 3 & 4: Expected activity profile
        # For demo, simulate expected baseline based on risk tier
        expected_annual = self._estimate_expected_annual_volume(customer)
        actual_annual = txn_metrics['txn_count_12m']
        
        if actual_annual > (2 * expected_annual):
            triggers['above_expected'] = True
        elif expected_annual > 0 and actual_annual < (0.25 * expected_annual) and activity_eval['activity_status'] == 'ACTIVE':
            triggers['below_expected'] = True
        
        return triggers
    
    def _estimate_expected_annual_volume(self, customer: pd.Series) -> int:
        """
        Estimate expected annual transaction volume based on risk tier and entity type.
        
        For demo: rough baseline. In production, would use stated profile or historical baseline.
        
        Returns:
            Expected transaction count per year
        """
        risk_rating = customer['risk_rating']
        entity_type = customer.get('entity_type', 'INDIVIDUAL')
        
        # Baseline expectations (demo)
        if entity_type == 'LEGAL_ENTITY':
            baselines = {
                'HIGH': 100,
                'MEDIUM': 50,
                'LOW': 20,
            }
        else:  # INDIVIDUAL
            baselines = {
                'HIGH': 50,
                'MEDIUM': 20,
                'LOW': 10,
            }
        
        return baselines.get(risk_rating, 20)
    
    def _evaluate_kyc_review_alignment(self, activity_status: str, risk_rating: str) -> Dict[str, Any]:
        """
        Evaluate whether KYC review is current per risk-based cycle.
        
        Returns:
            Dict with review due date and compliance
        """
        review_interval_months = self.KYC_REVIEW_INTERVALS.get(risk_rating, 24)
        review_due_date = self.evaluation_date + timedelta(days=review_interval_months * 30)
        
        return {
            'risk_rating': risk_rating,
            'review_interval_months': review_interval_months,
            'next_kyc_review_due': review_due_date.date().isoformat(),
            'review_note': f"KYC review due every {review_interval_months} months for {risk_rating}-risk tier",
        }
    
    def _determine_compliance(self, activity_eval: Dict, triggers: Dict, kyc_eval: Dict) -> tuple:
        """
        Determine overall compliance flag and pass/fail status.
        
        Returns:
            Tuple of (compliance_flag_string, passed_boolean)
        """
        activity_status = activity_eval['activity_status']
        
        # DORMANT accounts always non-compliant until reactivated and reviewed
        if activity_status == 'DORMANT':
            return ('REVIEW_DORMANCY', False)
        
        # INACTIVE accounts require review
        if activity_status == 'INACTIVE':
            return ('REVIEW_DORMANCY', False)
        
        # ACTIVE accounts: check for triggers
        if activity_status == 'ACTIVE':
            if triggers['reactivation']:
                return ('REVIEW_REACTIVATION', False)
            
            if triggers['volume_spike']:
                return ('REVIEW_VOLUME_SPIKE', False)
            
            if triggers['above_expected'] or triggers['below_expected']:
                return ('REVIEW_ACTIVITY_ANOMALY', False)
            
            # No triggers: compliant
            return ('COMPLIANT_ACTIVITY', True)
        
        return ('UNKNOWN', False)
    
    def _compile_findings(self, activity_eval: Dict, triggers: Dict, kyc_eval: Dict, txn_metrics: Dict) -> List[str]:
        """
        Compile human-readable findings from all evaluations.
        
        Returns:
            List of finding strings
        """
        findings = []
        
        # Activity status findings
        status = activity_eval['activity_status']
        days_since = activity_eval['days_since_last_txn']
        
        if status == 'ACTIVE':
            findings.append(f"[PASS] Account is ACTIVE: {days_since} days since last transaction")
        elif status == 'INACTIVE':
            findings.append(f"[WARN] Account is INACTIVE: {days_since} days since last transaction (dormancy threshold: {activity_eval['dormancy_threshold_days']} days)")
        else:  # DORMANT
            findings.append(f"[FAIL] Account is DORMANT: {days_since} days since last transaction (exceeds {activity_eval['dormancy_threshold_days']} day threshold)")
        
        # Transaction metrics findings
        findings.append(f"[INFO] Transaction history: {txn_metrics['txn_count_12m']} txns over {txn_metrics['days_of_history']} days (avg: {txn_metrics['avg_monthly_txn_count']} txns/month)")
        findings.append(f"[INFO] Recent activity (30d): {txn_metrics['txn_count_30d']} transactions")
        
        # Event trigger findings
        if triggers['reactivation']:
            findings.append(f"[WARN] REACTIVATION TRIGGER: Account approaching dormancy threshold; recent activity detected")
        
        if triggers['volume_spike']:
            findings.append(f"[WARN] VOLUME SPIKE TRIGGER: Recent 30-day activity significantly exceeds historical average")
        
        if triggers['above_expected']:
            findings.append(f"[WARN] ABOVE EXPECTED ACTIVITY: Transaction volume exceeds 2x expected baseline")
        
        if triggers['below_expected']:
            findings.append(f"[WARN] BELOW EXPECTED ACTIVITY: Active account with transaction volume below 25% of expected baseline")
        
        # KYC review findings
        findings.append(f"[INFO] KYC review cycle: Every {kyc_eval['review_interval_months']} months ({kyc_eval['risk_rating']}-risk)")
        
        return findings
    
    def _no_transactions_result(self, customer_id: str, risk_rating: str, jurisdiction: str) -> Dict[str, Any]:
        """Generate result for customer with no transaction records."""
        return {
            'customer_id': customer_id,
            'dimension': 'Account Activity',
            'passed': False,
            'status': 'Non-Compliant',
            'evaluation_details': {
                'risk_rating': risk_rating,
                'jurisdiction': jurisdiction,
                'activity_status': None,
                'days_since_last_txn': None,
                'transaction_metrics': None,
                'event_triggers': None,
            },
            'findings': ['[FAIL] No transaction records found for customer'],
            'remediation_required': True,
            'next_review_date': self.evaluation_date.date().isoformat(),
        }
    
    def _error_result(self, customer_id: str, error_msg: str) -> Dict[str, Any]:
        """Generate error result."""
        return {
            'customer_id': customer_id,
            'dimension': 'Account Activity',
            'passed': False,
            'status': 'Error',
            'findings': [f"Error: {error_msg}"],
            'remediation_required': True,
        }


# For testing
if __name__ == "__main__":
    
    setup_logging("INFO")
    
    config = Config()
    loader = DataLoader(config)
    
    try:
        data = loader.load_all()
        dimension = AccountActivityDimension(evaluation_date=datetime(2026, 4, 9))
        
        # Test on first customer
        result = dimension.evaluate('C001', data)
        
        print("\n" + "="*70)
        print("ACCOUNT ACTIVITY DIMENSION TEST RESULT")
        print("="*70)
        print(f"\nCustomer: {result['customer_id']}")
        print(f"Status: {result['status']}")
        print(f"Activity Compliance Flag: {result['evaluation_details']['activity_compliance_flag']}")
        print(f"\nFindings:")
        for finding in result['findings']:
            print(f"  {finding}")
        
    except Exception as e:
        print(f"Test failed: {e}")
