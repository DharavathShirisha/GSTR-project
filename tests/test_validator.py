import csv
from datetime import date

from backend.gstr1_validator import validate_invoice


def base_row():
    return {
        "Recipient GSTIN/UIN": "36ABCDE1234F1Z5",
        "Place of Supply": "36-Telangana",
        "Invoice Date": "01-Sep-26",
        "Taxable Value": "10000",
        "Rate": "18",
        "CGST": "900",
        "SGST": "900",
        "IGST": "0",
    }


def test_valid_intra_state_invoice():
    row = base_row()
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10))
    assert result.status == "Valid"
    assert result.expected_cgst == 900
    assert result.expected_sgst == 900
    assert result.calculated_invoice_value == 11800


def test_gstin_pos_mismatch_and_tax_error():
    row = base_row()
    row["Place of Supply"] = "27-Maharashtra"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10))
    assert result.status == "Error"
    assert result.expected_igst == 1800
    assert result.calculated_invoice_value == 11800
    assert any("do not match" in error for error in result.errors)


def test_invalid_future_date():
    row = base_row()
    row["Invoice Date"] = "01-Oct-26"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10))
    assert "Invoice date cannot be in the future" in result.errors


def test_invoice_date_must_be_in_selected_tax_period():
    row = base_row()
    result = validate_invoice(
        row,
        list(row),
        as_of=date(2026, 9, 10),
        tax_period=date(2026, 6, 1),
    )
    assert "Invoice date is outside the selected tax period (June 2026)" in result.errors


def test_blank_gstin_is_not_validated():
    row = base_row()
    row["Recipient GSTIN/UIN"] = ""
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10))
    assert result.status == "Skipped"
    assert result.recipient_state is None
    assert result.expected_cgst is None
    assert result.calculated_invoice_value is None


def test_calculates_tax_when_gst_columns_are_absent():
    row = base_row()
    row.pop("CGST")
    row.pop("SGST")
    row.pop("IGST")
    row["Rate"] = "3%"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10))
    assert result.status == "Valid"
    assert result.expected_cgst == 150
    assert result.expected_sgst == 150
    assert result.expected_igst == 0
    assert result.calculated_invoice_value == 10300


def test_excel_datetime_string_is_a_valid_invoice_date():
    row = base_row()
    row["Invoice Date"] = "2026-09-01 00:00:00"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10), tax_period=date(2026, 9, 1))
    assert "Invoice date is invalid or missing" not in result.errors


def test_month_day_year_excel_date_is_parsed_without_time():
    row = base_row()
    row["Invoice Date"] = "6-14-2026 00:00:00"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10), tax_period=date(2026, 6, 1))
    assert result.status == "Valid"


def test_accept_pos_uses_cgst_sgst_and_calculates_sft_difference():
    row = base_row()
    row["Place of Supply"] = "27-Maharashtra"
    row["Client Invoice Value"] = "11825"
    result = validate_invoice(row, list(row), as_of=date(2026, 9, 10), accept_pos=True)
    assert result.status == "Warning"
    assert result.expected_cgst == 900
    assert result.expected_sgst == 900
    assert result.expected_igst == 0
    assert result.calculated_invoice_value == 11800
    assert result.difference_amount == 25
