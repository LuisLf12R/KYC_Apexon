from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_boots_without_runtime_exception():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path))
    at.run(timeout=60)
    assert not at.exception
