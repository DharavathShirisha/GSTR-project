# GSTR-1 Data Validation & Filing Preparation

FastAPI + React application for validating GSTR-1 invoice data before filing. The original Streamlit dashboard remains available in `app.py` while the new API/client architecture is adopted.

## Core rule

- First 2 digits of recipient GSTIN = GST registration state code.
- First 2 digits of Place of Supply = POS state code.
- Same GSTIN state + POS state -> intra-state -> CGST + SGST expected, IGST should be zero.
- Different GSTIN state + POS state -> inter-state -> IGST expected, CGST/SGST should be zero.
- If GSTIN state and POS differ, the API reports a POS error and supports accepting POS rows in a later request.

> This project validates/prepares data. It does not directly submit a return to the GST portal. Production filing requires an approved GST API/ASP/GSP integration, authentication, authorization, audit controls and compliance review.

## Project structure

```text
gstr1-validation-project/
  backend/
    api/main.py
    gstr1_validator.py
    b2cl_validator.py
  frontend/
    src/
      main.jsx
      styles.css
    index.html
    package.json
  README.md
```

## Run the API

Python 3.11+ recommended.

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

## Run the React client

Node.js 20+ recommended.

```powershell
cd frontend
npm install
npm run dev
```
python -m streamlit run app.py
Open http://localhost:5173

The client sends multipart uploads to `http://localhost:8000/api/v1`. Set `VITE_API_URL` when the API is hosted elsewhere.

## API endpoints

- `GET /api/v1/health` - liveness check.
- `GET /api/v1/metadata` - aliases, required columns, and state codes.
- `POST /api/v1/validate/b2b` - CSV/XLS/XLSX upload with optional `tax_period`.
- `POST /api/v1/validate/b2cl` - CSV/XLS/XLSX upload with `month`, `year`, and `registered_state_code`.
- `POST /api/v1/validate/b2cs` - CSV/XLS/XLSX upload with `registered_state_code`.
- `POST /api/v1/validate/gstr1` - Excel workbook with required B2B and B2CL sheets and optional B2CS sheet.

B2CS requires `Type`, `Place Of Supply`, `Rate`, `Taxable Value`, `Cess Amount`, and `E-Commerce GSTIN`. Rows matching the registered state calculate CGST and SGST equally; other states calculate IGST.

Interactive API documentation is available at http://localhost:8000/docs.

## Sample

`backend/sample_data.csv` contains the rows from the example plus a couple of additional rows to demonstrate inter-state and same-state behavior.

## Production roadmap

1. GSTIN format + checksum validation.
2. Complete GST state/POS master from an authoritative source.
3. Duplicate invoice detection.
4. Taxable value/tax amount arithmetic checks.
5. Tax-rate validation.
6. B2B/B2C/CDNR/CDNUR/EXP classification.
7. Return-period and invoice-date validation.
8. Excel import/export and GST JSON generation.
9. Maker-checker approval and audit trail.
10. Authentication/RBAC.
11. Approved GST API/ASP/GSP filing integration.



Terminal 1: Backend API

From the project root:
cd "C:\Users\caviv\Desktop\gstr1-validation-project"

python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.api.main:app --reload --port 8000


Terminal 2: Frontend

cd "C:\Users\caviv\Desktop\gstr1-validation-project\frontend"
npm.cmd install
npm.cmd run dev