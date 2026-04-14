export const isBrowser = typeof window !== "undefined";

let apiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();

if (!apiUrl) {
  apiUrl = isBrowser ? `${window.location.origin}/api/v1` : "http://localhost:8000/api/v1";
} else if (apiUrl.startsWith("/")) {
  apiUrl = isBrowser ? `${window.location.origin}${apiUrl}` : `http://localhost:8000${apiUrl}`;
}

export const API_BASE_URL = apiUrl;

export const BACKEND_ROOT = API_BASE_URL.replace("/api/v1", "");

export const APP_ORIGIN = isBrowser ? window.location.origin : "http://localhost:5173";

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");
