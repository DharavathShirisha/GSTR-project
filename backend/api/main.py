"""FastAPI endpoints for GSTR-1 validation and filing preparation."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.b2cl_validator import (
    REQUIRED_COLUMNS,
    STATE_CODES,
    validate_b2cl_dataframe,
    validate_required_columns,
)
from backend.b2cs_validator import (
    REQUIRED_COLUMNS as B2CS_REQUIRED_COLUMNS,
    validate_b2cs_dataframe,
)
from backend.gstr1_validator import (
    ALIASES,
    default_difference_reason,
    find_column,
    normalize_pos_value,
    parse_invoice_date,
    validate_invoice,
)
from spreadsheet_parser import prepare_sheet

app = FastAPI(
    title="GSTR-1 Validation API",
    version="1.0.0",
    description="Validate B2B and B2CL invoice spreadsheets before filing.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_upload(contents: bytes, filename: str) -> pd.DataFrame:
    try:
        if filename.lower().endswith(".csv"):
            return pd.read_csv(BytesIO(contents), header=None, dtype=str, keep_default_na=False)
        if filename.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(BytesIO(contents), header=None, dtype=str, keep_default_na=False)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to read file: {error}") from error
    raise HTTPException(status_code=415, detail="Only CSV, XLSX and XLS files are supported.")


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _json_value(value) for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def _tax_period(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="tax_period must use YYYY-MM format") from error


def _b2b_validation(frame: pd.DataFrame, tax_period: date | None, accepted_rows: set[int], registered_state_code: str = "36") -> pd.DataFrame:
    columns = list(frame.columns)
    results = [
        validate_invoice(
            record.to_dict(),
            columns,
            as_of=date.today(),
            tax_period=tax_period,
            accept_pos=index in accepted_rows,
            registered_state_code=registered_state_code,
        )
        for index, record in frame.iterrows()
    ]
    output = frame.copy()
    invoice_date_column = find_column(columns, "invoice_date")
    if invoice_date_column:
        output[invoice_date_column] = [
            parsed.strftime("%d-%m-%Y") if (parsed := parse_invoice_date(value)) else value
            for value in frame[invoice_date_column]
        ]
    pos_column = find_column(columns, "place_of_supply")
    if pos_column:
        output[pos_column] = [normalize_pos_value(value) for value in frame[pos_column]]
    output["Validation Status"] = [result.status for result in results]
    output["Errors"] = ["; ".join(result.errors) for result in results]
    output["Warnings"] = ["; ".join(result.warnings) for result in results]
    output["Error Type"] = [
        "; ".join(
            category
            for category, marker in (
                ("POS Error", "GSTIN state code and Place of Supply state code do not match"),
                ("Period Error", "Invoice date is outside the selected tax period"),
            )
            if any(marker in error for error in result.errors)
        ) or ("Invoice Error" if result.errors else "")
        for result in results
    ]
    output["GSTIN State"] = [result.recipient_state or "" for result in results]
    output["POS State"] = [
        normalize_pos_value(frame.loc[index, pos_column]) if pos_column else ""
        for index in frame.index
    ]
    output["Supply Type"] = [result.supply_type or "" for result in results]
    output["Calculated Rate %"] = [result.rate for result in results]
    output["Calculated CGST"] = [result.expected_cgst for result in results]
    output["Calculated SGST"] = [result.expected_sgst for result in results]
    output["Calculated IGST"] = [result.expected_igst for result in results]
    output["SFT Invoice Value"] = [result.calculated_invoice_value for result in results]
    output["Client Invoice Value"] = [result.client_invoice_value for result in results]
    output["Difference Amount"] = [result.difference_amount for result in results]
    output["Reasons"] = [default_difference_reason(result.difference_amount) for result in results]
    output["POS Accepted"] = [index in accepted_rows for index in frame.index]
    return output


def _response(frame: pd.DataFrame, filename: str, missing_columns: list[str] | None = None) -> dict[str, Any]:
    statuses = frame.get("Validation Status", pd.Series(dtype=str))
    error_types = frame.get("Error Type", pd.Series(dtype=str)).fillna("").astype(str)
    has_error_type_status = "Validation Status" not in frame.columns and "Error Type" in frame.columns
    return {
        "filename": filename,
        "columns": [str(column) for column in frame.columns],
        "missing_columns": missing_columns or [],
        "summary": {
            "total": int(len(frame)),
            "valid": int((error_types == "").sum()) if has_error_type_status else int((statuses == "Valid").sum()),
            "errors": int((error_types != "").sum()) if has_error_type_status else int((statuses == "Error").sum()),
            "warnings": int((statuses == "Warning").sum()),
            "skipped": int((statuses == "Skipped").sum()),
        },
        "rows": _records(frame),
    }


def _error_breakdown(frame: pd.DataFrame, categories: tuple[str, ...]) -> dict[str, int]:
    error_types = frame.get("Error Type", pd.Series(dtype=str)).fillna("").astype(str)
    return {
        category: int(error_types.str.contains(category, case=False, na=False).sum())
        for category in categories
    }


def _b2cl_error_type(errors: Any) -> str:
    error_text = str(errors or "")
    categories = (
        "Tax Period Error",
        "Invoice Value Error",
        "Place of Supply Error",
        "Taxable Value Error",
    )
    return "; ".join(category for category in categories if category.casefold() in error_text.casefold())


def validate_gstr1_workbook(
    contents: bytes,
    month: int,
    year: int,
    registered_state_code: str,
    filename: str = "upload",
    accept_pos_all: bool = False,
) -> dict[str, Any]:
    try:
        workbook = pd.ExcelFile(BytesIO(contents))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to read workbook: {error}") from error

    normalized = {
        "".join(character for character in str(name).casefold() if character.isalnum()): name
        for name in workbook.sheet_names
    }

    def resolve(prefix: str) -> str | None:
        return next((name for key, name in normalized.items() if prefix in key), None)

    sheets = {"b2b": resolve("b2b"), "b2cl": resolve("b2cl"), "b2cs": resolve("b2cs")}
    missing = [name for name in ("b2b", "b2cl") if not sheets[name]]
    if missing:
        raise HTTPException(status_code=422, detail=f"Workbook must contain B2B and B2CL sheets. Missing: {', '.join(missing)}")

    results: dict[str, Any] = {"filename": filename, "month": month, "year": year, "registered_state_code": registered_state_code}
    for key in ("b2b", "b2cl", "b2cs"):
        sheet_name = sheets[key]
        if not sheet_name:
            continue
        source = workbook.parse(sheet_name, dtype=str, keep_default_na=False)
        source.columns = [str(column).strip() for column in source.columns]
        if key == "b2b":
            source = prepare_sheet(source)
            source.columns = [str(column).strip() for column in source.columns]
            missing_columns = [field for field in ("place_of_supply", "invoice_date", "taxable_value", "rate") if not find_column(list(source.columns), field)]
            if missing_columns:
                results[key] = _response(source, filename, [ALIASES[field][0] for field in missing_columns])
            else:
                validated = _b2b_validation(source, date(year, month, 1), set(), registered_state_code)
                if accept_pos_all:
                    accepted_rows = set(validated.index[validated["Error Type"].str.contains("POS Error", na=False)])
                    validated = _b2b_validation(source, date(year, month, 1), accepted_rows, registered_state_code)
                results[key] = _response(validated, filename)
                results[key]["error_breakdown"] = _error_breakdown(validated, ("POS Error", "Period Error", "Invoice Error"))
        elif key == "b2cl":
            missing_columns = validate_required_columns(list(source.columns))
            if missing_columns:
                results[key] = _response(source, filename, missing_columns)
            else:
                validated = validate_b2cl_dataframe(source, month, year, registered_state_code)
                validated["Error Type"] = validated["Errors"].map(_b2cl_error_type)
                results[key] = _response(validated, filename)
                results[key]["error_breakdown"] = _error_breakdown(
                    validated,
                    (
                        "Tax Period Error",
                        "Invoice Value Error",
                        "Place of Supply Error",
                        "Taxable Value Error",
                    ),
                )
        else:
            missing_columns = [column for column in B2CS_REQUIRED_COLUMNS if not any(str(existing).casefold() == column.casefold() for existing in source.columns)]
            if missing_columns:
                results[key] = _response(source, filename, missing_columns)
            else:
                validated = validate_b2cs_dataframe(source, registered_state_code)
                results[key] = _response(validated, filename)
                results[key]["error_breakdown"] = _error_breakdown(validated, ("POS Error",))
    return results


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/metadata")
def metadata() -> dict[str, Any]:
    return {
        "b2b_aliases": ALIASES,
        "b2cl_required_columns": REQUIRED_COLUMNS,
        "b2cs_required_columns": B2CS_REQUIRED_COLUMNS,
        "state_codes": STATE_CODES,
    }


@app.post("/api/v1/validate/b2b")
async def validate_b2b(
    file: UploadFile = File(...),
    tax_period: str | None = Form(None),
    accepted_rows: str = Form(""),
) -> dict[str, Any]:
    source = prepare_sheet(_read_upload(await file.read(), file.filename or "upload"))
    source.columns = [str(column).strip() for column in source.columns]
    missing = [field for field in ("place_of_supply", "invoice_date", "taxable_value", "rate") if not find_column(list(source.columns), field)]
    if missing:
        return _response(source, file.filename or "upload", [ALIASES[field][0] for field in missing])
    try:
        accepted = {int(value) for value in accepted_rows.split(",") if value.strip()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail="accepted_rows must be comma-separated row numbers") from error
    validated = _b2b_validation(source, _tax_period(tax_period), accepted)
    return _response(validated, file.filename or "upload")


@app.post("/api/v1/validate/b2cl")
async def validate_b2cl(
    file: UploadFile = File(...),
    month: int = Form(...),
    year: int = Form(...),
    registered_state_code: str = Form(...),
) -> dict[str, Any]:
    contents = await file.read()
    try:
        if file.filename and file.filename.lower().endswith(".csv"):
            source = pd.read_csv(BytesIO(contents), dtype=str)
        elif file.filename and file.filename.lower().endswith((".xlsx", ".xls")):
            source = pd.read_excel(BytesIO(contents), dtype=str)
        else:
            raise HTTPException(status_code=415, detail="Only CSV, XLSX and XLS files are supported.")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to read file: {error}") from error
    source.columns = [str(column).strip() for column in source.columns]
    missing = validate_required_columns(list(source.columns))
    if missing:
        return _response(source, file.filename or "upload", missing)
    if month not in range(1, 13) or len(str(year)) != 4 or registered_state_code not in STATE_CODES.values():
        raise HTTPException(status_code=422, detail="Invalid month, year, or registered state code")
    validated = validate_b2cl_dataframe(source, month, year, registered_state_code)
    return _response(validated, file.filename or "upload")


@app.post("/api/v1/validate/b2cs")
async def validate_b2cs(
    file: UploadFile = File(...),
    registered_state_code: str = Form(...),
) -> dict[str, Any]:
    contents = await file.read()
    try:
        if file.filename and file.filename.lower().endswith(".csv"):
            source = pd.read_csv(BytesIO(contents), dtype=str, keep_default_na=False)
        elif file.filename and file.filename.lower().endswith((".xlsx", ".xls")):
            source = pd.read_excel(BytesIO(contents), dtype=str, keep_default_na=False)
        else:
            raise HTTPException(status_code=415, detail="Only CSV, XLSX and XLS files are supported.")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to read file: {error}") from error

    source.columns = [str(column).strip() for column in source.columns]
    missing = [column for column in B2CS_REQUIRED_COLUMNS if not any(str(existing).casefold() == column.casefold() for existing in source.columns)]
    if missing:
        return _response(source, file.filename or "upload", missing)
    if registered_state_code not in STATE_CODES.values():
        raise HTTPException(status_code=422, detail="Invalid registered state code")
    validated = validate_b2cs_dataframe(source, registered_state_code)
    return _response(validated, file.filename or "upload")


@app.post("/api/v1/validate/gstr1")
async def validate_gstr1(
    file: UploadFile = File(...),
    month: int = Form(...),
    year: int = Form(...),
    registered_state_code: str = Form(...),
    accept_pos_all: bool = Form(False),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=415, detail="Only Excel workbooks (.xlsx, .xls) are supported.")
    return validate_gstr1_workbook(
        await file.read(),
        month,
        year,
        registered_state_code,
        file.filename,
        accept_pos_all,
    )
