import axios from "axios";
import { useAuthStore } from "../store/authStore";
import { API_BASE_URL } from "../config";

const BASE = API_BASE_URL;
const API_ROOT = BASE.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");

export const api = axios.create({
  baseURL: BASE,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
  timeout: 15_000,
});

let _refreshing: Promise<void> | null = null;

// Improved error handler with better error messages
function extractErrorDetail(error: any): { message: string; requestId?: string; retryAfter?: number } {
  const response = error.response;
  
  if (!response) {
    return { message: "Network error. Please check your connection and try again." };
  }
  
  const data = response.data;
  const status = response.status;
  const headers = response.headers;
  
  // Extract request ID from response for support
  const requestId = data?.request_id || headers["x-request-id"];
  
  // Handle rate limiting
  if (status === 429) {
    const retryAfter = parseInt(headers["retry-after"] || "60", 10);
    return {
      message: `Too many requests. Please wait ${retryAfter} seconds before retrying.`,
      requestId,
      retryAfter,
    };
  }
  
  // Handle validation errors
  if (status === 422) {
    const errors = data?.errors || [];
    const errorMessages = errors
      .map((e: any) => `${e.field}: ${e.message}`)
      .join("; ");
    return {
      message: `Validation error: ${errorMessages || "Please check your input"}`,
      requestId,
    };
  }
  
  // Handle server errors
  if (status >= 500) {
    return {
      message: data?.detail || "Server error. Please try again later or contact support.",
      requestId,
    };
  }
  
  // Default error
  return {
    message: data?.detail || `Error: ${status} ${response.statusText}`,
    requestId,
  };
}

// Silent cookie-based session refresh.
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;

    // Only attempt refresh on 401, and not on auth endpoints themselves
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      original._retry = true;

      // Deduplicate concurrent refresh attempts
      if (!_refreshing) {
        _refreshing = api
          .post("/auth/refresh")
          .then(() => undefined)
          .catch(() => {
            useAuthStore.getState().logout();
            window.location.href = "/login";
            throw new Error("Session expired");
          })
          .finally(() => {
            _refreshing = null;
          });
      }

      try {
        await _refreshing;
        return api(original);
      } catch {
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// Export error extraction for UI components
export { extractErrorDetail };

// ── API modules ───────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }).then((r) => r.data),
  signup: (email: string, password: string, full_name: string, business_name?: string) =>
    api.post("/auth/signup", { email, password, full_name, business_name }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
  refresh: () => api.post("/auth/refresh").then((r) => r.data),
  logout: () => api.post("/auth/logout").then((r) => r.data),
};

export const employeesApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/employees", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/employees/${id}`).then((r) => r.data),
  create: (data: unknown) => api.post("/employees", data).then((r) => r.data),
  update: (id: string, data: unknown) =>
    api.patch(`/employees/${id}`, data).then((r) => r.data),
  deactivate: (id: string) => api.delete(`/employees/${id}`),
  resetPassword: (id: string, new_password: string) =>
    api.post(`/employees/${id}/reset-password`, { new_password }).then((r) => r.data),
};

export const departmentsApi = {
  list: () => api.get("/departments").then((r) => r.data),
  create: (data: unknown) => api.post("/departments", data).then((r) => r.data),
  delete: (id: string) => api.delete(`/departments/${id}`),
};

export const devicesApi = {
  list: () => api.get("/devices").then((r) => r.data.items ?? r.data),
  pending: () => api.get("/devices/pending").then((r) => r.data.items ?? r.data),
  approve: (id: string) =>
    api.patch(`/devices/${id}/status`, { status: "approved" }).then((r) => r.data),
  revoke: (id: string) =>
    api.patch(`/devices/${id}/status`, { status: "revoked" }).then((r) => r.data),
  delete: (id: string) => api.delete(`/devices/${id}`),
};

export const analyticsApi = {
  overview: () => api.get("/analytics/overview").then((r) => r.data),
  timeline: (employeeId: string, date: string) =>
    api.get(`/analytics/timeline/${employeeId}`, { params: { date } }).then((r) => r.data),
  heatmap: (employeeId: string, date: string) =>
    api.get(`/analytics/heatmap/${employeeId}`, { params: { date } }).then((r) => r.data),
  appUsage: (employeeId: string, date: string) =>
    api.get(`/analytics/app-usage/${employeeId}`, { params: { date } }).then((r) => r.data),
  departmentComparison: (date: string) =>
    api.get("/analytics/department-comparison", { params: { date } }).then((r) => r.data),
  summaries: (employeeId: string, days = 7) =>
    api.get(`/analytics/summaries/${employeeId}`, { params: { days } }).then((r) => r.data),
  anomalies: (params?: Record<string, unknown>) =>
    api.get("/analytics/anomalies", { params }).then((r) => r.data),
  reviewAnomaly: (id: string) =>
    api.patch(`/analytics/anomalies/${id}/review`).then((r) => r.data),
  generateReport: (data: { employee_id?: string; days?: number; department_id?: string }) => {
    const days = data.days ?? 7;
    if (data.employee_id) {
      return api.get(`/reports/pdf/${data.employee_id}`, {
        params: { days },
        responseType: "blob",
      }).then((r) => r.data);
    }
    return api.get("/reports/pdf/team/all", {
      params: { days, department_id: data.department_id },
      responseType: "blob",
    }).then((r) => r.data);
  },
  screenshotPolicies: () => api.get("/screenshot-policies").then((r) => r.data),
  createPolicy: (data: unknown) =>
    api.post("/screenshot-policies", data).then((r) => r.data),
  togglePolicy: (id: string) =>
    api.patch(`/screenshot-policies/${id}/toggle`).then((r) => r.data),
  deletePolicy: (id: string) =>
    api.delete(`/screenshot-policies/${id}`).then((r) => r.data),
  cleanupMissingScreenshots: () =>
    api.delete("/screenshots/cleanup-missing").then((r) => r.data),
  deleteScreenshot: (id: string) =>
    api.delete(`/screenshots/${id}`).then((r) => r.data),
};

export const blockerApi = {
  list: () => api.get("/blocker/domains").then((r) => r.data),
  add: (data: unknown) => api.post("/blocker/domains", data).then((r) => r.data),
  remove: (id: string) => api.delete(`/blocker/domains/${id}`),
  toggle: (id: string) => api.patch(`/blocker/domains/${id}/toggle`).then((r) => r.data),
  loadDefaults: () => api.post("/blocker/load-defaults").then((r) => r.data),
  violations: () => api.get("/blocker/violations/summary").then((r) => r.data),
};

export const actionsApi = {
  create: (data: unknown) => api.post("/actions", data).then((r) => r.data),
  get: (id: string) => api.get(`/actions/${id}`).then((r) => r.data),
  getEmployeeItems: (employeeId: string, completed?: boolean, limit?: number) =>
    api.get(`/actions/employee/${employeeId}`, { params: { completed, limit } }).then((r) => r.data),
  update: (id: string, data: unknown) => api.patch(`/actions/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/actions/${id}`),
  getStats: (employeeId: string) =>
    api.get(`/actions/employee/${employeeId}/completion-stats`).then((r) => r.data),
};

export const settingsApi = {
  get: () => api.get("/settings").then((r) => r.data),
  update: (data: unknown) => api.put("/settings", data).then((r) => r.data),
};

export const reportsApi = {
  downloadEmployeePDF: async (employeeId: string, days: number = 7): Promise<Blob> => {
    const response = await api.get(`/reports/pdf/${employeeId}?days=${days}`, {
      responseType: "blob",
    });
    return response.data;
  },
  downloadTeamPDF: async (days: number = 7, departmentId?: string): Promise<Blob> => {
    const params = new URLSearchParams({ days: String(days) });
    if (departmentId) params.append("department_id", departmentId);
    const response = await api.get(`/reports/pdf/team/all?${params.toString()}`, {
      responseType: "blob",
    });
    return response.data;
  },
};

export const aiApi = {
  chat: (data: { message: string; history?: Array<{ role: string; content: string }> }) =>
    api.post("/ai/chat", data).then((r) => r.data),
  workRecommendations: (employeeId: string) =>
    api.get(`/ai/work-recommendations/${employeeId}`).then((r) => r.data),
  anomalyRecommendation: (employeeId: string) =>
    api.get(`/ai/anomaly-recommendation/${employeeId}`).then((r) => r.data),
  diagnostics: () => api.get("/ai/diagnostics/data-status").then((r) => r.data),
};

export const enrollApi = {
  generateLink: (employeeId: string, serverUrl: string) =>
    api
      .post(`${API_ROOT}/api/v1/enroll/generate-join-link?employee_id=${employeeId}&server_url=${encodeURIComponent(serverUrl)}`)
      .then((r) => r.data),
};

export const attendanceApi = {
  // Settings
  getSettings: () => api.get("/attendance/settings").then((r) => r.data),
  setup: (mode: string) => api.post("/attendance/setup", { mode }).then((r) => r.data),
  updateSettings: (data: Record<string, unknown>) => api.put("/attendance/settings", data).then((r) => r.data),

  // Locations
  getLocations: () => api.get("/attendance/locations").then((r) => r.data),
  createLocation: (data: Record<string, unknown>) => api.post("/attendance/locations", data).then((r) => r.data),
  updateLocation: (id: string, data: Record<string, unknown>) => api.put(`/attendance/locations/${id}`, data).then((r) => r.data),
  deleteLocation: (id: string) => api.delete(`/attendance/locations/${id}`).then((r) => r.data),

  // Check-in / Check-out
  checkIn: (employee_id: string, latitude?: number, longitude?: number) =>
    api.post("/attendance/check-in", { employee_id, latitude, longitude }).then((r) => r.data),
  checkOut: (employee_id: string, latitude?: number, longitude?: number) =>
    api.post("/attendance/check-out", { employee_id, latitude, longitude }).then((r) => r.data),

  // Lunch
  startLunch: (employee_id: string) => api.post("/attendance/lunch/start", { employee_id }).then((r) => r.data),
  endLunch: (employee_id: string) => api.post("/attendance/lunch/end", { employee_id }).then((r) => r.data),

  // Records
  getToday: () => api.get("/attendance/today").then((r) => r.data),
  getRecords: (params?: Record<string, unknown>) => api.get("/attendance/records", { params }).then((r) => r.data),
  updateRecord: (id: string, data: Record<string, unknown>) => api.put(`/attendance/records/${id}`, data).then((r) => r.data),
  deleteRecord: (id: string) => api.delete(`/attendance/records/${id}`).then((r) => r.data),
  getStats: (params?: Record<string, unknown>) => api.get("/attendance/stats", { params }).then((r) => r.data),
  exportRecords: (params?: Record<string, unknown>) =>
    api.get("/attendance/export", { params, responseType: "blob" }).then((r) => r.data),
};

export const liveStreamApi = {
  getStreamConfig: (employeeId: string) => api.get(`/agent/stream-config/${employeeId}`).then((r) => r.data),
  updateStreamConfig: (employeeId: string, enabled: boolean, fps?: number, quality?: number) =>
    api.put(`/agent/stream-config/${employeeId}`, { enabled, fps, quality }).then((r) => r.data),
};

export const employeePortalApi = {
  dashboard: () => api.get("/employee/portal/dashboard").then((r) => r.data),
  timeline: (date?: string) => api.get("/employee/portal/timeline", { params: { date } }).then((r) => r.data),
  consent: () => api.get("/employee/portal/consent").then((r) => r.data),
  toggleConsent: (consentGiven: boolean) => api.post("/employee/portal/consent", { consent_given: consentGiven }).then((r) => r.data),
  exportData: () => api.get("/employee/portal/export").then((r) => r.data),
  eraseData: () => api.delete("/employee/portal/erase").then((r) => r.data),
};

export const weeklySummariesApi = {
  list: () => api.get("/analytics/weekly-summaries").then((r) => r.data),
  trigger: (date: string) => api.post("/analytics/weekly-summaries/trigger", { date }).then((r) => r.data),
};
