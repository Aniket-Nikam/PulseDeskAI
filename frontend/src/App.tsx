import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "./components/layout/AppLayout";
const LoginPage = React.lazy(() => import("./pages/LoginPage").then(m => ({ default: m.LoginPage })));
const LandingPage = React.lazy(() => import("./pages/LandingPage").then(m => ({ default: m.LandingPage })));
const SignupPage = React.lazy(() => import("./pages/SignupPage").then(m => ({ default: m.SignupPage })));
const OverviewPage = React.lazy(() => import("./pages/OverviewPage").then(m => ({ default: m.OverviewPage })));
const EmployeesPage = React.lazy(() => import("./pages/EmployeesPage").then(m => ({ default: m.EmployeesPage })));
const DevicesPage = React.lazy(() => import("./pages/DevicesPage").then(m => ({ default: m.DevicesPage })));
const AnalyticsPage = React.lazy(() => import("./pages/AnalyticsPage").then(m => ({ default: m.AnalyticsPage })));
const AnomaliesPage = React.lazy(() => import("./pages/AnomaliesPage").then(m => ({ default: m.AnomaliesPage })));
const ScreenshotsPage = React.lazy(() => import("./pages/ScreenshotsPage").then(m => ({ default: m.ScreenshotsPage })));
const DepartmentsPage = React.lazy(() => import("./pages/DepartmentsPage").then(m => ({ default: m.DepartmentsPage })));
const LiveScreensPage = React.lazy(() => import("./pages/LiveScreensPage").then(m => ({ default: m.LiveScreensPage })));
const ReportsPage = React.lazy(() => import("./pages/ReportsPage").then(m => ({ default: m.ReportsPage })));
const BlockerPage = React.lazy(() => import("./pages/BlockerPage").then(m => ({ default: m.BlockerPage })));
const LeaderboardPage = React.lazy(() => import("./pages/LeaderboardPage").then(m => ({ default: m.LeaderboardPage })));
const SettingsPage = React.lazy(() => import("./pages/SettingsPage").then(m => ({ default: m.SettingsPage })));
const AttendancePage = React.lazy(() => import("./pages/AttendancePage").then(m => ({ default: m.AttendancePage })));
const ActivityGraphPage = React.lazy(() => import("./pages/ActivityGraphPage").then(m => ({ default: m.ActivityGraphPage })));
const AIInsightsPage = React.lazy(() => import("./pages/AIInsightsPage").then(m => ({ default: m.AIInsightsPage })));
const ActionItemsPage = React.lazy(() => import("./pages/ActionItemsPage").then(m => ({ default: m.ActionItemsPage })));
const EmployeePortalPage = React.lazy(() => import("./pages/EmployeePortalPage").then(m => ({ default: m.EmployeePortalPage })));
const EmployeeConsentPage = React.lazy(() => import("./pages/EmployeeConsentPage").then(m => ({ default: m.EmployeeConsentPage })));
import { AlertSystem } from "./components/ui/AlertSystem";
import { DialogContainer } from "./components/ui/Dialog";
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
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function PageLoader() {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "400px",
      width: "100%",
    }}>
      <div style={{
        width: 32,
        height: 32,
        borderRadius: "50%",
        border: "3px solid var(--border-subtle)",
        borderTopColor: "var(--accent)",
        animation: "spin 1s linear infinite",
      }} />
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function IndexRoute() {
  const { admin } = useAuthStore();
  if (admin?.role === "employee") {
    return <Navigate to="/dashboard/employee-portal" replace />;
  }
  return <OverviewPage />;
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
          <DialogContainer />
          <React.Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<RequireUnauth><LoginPage /></RequireUnauth>} />
              <Route path="/signup" element={<RequireUnauth><SignupPage /></RequireUnauth>} />
              <Route path="/dashboard" element={<RequireAuth><AppLayout /></RequireAuth>}>
                <Route index element={<IndexRoute />} />
                <Route path="employee-portal" element={<EmployeePortalPage />} />
                <Route path="gdpr-consent" element={<EmployeeConsentPage />} />
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
                <Route path="attendance" element={<AttendancePage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </React.Suspense>
        </SessionValidator>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
