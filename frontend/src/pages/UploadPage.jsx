import { useState } from "react";
import { UploadCloud, AlertCircle, FileCheck, FileText, ArrowRight, ShieldCheck, History } from "lucide-react";
import { api } from "../api/client";

export function UploadPage({ onUploadSuccess, onNavigate }) {
  const [sourceType, setSourceType] = useState("sales_register");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);

  const targets = [
    {
      id: "sales_register",
      title: "Sales Register",
      code: "Outward Supplies",
      desc: "Internal sales invoices recorded in company accounting books",
    },
    {
      id: "gstr1",
      title: "Form GSTR-1",
      code: "Portal Filed",
      desc: "Outward supplies reported on the GST Common Portal",
    },
    {
      id: "purchase_register",
      title: "Purchase Register",
      code: "Inward Supplies",
      desc: "Vendor bills and expense invoices recorded internally",
    },
    {
      id: "gstr2a",
      title: "Form GSTR-2A",
      code: "Dynamic Filing",
      desc: "Imported counterparty supplier filings reflecting in portal ITC register (Local demo statement — not a live API sync)",
    },
    {
      id: "gstr2b",
      title: "Form GSTR-2B",
      code: "Static Auto-Drafted ITC",
      desc: "Monthly static auto-drafted ITC statement for return filing under Rule 36(4) (Local demo statement)",
    },
    {
      id: "gstr3b",
      title: "Form GSTR-3B",
      code: "Monthly Summary",
      desc: "Self-assessed monthly summary return of tax liability & ITC (Treated as period-level summary, not invoice-level)",
    },
  ];

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setResult(null);
      setError("");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith(".csv")) {
        setSelectedFile(file);
        setResult(null);
        setError("");
      } else {
        setError("Only standard comma-separated CSV files (.csv) are supported.");
      }
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError("Please select a CSV file to upload.");
      return;
    }

    setUploading(true);
    setError("");
    setResult(null);

    try {
      const res = await api.uploadCsv(selectedFile, sourceType);
      setResult(res);
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      setError(err.message || "Failed to upload and validate CSV file.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: 960, margin: "0 auto" }}>
      {/* 1. Page Header */}
      <div className="section-header" style={{ marginBottom: 20 }}>
        <div>
          <h2 className="section-title">CSV Ledger Ingestion & Validation</h2>
          <p className="section-subtitle">
            Upload internal registers, supplier filing statements, and monthly summary returns to synchronize your database
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {onNavigate && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onNavigate("history")}
              style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
            >
              <History size={14} color="#ea580c" />
              <span>Import History</span>
            </button>
          )}
          <div className="section-badge">
            <ShieldCheck size={13} />
            <span>Active Tenant Storage (Local Mode)</span>
          </div>
        </div>
      </div>

      {/* 2. Main Upload Card */}
      <div className="institutional-card">
        <form onSubmit={handleUpload}>
          {/* Target Register Cards Selector */}
          <div style={{ marginBottom: 24 }}>
            <label className="form-label-heading">
              1. Select Data Target / Register Type
            </label>
            <div className="target-registers-grid">
              {targets.map((tgt) => (
                <div
                  key={tgt.id}
                  id={`target-card-${tgt.id}`}
                  className={`target-register-card ${sourceType === tgt.id ? "active" : ""}`}
                  onClick={() => {
                    setSourceType(tgt.id);
                    setResult(null);
                    setError("");
                  }}
                >
                  <div className="target-card-header">
                    <span className="target-code">{tgt.code}</span>
                    <span className="target-radio-dot"></span>
                  </div>
                  <h4 className="target-title">{tgt.title}</h4>
                  <p className="target-desc">{tgt.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Drag & Drop File Zone */}
          <div style={{ marginBottom: 20 }}>
            <label className="form-label-heading">
              2. Select or Drag & Drop File
            </label>
            <div
              className={`upload-dropzone ${isDragOver ? "drag-over" : ""} ${selectedFile ? "has-file" : ""}`}
              onClick={() => document.getElementById("csv-file-input").click()}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
            >
              <input
                id="csv-file-input"
                type="file"
                accept=".csv"
                style={{ display: "none" }}
                onChange={handleFileChange}
              />

              <div className="dropzone-icon-wrap">
                <UploadCloud size={32} color="#ea580c" />
              </div>

              {selectedFile ? (
                <div className="dropzone-file-info">
                  <div className="dropzone-filename">
                    <FileText size={16} />
                    <span>{selectedFile.name}</span>
                  </div>
                  <div className="dropzone-filesize">
                    {(selectedFile.size / 1024).toFixed(1)} KB • Ready for validation
                  </div>
                  <div className="dropzone-click-hint">Click or drag a new file to replace</div>
                </div>
              ) : (
                <div className="dropzone-placeholder">
                  <h4>Click to browse or drag and drop your CSV file</h4>
                  {sourceType === "gstr3b" ? (
                    <p>
                      <strong>GSTR-3B Monthly Summary:</strong> Required columns: <code>tax_period</code> (YYYY-MM), <code>output_tax</code>, <code>eligible_itc</code>. Optional: <code>itc_reversed</code>, <code>net_itc</code>. Treated as period summary, not invoice records.
                    </p>
                  ) : (
                    <p>
                      Accepts UTF-8 encoded CSV files. Standard columns: <code>invoice_no</code>, <code>invoice_date</code>, <code>customer_gstin / supplier_gstin</code>, <code>taxable_value</code>, <code>gst_amount</code> (Safe aliases supported: <code>invoice_number</code>, <code>date</code>, <code>counterparty_gstin</code>, <code>taxable_amount</code>, <code>tax_amount</code>).
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {error && (
            <div className="upload-error-banner">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="upload-actions-bar">
            <button
              id="btn-upload-submit"
              type="submit"
              className="btn btn-primary"
              disabled={!selectedFile || uploading}
              style={{ minWidth: 180, justifyContent: "center" }}
            >
              {uploading ? (
                <span>Validating & Ingesting...</span>
              ) : (
                <>
                  <span>Validate & Upload to DB</span>
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </form>

        {/* Validation & Ingestion Results */}
        {result && (
          <div className="upload-results-panel">
            <div className="results-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <FileCheck size={20} color="#059669" />
                <h4>Validation & Ingestion Report</h4>
              </div>
              {result.batch_id && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Batch:</span>
                  <code style={{ fontSize: 12, backgroundColor: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>
                    {result.batch_id}
                  </code>
                  {onNavigate && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => onNavigate("history")}
                      style={{ fontSize: 11, padding: "3px 8px", display: "flex", alignItems: "center", gap: 4 }}
                    >
                      <History size={12} />
                      View in History
                    </button>
                  )}
                </div>
              )}
            </div>

            {result.message && (
              <div
                style={{
                  padding: "8px 12px",
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: 6,
                  color: "#166534",
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 14,
                }}
              >
                {result.message}
              </div>
            )}

            <div className="results-grid">
              <div className="result-kpi-box">
                <div className="res-label">Total Records Evaluated</div>
                <div className="res-value">{result.total_records}</div>
              </div>
              <div className="result-kpi-box box-success">
                <div className="res-label">Imported to Database</div>
                <div className="res-value text-green">{result.imported}</div>
              </div>
              <div className="result-kpi-box box-warning">
                <div className="res-label">Duplicate Records Skipped</div>
                <div className="res-value text-amber">{result.duplicates}</div>
              </div>
              <div className="result-kpi-box box-error">
                <div className="res-label">Rejected Records (Rows)</div>
                <div className="res-value text-red">{result.rejected ?? result.invalid_records}</div>
              </div>
              <div className="result-kpi-box">
                <div className="res-label">Validation Findings</div>
                <div className="res-value" style={{ color: (result.validation_findings ?? 0) > 0 ? "#b91c1c" : "#059669" }}>
                  {result.validation_findings ?? (result.errors ? result.errors.length : 0)}
                </div>
              </div>
            </div>

            {result.errors && result.errors.length > 0 && (
              <div className="results-errors-list">
                <h5>
                  Validation Discrepancies Flagged ({result.validation_findings ?? result.errors.length} findings across {result.rejected ?? result.invalid_records} rejected row{(result.rejected ?? result.invalid_records) === 1 ? "" : "s"}):
                </h5>
                <div className="errors-scroll-container">
                  {result.errors.map((err, i) => (
                    <div key={i} className="error-item">
                      • {err}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

