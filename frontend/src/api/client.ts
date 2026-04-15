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

// ── API modules ───────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }).then((r) => r.data),
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

export const enrollApi = {
  generateLink: (employeeId: string, serverUrl: string) =>
    api
      .post(`${API_ROOT}/api/v1/enroll/generate-join-link?employee_id=${employeeId}&server_url=${encodeURIComponent(serverUrl)}`)
      .then((r) => r.data),
};
