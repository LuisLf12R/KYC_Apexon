from typing import Any, Dict, List
import pandas as pd

from src.data.contracts import DatasetContract, ContractValidationError


def validate_required_fields(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure all required fields defined by the contract exist in the DataFrame.
    """
    missing = contract.required_fields - set(df.columns)
    if missing:
        raise ContractValidationError(
            f"[{contract.name}] Missing required fields: {sorted(missing)}"
        )
    return True


def validate_allowed_fields(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure the DataFrame does not contain unexpected columns.

    This is optional from a business perspective, but very useful for catching
    schema drift early.
    """
    unexpected = set(df.columns) - contract.allowed_fields
    if unexpected:
        raise ContractValidationError(
            f"[{contract.name}] Unexpected fields present: {sorted(unexpected)}"
        )
    return True


def validate_enum_fields(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure enum-backed fields contain only allowed values.

    Null values are ignored here. Required-ness is handled separately by the
    required fields / null checks.
    """
    for field, allowed_values in contract.enum_fields.items():
        if field not in df.columns:
            continue

        non_null_values = df[field].dropna()
        invalid_values = sorted(set(non_null_values) - set(allowed_values))

        if invalid_values:
            raise ContractValidationError(
                f"[{contract.name}] Invalid values for '{field}': {invalid_values}. "
                f"Allowed values: {sorted(allowed_values)}"
            )
    return True


def validate_date_fields(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure date fields are already parsed as pandas datetime types.
    """
    for field in contract.date_fields:
        if field not in df.columns:
            continue

        if not pd.api.types.is_datetime64_any_dtype(df[field]):
            raise ContractValidationError(
                f"[{contract.name}] Field '{field}' is not datetime64 dtype"
            )
    return True


def validate_primary_key(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure primary key fields exist, are not null, and are unique as a combination.
    """
    if not contract.primary_key:
        return True

    missing_pk_fields = [field for field in contract.primary_key if field not in df.columns]
    if missing_pk_fields:
        raise ContractValidationError(
            f"[{contract.name}] Missing primary key fields: {missing_pk_fields}"
        )

    null_pk_mask = df[contract.primary_key].isnull().any(axis=1)
    if null_pk_mask.any():
        raise ContractValidationError(
            f"[{contract.name}] Null values found in primary key fields "
            f"{contract.primary_key}"
        )

    duplicate_mask = df.duplicated(subset=contract.primary_key, keep=False)
    if duplicate_mask.any():
        duplicates = df.loc[duplicate_mask, contract.primary_key].drop_duplicates()
        sample_duplicates = duplicates.head(10).to_dict(orient="records")
        raise ContractValidationError(
            f"[{contract.name}] Duplicate primary key values found for "
            f"{contract.primary_key}. Sample duplicates: {sample_duplicates}"
        )

    return True


def validate_non_null_required_fields(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Ensure required fields are not entirely or partially null.

    Presence of the column alone is not enough for a strong contract.
    """
    required_present = [field for field in contract.required_fields if field in df.columns]

    null_violations = []
    for field in required_present:
        if df[field].isnull().any():
            null_count = int(df[field].isnull().sum())
            null_violations.append((field, null_count))

    if null_violations:
        details = ", ".join([f"{field}: {count} null(s)" for field, count in null_violations])
        raise ContractValidationError(
            f"[{contract.name}] Null values found in required fields: {details}"
        )

    return True


def validate_dataframe(df: pd.DataFrame, contract: DatasetContract) -> bool:
    """
    Validate a pandas DataFrame against a dataset contract.
    """
    if not isinstance(df, pd.DataFrame):
        raise ContractValidationError(
            f"[{contract.name}] Expected pandas DataFrame, got {type(df).__name__}"
        )

    validate_required_fields(df, contract)
    validate_non_null_required_fields(df, contract)
    validate_allowed_fields(df, contract)
    validate_enum_fields(df, contract)
    validate_date_fields(df, contract)
    validate_primary_key(df, contract)
    return True


def validate_list_of_dicts(data: List[Dict[str, Any]], contract: DatasetContract) -> bool:
    """
    Validate list-of-dicts datasets by converting them into a DataFrame view and
    applying the same contract checks.

    This keeps one validation path for UBO and regulatory rules.
    """
    if not isinstance(data, list):
        raise ContractValidationError(
            f"[{contract.name}] Expected list of dicts, got {type(data).__name__}"
        )

    if not all(isinstance(item, dict) for item in data):
        raise ContractValidationError(
            f"[{contract.name}] All records must be dictionaries"
        )

    df = pd.DataFrame(data)

    # Date fields in list-of-dicts datasets may still need parsing upstream.
    # We validate after conversion, assuming upstream has already normalized them.
    validate_required_fields(df, contract)
    validate_non_null_required_fields(df, contract)
    validate_allowed_fields(df, contract)
    validate_enum_fields(df, contract)
    validate_primary_key(df, contract)

    # Optional: only validate date dtypes if the DataFrame is not empty
    if not df.empty:
        validate_date_fields(df, contract)

    return True


def validate_dataset(data: Any, contract: DatasetContract) -> bool:
    """
    Validate any dataset against its contract.

    Dispatches based on the contract record_type rather than guessing.
    """
    if contract.record_type == "dataframe":
        return validate_dataframe(data, contract)

    if contract.record_type == "list_of_dicts":
        return validate_list_of_dicts(data, contract)

    raise ContractValidationError(
        f"[{contract.name}] Unsupported contract record_type: {contract.record_type}"
    )