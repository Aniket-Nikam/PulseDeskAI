import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, Monitor, BarChart3, AlertTriangle,
  Camera, LogOut, ChevronLeft, ChevronRight, Activity,
  Building2, Moon, Sun, MonitorPlay, FileText, ShieldOff,
  Trophy, Settings, TrendingUp, Sparkles,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { authApi } from "../../api/client";
import { initials } from "../../utils/format";
import { ErrorBoundary } from "../ui/ErrorBoundary";

const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      { to: "/", icon: LayoutDashboard, label: "Overview" },
      { to: "/live", icon: MonitorPlay, label: "Live screens" },
      { to: "/graph", icon: TrendingUp, label: "Activity graph" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { to: "/analytics", icon: BarChart3, label: "Deep analytics" },
      { to: "/leaderboard", icon: Trophy, label: "Leaderboard" },
      { to: "/reports", icon: FileText, label: "Reports" },
      { to: "/actions", icon: Activity, label: "Action Items" },
      { to: "/ai-insights", icon: Sparkles, label: "AI Insights" },
    ],
  },
  {
    label: "Team",
    items: [
      { to: "/employees", icon: Users, label: "Employees" },
      { to: "/departments", icon: Building2, label: "Departments" },
      { to: "/devices", icon: Monitor, label: "Devices" },
    ],
  },
  {
    label: "Security",
    items: [
      { to: "/anomalies", icon: AlertTriangle, label: "Anomalies" },
      { to: "/blocker", icon: ShieldOff, label: "Site blocker" },
      { to: "/screenshots", icon: Camera, label: "Screenshots" },
    ],
  },
];

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");
  const { admin, logout } = useAuthStore();
  const navigate = useNavigate();

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "";
    localStorage.setItem("pd-theme", next ? "dark" : "light");
  }

  async function handleLogout() {
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors during logout and still clear client state.
    }
    logout();
    navigate("/login");
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--bg-tertiary)" }}>
      <aside style={{
        width: collapsed ? 52 : 212,
        minWidth: collapsed ? 52 : 212,
        background: "var(--sidebar-bg)",
        borderRight: "1px solid var(--sidebar-border)",
        display: "flex", flexDirection: "column",
        transition: "width 0.18s ease, min-width 0.18s ease",
        overflow: "hidden",
      }}>
        {/* Logo */}
        <div style={{
          height: 50, display: "flex", alignItems: "center",
          padding: "0 14px", borderBottom: "1px solid var(--sidebar-border)",
          gap: 9, flexShrink: 0,
        }}>
          <div style={{
            width: 24, height: 24, borderRadius: 7, background: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <Activity size={13} color="#fff" strokeWidth={2.5}/>
          </div>
          {!collapsed && (
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", whiteSpace: "nowrap" }}>
              PulseDesk
            </span>
          )}
        </div>

        {/* Grouped nav */}
        <nav style={{ flex: 1, padding: "8px 0", overflowY: "auto" }}>
          {NAV_GROUPS.map(group => (
            <div key={group.label} style={{ marginBottom: 2 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 10, fontWeight: 600, color: "var(--text-tertiary)",
                  textTransform: "uppercase", letterSpacing: "0.06em",
                  padding: "8px 14px 2px",
                }}>
                  {group.label}
                </div>
              )}
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink key={to} to={to} end={to === "/"}
                  style={({ isActive }) => ({
                    display: "flex", alignItems: "center", gap: 8,
                    padding: collapsed ? "7px 14px" : "6px 10px",
                    margin: "1px 6px", borderRadius: "var(--radius-md)",
                    textDecoration: "none", fontSize: 13,
                    fontWeight: isActive ? 500 : 400,
                    color: isActive ? "var(--sidebar-item-active-text)" : "var(--text-secondary)",
                    background: isActive ? "var(--sidebar-item-active)" : "transparent",
                    transition: "background 0.1s",
                    whiteSpace: "nowrap", overflow: "hidden",
                  })}
                  title={collapsed ? label : undefined}
                >
                  {({ isActive }) => (
                    <>
                      <Icon size={15} strokeWidth={isActive ? 2.2 : 1.8}
                        style={{ flexShrink: 0, color: isActive ? "var(--sidebar-item-active-text)" : "var(--text-tertiary)" }}/>
                      {!collapsed && label}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Bottom */}
        <div style={{ padding: "6px 0 4px", borderTop: "1px solid var(--sidebar-border)", flexShrink: 0 }}>
          <button onClick={toggleTheme} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: collapsed ? "7px 14px" : "6px 10px",
            margin: "1px 6px", borderRadius: "var(--radius-md)",
            border: "none", cursor: "pointer", fontSize: 13,
            color: "var(--text-secondary)", background: "transparent",
            width: "calc(100% - 12px)", whiteSpace: "nowrap", overflow: "hidden", fontFamily: "inherit",
          }}>
            {dark
              ? <Sun size={15} style={{ flexShrink: 0, color: "var(--text-tertiary)" }}/>
              : <Moon size={15} style={{ flexShrink: 0, color: "var(--text-tertiary)" }}/>}
            {!collapsed && (dark ? "Light mode" : "Dark mode")}
          </button>

          <NavLink to="/settings" style={({ isActive }) => ({
            display: "flex", alignItems: "center", gap: 8,
            padding: collapsed ? "7px 14px" : "6px 10px",
            margin: "1px 6px", borderRadius: "var(--radius-md)",
            textDecoration: "none", fontSize: 13,
            color: isActive ? "var(--sidebar-item-active-text)" : "var(--text-secondary)",
            background: isActive ? "var(--sidebar-item-active)" : "transparent",
            whiteSpace: "nowrap", overflow: "hidden",
          })}>
            <Settings size={15} style={{ flexShrink: 0, color: "var(--text-tertiary)" }}/>
            {!collapsed && "Settings"}
          </NavLink>

          {/* User */}
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: collapsed ? "7px 14px" : "7px 10px",
            margin: "1px 6px", borderRadius: "var(--radius-md)",
            justifyContent: collapsed ? "center" : "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
              <div style={{
                width: 26, height: 26, borderRadius: "50%",
                background: "var(--accent-subtle)", border: "1px solid var(--border-default)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700, color: "var(--accent-text)", flexShrink: 0,
              }}>
                {initials(admin?.full_name ?? "A")}
              </div>
              {!collapsed && (
                <div style={{ overflow: "hidden" }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {admin?.full_name}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "capitalize" }}>
                    {admin?.role?.replace("_", " ")}
                  </div>
                </div>
              )}
            </div>
            {!collapsed && (
              <button onClick={handleLogout}
                title="Sign out"
                style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: "var(--text-tertiary)", display: "flex", flexShrink: 0 }}>
                <LogOut size={13}/>
              </button>
            )}
          </div>

          <button onClick={() => setCollapsed(c => !c)} style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: "calc(100% - 12px)", margin: "2px 6px 4px",
            padding: 5, borderRadius: "var(--radius-md)",
            background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)",
          }}>
            {collapsed ? <ChevronRight size={13}/> : <ChevronLeft size={13}/>}
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, overflow: "auto", minWidth: 0 }}>
        <ErrorBoundary>
          <Outlet/>
        </ErrorBoundary>
      </main>
    </div>
  );
}
