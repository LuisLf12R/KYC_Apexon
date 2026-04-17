import pandas as pd

from src.dataframe_arrow_compat import coerce_expected_text_columns, make_arrow_compatible


def test_coerce_expected_text_columns_converts_boolean_status_values():
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C2"],
            "screening_result": [True, "MATCH"],
            "hit_status": [False, None],
        }
    )

    out = coerce_expected_text_columns(df, dataset_type="screenings")

    assert str(out["screening_result"].dtype) == "string"
    assert str(out["hit_status"].dtype) == "string"
    assert out.loc[0, "screening_result"] == "TRUE"
    assert out.loc[0, "hit_status"] == "FALSE"
    assert pd.isna(out.loc[1, "hit_status"])


def test_make_arrow_compatible_normalizes_mixed_object_columns():
    df = pd.DataFrame(
        {
            "status": ["PASS", True, None],
            "metadata": [{"source": "ocr"}, ["manual"], None],
            "score": [95, 88, 70],
        }
    )

    out = make_arrow_compatible(df)

    assert str(out["status"].dtype) == "string"
    assert str(out["metadata"].dtype) == "string"
    assert out.loc[0, "status"] == "PASS"
    assert out.loc[1, "status"] == "TRUE"
    assert '"source": "ocr"' in out.loc[0, "metadata"]


def test_make_arrow_compatible_preserves_missing_and_empty_values():
    df = pd.DataFrame(
        {
            "document_status": ["VERIFIED", "", None, pd.NA, float("nan")],
        }
    )

    out = make_arrow_compatible(df)

    assert pd.isna(out.loc[1, "document_status"])
    assert pd.isna(out.loc[2, "document_status"])
    assert pd.isna(out.loc[3, "document_status"])
    assert pd.isna(out.loc[4, "document_status"])
