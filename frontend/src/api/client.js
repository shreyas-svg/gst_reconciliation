const rawApiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_BASE = rawApiUrl.replace(/\/+$/, "");

const TOKEN_KEY = "gst_auth_token";
const BIZ_KEY = "gst_active_biz_id";

export const authStorage = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },
  getActiveBusinessId() {
    return localStorage.getItem(BIZ_KEY);
  },
  setActiveBusinessId(id) {
    if (id) localStorage.setItem(BIZ_KEY, String(id));
    else localStorage.removeItem(BIZ_KEY);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(BIZ_KEY);
  },
};

async function request(endpoint, options = {}) {
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${API_BASE}${cleanEndpoint}`;
  const token = authStorage.getToken();
  const bizId = authStorage.getActiveBusinessId();

  const headers = {
    Accept: "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (bizId) {
    headers["X-Business-ID"] = String(bizId);
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (res.status === 401 && !cleanEndpoint.startsWith("/auth/login") && !cleanEndpoint.startsWith("/auth/register")) {
      authStorage.clear();
      window.dispatchEvent(new Event("auth:unauthorized"));
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (!res.ok) {
      let errorMsg = `Server error (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errorMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch (parseErr) {
        errorMsg = parseErr.message || errorMsg;
      }
      throw new Error(errorMsg);
    }

    return await res.json();
  } catch (err) {
    if (
      err.name === "TypeError" ||
      (err.message && (err.message.toLowerCase().includes("fetch") || err.message.toLowerCase().includes("network")))
    ) {
      throw new Error(
        `Unable to connect to the backend API server at ${API_BASE}. Please ensure the server is running and accessible.`,
        { cause: err }
      );
    }
    throw err;
  }
}

export const api = {
  baseUrl: API_BASE,

  // Auth Endpoints
  async login(email, password) {
    const data = await request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (data.access_token) {
      authStorage.setToken(data.access_token);
      if (data.businesses && data.businesses.length > 0) {
        authStorage.setActiveBusinessId(data.businesses[0].id);
      }
    }
    return data;
  },

  async register(payload) {
    const data = await request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (data.access_token) {
      authStorage.setToken(data.access_token);
      if (data.businesses && data.businesses.length > 0) {
        authStorage.setActiveBusinessId(data.businesses[0].id);
      }
    }
    return data;
  },

  async getMe() {
    return request("/auth/me");
  },

  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      authStorage.clear();
    }
  },

  async addBusiness(name, gstin) {
    return request("/auth/businesses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, gstin }),
    });
  },

  // Health
  async getHealth() {
    return request("/health");
  },

  // Reconciliation
  async getReconciliation(params = {}) {
    const query = new URLSearchParams();
    if (params.tax_period) query.set("tax_period", params.tax_period);
    if (params.purchase_source) query.set("purchase_source", params.purchase_source);
    const qs = query.toString();
    return request(`/reconcile${qs ? `?${qs}` : ""}`);
  },

  async getGstr3bSummary(taxPeriod) {
    const qs = taxPeriod ? `?tax_period=${encodeURIComponent(taxPeriod)}` : "";
    return request(`/gstr3b/summary${qs}`);
  },

  async getGstr3bCrossForm(taxPeriod) {
    const qs = taxPeriod ? `?tax_period=${encodeURIComponent(taxPeriod)}` : "";
    return request(`/gstr3b/cross-form${qs}`);
  },

  async getInvoices(params = {}) {
    const query = new URLSearchParams();
    if (params.source) query.set("source", params.source);
    if (params.gstin) query.set("gstin", params.gstin);
    if (params.search) query.set("search", params.search);
    if (params.limit) query.set("limit", params.limit);
    if (params.offset) query.set("offset", params.offset);
    const qs = query.toString();
    return request(`/invoices${qs ? `?${qs}` : ""}`);
  },

  async getInvoice(id) {
    return request(`/invoices/${id}`);
  },

  async uploadCsv(file, sourceType) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_type", sourceType);

    const token = authStorage.getToken();
    const bizId = authStorage.getActiveBusinessId();
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (bizId) headers["X-Business-ID"] = String(bizId);

    const url = `${API_BASE}/upload`;
    const res = await fetch(url, {
      method: "POST",
      body: formData,
      headers,
    });

    if (!res.ok) {
      let errMsg = "Upload failed";
      try {
        const data = await res.json();
        if (data.detail) errMsg = data.detail;
      } catch (parseErr) {
        errMsg = parseErr.message || errMsg;
      }
      throw new Error(errMsg);
    }

    return await res.json();
  },

  async getAnomalies(params = {}) {
    const query = new URLSearchParams();
    if (params.severity) query.set("severity", params.severity);
    if (params.type) query.set("type", params.type);
    if (params.search) query.set("search", params.search);
    if (params.purchase_source) query.set("purchase_source", params.purchase_source);
    if (params.include_ml !== undefined) query.set("include_ml", String(params.include_ml));
    const qs = query.toString();
    return request(`/anomalies${qs ? `?${qs}` : ""}`);
  },

  async getReportsSummary(params = {}) {
    const query = new URLSearchParams();
    if (params.purchase_source) query.set("purchase_source", params.purchase_source);
    if (params.tax_period) query.set("tax_period", params.tax_period);
    const qs = query.toString();
    return request(`/reports/summary${qs ? `?${qs}` : ""}`);
  },

  async downloadReport(reportType, purchaseSource = "gstr2a", taxPeriod = null) {
    const query = new URLSearchParams();
    query.set("report_type", reportType);
    query.set("purchase_source", purchaseSource);
    if (taxPeriod) query.set("tax_period", taxPeriod);

    const token = authStorage.getToken();
    const bizId = authStorage.getActiveBusinessId();

    const headers = {
      Accept: "text/csv, application/json, */*",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    if (bizId) {
      headers["X-Business-ID"] = String(bizId);
    }

    let response;
    try {
      response = await fetch(`${API_BASE}/reports/export?${query.toString()}`, {
        method: "GET",
        headers,
      });
    } catch (netErr) {
      throw new Error(
        `Network error: Unable to connect to backend at ${API_BASE}. Please ensure server is running.`,
        { cause: netErr }
      );
    }

    if (response.status === 401) {
      authStorage.clear();
      window.dispatchEvent(new Event("auth:unauthorized"));
      throw new Error("Your session has expired or authentication is missing. Please sign in again.");
    }

    if (!response.ok) {
      let errorMsg = `Server error (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson && errorJson.detail) {
          errorMsg = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        try {
          const text = await response.text();
          if (text) errorMsg = text;
        } catch {
          // ignore
        }
      }
      throw new Error(errorMsg);
    }

    // Extract filename from Content-Disposition header if available
    let filename = `gst_${reportType}_${purchaseSource}${taxPeriod ? `_${taxPeriod.replace('-', '_')}` : ""}.csv`;
    const disposition = response.headers.get("content-disposition");
    if (disposition) {
      const filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
      if (filenameMatch && filenameMatch[1]) {
        filename = decodeURIComponent(filenameMatch[1].trim());
      }
    }

    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => {
      window.URL.revokeObjectURL(objectUrl);
    }, 2000);

    return { success: true, filename, size: blob.size };
  },

  getExportUrl(reportType, purchaseSource = "gstr2a", taxPeriod = null) {
    const token = authStorage.getToken() || "";
    const bizId = authStorage.getActiveBusinessId() || "";
    let url = `${API_BASE}/reports/export?report_type=${encodeURIComponent(reportType)}&purchase_source=${encodeURIComponent(purchaseSource)}&token=${encodeURIComponent(token)}&biz_id=${encodeURIComponent(bizId)}`;
    if (taxPeriod) {
      url += `&tax_period=${encodeURIComponent(taxPeriod)}`;
    }
    return url;
  },

  // Import History & Undo Endpoints
  async getImportBatches(params = {}) {
    const searchParams = new URLSearchParams();
    if (params.source_type) searchParams.append("source_type", params.source_type);
    if (params.status) searchParams.append("status", params.status);
    if (params.limit !== undefined) searchParams.append("limit", params.limit);
    if (params.offset !== undefined) searchParams.append("offset", params.offset);

    const qs = searchParams.toString();
    const endpoint = `/imports${qs ? `?${qs}` : ""}`;
    return await request(endpoint);
  },

  async getImportBatchDetails(batchId) {
    return await request(`/imports/${encodeURIComponent(batchId)}`);
  },

  async previewUndoImport(batchId) {
    return await request(`/imports/${encodeURIComponent(batchId)}/preview-undo`);
  },

  async undoImportBatch(batchId, { confirmed = false, notes = "" } = {}) {
    return await request(`/imports/${encodeURIComponent(batchId)}/undo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed, notes }),
    });
  },
};

