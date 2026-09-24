"""Reusable GSTR-1 B2B invoice validation rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")

ALIASES = {
    "invoice_number": ["Invoice Number", "Invoice No", "Invoice No."],
    "invoice_date": ["Invoice Date", "Invoice date"],
    "recipient_gstin": ["Recipient GSTIN/UIN", "GSTIN/UIN of Recipient", "GSTIN of Recipient"],
    "place_of_supply": ["Place of Supply", "POS"],
    "taxable_value": ["Taxable Value", "Taxable value"],
    "cgst": ["CGST", "CGST Amount"],
    "sgst": ["SGST", "SGST Amount"],
    "igst": ["IGST", "IGST Amount"],
    "invoice_value": ["Client Invoice Value", "Invoice Value", "Total Invoice Value", "Invoice value"],
    "rate": ["Rate", "Tax Rate", "GST Rate"],
}

DIFFERENCE_REASONS = ["Round off diff.", "TCS/Discount"]
INVOICE_ERROR_REASONS = {"TCS/Discount"}


def default_difference_reason(difference_amount: float | None) -> str:
    """Suggest a treatment from the absolute difference amount."""
    if difference_amount is None:
        return "Discount"
    difference = abs(difference_amount)
    if difference < 50:
        return DIFFERENCE_REASONS[0]
    if difference <= 100:
        return "Discount"
    return "TCS"


def is_invoice_error_reason(reason: str | None) -> bool:
    normalized = str(reason or "").strip().casefold()
    return normalized not in {"", "round off diff.","TCS/Discount"}


def find_column(columns: list[str], key: str) -> str | None:
    """Return the first accepted input header for a canonical field."""
    normalized = {str(column).strip().casefold(): column for column in columns}
    for candidate in ALIASES[key]:
        actual = normalized.get(candidate.casefold())
        if actual is not None:
            return actual
    return None


def extract_state_code(value: Any) -> str | None:
    """Extract the two-digit GST state/POS code from values like 36-Telangana."""
    if value is None:
        return None
    match = re.match(r"^\s*(\d{2})(?:\D|$)", str(value))
    return match.group(1) if match else None


def normalize_pos_value(value: Any) -> str:
    """Keep POS in a consistent code-name form, for example ``36-Telangana``."""
    text = str(value or "").strip()
    match = re.match(r"^(\d{2})\s*-?\s*(.*?)\s*$", text)
    if not match:
        return text
    code, name = match.groups()
    return f"{code}-{name}" 


def parse_amount(value: Any) -> float | None:
    if value is None or str(value).strip() in {"", "-", "nan", "None"}:
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("₹", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def parse_invoice_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        # Excel commonly imports a date cell as "2026-06-14 00:00:00".
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for pattern in (
        "%Y-%m-%d",
        "%d-%b-%y",
        "%d-%b-%Y",
        "%d-%b-%y %H:%M:%S",
        "%d-%b-%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


@dataclass
class ValidationResult:
    status: str
    errors: list[str]
    warnings: list[str]
    recipient_state: str | None
    pos_state: str | None
    supply_type: str | None
    rate: float | None
    expected_cgst: float | None
    expected_sgst: float | None
    expected_igst: float | None
    calculated_invoice_value: float | None
    client_invoice_value: float | None
    difference_amount: float | None


def validate_invoice(
    row: dict[str, Any],
    columns: list[str],
    as_of: date | None = None,
    tax_period: date | None = None,
    accept_pos: bool = False,
    registered_state_code: str | None = None,
) -> ValidationResult:
    """Validate one invoice and calculate statutory expected tax amounts."""
    as_of = as_of or date.today()
    get = lambda key: row.get(find_column(columns, key)) if find_column(columns, key) else None
    errors: list[str] = []
    warnings: list[str] = []

    gstin = str(get("recipient_gstin") or "").strip().upper()
    if not gstin:
        return ValidationResult(
            "Skipped",
            [],
            [],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    recipient_state = extract_state_code(gstin)
    if not GSTIN_PATTERN.fullmatch(gstin):
        errors.append("Recipient GSTIN format is invalid")

    pos_state = extract_state_code(get("place_of_supply"))
    
    if not pos_state:
        errors.append("Place of Supply must begin with a two-digit state code")

    invoice_date = parse_invoice_date(get("invoice_date"))
    if not invoice_date:
        errors.append("Invoice date is invalid or missing")
    elif invoice_date > as_of:
        errors.append("Invoice date cannot be in the future")
    elif tax_period and (invoice_date.year, invoice_date.month) != (tax_period.year, tax_period.month):
        errors.append(f"Invoice date is outside the selected tax period ({tax_period:%B %Y})")

    taxable_value = parse_amount(get("taxable_value"))
    entered_tax = tuple(
        parse_amount(get(key)) if find_column(columns, key) else None
        for key in ("cgst", "sgst", "igst")
    )
    if taxable_value is None or taxable_value < 0:
        errors.append("Taxable Value must be a non-negative number")
    if any(value is not None and value < 0 for value in entered_tax):
        errors.append("GST amounts must be non-negative numbers")

    rate = parse_amount(get("rate")) if find_column(columns, "rate") else None
    if rate is None or rate < 0:
        errors.append("GST rate must be a non-negative number")

    supply_type = None
    expected_cgst = expected_sgst = expected_igst = calculated_invoice_value = None
    client_invoice_value = difference_amount = None
    if recipient_state and pos_state and taxable_value is not None and rate is not None:
        registered_state = registered_state_code or recipient_state
        pos_error = recipient_state != pos_state
        if pos_error and not accept_pos:
            errors.append("GSTIN state code and Place of Supply state code do not match")
        if accept_pos and pos_error:
            warnings.append("POS accepted: CGST and IGST calculated")
            supply_type = "POS accepted (CGST + IGST)"
        elif recipient_state == pos_state and registered_state == pos_state:
            supply_type = "Intra-state"
        else:
            # A registered-state mismatch is inter-state even when GSTIN and POS agree.
            supply_type = "Inter-state"
        total_tax = round(taxable_value * rate / 100, 2)
        if supply_type == "Intra-state":
            expected_cgst = expected_sgst = round(total_tax / 2, 2)
            expected_igst = 0.0
        elif supply_type == "POS accepted (CGST + IGST)":
            expected_cgst = round(total_tax / 2, 2)
            expected_sgst = 0.0
            expected_igst = round(total_tax - expected_cgst, 2)
        else:
            expected_cgst = expected_sgst = 0.0
            expected_igst = total_tax
        calculated_invoice_value = round(taxable_value + expected_cgst + expected_sgst + expected_igst, 2)
        if find_column(columns, "invoice_value"):
            client_invoice_value = parse_amount(get("invoice_value"))
            if client_invoice_value is not None:
                difference_amount = round(client_invoice_value - calculated_invoice_value, 2)
                if abs(difference_amount) >= 10:
                    if accept_pos:
                        warnings.append("Invoice value difference requires TCS or Discount treatment")
                    else:
                        errors.append("Invoice value difference requires TCS or Discount treatment")
        expected = (expected_cgst, expected_sgst, expected_igst)
        if not (accept_pos and pos_error) and None not in entered_tax and any(abs(actual - calculated) > 0.01 for actual, calculated in zip(entered_tax, expected)):
            errors.append("GST split does not match the GSTIN/POS supply type and rate")

    return ValidationResult(
        "Error" if errors else ("Warning" if warnings else "Valid"), errors, warnings,
        recipient_state, pos_state, supply_type, rate, expected_cgst, expected_sgst,
        expected_igst,
        calculated_invoice_value,
        client_invoice_value,
        difference_amount,
    )
