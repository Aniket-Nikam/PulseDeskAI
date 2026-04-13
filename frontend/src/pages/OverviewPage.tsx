import React, { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, Wifi, Activity, Clock, AlertTriangle, TrendingUp } from "lucide-react";
import { analyticsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { StatCard } from "../components/ui/StatCard";
import { OnlineBadge } from "../components/ui/OnlineBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { EmployeeStatus, WsMessage } from "../types";
import { formatSeconds, formatTime, activityColor, productivityColor, categoryColor } from "../utils/format";

export function OverviewPage() {
  const queryClient = useQueryClient();
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const { data: employees = [], isLoading } = useQuery<EmployeeStatus[]>({
    queryKey: ["overview"],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type !== "employee_update") return;
    setLastUpdate(new Date());
    queryClient.setQueryData<EmployeeStatus[]>(["overview"], (old = []) =>
      old.map((e) =>
        e.employee_id === msg.data.employee_id
          ? {
              ...e,
              activity_type: msg.data.activity_type,
              active_app: msg.data.active_app,
              active_window_title: msg.data.active_window_title,
              idle_seconds: msg.data.idle_seconds,
              last_seen: msg.data.timestamp,
              is_online: true,
            }
          : e
      )
    );
  }, [queryClient]);

  useWebSocket(handleWsMessage);

  const online = employees.filter((e) => e.is_online).length;
  const active = employees.filter((e) => e.activity_type === "active").length;
  const idle = employees.filter((e) => e.activity_type === "idle").length;
  const avgScore = employees.length > 0
    ? Math.round(employees.reduce((s, e) => s + (e.today_productivity_score ?? 0), 0) / employees.length)
    : 0;

  if (isLoading) {
    return (
      <div style={{ padding: "var(--space-8)" }}>
        <PageHeader title="Overview" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card skeleton" style={{ height: 110 }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Overview"
        subtitle={
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
            Live — updated {formatTime(lastUpdate.toISOString())}
          </span>
        }
      />

      {/* Stats row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
        gap: 12, marginBottom: 24,
      }}>
        <StatCard label="Total employees" value={employees.length} icon={<Users size={16} />} />
        <StatCard label="Online now" value={online} color="var(--success)" icon={<Wifi size={16} />} />
        <StatCard label="Active" value={active} color="var(--accent)" icon={<Activity size={16} />} />
        <StatCard label="Idle" value={idle} color="var(--warning)" icon={<Clock size={16} />} />
        <StatCard label="Avg score today" value={avgScore > 0 ? `${avgScore}%` : "—"} color={productivityColor(avgScore)} icon={<TrendingUp size={16} />} />
      </div>

      {employees.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">🖥️</div>
          <div className="empty-state-title">No employees yet</div>
          <div className="empty-state-body">
            Add employees, then enroll their devices using the join portal.
          </div>
          <Link to="/employees" className="btn btn-primary" style={{ marginTop: 8 }}>
            Add employees
          </Link>
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))",
          gap: 12,
        }}>
          {employees
            .sort((a, b) => (b.is_online ? 1 : 0) - (a.is_online ? 1 : 0))
            .map((emp) => (
              <EmployeeCard key={emp.employee_id} employee={emp} />
            ))}
        </div>
      )}
    </div>
  );
}

function EmployeeCard({ employee: emp }: { employee: EmployeeStatus }) {
  const scoreColor = productivityColor(emp.today_productivity_score);

  return (
    <Link to={`/analytics?employee=${emp.employee_id}`} style={{ textDecoration: "none" }}>
      <div
        className="card"
        style={{
          padding: "var(--space-4) var(--space-5)",
          transition: "box-shadow 0.12s, border-color 0.12s",
          cursor: "pointer",
          borderLeft: emp.is_online ? `3px solid ${activityColor(emp.activity_type)}` : "3px solid var(--border-subtle)",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-md)";
          (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-sm)";
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
              {emp.employee_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 1 }}>
              {emp.department_name ?? "No department"}
            </div>
          </div>
          <OnlineBadge online={emp.is_online} size="sm" />
        </div>

        {/* Current activity */}
        <div style={{
          padding: "8px 10px",
          background: "var(--bg-secondary)",
          borderRadius: "var(--radius-md)",
          marginBottom: 10,
        }}>
          {emp.is_online && emp.active_app ? (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <div style={{
                  width: 7, height: 7, borderRadius: "50%",
                  background: activityColor(emp.activity_type),
                  flexShrink: 0,
                }} />
                <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {emp.active_app}
                </span>
              </div>
              {emp.active_window_title && (
                <div style={{
                  fontSize: 11, color: "var(--text-tertiary)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  paddingLeft: 13,
                }}>
                  {emp.active_window_title}
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--border-default)", flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                {emp.is_online ? (emp.activity_type ?? "Monitoring") : "Offline"}
              </span>
            </div>
          )}
          {emp.activity_type === "idle" && emp.idle_seconds > 0 && (
            <div style={{ fontSize: 11, color: "var(--warning)", marginTop: 4, paddingLeft: 13 }}>
              Idle for {formatSeconds(emp.idle_seconds)}
            </div>
          )}
        </div>

        {/* Bottom row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            {emp.today_active_seconds > 0
              ? `${formatSeconds(emp.today_active_seconds)} active today`
              : emp.last_seen
              ? `Last seen ${formatTime(emp.last_seen)}`
              : "No data today"}
          </div>
          {emp.today_productivity_score !== null && emp.today_productivity_score > 0 && (
            <div style={{
              fontSize: 12, fontWeight: 600, color: scoreColor,
              background: `${scoreColor}18`,
              padding: "2px 8px", borderRadius: "var(--radius-full)",
            }}>
              {Math.round(emp.today_productivity_score)}%
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
