# Phase 3: Dimension Schema Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize all six core dimension `evaluate()` output contracts to a strict schema (always-present `score`, canonical status keys inside `evaluation_details`), then remove the adapter glue in `KYCComplianceEngine.evaluate_customer()` while preserving the external response shape.

**Architecture:** Each dimension will emit a uniform dict with a root `score: int` (0–100) computed from its own `compliance_status` / `compliance_flag`. The engine drops its inner `_extract_score()` helper and the ad-hoc status-mapping block, reading `.score` directly from every result. AML's non-standard root keys (`aml_status`, `aml_hit_status`) migrate into its `evaluation_details`; the engine is updated to read them from there in the same commit.

**Tech Stack:** Python 3.9+, pandas, pytest (`PYTHONPATH=. pytest tests/ -v`).

---

## File Map

| Action | Path | What changes |
|--------|------|--------------|
| **Create** | `kyc_engine/dimensions/schema.py` | `DimensionResult` TypedDict + `validate_dimension_result()` helper |
| **Modify** | `kyc_engine/dimensions/identity.py` | Add `_compute_score()`, emit `score` in all return paths |
| **Modify** | `kyc_engine/dimensions/account_activity.py` | Add `_compute_score()`, emit `score` in all return paths |
| **Modify** | `kyc_engine/dimensions/proof_of_address.py` | Add `_compute_score()`, emit `score` in all return paths |
| **Modify** | `kyc_engine/dimensions/data_quality.py` | Emit root `score = round(weighted_score)` in all return paths |
| **Modify** | `kyc_engine/dimensions/aml_screening.py` | Move `aml_status` + `aml_hit_status` from root into `evaluation_details` |
| **Modify** | `kyc_engine/engine.py` | Delete `_extract_score()`, read `.score` directly, read AML keys from `evaluation_details` |
| **Modify** | `tests/test_dimensions.py` | Add schema-contract tests for all six dimensions |
| **Modify** | `CHANGELOG.md` | Document Phase 3 changes |

---

## Task 1: Create DimensionResult schema contract

**Files:**
- Create: `kyc_engine/dimensions/schema.py`
- Create: `tests/test_dimension_schema.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_dimension_schema.py
from kyc_engine.dimensions.schema import validate_dimension_result


def _minimal_result(overrides=None):
    base = {
        "customer_id": "C001",
        "dimension": "TestDim",
        "passed": True,
        "status": "Compliant",
        "score": 80,
        "findings": ["[PASS] ok"],
        "remediation_required": False,
        "next_review_date": "2027-04-28",
        "evaluation_details": {},
    }
    if overrides:
        base.update(overrides)
    return base


def test_valid_result_passes():
    result = _minimal_result()
    validate_dimension_result(result)  # must not raise


def test_missing_score_raises():
    result = _minimal_result()
    del result["score"]
    try:
        validate_dimension_result(result)
        assert False, "should have raised"
    except KeyError:
        pass


def test_score_out_of_range_raises():
    result = _minimal_result({"score": 150})
    try:
        validate_dimension_result(result)
        assert False, "should have raised"
    except ValueError:
        pass


def test_missing_required_key_raises():
    for key in ("customer_id", "dimension", "passed", "status", "findings",
                "remediation_required", "next_review_date", "evaluation_details"):
        result = _minimal_result()
        del result[key]
        try:
            validate_dimension_result(result)
            assert False, f"should have raised for missing key: {key}"
        except KeyError:
            pass
```

- [ ] **Step 1.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` (schema.py doesn't exist yet).

- [ ] **Step 1.3: Implement `kyc_engine/dimensions/schema.py`**

```python
"""
schema.py
---------
Strict contract for dimension evaluate() outputs.
All six core dimensions must conform to DimensionResult.
"""

from typing import Any

REQUIRED_KEYS = {
    "customer_id",
    "dimension",
    "passed",
    "status",
    "score",
    "findings",
    "remediation_required",
    "next_review_date",
    "evaluation_details",
}


def validate_dimension_result(result: dict[str, Any]) -> None:
    """
    Raise KeyError if a required key is absent.
    Raise ValueError if score is outside [0, 100].
    """
    for key in REQUIRED_KEYS:
        if key not in result:
            raise KeyError(f"DimensionResult missing required key: '{key}'")
    score = result["score"]
    if not (0 <= int(score) <= 100):
        raise ValueError(f"DimensionResult score {score!r} out of range [0, 100]")
```

- [ ] **Step 1.4: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **4 passed**.

- [ ] **Step 1.5: Commit**

```bash
git add kyc_engine/dimensions/schema.py tests/test_dimension_schema.py
git commit -m "feat: add DimensionResult schema contract and validator"
```

---

## Task 2: Add `score` to IdentityVerificationDimension

**Files:**
- Modify: `kyc_engine/dimensions/identity.py`
- Modify: `tests/test_dimension_schema.py` (add identity contract test)

Score mapping derived from compliance flags defined in the module docstring:

| compliance_status | score |
|---|---|
| COMPLIANT_PRIMARY_VERIFIED | 100 |
| COMPLIANT_SECONDARY_VERIFIED | 80 |
| NON_COMPLIANT_VERIFICATION_STALE | 60 |
| NON_COMPLIANT_DOCUMENT_EXPIRED | 40 |
| NON_COMPLIANT_DATA_DISCREPANCY | 40 |
| NON_COMPLIANT_HIGH_RISK_INSUFFICIENT | 30 |
| NON_COMPLIANT_MISSING_IDENTITY | 0 |
| (fallback / Error) | 0 |

- [ ] **Step 2.1: Write the failing test**

Append to `tests/test_dimension_schema.py`:

```python
def test_identity_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.identity import IdentityVerificationDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.identity

    customers = pd.DataFrame([{
        "customer_id": "SC001",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
        "customer_name": "Jane Doe",
    }])
    id_verifications = pd.DataFrame([{
        "customer_id": "SC001",
        "document_type": "PASSPORT",
        "expiry_date": "2030-01-01",
        "issue_date": "2020-01-01",
        "verification_date": "2024-01-01",
        "verification_method": "IN_PERSON",
        "name_on_document": "Jane Doe",
    }])
    data = {"customers": customers, "id_verifications": id_verifications}
    dim = IdentityVerificationDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC001", data)

    assert "score" in result, "identity result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)
```

- [ ] **Step 2.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py::test_identity_result_has_score -v
```
Expected: FAIL — `AssertionError: identity result must include 'score'`.

- [ ] **Step 2.3: Implement score in `kyc_engine/dimensions/identity.py`**

Add the score map and helper just before `def evaluate(...)` inside `IdentityVerificationDimension`:

```python
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
```

Then in the `return` dict inside `evaluate()` (line ~201), add `'score'` after `'status'`:

```python
            return {
                'customer_id': customer_id,
                'dimension': 'IdentityVerification',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': self._compute_score(compliance_status),
                'evaluation_details': {
                    ...  # unchanged
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
```

Also add `'score': 0` to both `_no_customer_error()` and `_evaluation_error()` return dicts:

```python
    def _no_customer_error(self, customer_id: str) -> Dict:
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
```

- [ ] **Step 2.4: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **5 passed**.

- [ ] **Step 2.5: Run full suite to confirm no regressions**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: all previously-passing tests still pass.

- [ ] **Step 2.6: Commit**

```bash
git add kyc_engine/dimensions/identity.py tests/test_dimension_schema.py
git commit -m "feat: emit root score in IdentityVerificationDimension"
```

---

## Task 3: Add `score` to AccountActivityDimension

**Files:**
- Modify: `kyc_engine/dimensions/account_activity.py`
- Modify: `tests/test_dimension_schema.py`

Score mapping derived from `activity_compliance_flag` values in `_determine_compliance()`:

| compliance_flag | score |
|---|---|
| COMPLIANT_ACTIVITY | 90 |
| REVIEW_REACTIVATION | 60 |
| REVIEW_VOLUME_SPIKE | 50 |
| REVIEW_ACTIVITY_ANOMALY | 50 |
| REVIEW_DORMANCY | 30 |
| UNKNOWN | 0 |
| (fallback / Error) | 0 |

- [ ] **Step 3.1: Write the failing test**

Append to `tests/test_dimension_schema.py`:

```python
def test_account_activity_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.account_activity import AccountActivityDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.transactions

    customers = pd.DataFrame([{
        "customer_id": "SC002",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    transactions = pd.DataFrame([{
        "customer_id": "SC002",
        "last_txn_date": "2026-03-01",
    }])
    data = {"customers": customers, "transactions": transactions}
    dim = AccountActivityDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC002", data)

    assert "score" in result, "account_activity result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)
```

- [ ] **Step 3.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py::test_account_activity_result_has_score -v
```
Expected: FAIL — `AssertionError: account_activity result must include 'score'`.

- [ ] **Step 3.3: Implement score in `kyc_engine/dimensions/account_activity.py`**

Add inside `AccountActivityDimension` class, before `evaluate()`:

```python
    _SCORE_MAP = {
        'COMPLIANT_ACTIVITY': 90,
        'REVIEW_REACTIVATION': 60,
        'REVIEW_VOLUME_SPIKE': 50,
        'REVIEW_ACTIVITY_ANOMALY': 50,
        'REVIEW_DORMANCY': 30,
        'UNKNOWN': 0,
    }

    def _compute_score(self, compliance_flag: str) -> int:
        return self._SCORE_MAP.get(compliance_flag, 0)
```

In the main `return` dict inside `evaluate()` (line ~127), add `'score'` after `'status'`:

```python
            return {
                'customer_id': customer_id,
                'dimension': 'Account Activity',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': self._compute_score(compliance_flag),
                'evaluation_details': {
                    ...  # unchanged
                },
                'findings': findings,
                'remediation_required': not passed,
                'next_review_date': (self.evaluation_date + timedelta(days=90)).date().isoformat(),
            }
```

Add `'score': 0` to `_no_transactions_result()` and `_error_result()`:

```python
    def _no_transactions_result(self, customer_id, risk_rating, jurisdiction):
        return {
            'customer_id': customer_id,
            'dimension': 'Account Activity',
            'passed': False,
            'status': 'Non-Compliant',
            'score': 0,
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

    def _error_result(self, customer_id, error_msg):
        return {
            'customer_id': customer_id,
            'dimension': 'Account Activity',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f"Error: {error_msg}"],
            'remediation_required': True,
            'evaluation_details': {},
            'next_review_date': self.evaluation_date.date().isoformat(),
        }
```

- [ ] **Step 3.4: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **6 passed**.

- [ ] **Step 3.5: Run full suite**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: all previously-passing tests still pass.

- [ ] **Step 3.6: Commit**

```bash
git add kyc_engine/dimensions/account_activity.py tests/test_dimension_schema.py
git commit -m "feat: emit root score in AccountActivityDimension"
```

---

## Task 4: Add `score` to ProofOfAddressDimension

**Files:**
- Modify: `kyc_engine/dimensions/proof_of_address.py`
- Modify: `tests/test_dimension_schema.py`

Score mapping derived from `compliance_status` values in that file:

| compliance_status | score |
|---|---|
| COMPLIANT_PRIMARY_POA | 100 |
| COMPLIANT_SECONDARY_POA | 80 |
| NON_COMPLIANT_POA_EXPIRED | 50 |
| NON_COMPLIANT_REVERIFICATION_OVERDUE | 40 |
| NON_COMPLIANT_ADDRESS_DISCREPANCY | 20 |
| NON_COMPLIANT_POA_MISSING | 0 |
| (fallback / Error) | 0 |

- [ ] **Step 4.1: Write the failing test**

Append to `tests/test_dimension_schema.py`:

```python
def test_proof_of_address_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.proof_of_address import ProofOfAddressDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.documents

    customers = pd.DataFrame([{
        "customer_id": "SC003",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    documents = pd.DataFrame([{
        "customer_id": "SC003",
        "document_type": "UTILITY_BILL",
        "issue_date": "2026-02-01",
        "verification_date": "2026-02-01",
    }])
    data = {"customers": customers, "documents": documents}
    dim = ProofOfAddressDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC003", data)

    assert "score" in result, "proof_of_address result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)
```

- [ ] **Step 4.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py::test_proof_of_address_result_has_score -v
```
Expected: FAIL — `AssertionError: proof_of_address result must include 'score'`.

- [ ] **Step 4.3: Implement score in `kyc_engine/dimensions/proof_of_address.py`**

Add inside `ProofOfAddressDimension` class, before `evaluate()`:

```python
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
```

In the main `return` dict inside `evaluate()` (line ~174), add `'score'` after `'status'`:

```python
            return {
                'customer_id': customer_id,
                'dimension': 'ProofOfAddressDimension',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': self._compute_score(compliance_status),
                'evaluation_details': {
                    ...  # unchanged
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': next_review_date.strftime('%Y-%m-%d'),
            }
```

Add `'score': 0` to `_no_customer_error()` and `_evaluation_error()`:

```python
    def _no_customer_error(self, customer_id):
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

    def _evaluation_error(self, customer_id, error_msg):
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
```

- [ ] **Step 4.4: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **7 passed**.

- [ ] **Step 4.5: Run full suite**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: all previously-passing tests still pass.

- [ ] **Step 4.6: Commit**

```bash
git add kyc_engine/dimensions/proof_of_address.py tests/test_dimension_schema.py
git commit -m "feat: emit root score in ProofOfAddressDimension"
```

---

## Task 5: Promote DataQuality score to root

**Files:**
- Modify: `kyc_engine/dimensions/data_quality.py`
- Modify: `tests/test_dimension_schema.py`

`weighted_score` is already computed. It just needs to appear as root `score: int` (rounded to nearest integer). `evaluation_details.data_quality_score` stays unchanged for backward compat.

- [ ] **Step 5.1: Write the failing test**

Append to `tests/test_dimension_schema.py`:

```python
def test_data_quality_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.data_quality import DataQualityDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.data_quality

    customers = pd.DataFrame([{
        "customer_id": "SC004",
        "risk_rating": "LOW",
        "entity_type": "INDIVIDUAL",
        "jurisdiction": "US",
        "account_open_date": "2020-01-01",
        "last_kyc_review_date": "2025-01-01",
    }])
    screenings = pd.DataFrame([{
        "customer_id": "SC004",
        "screening_date": "2026-04-27",
        "screening_result": "NO_HIT",
    }])
    empty = pd.DataFrame()
    data = {
        "customers": customers,
        "id_verifications": empty,
        "documents": empty,
        "screenings": screenings,
        "ubo": [],
        "transactions": empty,
    }
    dim = DataQualityDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC004", data)

    assert "score" in result, "data_quality result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert result["score"] == round(result["evaluation_details"]["data_quality_score"])
    validate_dimension_result(result)
```

- [ ] **Step 5.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py::test_data_quality_result_has_score -v
```
Expected: FAIL — `AssertionError: data_quality result must include 'score'`.

- [ ] **Step 5.3: Implement in `kyc_engine/dimensions/data_quality.py`**

In the main `return` dict inside `evaluate()` (line ~181), add `'score'` after `'status'`:

```python
            return {
                'customer_id': customer_id,
                'dimension': 'DataQuality',
                'passed': passed,
                'status': status,
                'score': round(weighted_score),
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
```

Add `'score': 0` to `_no_customer_error()` and `_evaluation_error()`:

```python
    def _no_customer_error(self, customer_id):
        return {
            'customer_id': customer_id,
            'dimension': 'DataQuality',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f'Customer {customer_id} not found in dataset'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }

    def _evaluation_error(self, customer_id, error_msg):
        return {
            'customer_id': customer_id,
            'dimension': 'DataQuality',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'findings': [f'Evaluation error: {error_msg}'],
            'evaluation_details': {},
            'remediation_required': True,
            'next_review_date': self.evaluation_date.strftime('%Y-%m-%d'),
        }
```

- [ ] **Step 5.4: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **8 passed**.

- [ ] **Step 5.5: Run full suite**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: all previously-passing tests still pass.

- [ ] **Step 5.6: Commit**

```bash
git add kyc_engine/dimensions/data_quality.py tests/test_dimension_schema.py
git commit -m "feat: promote data_quality_score to root score in DataQualityDimension"
```

---

## Task 6: Migrate AML root keys into `evaluation_details` and simplify engine adapter

This task changes `aml_screening.py` and `engine.py` in one commit because the key migration is a breaking change that the engine must absorb simultaneously.

**Files:**
- Modify: `kyc_engine/dimensions/aml_screening.py`
- Modify: `kyc_engine/engine.py`
- Modify: `tests/test_dimension_schema.py`

- [ ] **Step 6.1: Write the failing tests**

Append to `tests/test_dimension_schema.py`:

```python
def test_aml_status_is_in_evaluation_details():
    import pandas as pd
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)

    # empty screening → _missing_screenings_result path
    result = dim.evaluate("TEST-AML", {"screening": pd.DataFrame()})

    # aml_status must be inside evaluation_details, NOT at root
    assert "aml_status" not in result, "aml_status must be in evaluation_details, not at root"
    assert "aml_hit_status" not in result, "aml_hit_status must be in evaluation_details, not at root"
    assert result.get("evaluation_details", {}).get("aml_status") is not None


def test_engine_adapter_reads_score_directly():
    """Engine evaluate_customer must not use _extract_score fallback logic."""
    import inspect
    from kyc_engine import engine as eng_module
    src = inspect.getsource(eng_module)
    assert "_extract_score" not in src, (
        "_extract_score adapter must be removed from engine.py"
    )
```

- [ ] **Step 6.2: Run to confirm failure**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py::test_aml_status_is_in_evaluation_details tests/test_dimension_schema.py::test_engine_adapter_reads_score_directly -v
```
Expected: both FAIL.

- [ ] **Step 6.3: Migrate AML root keys into `evaluation_details` in `kyc_engine/dimensions/aml_screening.py`**

**In `_missing_screenings_result()`** (lines ~420–440), move `aml_status` and `aml_hit_status` into `evaluation_details` and remove them from root:

```python
    def _missing_screenings_result(self, customer_id, risk_rating, jurisdiction):
        return {
            'customer_id': customer_id,
            'dimension': 'AML Screening',
            'passed': False,
            'status': 'Non-Compliant',
            'score': 0,
            'evaluation_details': {
                'risk_rating': risk_rating,
                'jurisdiction': jurisdiction,
                'aml_status': 'no_screening_data',
                'aml_hit_status': '',
                'screening_evaluation': None,
                'rescreening_evaluation': None,
                'hit_evaluation': None,
            },
            'findings': ['✗ No AML screening records found for customer'],
            'remediation_required': True,
            'next_review_date': self.evaluation_date.date().isoformat(),
        }
```

**In `_error_result()`**, move `aml_status` and `aml_hit_status` into `evaluation_details`:

```python
    def _error_result(self, customer_id, error_msg):
        return {
            'customer_id': customer_id,
            'dimension': 'AML Screening',
            'passed': False,
            'status': 'Error',
            'score': 0,
            'evaluation_details': {
                'aml_status': 'no_screening_data',
                'aml_hit_status': '',
            },
            'findings': [f"Error: {error_msg}"],
            'remediation_required': True,
            'next_review_date': self.evaluation_date.date().isoformat(),
        }
```

**In the main `return` dict of `evaluate()`** (find where `aml_status` and `aml_hit_status` are returned at root — search for `'aml_status': aml_status`), move them into `evaluation_details`:

The main return in `evaluate()` currently puts `aml_status` and `aml_hit_status` at root. Change it to nest them inside `evaluation_details` instead:

```python
            return {
                'customer_id': customer_id,
                'dimension': 'AML Screening',
                'passed': passed,
                'status': 'Compliant' if passed else 'Non-Compliant',
                'score': score,
                'evaluation_details': {
                    'risk_rating': risk_rating,
                    'jurisdiction': jurisdiction,
                    'aml_status': aml_status,
                    'aml_hit_status': aml_hit_status,
                    'screening_evaluation': screening_eval,
                    'rescreening_evaluation': rescreening_eval,
                    'hit_evaluation': hit_eval,
                    'last_screening_date': ...,
                    'days_since_last_screening': ...,
                    'next_screening_due': ...,
                    'screening_overdue': ...,
                },
                'findings': findings,
                'remediation_required': remediation_required,
                'next_review_date': ...,
            }
```

(Keep the exact same keys — just move `aml_status` and `aml_hit_status` from root to inside `evaluation_details`. All other `evaluation_details` contents remain unchanged.)

- [ ] **Step 6.4: Update `kyc_engine/engine.py` to remove `_extract_score` and read from `.score` and `evaluation_details`**

Locate the adapter block at lines ~290–346. Replace it entirely:

**Remove** (delete these lines):
```python
        def _extract_score(
            result: dict,
            fallback_pass: int = 80,
            fallback_fail: int = 40,
        ) -> int:
            if "score" in result and result["score"] is not None:
                return int(result["score"])
            return fallback_pass if result.get("passed") else fallback_fail

        aml_score = float(_extract_score(screening_result))
        aml_status = screening_result.get("aml_status", "no_screening_data")
        aml_hit_status = screening_result.get("aml_hit_status", "")
        aml_finding = "; ".join(screening_result.get("findings", [])[:2])

        id_score = _extract_score(identity_result)
        act_score = _extract_score(txn_result)
        poa_score = _extract_score(doc_result)
        ubo_score = _extract_score(ubo_result)
        dq_score = _extract_score(dq_result)

        aml_details = {"status": aml_status, "hit_status": aml_hit_status, "finding": aml_finding}
        id_details = {
            "status": "verified" if identity_result.get("passed") else "no_documents",
            "finding": "; ".join(identity_result.get("findings", [])[:2]),
        }
        act_details = {
            "status": "activity_assessed" if txn_result.get("passed") else "no_activity",
            "finding": "; ".join(txn_result.get("findings", [])[:2]),
        }
        poa_details = {
            "status": "address_on_file" if doc_result.get("passed") else "address_incomplete",
            "finding": "; ".join(doc_result.get("findings", [])[:2]),
        }
        ubo_details = {
            "status": "ubo_identified" if ubo_result.get("passed") else "no_ubo_record",
            "finding": "; ".join(ubo_result.get("findings", [])[:2]),
        }
        dq_details = {
            "status": "data_quality",
            "quality_rating": "Good" if dq_result.get("passed") else "Poor",
            "finding": "; ".join(dq_result.get("findings", [])[:2]),
        }
        sow_score = float(_extract_score(sow_result))
        sow_details = {
            "status": sow_result.get("sow_status", "sow_not_declared"),
            "finding": "; ".join(sow_result.get("findings", [])[:2]),
        }
        crs_score = float(_extract_score(crs_result))
        crs_details = {
            "status": crs_result.get("crs_fatca_status", "not_applicable"),
            "finding": "; ".join(crs_result.get("findings", [])[:2]),
        }
```

**Replace with** (clean, no adapter logic):
```python
        aml_score = float(screening_result["score"])
        aml_eval = screening_result.get("evaluation_details", {})
        aml_status = aml_eval.get("aml_status", "no_screening_data")
        aml_hit_status = aml_eval.get("aml_hit_status", "")
        aml_finding = "; ".join(screening_result.get("findings", [])[:2])

        id_score = float(identity_result["score"])
        act_score = float(txn_result["score"])
        poa_score = float(doc_result["score"])
        ubo_score = float(ubo_result["score"])
        dq_score = float(dq_result["score"])

        aml_details = {"status": aml_status, "hit_status": aml_hit_status, "finding": aml_finding}
        id_details = {
            "status": "verified" if identity_result.get("passed") else "no_documents",
            "finding": "; ".join(identity_result.get("findings", [])[:2]),
        }
        act_details = {
            "status": "activity_assessed" if txn_result.get("passed") else "no_activity",
            "finding": "; ".join(txn_result.get("findings", [])[:2]),
        }
        poa_details = {
            "status": "address_on_file" if doc_result.get("passed") else "address_incomplete",
            "finding": "; ".join(doc_result.get("findings", [])[:2]),
        }
        ubo_details = {
            "status": "ubo_identified" if ubo_result.get("passed") else "no_ubo_record",
            "finding": "; ".join(ubo_result.get("findings", [])[:2]),
        }
        dq_details = {
            "status": "data_quality",
            "quality_rating": "Good" if dq_result.get("passed") else "Poor",
            "finding": "; ".join(dq_result.get("findings", [])[:2]),
        }
        sow_score = float(sow_result.get("score", 80 if sow_result.get("passed") else 40))
        sow_details = {
            "status": sow_result.get("sow_status", "sow_not_declared"),
            "finding": "; ".join(sow_result.get("findings", [])[:2]),
        }
        crs_score = float(crs_result.get("score", 80 if crs_result.get("passed") else 40))
        crs_details = {
            "status": crs_result.get("crs_fatca_status", "not_applicable"),
            "finding": "; ".join(crs_result.get("findings", [])[:2]),
        }
```

> Note: SOW and CRS are not in scope for Phase 3 schema migration, so `.get("score", fallback)` is used for them as a conservative shim — this is intentional and not adapter glue (the six core dimensions now have guaranteed `.score`).

Also update the `aml_status` check below the `result = {...}` block (line ~385). It currently reads:
```python
        if aml_status == "no_screening_data":
```
This variable is now sourced from `evaluation_details` — the variable name `aml_status` is preserved in the new code above, so this line needs no change.

- [ ] **Step 6.5: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **10 passed**.

- [ ] **Step 6.6: Run full suite**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: **38+ passed**, no regressions.

- [ ] **Step 6.7: Commit**

```bash
git add kyc_engine/dimensions/aml_screening.py kyc_engine/engine.py tests/test_dimension_schema.py
git commit -m "feat: move AML root keys into evaluation_details and remove _extract_score adapter from engine"
```

---

## Task 7: Add schema-contract tests for BeneficialOwnership (already conformant) + overall six-dim sweep

BeneficialOwnership already emits `score` — add a contract test to lock it in and complete coverage for all six dimensions.

**Files:**
- Modify: `tests/test_dimension_schema.py`

- [ ] **Step 7.1: Append the final two tests**

```python
def test_beneficial_ownership_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.ubo

    customers = pd.DataFrame([{
        "customer_id": "SC005",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    data = {"customers": customers, "ubo": []}
    dim = BeneficialOwnershipDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC005", data)

    assert "score" in result, "beneficial_ownership result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)


def test_aml_result_has_score_and_conforms():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)

    result = dim.evaluate("TEST-AML2", {"screening": pd.DataFrame()})

    assert "score" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)
```

- [ ] **Step 7.2: Run to confirm passing**

```
PYTHONPATH=. pytest tests/test_dimension_schema.py -v
```
Expected: **12 passed**.

- [ ] **Step 7.3: Run full suite — final gate**

```
PYTHONPATH=. pytest tests/ -v
```
Expected: **40+ passed** (38 original + new schema tests), no failures.

- [ ] **Step 7.4: Commit**

```bash
git add tests/test_dimension_schema.py
git commit -m "test: complete schema-contract coverage for all six core dimensions"
```

---

## Task 8: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 8.1: Prepend Phase 3 entry to `CHANGELOG.md`**

Add at the top (after any existing title):

```markdown
## Phase 3 — Dimension Schema Normalization (2026-04-28)

### Changed
- All six core dimensions (`IdentityVerification`, `AccountActivity`, `ProofOfAddressDimension`, `DataQuality`, `AMLScreening`, `BeneficialOwnership`) now emit a root `score: int` (0–100) in every code path, including error and missing-data paths.
- `AMLScreeningDimension`: `aml_status` and `aml_hit_status` moved from the result root into `evaluation_details`. Engine reads them from `evaluation_details`.
- `KYCComplianceEngine.evaluate_customer()`: removed `_extract_score()` adapter helper and the pass/fail fallback approximation (80/40). Scores are now read directly from `result["score"]` for all six core dimensions.

### Added
- `kyc_engine/dimensions/schema.py`: `DimensionResult` required-key set and `validate_dimension_result()` helper for contract enforcement.
- `tests/test_dimension_schema.py`: 12 schema-contract tests covering all six core dimensions and the validator itself.

### Deferred
- SOW (`SourceOfWealthDimension`) and CRS (`CRSFATCADimension`) schema migration (engine uses `.get("score", fallback)` shim for these two).
```

- [ ] **Step 8.2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for Phase 3 dimension schema normalization"
```

---

## Spec Coverage Check

| Phase 3 requirement | Covered by |
|---|---|
| Strict dimension result schema with `score` | Task 1 (schema.py), Tasks 2–5 |
| Canonical status keys (aml_status, aml_hit_status in evaluation_details) | Task 6 |
| Migrate all six dimensions to schema | Tasks 2–7 |
| Simplify engine dispositioning to consume only canonical schema | Task 6 (engine.py) |
| Preserve external `evaluate_customer()` response shape | Task 6 — output dict keys unchanged |
| Remove temporary compatibility mappings (`_extract_score`) | Task 6 |
| Add migration tests | Tasks 1–7 |
| Update docs/changelog | Task 8 |
