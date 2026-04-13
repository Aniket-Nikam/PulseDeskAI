import axios from "axios";
import { useAuthStore } from "../store/authStore";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// Attach token from store on every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let _refreshing: Promise<string> | null = null;

// Silent token refresh — only redirect to /login if refresh itself fails
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
      const refreshToken = useAuthStore.getState().refreshToken;

      if (!refreshToken) {
        useAuthStore.getState().logout();
        window.location.href = "/login";
        return Promise.reject(error);
      }

      // Deduplicate concurrent refresh attempts
      if (!_refreshing) {
        _refreshing = axios
          .post(`${BASE}/auth/refresh`, { refresh_token: refreshToken })
          .then((r) => {
            const { access_token, refresh_token } = r.data;
            useAuthStore.getState().setTokens(access_token, refresh_token);
            return access_token;
          })
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
        const newToken = await _refreshing;
        original.headers.Authorization = `Bearer ${newToken}`;
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
  refresh: (token: string) =>
    api.post("/auth/refresh", { refresh_token: token }).then((r) => r.data),
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
  list: () => api.get("/devices").then((r) => r.data),
  pending: () => api.get("/devices/pending").then((r) => r.data),
  approve: (id: string) =>
    api.patch(`/devices/${id}/status`, { status: "approved" }).then((r) => r.data),
  revoke: (id: string) =>
    api.patch(`/devices/${id}/status`, { status: "revoked" }).then((r) => r.data),
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
  generateReport: (data: unknown) =>
    api.post("/analytics/reports/generate", data).then((r) => r.data),
  screenshotPolicies: () => api.get("/screenshot-policies").then((r) => r.data),
  createPolicy: (data: unknown) =>
    api.post("/screenshot-policies", data).then((r) => r.data),
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
  generateLink: async (employeeId: string, serverUrl: string) => {
    // The join portal is mounted at root (no /api/v1 prefix), so we call the root URL directly
    const rootUrl = BASE.replace(/\/api\/v1\/?$/, "");
    const res = await api.post(`${rootUrl}/enroll/generate-link?employee_id=${employeeId}&server_url=${encodeURIComponent(serverUrl)}`);
    return res.data;
  },
};
