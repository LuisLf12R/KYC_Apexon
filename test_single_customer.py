"""
Test single customer through both dimensions - FIXED VERSION
"""

from datetime import datetime
from src.config import Config
from src.data_loader import DataLoader
from src.logging_config import setup_logging
from src.dimensions.aml_screening import AMLScreeningDimension
from src.dimensions.account_activity import AccountActivityDimension

# Setup logging
setup_logging("INFO")

# Initialize
config = Config()
loader = DataLoader(config)

# Load data
print("[*] Loading data...")
data = loader.load_all()
print(f"[OK] Loaded:")
print(f"     - {len(data['customers'])} customers")
print(f"     - {len(data['screenings'])} screening records")
print(f"     - {len(data['transactions'])} transaction records")

# Initialize dimensions
aml_dim = AMLScreeningDimension(evaluation_date=datetime(2026, 4, 9))
activity_dim = AccountActivityDimension(evaluation_date=datetime(2026, 4, 9))

# Test customer
customer_id = 'C001'

print(f"\n{'='*70}")
print(f"EVALUATING CUSTOMER: {customer_id}")
print(f"{'='*70}")

# Run AML Screening
print(f"\n[*] Running AML Screening Dimension...")
aml_result = aml_dim.evaluate(customer_id, data)
print(f"[OK] AML Screening: {aml_result['status']}")
print(f"     Passed: {aml_result['passed']}")
print(f"     Findings:")
for finding in aml_result.get('findings', []):
    print(f"       {finding}")

# Debug: Print structure
print(f"\n     [DEBUG] AML Result Keys: {list(aml_result.keys())}")
if 'evaluation_details' in aml_result:
    print(f"     [DEBUG] Eval Details Keys: {list(aml_result['evaluation_details'].keys())}")

# Run Account Activity
print(f"\n[*] Running Account Activity Dimension...")
activity_result = activity_dim.evaluate(customer_id, data)
print(f"[OK] Account Activity: {activity_result['status']}")
print(f"     Passed: {activity_result['passed']}")
print(f"     Findings:")
for finding in activity_result.get('findings', []):
    print(f"       {finding}")

# Debug: Print structure
print(f"\n     [DEBUG] Activity Result Keys: {list(activity_result.keys())}")
if 'evaluation_details' in activity_result:
    print(f"     [DEBUG] Eval Details Keys: {list(activity_result['evaluation_details'].keys())}")

# Summary
print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"AML Screening: {'PASSED' if aml_result['passed'] else 'FAILED'}")
print(f"Account Activity: {'PASSED' if activity_result['passed'] else 'FAILED'}")

overall = aml_result['passed'] and activity_result['passed']
print(f"\nOVERALL COMPLIANCE: {'PASS' if overall else 'FAIL'}")