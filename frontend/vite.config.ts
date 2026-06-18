import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      // Explicit WebSocket proxy for live streaming paths
      "/api/v1/ws": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      "/join": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/enroll": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
