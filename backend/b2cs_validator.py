from __future__ import annotations

from typing import Any

import pandas as pd

from backend.b2cl_validator import STATE_CODES

REQUIRED_COLUMNS = [
    "Type",
    "Place Of Supply",
    "Rate",
    "Taxable Value",
    "Cess Amount",
    "E-Commerce GSTIN",
]


def _find_column(columns: list[str], name: str) -> str | None:
    normalized = {str(column).strip().casefold(): column for column in columns}
    return normalized.get(name.casefold())


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(str(value).replace(",", "").replace("₹", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _state_code(value: Any) -> str:
    text = str(value or "").strip()
    return text[:2] if text[:2].isdigit() else ""


def _state_name(code: str) -> str:
    return next((name for name, state_code in STATE_CODES.items() if state_code == code), "Unknown")


def validate_b2cs_dataframe(
    dataframe: pd.DataFrame,
    registered_state_code: str,
) -> pd.DataFrame:
    source = dataframe.copy()
    columns = list(source.columns)
    type_column = _find_column(columns, "Type")
    pos_column = _find_column(columns, "Place Of Supply")
    rate_column = _find_column(columns, "Rate")
    taxable_column = _find_column(columns, "Taxable Value")
    cess_column = _find_column(columns, "Cess Amount")

    statuses: list[str] = []
    errors: list[str] = []
    supply_types: list[str] = []
    pos_states: list[str] = []
    calculated_cgst: list[float] = []
    calculated_sgst: list[float] = []
    calculated_igst: list[float] = []

    for _, row in source.iterrows():
        row_errors: list[str] = []
        pos = _state_code(row.get(pos_column)) if pos_column else ""
        rate = _number(row.get(rate_column)) if rate_column else None
        taxable = _number(row.get(taxable_column)) if taxable_column else None
        cess = _number(row.get(cess_column)) if cess_column else None

        # if not pos:
        #     row_errors.append("Place of Supply must begin with a two-digit state code")
        # elif pos not in STATE_CODES.values():
        #     row_errors.append(f"Invalid Place of Supply state code: {pos}")
        # elif pos != registered_state_code:
        #     row_errors.append(
        #         f"POS Error: Place of Supply state {pos} differs from registered state {registered_state_code}"
        #     )
        # if rate is None or rate < 0:
        #     row_errors.append("Rate must be a non-negative number")
        # if taxable is None or taxable < 0:
        #     row_errors.append("Taxable Value must be a non-negative number")
        # if cess is None or cess < 0:
        #     row_errors.append("Cess Amount must be a non-negative number")

        cgst = sgst = igst = 0.0
        supply_type = ""
        if taxable is not None and rate is not None and pos in STATE_CODES.values():
            tax = round(taxable * rate / 100, 2)
            if pos == registered_state_code:
                supply_type = "Intra-state"
                cgst = round(tax / 2, 2)
                sgst = round(tax / 2, 2)
            else:
                supply_type = "Inter-state"
                igst = tax

        statuses.append("Error" if row_errors else "Valid")
        errors.append("; ".join(row_errors))
        supply_types.append(supply_type)
        pos_states.append(f"{pos}-{_state_name(pos)}" if pos else "")
        calculated_cgst.append(cgst)
        calculated_sgst.append(sgst)
        calculated_igst.append(igst)

    output = source.copy()

    output["POS State"] = pos_states
    output["Supply Type"] = supply_types
    output["Calculated CGST"] = calculated_cgst
    output["Calculated SGST"] = calculated_sgst
    output["Calculated IGST"] = calculated_igst
    # output["Error Type"] = [
    #     "POS Error" if "POS Error:" in error else ""
    #     for error in errors
    # ]
    return output
