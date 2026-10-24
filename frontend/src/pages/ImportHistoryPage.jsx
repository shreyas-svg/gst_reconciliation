import { useState, useEffect, useCallback } from "react";
import {
  History,
  RotateCcw,
  Eye,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  RefreshCw,
  Search,
  Filter,
  X,
  ShieldAlert,
  ShieldCheck,
  Info,
  Layers,
} from "lucide-react";
import { api } from "../api/client";

const SOURCE_LABELS = {
  sales_register: "Sales Register",
  gstr1: "Form GSTR-1",
  purchase_register: "Purchase Register",
  gstr2a: "Form GSTR-2A",
  gstr2b: "Form GSTR-2B",
  gstr3b: "Form GSTR-3B Summary",
};

export function ImportHistoryPage({ onUndoSuccess }) {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionMessage, setActionMessage] = useState(null);

  // Inspection Modal State
  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [batchDetails, setBatchDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");

  // Undo Confirmation Modal State
  const [undoTarget, setUndoTarget] = useState(null);
  const [undoPreview, setUndoPreview] = useState(null);
  const [undoPreviewLoading, setUndoPreviewLoading] = useState(false);
  const [undoNotes, setUndoNotes] = useState("");
  const [reconciledAcknowledged, setReconciledAcknowledged] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [undoError, setUndoError] = useState("");

  const loadBatches = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError("");
    try {
      const params = {};
      if (sourceFilter !== "all") params.source_type = sourceFilter;
      if (statusFilter !== "all") params.status = statusFilter;
      const res = await api.getImportBatches(params);
      setBatches(res.items || []);
    } catch (err) {
      setError(err.message || "Failed to load import batches.");
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [sourceFilter, statusFilter]);

  useEffect(() => {
    let ignore = false;
    const params = {};
    if (sourceFilter !== "all") params.source_type = sourceFilter;
    if (statusFilter !== "all") params.status = statusFilter;

    api.getImportBatches(params)
      .then((res) => {
        if (!ignore) {
          setBatches(res.items || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message || "Failed to load import batches.");
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [sourceFilter, statusFilter]);

  // Load batch details when inspection modal opens
  const handleOpenDetails = async (batchId) => {
    setSelectedBatchId(batchId);
    setDetailsLoading(true);
    setDetailsError("");
    setBatchDetails(null);
    try {
      const data = await api.getImportBatchDetails(batchId);
      setBatchDetails(data);
    } catch (err) {
      setDetailsError(err.message || "Failed to load batch details.");
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleCloseDetails = () => {
    setSelectedBatchId(null);
    setBatchDetails(null);
    setDetailsError("");
  };

  // Open undo confirmation dialog
  const handleInitiateUndo = async (batch) => {
    setUndoTarget(batch);
    setUndoPreview(null);
    setUndoPreviewLoading(true);
    setUndoError("");
    setUndoNotes("");
    setReconciledAcknowledged(false);

    try {
      const preview = await api.previewUndoImport(batch.batch_id);
      setUndoPreview(preview);
    } catch (err) {
      setUndoError(err.message || "Failed to preview undo operation.");
    } finally {
      setUndoPreviewLoading(false);
    }
  };

  const handleCloseUndoModal = () => {
    setUndoTarget(null);
    setUndoPreview(null);
    setUndoError("");
    setUndoing(false);
  };

  // Execute safe undo
  const handleConfirmUndo = async () => {
    if (!undoTarget) return;

    if (undoPreview?.counterpart_matched_records > 0 && !reconciledAcknowledged) {
      setUndoError("Please acknowledge that active reconciliation matches will be removed.");
      return;
    }

    setUndoing(true);
    setUndoError("");

    try {
      const res = await api.undoImportBatch(undoTarget.batch_id, {
        confirmed: true,
        notes: undoNotes,
      });

      setActionMessage({
        type: "success",
        text: res.message || `Import batch ${undoTarget.batch_id} undone successfully.`,
      });

      handleCloseUndoModal();
      handleCloseDetails();
      await loadBatches();

      if (onUndoSuccess) {
        onUndoSuccess();
      }
    } catch (err) {
      setUndoError(err.message || "Failed to undo import batch.");
    } finally {
      setUndoing(false);
    }
  };

  const filteredBatches = batches.filter((b) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      b.batch_id.toLowerCase().includes(q) ||
      b.filename.toLowerCase().includes(q) ||
      (b.source_type && b.source_type.toLowerCase().includes(q))
    );
  });

  const totalImports = batches.length;
  const activeBatches = batches.filter((b) => b.status === "COMPLETED").length;
  const undoneBatches = batches.filter((b) => b.status === "UNDONE").length;
  const totalImportedRecords = batches
    .filter((b) => b.status === "COMPLETED")
    .reduce((sum, b) => sum + (b.active_records_count || 0), 0);
  const totalDuplicatesSkipped = batches.reduce((sum, b) => sum + (b.duplicate_rows || 0), 0);

  const formatCurrency = (val) => {
    if (val === null || val === undefined) return "—";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(val);
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1200, margin: "0 auto", paddingBottom: 40 }}>
      {/* 1. Page Header */}
      <div className="section-header" style={{ marginBottom: 20 }}>
        <div>
          <h2 className="page-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <History size={24} color="#ea580c" />
            CSV Import History & Safe Undo
          </h2>
          <p className="card-subtitle">
            Immutable audit record of all CSV uploads with granular rollback and business-level isolation.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={loadBatches}
          disabled={loading}
          style={{ display: "flex", alignItems: "center", gap: 6 }}
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div
          className="animate-fade-in"
          style={{
            marginBottom: 20,
            padding: "12px 16px",
            borderRadius: "var(--radius-sm, 10px)",
            backgroundColor: actionMessage.type === "success" ? "#ecfdf5" : "#fef2f2",
            border: `1px solid ${actionMessage.type === "success" ? "#a7f3d0" : "#fecaca"}`,
            color: actionMessage.type === "success" ? "#065f46" : "#991b1b",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <CheckCircle2 size={16} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>{actionMessage.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "inherit" }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 2. Overview Metrics Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Total Uploads</span>
            <div className="kpi-icon" style={{ backgroundColor: "#eff6ff", color: "#2563eb" }}>
              <Layers size={18} />
            </div>
          </div>
          <div className="kpi-value">{totalImports}</div>
          <div className="kpi-subtitle">{activeBatches} active • {undoneBatches} undone</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Active Database Records</span>
            <div className="kpi-icon" style={{ backgroundColor: "#ecfdf5", color: "#059669" }}>
              <CheckCircle2 size={18} />
            </div>
          </div>
          <div className="kpi-value">{totalImportedRecords.toLocaleString("en-IN")}</div>
          <div className="kpi-subtitle">Associated across active batches</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Duplicates Protected</span>
            <div className="kpi-icon" style={{ backgroundColor: "#fffbeb", color: "#d97706" }}>
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="kpi-value">{totalDuplicatesSkipped.toLocaleString("en-IN")}</div>
          <div className="kpi-subtitle">Safely preserved pre-existing records</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Reverted Imports</span>
            <div className="kpi-icon" style={{ backgroundColor: "#f3f4f6", color: "#6b7280" }}>
              <RotateCcw size={18} />
            </div>
          </div>
          <div className="kpi-value">{undoneBatches}</div>
          <div className="kpi-subtitle">Cleanly undone with zero side effects</div>
        </div>
      </div>

      {/* 3. Filters and Search Bar */}
      <div
        className="card"
        style={{
          padding: "16px 20px",
          marginBottom: 20,
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Filter size={14} color="var(--text-muted, #64748b)" />
            <span style={{ fontSize: 13, fontWeight: 600 }}>Source:</span>
            <select
              className="form-control"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              style={{ fontSize: 13, padding: "6px 10px", width: "auto" }}
            >
              <option value="all">All Sources</option>
              <option value="sales_register">Sales Register</option>
              <option value="gstr1">Form GSTR-1</option>
              <option value="purchase_register">Purchase Register</option>
              <option value="gstr2a">Form GSTR-2A</option>
              <option value="gstr2b">Form GSTR-2B</option>
              <option value="gstr3b">Form GSTR-3B</option>
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Status:</span>
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ fontSize: 13, padding: "6px 10px", width: "auto" }}
            >
              <option value="all">All Statuses</option>
              <option value="COMPLETED">Active (Completed)</option>
              <option value="UNDONE">Undone (Reverted)</option>
            </select>
          </div>
        </div>

        <div style={{ position: "relative", minWidth: 260 }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: 11, color: "var(--text-muted)" }} />
          <input
            type="text"
            className="form-control"
            placeholder="Search by batch ID, filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 30, fontSize: 13 }}
          />
        </div>
      </div>

      {/* 4. Import Batches Table */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 12px" }} />
            <p>Loading import batches history...</p>
          </div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: "center", color: "#dc2626" }}>
            <AlertTriangle size={24} style={{ margin: "0 auto 12px" }} />
            <p>{error}</p>
          </div>
        ) : filteredBatches.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)" }}>
            <FileSpreadsheet size={36} color="#94a3b8" style={{ margin: "0 auto 12px" }} />
            <h4 style={{ fontSize: 15, fontWeight: 700, color: "var(--navy-950)", marginBottom: 4 }}>
              No Import Batches Found
            </h4>
            <p style={{ fontSize: 13 }}>
              {batches.length === 0
                ? "No CSV files have been imported yet. Head to CSV Ingestion to upload your data."
                : "No import batches match your current filter criteria."}
            </p>
          </div>
        ) : (
          <div className="table-container" style={{ margin: 0 }}>
            <table className="reconcile-table" style={{ width: "100%", fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={{ paddingLeft: 20 }}>Upload Date</th>
                  <th>Batch ID</th>
                  <th>File & Source</th>
                  <th style={{ textAlign: "center" }}>Total Rows</th>
                  <th style={{ textAlign: "center" }}>Imported</th>
                  <th style={{ textAlign: "center" }}>Duplicates</th>
                  <th style={{ textAlign: "center" }}>Rejected</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "right", paddingRight: 20 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredBatches.map((batch) => {
                  const isUndone = batch.status === "UNDONE";
                  const dateStr = batch.created_at
                    ? new Date(batch.created_at).toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—";

                  return (
                    <tr
                      key={batch.batch_id}
                      style={{
                        backgroundColor: isUndone ? "rgba(248, 250, 252, 0.7)" : undefined,
                        opacity: isUndone ? 0.85 : 1,
                      }}
                    >
                      <td style={{ paddingLeft: 20, whiteSpace: "nowrap" }}>
                        <div style={{ fontWeight: 600 }}>{dateStr}</div>
                        {isUndone && batch.undone_at && (
                          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            Undone: {new Date(batch.undone_at).toLocaleDateString("en-IN")}
                          </div>
                        )}
                      </td>
                      <td>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontSize: 12,
                            padding: "3px 6px",
                            backgroundColor: "#f1f5f9",
                            borderRadius: 4,
                            border: "1px solid #e2e8f0",
                          }}
                        >
                          {batch.batch_id}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: "var(--navy-950)" }}>{batch.filename}</div>
                        <span
                          style={{
                            display: "inline-block",
                            fontSize: 11,
                            padding: "1px 6px",
                            borderRadius: 4,
                            backgroundColor: "#fff7ed",
                            color: "#c2410c",
                            fontWeight: 500,
                            marginTop: 2,
                          }}
                        >
                          {SOURCE_LABELS[batch.source_type] || batch.source_type}
                        </span>
                      </td>
                      <td style={{ textAlign: "center", fontWeight: 500 }}>{batch.total_rows}</td>
                      <td style={{ textAlign: "center" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 700,
                            backgroundColor: isUndone ? "#f3f4f6" : "#ecfdf5",
                            color: isUndone ? "#6b7280" : "#059669",
                            textDecoration: isUndone ? "line-through" : "none",
                          }}
                        >
                          {batch.imported_rows}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 600,
                            backgroundColor: batch.duplicate_rows > 0 ? "#fffbeb" : "transparent",
                            color: batch.duplicate_rows > 0 ? "#b45309" : "var(--text-muted)",
                          }}
                        >
                          {batch.duplicate_rows}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 600,
                            backgroundColor: batch.rejected_rows > 0 ? "#fef2f2" : "transparent",
                            color: batch.rejected_rows > 0 ? "#dc2626" : "var(--text-muted)",
                          }}
                        >
                          {batch.rejected_rows}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {isUndone ? (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 12,
                              backgroundColor: "#f1f5f9",
                              color: "#64748b",
                            }}
                          >
                            <RotateCcw size={11} /> UNDONE
                          </span>
                        ) : (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 12,
                              backgroundColor: "#ecfdf5",
                              color: "#059669",
                            }}
                          >
                            <CheckCircle2 size={11} /> ACTIVE
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right", paddingRight: 20 }}>
                        <div style={{ display: "inline-flex", gap: 8 }}>
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => handleOpenDetails(batch.batch_id)}
                            title="View import details and record inspection"
                            style={{ padding: "4px 8px", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}
                          >
                            <Eye size={13} />
                            Details
                          </button>

                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => handleInitiateUndo(batch)}
                            disabled={!batch.can_undo}
                            title={batch.undo_block_reason || "Safely rollback this import batch"}
                            style={{
                              padding: "4px 8px",
                              fontSize: 12,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              color: batch.can_undo ? "#b91c1c" : "var(--text-muted)",
                              borderColor: batch.can_undo ? "#fecaca" : undefined,
                              backgroundColor: batch.can_undo ? "#fff5f5" : undefined,
                              cursor: batch.can_undo ? "pointer" : "not-allowed",
                            }}
                          >
                            <RotateCcw size={13} />
                            Undo
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Batch Details Modal */}
      {selectedBatchId && (
        <div className="modal-overlay" onClick={handleCloseDetails}>
          <div
            className="modal-content animate-fade-in"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 840, width: "95%" }}
          >
            <div className="modal-header">
              <div>
                <h3 className="modal-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <FileSpreadsheet size={18} color="#ea580c" />
                  Import Batch Breakdown
                </h3>
                <p className="card-subtitle" style={{ fontFamily: "monospace", fontSize: 12, marginTop: 2 }}>
                  {selectedBatchId}
                </p>
              </div>
              <button type="button" className="topbar-btn" onClick={handleCloseDetails}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              {detailsLoading ? (
                <div style={{ padding: 40, textAlign: "center" }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 8px" }} />
                  <p>Loading batch details...</p>
                </div>
              ) : detailsError ? (
                <div style={{ padding: 24, color: "#dc2626", textAlign: "center" }}>
                  <AlertTriangle size={24} style={{ margin: "0 auto 8px" }} />
                  <p>{detailsError}</p>
                </div>
              ) : batchDetails ? (
                <>
                  {/* Status Banner */}
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: 8,
                      marginBottom: 16,
                      backgroundColor: batchDetails.status === "UNDONE" ? "#f8fafc" : "#f0fdf4",
                      border: `1px solid ${batchDetails.status === "UNDONE" ? "#e2e8f0" : "#bbf7d0"}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {batchDetails.status === "UNDONE" ? (
                        <RotateCcw size={16} color="#64748b" />
                      ) : (
                        <CheckCircle2 size={16} color="#16a34a" />
                      )}
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 13 }}>
                          Status: {batchDetails.status === "UNDONE" ? "REVERTED / UNDONE" : "ACTIVE & COMPLETED"}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          {batchDetails.status === "UNDONE"
                            ? `Undone on ${new Date(batchDetails.undone_at).toLocaleString("en-IN")}`
                            : `Imported on ${new Date(batchDetails.created_at).toLocaleString("en-IN")}`}
                        </div>
                      </div>
                    </div>

                    {batchDetails.can_undo && (
                      <button
                        type="button"
                        className="btn-danger"
                        style={{ fontSize: 12, padding: "5px 12px" }}
                        onClick={() => {
                          handleCloseDetails();
                          handleInitiateUndo(batchDetails);
                        }}
                      >
                        <RotateCcw size={13} style={{ marginRight: 4 }} />
                        Undo This Import
                      </button>
                    )}
                  </div>

                  {/* Metadata Grid */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: 12,
                      marginBottom: 20,
                    }}
                  >
                    <div
                      style={{
                        padding: 12,
                        backgroundColor: "var(--slate-50, #f8fafc)",
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Source Type</div>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>
                        {SOURCE_LABELS[batchDetails.source_type] || batchDetails.source_type}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 12,
                        backgroundColor: "var(--slate-50, #f8fafc)",
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Original Filename</div>
                      <div style={{ fontWeight: 700, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {batchDetails.filename}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 12,
                        backgroundColor: "var(--slate-50, #f8fafc)",
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Active DB Records</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: "#059669" }}>
                        {batchDetails.active_records_count}
                      </div>
                    </div>

                    <div
                      style={{
                        padding: 12,
                        backgroundColor: "var(--slate-50, #f8fafc)",
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Duplicates Skipped</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: "#d97706" }}>
                        {batchDetails.duplicate_rows}
                      </div>
                    </div>
                  </div>

                  {/* Safety Checks Notice */}
                  {batchDetails.counterpart_matched_records > 0 && (
                    <div
                      style={{
                        padding: "10px 14px",
                        backgroundColor: "#fffbeb",
                        border: "1px solid #fde68a",
                        borderRadius: 8,
                        color: "#92400e",
                        fontSize: 12,
                        marginBottom: 16,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Info size={16} />
                      <span>
                        <strong>{batchDetails.counterpart_matched_records} record(s)</strong> in this batch match
                        counterpart records in active reconciliation.
                      </span>
                    </div>
                  )}

                  {/* Records Preview Table */}
                  <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8, color: "var(--navy-950)" }}>
                    Records Ingested by This Batch{" "}
                    <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-muted)" }}>
                      (Previewing first {batchDetails.preview_records?.length || 0})
                    </span>
                  </h4>

                  {batchDetails.preview_records && batchDetails.preview_records.length > 0 ? (
                    <div className="table-container" style={{ maxHeight: 220, overflowY: "auto", marginBottom: 20 }}>
                      <table className="reconcile-table" style={{ width: "100%", fontSize: 12 }}>
                        <thead>
                          <tr>
                            {batchDetails.source_type === "gstr3b" ? (
                              <>
                                <th>Tax Period</th>
                                <th>Output Tax</th>
                                <th>Eligible ITC</th>
                                <th>ITC Reversed</th>
                                <th>Net ITC</th>
                              </>
                            ) : (
                              <>
                                <th>Invoice No</th>
                                <th>Date</th>
                                <th>Counterparty GSTIN</th>
                                <th>Taxable Value</th>
                                <th>GST Amount</th>
                              </>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {batchDetails.preview_records.map((r, i) => (
                            <tr key={r.id || i}>
                              {batchDetails.source_type === "gstr3b" ? (
                                <>
                                  <td style={{ fontWeight: 600 }}>{r.tax_period}</td>
                                  <td>{formatCurrency(r.output_tax)}</td>
                                  <td>{formatCurrency(r.eligible_itc)}</td>
                                  <td>{formatCurrency(r.itc_reversed)}</td>
                                  <td>{formatCurrency(r.net_itc)}</td>
                                </>
                              ) : (
                                <>
                                  <td style={{ fontWeight: 600 }}>{r.invoice_no}</td>
                                  <td>{r.invoice_date || "—"}</td>
                                  <td style={{ fontFamily: "monospace" }}>{r.gstin || "—"}</td>
                                  <td>{formatCurrency(r.taxable_value)}</td>
                                  <td>{formatCurrency(r.gst_amount)}</td>
                                </>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: 16, backgroundColor: "#f8fafc", borderRadius: 8, color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>
                      No active records currently in database for this batch.
                    </div>
                  )}

                  {/* Audit Trail Timeline */}
                  {batchDetails.audit_logs && batchDetails.audit_logs.length > 0 && (
                    <div>
                      <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8, color: "var(--navy-950)" }}>
                        Audit Log
                      </h4>
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {batchDetails.audit_logs.map((log) => (
                          <div
                            key={log.id}
                            style={{
                              padding: "8px 12px",
                              backgroundColor: "#f8fafc",
                              border: "1px solid #e2e8f0",
                              borderRadius: 6,
                              fontSize: 12,
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                              <strong style={{ color: log.action === "UNDO_IMPORT" ? "#dc2626" : "#2563eb" }}>
                                {log.action}
                              </strong>
                              <span style={{ color: "var(--text-muted)", fontSize: 11 }}>
                                {log.created_at ? new Date(log.created_at).toLocaleString("en-IN") : "—"}
                              </span>
                            </div>
                            <div style={{ color: "#334155" }}>{log.details}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* 6. Safe Undo Confirmation Modal */}
      {undoTarget && (
        <div className="modal-overlay" onClick={handleCloseUndoModal}>
          <div
            className="modal-content animate-fade-in"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 560, width: "95%" }}
          >
            <div className="modal-header" style={{ borderBottomColor: "#fee2e2" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    backgroundColor: "#fee2e2",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#dc2626",
                  }}
                >
                  <ShieldAlert size={18} />
                </div>
                <div>
                  <h3 className="modal-title" style={{ color: "#991b1b" }}>
                    Confirm Safe Undo Import
                  </h3>
                  <p className="card-subtitle">Permanent rollback of records from this upload batch</p>
                </div>
              </div>
              <button type="button" className="topbar-btn" onClick={handleCloseUndoModal}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              {undoPreviewLoading ? (
                <div style={{ padding: 30, textAlign: "center" }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 8px" }} />
                  <p>Analyzing import dependencies and safety checks...</p>
                </div>
              ) : (
                <>
                  {undoError && (
                    <div
                      style={{
                        padding: 12,
                        backgroundColor: "#fef2f2",
                        border: "1px solid #fecaca",
                        borderRadius: 8,
                        color: "#991b1b",
                        fontSize: 13,
                        marginBottom: 16,
                      }}
                    >
                      {undoError}
                    </div>
                  )}

                  {/* Summary Box */}
                  <div
                    style={{
                      padding: 14,
                      backgroundColor: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 10,
                      marginBottom: 16,
                      fontSize: 13,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ color: "var(--text-muted)" }}>Target File:</span>
                      <strong>{undoTarget.filename}</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ color: "var(--text-muted)" }}>Source Type:</span>
                      <span>{SOURCE_LABELS[undoTarget.source_type] || undoTarget.source_type}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ color: "var(--text-muted)" }}>Batch ID:</span>
                      <code style={{ fontSize: 12 }}>{undoTarget.batch_id}</code>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        paddingTop: 8,
                        borderTop: "1px solid #e2e8f0",
                        color: "#dc2626",
                        fontWeight: 700,
                      }}
                    >
                      <span>Records to be Deleted:</span>
                      <span>{undoPreview?.records_to_delete ?? undoTarget.imported_rows} records</span>
                    </div>
                  </div>

                  {/* Safety Guarantees */}
                  <div
                    style={{
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: 8,
                      padding: 12,
                      marginBottom: 16,
                      fontSize: 12,
                      color: "#166534",
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                      <ShieldCheck size={14} /> Guaranteed Safety Boundaries:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.5 }}>
                      <li>Pre-existing records and duplicate rows will remain completely intact.</li>
                      <li>Records from other businesses and other upload batches will not be touched.</li>
                      <li>CSV files in the data directory are preserved and never deleted.</li>
                    </ul>
                  </div>

                  {/* Active Reconciled Warning */}
                  {undoPreview?.counterpart_matched_records > 0 && (
                    <div
                      style={{
                        backgroundColor: "#fffbeb",
                        border: "1px solid #fde68a",
                        borderRadius: 8,
                        padding: 12,
                        marginBottom: 16,
                        color: "#92400e",
                        fontSize: 12,
                      }}
                    >
                      <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                        <AlertTriangle size={14} /> Reconciliation Warning:
                      </div>
                      <p style={{ margin: "0 0 8px 0" }}>
                        <strong>{undoPreview.counterpart_matched_records} record(s)</strong> in this batch currently
                        match counterparty filings. Reverting this batch will update your dashboard and reports.
                      </p>
                      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontWeight: 600 }}>
                        <input
                          type="checkbox"
                          checked={reconciledAcknowledged}
                          onChange={(e) => setReconciledAcknowledged(e.target.checked)}
                        />
                        I confirm and acknowledge removal of these reconciled records
                      </label>
                    </div>
                  )}

                  {/* Optional Audit Reason */}
                  <div style={{ marginBottom: 20 }}>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                      Audit Reason / Note (Optional):
                    </label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g., Uploaded wrong accounting period or corrupted export"
                      value={undoNotes}
                      onChange={(e) => setUndoNotes(e.target.value)}
                      style={{ fontSize: 13 }}
                    />
                  </div>

                  {/* Action Buttons */}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleCloseUndoModal}
                      disabled={undoing}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={handleConfirmUndo}
                      disabled={
                        undoing ||
                        (undoPreview?.counterpart_matched_records > 0 && !reconciledAcknowledged) ||
                        undoPreview?.can_undo === false
                      }
                      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                    >
                      <RotateCcw size={14} className={undoing ? "animate-spin" : ""} />
                      {undoing ? "Undoing Import..." : "Yes, Undo Import"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
