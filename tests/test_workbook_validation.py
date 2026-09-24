from io import BytesIO

import pandas as pd

from backend.api.main import validate_gstr1_workbook


def test_validates_b2b_and_b2cl_sheets_from_one_workbook():
    buffer = BytesIO()

    b2b_df = pd.DataFrame(
        [
            ["36ABCDE1234F1Z5", "01-Sep-26", "36-Telangana", "10000", "18", "900", "900", "0"],
        ],
        columns=["Recipient GSTIN/UIN", "Invoice Date", "Place of Supply", "Taxable Value", "Rate", "CGST", "SGST", "IGST"],
    )
    b2cl_df = pd.DataFrame(
        [
            ["01-09-2026", "150000", "27-Maharashtra", "18", "100000"],
        ],
        columns=["Invoice date", "Invoice Value", "Place Of Supply", "Rate", "Taxable Value"],
    )

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        b2b_df.to_excel(writer, sheet_name="B2B", index=False)
        b2cl_df.to_excel(writer, sheet_name="B2CL", index=False)

    result = validate_gstr1_workbook(
        buffer.getvalue(),
        month=9,
        year=2026,
        registered_state_code="36",
    )

    assert "b2b" in result
    assert "b2cl" in result
    assert result["b2b"]["summary"]["total"] == 1
    assert result["b2cl"]["summary"]["total"] == 1


def test_validates_b2b_and_b2cl_sheets_with_descriptive_names():
    buffer = BytesIO()

    b2b_df = pd.DataFrame(
        [["36ABCDE1234F1Z5", "01-Sep-26", "36-Telangana", "10000", "18", "900", "900", "0"]],
        columns=["Recipient GSTIN/UIN", "Invoice Date", "Place of Supply", "Taxable Value", "Rate", "CGST", "SGST", "IGST"],
    )
    b2cl_df = pd.DataFrame(
        [["01-09-2026", "150000", "27-Maharashtra", "18", "100000"]],
        columns=["Invoice date", "Invoice Value", "Place Of Supply", "Rate", "Taxable Value"],
    )

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        b2b_df.to_excel(writer, sheet_name="B2B Data", index=False)
        b2cl_df.to_excel(writer, sheet_name="B2CL Data", index=False)

    result = validate_gstr1_workbook(
        buffer.getvalue(),
        month=9,
        year=2026,
        registered_state_code="36",
    )

    assert "b2b" in result
    assert "b2cl" in result
    assert result["b2b"]["summary"]["total"] == 1
    assert result["b2cl"]["summary"]["total"] == 1
