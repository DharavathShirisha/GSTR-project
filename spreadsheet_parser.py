"""Import helpers for GSTR-1 spreadsheets that have title rows above a table."""

import pandas as pd

from backend.gstr1_validator import find_column


REQUIRED_FIELDS = ("place_of_supply", "invoice_date", "taxable_value", "rate")


def clean_cell(value) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def header_row_index(raw: pd.DataFrame) -> int | None:
    """Find a GSTR-1 header row among the first 30 spreadsheet rows."""
    for index, row in raw.head(30).iterrows():
        headers = [clean_cell(value) for value in row.tolist()]
        matched = sum(find_column(headers, field) is not None for field in REQUIRED_FIELDS)
        if matched == len(REQUIRED_FIELDS):
            return index
    return None


def prepare_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """Promote the detected table header and remove title/blank rows."""
    index = header_row_index(raw)
    if index is None:
        return raw
    headers = [clean_cell(value) or f"Column {position + 1}" for position, value in enumerate(raw.iloc[index].tolist())]
    data = raw.iloc[index + 1 :].copy()
    data.columns = headers
    data = data.dropna(how="all")
    return data.loc[:, ~data.columns.duplicated()]
