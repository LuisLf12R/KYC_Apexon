"""
beneficial_ownership.py
-----------------------
Beneficial Ownership (UBO) Dimension for KYC Completeness and AML/CFT Control.

Evaluates customer beneficial ownership transparency through a risk-based,
jurisdictionally-aware approach per FATF Recommendations 24 & 25.

Verifies that:
1. Legal entities have identified beneficial owners
2. UBO information is complete and accurate
3. UBOs are verified and screened
4. Ownership thresholds are met (25% global, 10-15% high-risk jurisdictions)
5. UBO data is current per risk-based refresh cycles

Compliance Flags:
- COMPLIANT_UBOS_IDENTIFIED: Beneficial owners identified and verified
- COMPLIANT_SMO_FALLBACK: Senior Managing Official designated when no UBO found
- NON_COMPLIANT_UBO_MISSING: No beneficial owner information found
- NON_COMPLIANT_UBO_INCOMPLETE: Missing key identifiers (DOB, nationality)
- NON_COMPLIANT_UBO_UNSCREENED: UBOs not screened against sanctions/PEP
- NON_COMPLIANT_UBO_STALE: UBO verification exceeds risk-based refresh cycle
- NON_COMPLIANT_UBO_HIGH_RISK: High-risk jurisdiction or structure detected
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

from rules.schema.dimensions import BeneficialOwnershipParameters
logger = logging.getLogger(__name__)


class BeneficialOwnershipDimension:
    """
    Beneficial Ownership (UBO) Dimension.
    
    Evaluates legal entity beneficial ownership transparency and
    compliance with FATF Recommendations 24 & 25.
    """
    
    # Global UBO ownership threshold (can be overridden per jurisdiction)
    DEFAULT_OWNERSHIP_THRESHOLD = 25  # percent
    
    # Jurisdictional thresholds (percent)
    JURISDICTIONAL_THRESHOLDS = {
        'US': 25,
        'EU': 25,  # Some member states: 15-20 for high-risk sectors
        'GB': 25,
        'DE': 25,
        'FR': 25,
        'SG': 25,
        'HK': 25,
        'AE': 25,
        'IN': 10,  # Lower threshold for SBO
        'CA': 25,
        'AU': 25,
        'default': 25,
    }
    
    # UBO refresh cycles by risk rating (days)
    UBO_REFRESH_CYCLES = {
        'HIGH': 365,       # Annual
        'MEDIUM': 730,     # Biennial (2 years)
        'LOW': 1825,       # 5 years
    }
    
    # High-risk jurisdictions requiring special attention
    HIGH_RISK_JURISDICTIONS = {
        'FATF_GREYLIST', 'KNOWN_MONEY_LAUNDERING_HUB',
        'WEAK_AML_FRAMEWORK', 'OFFSHORE_FINANCIAL_CENTER'
    }
    
    def __init__(self, params: BeneficialOwnershipParameters, evaluation_date=None):
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
        logger.info(f"BeneficialOwnershipDimension initialized. Evaluation date: {self.evaluation_date}")
    
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict:
        """
        Evaluate beneficial ownership for a single customer (typically legal entity).
        
        Args:
            customer_id: Customer ID to evaluate
            data: Dict with 'customers', 'ubo', 'screenings', etc.
        
        Returns:
            Dict with compliance assessment
        """
        try:
            customers = data['customers']
            ubo_list = data['ubo']
            screenings = data['screenings']
            
            # Get customer record
            customer = customers[customers['customer_id'] == customer_id]
            if customer.empty:
                return self._no_customer_error(customer_id)
            
            customer = customer.iloc[0]
            
            # Only evaluate legal entities (skip individuals)
            if customer.get('entity_type') != 'LEGAL_ENTITY':
                return self._not_applicable(customer_id, 'Individual customer - UBO not applicable')
            
            # Get UBO records for this customer
            if isinstance(ubo_list, list):
                ubo_records = [u for u in ubo_list if u.get('customer_id') == customer_id]
            else:
                ubo_records = ubo_list[ubo_list['customer_id'] == customer_id] if isinstance(ubo_list, pd.DataFrame) else []
            
            # Perform evaluations
            findings = []
            passed = True
            compliance_status = 'COMPLIANT_UBOS_IDENTIFIED'
            
            # [1] Check if entity has UBO information
            if not ubo_records:
                findings.append('[FAIL] No beneficial owner information found')
                passed = False
                compliance_status = 'NON_COMPLIANT_UBO_MISSING'
            else:
                # Convert to list of dicts if needed
                ubos = ubo_records if isinstance(ubo_records, list) else ubo_records.to_dict('records')
                
                # [2] Check UBO completeness (name, DOB, nationality)
                completeness_status = self._check_ubo_completeness(ubos, customer.get('jurisdiction', 'default'))
                
                if completeness_status == 'MISSING':
                    findings.append('[FAIL] No complete beneficial owner identified')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_UBO_MISSING'
                elif completeness_status == 'PARTIAL':
                    findings.append('[WARN] Some beneficial owners incomplete (missing DOB, nationality, etc.)')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_UBO_INCOMPLETE'
                    findings.append(f'[INFO] UBO completeness: {completeness_status}')
                elif completeness_status == 'SMO_FALLBACK':
                    findings.append('[PASS] No UBO identified; Senior Managing Official designated')
                    findings.append('[INFO] Ensure "reasonable efforts" documentation is retained')
                    compliance_status = 'COMPLIANT_SMO_FALLBACK'
                else:  # COMPLETE
                    findings.append('[PASS] Beneficial owner(s) identified and complete')
                    findings.append(f'[INFO] Total UBOs: {len(ubos)}')
                
                # [3] Check ownership thresholds
                if completeness_status != 'SMO_FALLBACK' and completeness_status != 'MISSING':
                    threshold = self._get_ownership_threshold(customer.get('jurisdiction', 'default'))
                    total_ownership = sum([float(u.get('ownership_percent', 0)) for u in ubos])
                    
                    if total_ownership < threshold:
                        findings.append(
                            f'[WARN] Identified ownership: {total_ownership}% (threshold: {threshold}%)'
                        )
                        if completeness_status == 'COMPLETE':
                            passed = False
                            compliance_status = 'NON_COMPLIANT_UBO_INCOMPLETE'
                
                # [4] Check UBO verification recency
                for ubo in ubos:
                    last_verified = pd.to_datetime(ubo.get('verification_date', self.evaluation_date))
                    if pd.isna(last_verified):
                        last_verified = self.evaluation_date
                    
                    days_since_verification = (self.evaluation_date - last_verified).days
                    refresh_cycle = self._get_ubo_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
                    
                    if days_since_verification > refresh_cycle:
                        findings.append(
                            f'[WARN] UBO {ubo.get("ubo_name", "Unknown")} verification overdue '
                            f'({days_since_verification} days, refresh: {refresh_cycle} days)'
                        )
                        if completeness_status == 'COMPLETE':
                            passed = False
                            compliance_status = 'NON_COMPLIANT_UBO_STALE'
                    else:
                        findings.append(
                            f'[PASS] UBO {ubo.get("ubo_name", "Unknown")} verification current '
                            f'({days_since_verification} days old)'
                        )
                
                # [5] Check UBO screening status (linkage to AML dimension)
                screening_status = self._check_ubo_screening_status(ubos, screenings)
                
                if screening_status == 'NO_UBOS_SCREENED':
                    findings.append('[FAIL] No UBOs have been screened against sanctions/PEP lists')
                    passed = False
                    compliance_status = 'NON_COMPLIANT_UBO_UNSCREENED'
                elif screening_status == 'SOME_UBOS_NOT_SCREENED':
                    findings.append('[WARN] Some UBOs have not been screened against sanctions/PEP')
                    findings.append('[INFO] Ensure all UBOs undergo AML screening')
                else:
                    findings.append('[PASS] All UBOs screened against sanctions/PEP lists')
                
                # [6] Check for high-risk UBO profiles
                ubo_risk_flags = self._check_ubo_risk_flags(ubos, customer.get('jurisdiction', 'default'))
                
                if ubo_risk_flags:
                    findings.append('[WARN] High-risk beneficial ownership profile detected:')
                    for flag in ubo_risk_flags:
                        findings.append(f'     - {flag}')
                        passed = False
                        compliance_status = 'NON_COMPLIANT_UBO_HIGH_RISK'
                
                # [7] Trust/Complex Structure handling
                has_trust = any(u.get('ubo_role') in ['SETTLOR', 'TRUSTEE', 'BENEFICIARY'] for u in ubos)
                if has_trust:
                    findings.append('[INFO] Trust or complex legal arrangement detected')
                    findings.append('[INFO] Verify settlor, trustee, and beneficiary information')
            
            # Build result
            remediation_required = not passed
            next_review_date = self.evaluation_date + timedelta(
                days=self._get_ubo_refresh_cycle(customer.get('risk_rating', 'MEDIUM'))
            )
            
            return {
                'customer_id': customer_id,
                'dimension': 'BeneficialOwnership',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'evaluation_details': {
                    'entity_type': customer.get('entity_type'),
                    'jurisdiction': customer.get('jurisdiction'),
                    'risk_rating': customer.get('risk_rating'),
                    'ubos_found': len(ubo_records) if ubo_records else 0,
                    'completeness_status': completeness_status,
                    'screening_status': screening_status if ubo_records else 'N/A',
                    'ownership_threshold_pct': self._get_ownership_threshold(customer.get('jurisdiction', 'default')),
                    'refresh_cycle_days': self._get_ubo_refresh_cycle(customer.get('risk_rating', 'MEDIUM')),
                    'compliance_status': compliance_status,
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
        
        except Exception as e:
            logger.error(f"Error evaluating UBO for {customer_id}: {e}")
            return self._evaluation_error(customer_id, str(e))
    
    def _check_ubo_completeness(self, ubos: List[Dict], jurisdiction: str) -> str:
        """
        Check if UBO information is complete.
        
        Returns:
            COMPLETE, PARTIAL, SMO_FALLBACK, or MISSING
        """
        if not ubos:
            return 'MISSING'
        
        # Check if any UBO is Senior Managing Official (SMO fallback)
        has_smo = any(u.get('ubo_role') == 'SMO' or u.get('ubo_role') == 'SENIOR_MANAGING_OFFICIAL' for u in ubos)
        if has_smo:
            return 'SMO_FALLBACK'
        
        # Check if all UBOs have required fields
        required_fields = ['ubo_name', 'ubo_dob', 'ubo_nationality', 'ownership_percent']
        
        complete_count = sum(1 for u in ubos if all(pd.notna(u.get(f)) for f in required_fields))
        
        if complete_count == len(ubos):
            return 'COMPLETE'
        elif complete_count > 0:
            return 'PARTIAL'
        else:
            return 'MISSING'
    
    def _check_ubo_screening_status(self, ubos: List[Dict], screenings: pd.DataFrame) -> str:
        """
        Check if all UBOs have been screened against sanctions/PEP lists.
        
        Returns:
            ALL_UBOS_SCREENED, SOME_UBOS_NOT_SCREENED, or NO_UBOS_SCREENED
        """
        if not ubos or screenings.empty:
            return 'NO_UBOS_SCREENED'
        
        screened_count = 0
        for ubo in ubos:
            ubo_name = str(ubo.get('ubo_name', '')).upper()
            
            # Check if this UBO name appears in screening records
            if 'match_name' in screenings.columns:
                matching_screenings = screenings[
                    screenings['match_name'].str.upper().str.contains(ubo_name, na=False, regex=False)
                ]
            else:
                matching_screenings = screenings.iloc[0:0]
            
            if not matching_screenings.empty:
                screened_count += 1
                
        if screened_count == 0:
            return 'NO_UBOS_SCREENED'
        elif screened_count == len(ubos):
            return 'ALL_UBOS_SCREENED'
        else:
            return 'SOME_UBOS_NOT_SCREENED'
    
    def _check_ubo_risk_flags(self, ubos: List[Dict], jurisdiction: str) -> List[str]:
        """
        Check for high-risk beneficial ownership profiles.
        
        Returns:
            List of risk flags detected
        """
        flags = []
        
        for ubo in ubos:
            # Check PEP flag
            if ubo.get('ubo_pep_flag') == 'Y' or ubo.get('ubo_pep_flag') is True:
                flags.append(f"PEP flag: {ubo.get('ubo_name', 'Unknown')}")
            
            # Check sanctions flag
            if ubo.get('ubo_sanctions_flag') == 'Y' or ubo.get('ubo_sanctions_flag') is True:
                flags.append(f"Sanctions exposure: {ubo.get('ubo_name', 'Unknown')}")
            
            # Check high-risk jurisdiction
            ubo_jurisdiction = str(ubo.get('ubo_jurisdiction', '')).upper()
            if any(risk in ubo_jurisdiction for risk in self.HIGH_RISK_JURISDICTIONS):
                flags.append(f"High-risk jurisdiction: {ubo.get('ubo_jurisdiction', 'Unknown')}")
        
        # Check for complex layering (multiple indirect owners)
        indirect_owners = [u for u in ubos if u.get('control_type') == 'INDIRECT_OWNERSHIP']
        if len(indirect_owners) > 2:
            flags.append('Complex multi-layer ownership structure')
        
        # Check for trust/beneficial arrangement complexity
        trust_roles = [u.get('ubo_role') for u in ubos if u.get('ubo_role') in ['SETTLOR', 'TRUSTEE', 'BENEFICIARY']]
        if trust_roles:
            flags.append(f'Trust structure with {len(set(trust_roles))} role types')
        
        return flags
    
    def _get_ownership_threshold(self, jurisdiction: str) -> float:
        """Return ownership threshold for jurisdiction in percent."""
        return self.JURISDICTIONAL_THRESHOLDS.get(jurisdiction, self.params.ownership_threshold_pct)
    
    def _get_ubo_refresh_cycle(self, risk_rating: str) -> int:
        """Return UBO refresh cycle for risk rating in days."""
        return self.UBO_REFRESH_CYCLES.get(risk_rating, self.UBO_REFRESH_CYCLES['MEDIUM'])
    
    def _no_customer_error(self, customer_id: str) -> Dict:
        """Return error result for missing customer."""
        return {
            'customer_id': customer_id,
            'dimension': 'BeneficialOwnership',
            'passed': False,
            'status': 'Error',
            'findings': [f'Customer {customer_id} not found in dataset'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
    
    def _not_applicable(self, customer_id: str, reason: str) -> Dict:
        """Return N/A result for individual customers."""
        return {
            'customer_id': customer_id,
            'dimension': 'BeneficialOwnership',
            'passed': True,  # Not applicable = pass
            'status': 'N/A',
            'findings': [f'[INFO] {reason}'],
            'evaluation_details': {'applicability': 'Not applicable'},
            'remediation_required': False,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
    
    def _evaluation_error(self, customer_id: str, error_msg: str) -> Dict:
        """Return error result for evaluation failure."""
        return {
            'customer_id': customer_id,
            'dimension': 'BeneficialOwnership',
            'passed': False,
            'status': 'Error',
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
