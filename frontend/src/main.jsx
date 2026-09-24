import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import * as XLSX from "xlsx";
import { jsPDF } from "jspdf";
import "./styles.css";
import "./workbook.css";

const API_URL = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
const DEFAULT_STATE_CODES = {
  "Jammu & Kashmir": "01", "Himachal Pradesh": "02", Punjab: "03", Chandigarh: "04",
  Uttarakhand: "05", Haryana: "06", Delhi: "07", Rajasthan: "08", "Uttar Pradesh": "09",
  Bihar: "10", Sikkim: "11", "Arunachal Pradesh": "12", Nagaland: "13", Manipur: "14",
  Mizoram: "15", Tripura: "16", Meghalaya: "17", Assam: "18", "West Bengal": "19",
  Jharkhand: "20", Odisha: "21", Chhattisgarh: "22", "Madhya Pradesh": "23", Gujarat: "24",
  "Dadra and Nagar Haveli and Daman and Diu": "26", Maharashtra: "27", "Andhra Pradesh (Old)": "28",
  Karnataka: "29", Goa: "30", Lakshadweep: "31", Kerala: "32", "Tamil Nadu": "33",
  Puducherry: "34", "Andaman and Nicobar Islands": "35", Telangana: "36", "Andhra Pradesh": "37",
  Ladakh: "38", "Other Territory": "97",
};

function downloadExcel(reports, filename) {
  const workbook = XLSX.utils.book_new();
  reports.forEach(({ title, report }) => {
    if (!report) return;
    const rows = report.rows || [];
    const columns = report.columns || Object.keys(rows[0] || {});
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(rows, { header: columns }), title.slice(0, 31));
  });
  XLSX.writeFile(workbook, filename);
}

function downloadPdf(reports, filename) {
  const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  reports.forEach(({ title, report }, reportIndex) => {
    if (!report) return;
    if (reportIndex > 0) pdf.addPage();
    const rows = report.rows || [];
    const columns = report.columns || Object.keys(rows[0] || {});
    const visibleColumns = title === "B2CS"
      ? columns.filter((column) => !["Supply Type", "Errors", "Validation Status"].includes(column))
      : columns;
    const columnWidth = Math.max(58, (pdf.internal.pageSize.getWidth() - 48) / Math.max(visibleColumns.length, 1));
    pdf.setFontSize(14);
    pdf.text(`${title} Validation Report`, 24, 28);
    pdf.setFontSize(7);
    visibleColumns.forEach((column, columnIndex) => pdf.text(String(column).slice(0, 18), 24 + columnIndex * columnWidth, 45));
    rows.forEach((row, rowIndex) => {
      const y = 58 + (rowIndex % 42) * 15;
      if (rowIndex > 0 && rowIndex % 42 === 0) {
        pdf.addPage();
        pdf.setFontSize(7);
      }
      visibleColumns.forEach((column, columnIndex) => pdf.text(String(row[column] ?? "-").slice(0, 18), 24 + columnIndex * columnWidth, y));
    });
  });
  pdf.save(filename);
}

function Summary({ summary, selectedStatus, onSelect }) {
  const filters = [["Total", "All", summary?.total], ["Valid", "Valid", summary?.valid], ["Errors", "Error", summary?.errors], ["Warnings", "Warning", summary?.warnings]];
  return <div className="summary">{filters.map(([label, filter, value]) => <button className={`metric ${label.toLowerCase()} ${selectedStatus === filter ? "selected" : ""}`} key={label} onClick={() => onSelect(filter)}><span>{label}</span><strong>{value ?? 0}</strong></button>)}</div>;
}

function Report({ title, report, onAcceptPos, loading, posAccepted }) {
  const [selectedErrorType, setSelectedErrorType] = useState("All");
  const [selectedStatus, setSelectedStatus] = useState("All");

  if (!report) return null;
  const rows = report.rows || [];
  const columns = report.columns || Object.keys(rows[0] || {});
  const displayColumns = title === "B2CS"
    ? [
        ...columns.filter((column) => !["Supply Type", "Errors", "Validation Status", "Error Type"].includes(column)),
        ...(columns.includes("Error Type") ? ["Error Type"] : []),
      ]
    : columns;
  const visibleRows = rows.filter((row) => {
    const rowStatus = title === "B2CS"
      ? (String(row["Error Type"] || "").trim() ? "Error" : "Valid")
      : row["Validation Status"];
    const matchesStatus = selectedStatus === "All" || rowStatus === selectedStatus;
    const matchesError = selectedErrorType === "All" || String(row["Error Type"] || "").includes(selectedErrorType);
    return matchesStatus && matchesError;
  });
  function reportData() {
    return [{ title, report: { ...report, rows: visibleRows, columns: displayColumns } }];
  }
  return <section className="report workbook-report">
    <div className="section-heading"><div><p className="eyebrow">Validation results</p><h2>{title}</h2></div><span className="row-count">{report.summary?.total ?? 0} rows</span></div>
    <Summary summary={report.summary} selectedStatus={selectedStatus} onSelect={(filter) => { setSelectedStatus(filter); setSelectedErrorType("All"); }} />
    {title === "B2B" && (report.error_breakdown?.["POS Error"] > 0 || posAccepted) && <button className="accept-pos" onClick={onAcceptPos} disabled={loading}>{loading ? "Applying POS..." : posAccepted ? "Undo POS acceptance" : "Accept POS for all errors"}</button>}
    {report.error_breakdown && <div className="breakdown"><button className={selectedErrorType === "All" ? "selected" : ""} onClick={() => setSelectedErrorType("All")}>All errors <strong>{report.summary?.errors ?? 0}</strong></button>{Object.entries(report.error_breakdown).filter(([label]) => label !== "Tax Error").map(([label, value]) => <button className={selectedErrorType === label ? "selected" : ""} key={label} onClick={() => setSelectedErrorType(label)}><span>{label}</span><strong>{value}</strong></button>)}</div>}
    {selectedStatus !== "All" && <p className="filter-note">Showing {visibleRows.length} {selectedStatus.toLowerCase()} row{visibleRows.length === 1 ? "" : "s"} in {title}.</p>}
    {report.missing_columns?.length > 0 && <p className="error">Missing required columns: {report.missing_columns.join(", ")}</p>}
    <div className="table-wrap"><table><thead><tr>{displayColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{visibleRows.map((row, index) => <tr key={`${title}-${index}`}>{displayColumns.map((column) => <td key={column}>{row[column] ?? "-"}</td>)}</tr>)}</tbody></table></div>
    <div className="report-downloads"><button onClick={() => downloadExcel(reportData(), `${title.toLowerCase()}_validation.xlsx`)}>Download Excel</button><button onClick={() => downloadPdf(reportData(), `${title.toLowerCase()}_validation.pdf`)}>Download PDF</button></div>
  </section>;
}

function App() {
  const [file, setFile] = useState(null);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [stateCode, setStateCode] = useState("36");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stateCodes, setStateCodes] = useState(DEFAULT_STATE_CODES);
  const [posAccepted, setPosAccepted] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/health`).then((response) => {
      if (!response.ok) throw new Error("API unavailable");
      setApiConnected(true);
    }).catch(() => setApiConnected(false));
    fetch(`${API_URL}/metadata`).then((response) => response.json()).then((metadata) => {
      setStateCodes({ ...DEFAULT_STATE_CODES, ...(metadata.state_codes || {}) });
    }).catch(() => {});
  }, []);

  async function revalidateForState(code) {
    if (!file || !result) return;
    setLoading(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("month", String(month));
    form.append("year", String(year));
    form.append("registered_state_code", code);
    try {
      const response = await fetch(`${API_URL}/validate/gstr1`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Validation failed");
      setResult(payload);
      setPosAccepted(false);
    } catch (requestError) {
      setError(requestError instanceof TypeError ? `Cannot reach the validation API at ${API_URL}. Start the backend on port 8000 and try again.` : requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function acceptAllPosErrors() {
    if (!file) return;
    setLoading(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("month", String(month));
    form.append("year", String(year));
    form.append("registered_state_code", stateCode);
    const nextAccepted = !posAccepted;
    form.append("accept_pos_all", String(nextAccepted));
    try {
      const response = await fetch(`${API_URL}/validate/gstr1`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Unable to accept POS errors");
      setResult(payload);
      setPosAccepted(nextAccepted);
    } catch (requestError) {
      setError(requestError instanceof TypeError ? `Cannot reach the validation API at ${API_URL}. Start the backend on port 8000 and try again.` : requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function validate(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose an Excel workbook first.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    const form = new FormData();
    form.append("file", file);
    form.append("month", String(month));
    form.append("year", String(year));
    form.append("registered_state_code", stateCode);
    try {
      const response = await fetch(`${API_URL}/validate/gstr1`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Validation failed");
      setResult(payload);
    } catch (requestError) {
      setError(requestError instanceof TypeError ? `Cannot reach the validation API at ${API_URL}. Start the backend on port 8000 and try again.` : requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function downloadAll(format) {
    const reports = [
      { title: "B2B", report: result?.b2b },
      { title: "B2CL", report: result?.b2cl },
      { title: "B2CS", report: result?.b2cs },
    ].filter(({ report }) => report);
    if (format === "excel") downloadExcel(reports, "gstr1_validation_all.xlsx");
    else downloadPdf(reports, "gstr1_validation_all.pdf");
  }

  return <main>
    <header><div><p className="eyebrow">Filing preparation workspace</p><h1>GSTR-1 <em>Validator</em></h1><p className="subtitle">Upload one workbook and validate its B2B and B2CL sheets together.</p></div><div className="api-status">{apiConnected ? "● API connected" : "● API unavailable"}</div></header>
    <section className="workbook-flow">
      <div className="section-heading"><div><p className="eyebrow">WORKBOOK / CHECK</p><h2>Upload your GSTR-1 Excel workbook</h2></div><span className="version">v1.0</span></div>
      <form onSubmit={validate} className="upload-panel">
        <label className="dropzone"><input type="file" accept=".xlsx,.xls" onChange={(event) => setFile(event.target.files[0])} /><span className="upload-mark">↑</span><strong>{file ? file.name : "Choose Excel file"}</strong><small>XLSX or XLS with B2B and B2CL sheets</small></label>
        <div className="fields"><label>Month<select value={month} onChange={(event) => setMonth(event.target.value)}>{Array.from({ length: 12 }, (_, index) => <option value={index + 1} key={index}>{new Date(2000, index).toLocaleString("en", { month: "long" })}</option>)}</select></label><label>Year<input type="number" value={year} onChange={(event) => setYear(event.target.value)} /></label><label>Registered state<select value={stateCode} onChange={(event) => { const code = event.target.value; setStateCode(code); setPosAccepted(false); revalidateForState(code); }}>{Object.entries(stateCodes).map(([name, code]) => <option value={code} key={code}>{code} · {name}</option>)}</select></label></div>
        <button className="primary" disabled={loading}>{loading ? "Validating..." : "Validate GSTR-1 →"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && <>
        <div className="workbook-results"><Report title="B2B" report={result.b2b} onAcceptPos={acceptAllPosErrors} loading={loading} posAccepted={posAccepted} /><Report title="B2CL" report={result.b2cl} /><Report title="B2CS" report={result.b2cs} /></div>
        <div className="all-downloads"><strong>Download all reports</strong><button onClick={() => downloadAll("excel")}>Excel workbook</button><button onClick={() => downloadAll("pdf")}>PDF report</button></div>
      </>}
    </section>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
