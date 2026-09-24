from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


# ============================================================
# B2CL Required Columns
# ============================================================

REQUIRED_COLUMNS = [
    "Invoice date",
    "Invoice Value",
    "Place Of Supply",
    "Rate",
    "Taxable Value",
]


# ============================================================
# State Codes
# ============================================================

STATE_CODES = {
    "Jammu & Kashmir": "01",
    "Himachal Pradesh": "02",
    "Punjab": "03",
    "Chandigarh": "04",
    "Uttarakhand": "05",
    "Haryana": "06",
    "Delhi": "07",
    "Rajasthan": "08",
    "Uttar Pradesh": "09",
    "Bihar": "10",
    "Sikkim": "11",
    "Arunachal Pradesh": "12",
    "Nagaland": "13",
    "Manipur": "14",
    "Mizoram": "15",
    "Tripura": "16",
    "Meghalaya": "17",
    "Assam": "18",
    "West Bengal": "19",
    "Jharkhand": "20",
    "Odisha": "21",
    "Chhattisgarh": "22",
    "Madhya Pradesh": "23",
    "Gujarat": "24",
    "Dadra and Nagar Haveli and Daman and Diu": "26",
    "Maharashtra": "27",
    "Andhra Pradesh": "37",
    "Karnataka": "29",
    "Goa": "30",
    "Lakshadweep": "31",
    "Kerala": "32",
    "Tamil Nadu": "33",
    "Puducherry": "34",
    "Andaman and Nicobar Islands": "35",
    "Telangana": "36",
    "Andhra Pradesh (Old)": "28",
    "Ladakh": "38",
    "Other Territory": "97",
}


# ============================================================
# Find Column
# ============================================================

def find_column(
    columns: list[str],
    expected_name: str,
) -> str | None:

    for column in columns:

        if str(column).strip().casefold() == expected_name.casefold():
            return column

    return None


# ============================================================
# Required Column Validation
# ============================================================

def validate_required_columns(
    columns: list[str],
) -> list[str]:

    missing_columns = []

    for required_column in REQUIRED_COLUMNS:

        if find_column(columns, required_column) is None:
            missing_columns.append(required_column)

    return missing_columns


# ============================================================
# Parse Date
# ============================================================

def parse_invoice_date(
    value: Any,
) -> pd.Timestamp | None:

    if pd.isna(value):
        return None

    try:

        parsed = pd.to_datetime(
            value,
            dayfirst=True,
            errors="coerce",
        )

        if pd.isna(parsed):
            return None

        return parsed

    except Exception:

        return None


# ============================================================
# Convert Number
# ============================================================

def to_number(value: Any) -> float | None:

    if pd.isna(value):
        return None

    try:

        if isinstance(value, str):

            value = (
                value
                .replace("₹", "")
                .replace(",", "")
                .strip()
            )

        return float(value)

    except (TypeError, ValueError):

        return None


# ============================================================
# Normalize POS
# ============================================================

def normalize_pos(
    value: Any,
) -> str:

    if pd.isna(value):
        return ""

    value = str(value).strip()

    # Example:
    # "36 - Telangana" -> "36"
    # "36"             -> "36"

    if "-" in value:

        value = value.split("-")[0].strip()

    return value.zfill(2)


# ============================================================
# Get State Name
# ============================================================

def get_state_name(
    state_code: str,
) -> str:

    for state, code in STATE_CODES.items():

        if code == state_code:
            return state

    return "Unknown"


# ============================================================
# Validate One B2CL Invoice
# ============================================================

def validate_b2cl_invoice(
    record: dict[str, Any],
    columns: list[str],
    selected_month: int,
    selected_year: int,
    registered_state_code: str,
) -> dict[str, Any]:

    errors: list[str] = []
    warnings: list[str] = []

    # --------------------------------------------------------
    # Find columns
    # --------------------------------------------------------

    invoice_date_column = find_column(
        columns,
        "Invoice date",
    )

    invoice_value_column = find_column(
        columns,
        "Invoice Value",
    )

    pos_column = find_column(
        columns,
        "Place Of Supply",
    )

    rate_column = find_column(
        columns,
        "Rate",
    )

    taxable_value_column = find_column(
        columns,
        "Taxable Value",
    )


    # --------------------------------------------------------
    # Read values
    # --------------------------------------------------------

    invoice_date = (
        parse_invoice_date(record.get(invoice_date_column))
        if invoice_date_column
        else None
    )

    invoice_value = (
        to_number(record.get(invoice_value_column))
        if invoice_value_column
        else None
    )

    pos_code = (
        normalize_pos(record.get(pos_column))
        if pos_column
        else ""
    )

    rate = (
        to_number(record.get(rate_column))
        if rate_column
        else None
    )

    taxable_value = (
        to_number(record.get(taxable_value_column))
        if taxable_value_column
        else None
    )


    # ========================================================
    # 1. TAX PERIOD VALIDATION
    # ========================================================

    if invoice_date is None:

        errors.append(
            "TAX Period Error: Invoice date is invalid or missing."
        )

    else:

        if (
            invoice_date.month != selected_month
            or invoice_date.year != selected_year
        ):

            errors.append(
                "TAX Period Error: "
                f"Invoice date {invoice_date.strftime('%d-%m-%Y')} "
                "is outside the selected tax period."
            )


        # Invoice cannot be in future
        if invoice_date.date() > date.today():

            errors.append(
                "Invoice date cannot be in the future."
            )


    # ========================================================
    # 2. INVOICE VALUE > ₹1 LAKH
    # ========================================================

    if invoice_value is None:

        errors.append(
            "Invoice Value Error: Invoice value is missing or invalid."
        )

    elif invoice_value <= 100000:

        errors.append(
            "Invoice Value Error: "
            "B2CL invoice value should be greater than ₹1,00,000."
        )


    # ========================================================
    # 3. PLACE OF SUPPLY
    # ========================================================

    if not pos_code:

        errors.append(
            "Place of Supply Error: Place Of Supply is missing."
        )

    elif pos_code not in STATE_CODES.values():

        errors.append(
            f"Place of Supply Error: Invalid state code '{pos_code}'."
        )

    elif pos_code == registered_state_code:

        errors.append(
            "Place of Supply Error: "
            f"Place Of Supply ({pos_code} - {get_state_name(pos_code)}) "
            "does not match the selected principal place of business "
            f"({registered_state_code} - "
            f"{get_state_name(registered_state_code)})."
        )


    # ========================================================
    # 4. RATE VALIDATION
    # ========================================================

    if rate is None:

        errors.append(
            "Tax Error: GST rate is missing or invalid."
        )

    elif rate < 0:

        errors.append(
            "Tax Error: GST rate cannot be negative."
        )


    # ========================================================
    # 5. TAXABLE VALUE VALIDATION
    # ========================================================

    if taxable_value is None:

        errors.append(
            "Taxable Value Error: Taxable value is missing or invalid."
        )

    elif taxable_value < 0:

        errors.append(
            "Taxable Value Error: Taxable value cannot be negative."
        )


    # ========================================================
    # 6. GST CALCULATION
    # ========================================================

    if taxable_value is not None and rate is not None:

        # User requirement:
        # IGST only
        # CGST = 0
        # SGST = 0

        calculated_igst = (
            taxable_value * rate / 100
        )

        calculated_cgst = 0.0
        calculated_sgst = 0.0

    else:

        calculated_igst = 0.0
        calculated_cgst = 0.0
        calculated_sgst = 0.0


    # ========================================================
    # 7. SFI INVOICE VALUE
    # ========================================================

    if taxable_value is not None:

        sfi_invoice_value = taxable_value

    else:

        sfi_invoice_value = 0.0


    # ========================================================
    # 8. CLIENT VS SFI DIFFERENCE
    # ========================================================

    if invoice_value is not None:

        difference_amount = (
            invoice_value - sfi_invoice_value
        )

    else:

        difference_amount = 0.0


    # ========================================================
    # 9. FINAL STATUS
    # ========================================================

    if errors:

        status = "Error"

    elif warnings:

        status = "Warning"

    else:

        status = "Valid"


    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,

        "invoice_date": (
            invoice_date.strftime("%d-%m-%Y")
            if invoice_date is not None
            else ""
        ),

        "invoice_value": invoice_value,
        "place_of_supply": pos_code,
        "place_of_supply_name": get_state_name(pos_code),
        "rate": rate,
        "taxable_value": taxable_value,

        "calculated_igst": calculated_igst,
        "calculated_cgst": calculated_cgst,
        "calculated_sgst": calculated_sgst,

        "sfi_invoice_value": sfi_invoice_value,
        "difference_amount": difference_amount,
    }


# ============================================================
# Validate Entire DataFrame
# ============================================================

def validate_b2cl_dataframe(
    dataframe: pd.DataFrame,
    selected_month: int,
    selected_year: int,
    registered_state_code: str,
) -> pd.DataFrame:

    source = dataframe.copy()

    columns = list(source.columns)

    results = []

    for _, row in source.iterrows():

        result = validate_b2cl_invoice(
            record=row.to_dict(),
            columns=columns,
            selected_month=selected_month,
            selected_year=selected_year,
            registered_state_code=registered_state_code,
        )

        results.append(result)


    output = source.copy()

    output["Validation Status"] = [
        result["status"]
        for result in results
    ]

    output["Errors"] = [
        "; ".join(result["errors"])
        for result in results
    ]

    output["Warnings"] = [
        "; ".join(result["warnings"])
        for result in results
    ]

    output["POS State"] = [
        (
            f'{result["place_of_supply"]} - '
            f'{result["place_of_supply_name"]}'
        )
        if result["place_of_supply"]
        else ""
        for result in results
    ]

    output["Calculated IGST"] = [
        result["calculated_igst"]
        for result in results
    ]

    output["Calculated CGST"] = [
        result["calculated_cgst"]
        for result in results
    ]

    output["Calculated SGST"] = [
        result["calculated_sgst"]
        for result in results
    ]

    output["SFI Invoice Value"] = [
        result["sfi_invoice_value"]
        for result in results
    ]

    output["Difference Amount"] = [
        result["difference_amount"]
        for result in results
    ]

    return output