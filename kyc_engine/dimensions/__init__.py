"""
Dimensions module - KYC compliance validators
"""

from src.dimensions.aml_screening import AMLScreeningDimension
from src.dimensions.account_activity import AccountActivityDimension
from src.dimensions.identity import IdentityVerificationDimension
from src.dimensions.proof_of_address import ProofOfAddressDimension
from src.dimensions.beneficial_ownership import BeneficialOwnershipDimension
from src.dimensions.data_quality import DataQualityDimension

# List of all active dimensions
ALL_DIMENSIONS = [
    AMLScreeningDimension(),
    AccountActivityDimension(),
    IdentityVerificationDimension(),
    ProofOfAddressDimension(),
    BeneficialOwnershipDimension(),
    DataQualityDimension(),
]

def run_all_dimensions(customer_id: str, data: dict):
    """
    Run all dimensions for a single customer.
    
    Args:
        customer_id: Customer ID to evaluate
        data: Dict with 'customers', 'transactions', 'screenings', etc.
    
    Returns:
        Dict of dimension_name: result
    """
    results = {}
    for dimension in ALL_DIMENSIONS:
        dimension_name = dimension.__class__.__name__
        try:
            results[dimension_name] = dimension.evaluate(customer_id, data)
        except Exception as e:
            results[dimension_name] = {
                'customer_id': customer_id,
                'dimension': dimension_name,
                'passed': False,
                'status': 'Error',
                'findings': [f"Error: {e}"],
            }
    return results
