import pandas as pd
import pyarrow as pa

from kyc_engine.dataframe_arrow_compat import ensure_arrow_compatible


def test_llm_like_records_can_convert_to_arrow_after_hardening():
    records = [
        {"customer_id": "C001", "screening_result": True, "hit_status": "CONFIRMED"},
        {"customer_id": "C002", "screening_result": "MATCH", "hit_status": False},
    ]

    raw_df = pd.DataFrame(records)
    hardened_df = ensure_arrow_compatible(raw_df, dataset_type="screenings")

    table = pa.Table.from_pandas(hardened_df, preserve_index=False)

    assert table.num_rows == 2
    assert hardened_df["screening_result"].tolist() == ["TRUE", "MATCH"]
    assert hardened_df["hit_status"].tolist() == ["CONFIRMED", "FALSE"]
