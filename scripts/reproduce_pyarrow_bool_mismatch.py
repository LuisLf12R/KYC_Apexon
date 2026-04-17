"""Minimal repro for the ArrowTypeError seen in Streamlit DataFrame rendering.

Run:
    python scripts/reproduce_pyarrow_bool_mismatch.py
"""

import pandas as pd
import pyarrow as pa


def main() -> None:
    df = pd.DataFrame(
        {
            "customer_id": ["C001", "C002", "C003"],
            "screening_result": ["MATCH", True, "NO_MATCH"],
            "hit_status": ["CONFIRMED", False, "UNDER_REVIEW"],
        }
    )

    print("DataFrame dtypes:")
    print(df.dtypes)
    print("\nPython types in screening_result:")
    print(df["screening_result"].map(lambda v: type(v).__name__).tolist())

    try:
        pa.Table.from_pandas(df, preserve_index=False)
        print("\nNo error (unexpected for mixed bool/string object columns).")
    except Exception as exc:
        print("\nReproduced conversion error:")
        print(type(exc).__name__, exc)


if __name__ == "__main__":
    main()
