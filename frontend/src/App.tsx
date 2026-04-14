import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { DevicesPage } from "./pages/DevicesPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AnomaliesPage } from "./pages/AnomaliesPage";
import { ScreenshotsPage } from "./pages/ScreenshotsPage";
import { DepartmentsPage } from "./pages/DepartmentsPage";
import { LiveScreensPage } from "./pages/LiveScreensPage";
import { ReportsPage } from "./pages/ReportsPage";
import { BlockerPage } from "./pages/BlockerPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ActivityGraphPage } from "./pages/ActivityGraphPage";
import { AIInsightsPage } from "./pages/AIInsightsPage";
import { ActionItemsPage } from "./pages/ActionItemsPage";
import { AlertSystem } from "./components/ui/AlertSystem";
import { useAuthStore, selectIsAuthenticated } from "./store/authStore";
import { authApi } from "./api/client";
import "./styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

function SessionValidator({ children }: { children: React.ReactNode }) {
  const { setAdmin, logout, isHydrated } = useAuthStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isHydrated) return;

    authApi.me()
      .then(me => setAdmin(me))
      .catch(async err => {
        if (err?.response?.status === 401) {
          try {
            await authApi.refresh();
            const me = await authApi.me();
            setAdmin(me);
          } catch {
            logout();
          }
        }
      })
      .finally(() => setChecking(false));
  }, [isHydrated]);

  if (!isHydrated || checking) {
    return (
      <div style={{
        height: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "var(--bg-tertiary)",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 14px",
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </div>
          <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>Loading PulseDesk…</div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireUnauth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  useEffect(() => {
    const saved = localStorage.getItem("pd-theme");
    if (saved === "dark") document.documentElement.dataset.theme = "dark";
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SessionValidator>
          <AlertSystem />
          <Routes>
            <Route path="/login" element={<RequireUnauth><LoginPage /></RequireUnauth>} />
            <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
              <Route index element={<OverviewPage />} />
              <Route path="live" element={<LiveScreensPage />} />
              <Route path="graph" element={<ActivityGraphPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="leaderboard" element={<LeaderboardPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="employees" element={<EmployeesPage />} />
              <Route path="departments" element={<DepartmentsPage />} />
              <Route path="devices" element={<DevicesPage />} />
              <Route path="anomalies" element={<AnomaliesPage />} />
              <Route path="blocker" element={<BlockerPage />} />
              <Route path="screenshots" element={<ScreenshotsPage />} />
              <Route path="ai-insights" element={<AIInsightsPage />} />
              <Route path="actions" element={<ActionItemsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </SessionValidator>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
