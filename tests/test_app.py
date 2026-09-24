from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from spreadsheet_parser import prepare_sheet


def test_sample_dashboard_renders():
    at = AppTest.from_file(Path(__file__).parents[1] / "app.py")
    at.session_state["use_sample"] = True
    at.run(timeout=10)

    assert not at.exception
    assert len(at.metric) == 5
    assert len(at.dataframe) == 1


def test_title_rows_are_removed_before_validation():
    raw = pd.DataFrame(
        [
            ["Summary for B2B(4)", None, None, None, None, None, None],
            [None, None, None, None, None, None, None],
            ["GSTIN/UIN of Recipient", "Invoice date", "Place Of Supply", "Taxable Value", "Rate"],
            ["27FIKPS7307M1ZJ", "2026-06-14", "36-Telangana", "97087", "3%"],
        ]
    )

    prepared = prepare_sheet(raw)

    assert len(prepared) == 1
    assert "GSTIN/UIN of Recipient" in prepared.columns
