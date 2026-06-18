import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clock, Activity, Award, AlertCircle, BarChart2, Calendar, Layout } from "lucide-react";
import { ResponsiveContainer, AreaChart, XAxis, YAxis, Tooltip, Area, CartesianGrid } from "recharts";
import { employeePortalApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { StatCard } from "../components/ui/StatCard";
import { formatSeconds, formatTime } from "../utils/format";

export function EmployeePortalPage() {
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split("T")[0]);

  // Fetch Dashboard Stats
  const { data: dashboardData, isLoading: isDashboardLoading } = useQuery({
    queryKey: ["employeeDashboard"],
    queryFn: employeePortalApi.dashboard,
  });

  // Fetch Timeline Data
  const { data: timelineData, isLoading: isTimelineLoading } = useQuery({
    queryKey: ["employeeTimeline", selectedDate],
    queryFn: () => employeePortalApi.timeline(selectedDate),
  });

  if (isDashboardLoading) {
    return (
      <div style={{ padding: "var(--space-8)" }}>
        <PageHeader title="My Performance Portal" subtitle="Analyze your personal work metrics" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card skeleton" style={{ height: 110 }} />
          ))}
        </div>
      </div>
    );
  }

  const stats = dashboardData?.stats || {
    total_active_hours: 0,
    total_idle_hours: 0,
    total_focus_hours: 0,
    total_tracked_hours: 0,
    avg_productivity_score: 0,
    total_anomalies: 0,
    top_app: "None",
    top_category: "None",
  };

  const chartData = dashboardData?.chart_data || [];
  const timeline = timelineData?.blocks || [];

  return (
    <div style={{ padding: "var(--space-8)", maxWidth: 1200, margin: "0 auto" }}>
      <PageHeader
        title={`Welcome, ${dashboardData?.employee?.full_name || "Employee"}`}
        subtitle={`Role: Employee Self-Monitoring • Job Title: ${dashboardData?.employee?.job_title || "Team Member"}`}
      />

      {/* Grid of personal statistics */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 16,
        marginBottom: 24,
      }}>
        <StatCard
          label="Tracked Active Hours"
          value={`${stats.total_active_hours} hrs`}
          color="var(--accent)"
          icon={<Clock size={16} />}
        />
        <StatCard
          label="Total Idle Hours"
          value={`${stats.total_idle_hours} hrs`}
          color="var(--warning)"
          icon={<Activity size={16} />}
        />
        <StatCard
          label="Avg Productivity Score"
          value={`${stats.avg_productivity_score}%`}
          color={stats.avg_productivity_score >= 70 ? "var(--success)" : "var(--error)"}
          icon={<Award size={16} />}
        />
        <StatCard
          label="Total Flagged Anomalies"
          value={stats.total_anomalies}
          color={stats.total_anomalies > 0 ? "var(--error)" : "var(--success)"}
          icon={<AlertCircle size={16} />}
        />
      </div>

      {/* Detailed statistics / Top usage */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: 20,
        marginBottom: 24,
      }}>
        {/* Top App & Top Category */}
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: 14, fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
            <Layout size={16} color="var(--accent)" />
            Top Application Usage
          </h3>
          <div style={{ display: "flex", gap: 12, flexDirection: "column" }}>
            <div style={{ padding: "12px 16px", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>MOST USED APPLICATION</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>{stats.top_app || "None"}</div>
            </div>
            <div style={{ padding: "12px 16px", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>MOST ACTIVE CATEGORY</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>{stats.top_category || "None"}</div>
            </div>
          </div>
        </div>

        {/* Privacy Note */}
        <div className="card" style={{ padding: 20, borderLeft: "4px solid var(--accent)" }}>
          <h3 style={{ margin: "0 0 10px 0", fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
            🔒 Privacy & GDPR Governance
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
            PulseDesk is configured for strict GDPR compliance. Data minimization policies automatically restrict 
            raw monitoring data to a 30-day rolling retention window. You have full Right of Access and Erasure 
            over your statistics. Use the <strong>Privacy & GDPR</strong> page to view, download, or permanently 
            erase your data.
          </p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="card" style={{ padding: 20, marginBottom: 24 }}>
        <h3 style={{ margin: "0 0 20px 0", fontSize: 14, fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
          <BarChart2 size={16} color="var(--accent)" />
          Personal Productivity & Tracking Trends (Last 30 Days)
        </h3>
        <div style={{ width: "100%", height: 300 }}>
          {chartData.length === 0 ? (
            <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-tertiary)" }}>
              No trend data available for the last 30 days yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorProd" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="date" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "var(--radius-md)",
                    fontSize: 12
                  }}
                />
                <Area type="monotone" dataKey="productivity_score" stroke="var(--accent)" fillOpacity={1} fill="url(#colorProd)" name="Productivity (%)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Daily Workday Timeline */}
      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
            <Calendar size={16} color="var(--accent)" />
            Activity Timeline Details
          </h3>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>Select Date:</span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-primary)",
                padding: "4px 8px",
                fontSize: 12,
                outline: "none"
              }}
            />
          </div>
        </div>

        {isTimelineLoading ? (
          <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div className="skeleton" style={{ width: "100%", height: 40 }} />
          </div>
        ) : timeline.length === 0 ? (
          <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>
            No activity tracked on this date.
          </div>
        ) : (
          <div>
            <div style={{ display: "flex", gap: 20, marginBottom: 16, fontSize: 12, color: "var(--text-secondary)", background: "var(--bg-secondary)", padding: "10px 14px", borderRadius: "var(--radius-md)" }}>
              <div>Tracked: <strong>{formatSeconds(timelineData.total_tracked_seconds)}</strong></div>
              <div>Active: <strong>{formatSeconds(timelineData.active_seconds)}</strong></div>
              <div>Idle: <strong>{formatSeconds(timelineData.idle_seconds)}</strong></div>
              <div>Productivity Score: <strong>{timelineData.productivity_score}%</strong></div>
            </div>

            {/* Visual block timeline */}
            <div style={{
              display: "flex",
              height: 36,
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-default)",
              marginBottom: 20
            }}>
              {timeline.map((block: any, idx: number) => {
                const colors: Record<string, string> = {
                  active: "var(--accent)",
                  idle: "var(--warning)",
                  locked: "var(--border-default)",
                  away: "var(--text-tertiary)"
                };
                return (
                  <div
                    key={idx}
                    style={{
                      flex: 1,
                      background: colors[block.activity_type] || "var(--border-default)",
                      borderRight: "1px solid var(--bg-tertiary)"
                    }}
                    title={`${block.activity_type} - ${block.app || "System"} (${block.app_category || "Uncategorized"})`}
                  />
                );
              })}
            </div>

            {/* List of activity items */}
            <div style={{ maxHeight: 300, overflowY: "auto", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--border-default)", textAlign: "left" }}>
                    <th style={{ padding: "8px 12px", color: "var(--text-secondary)", fontWeight: 500 }}>Time</th>
                    <th style={{ padding: "8px 12px", color: "var(--text-secondary)", fontWeight: 500 }}>Activity</th>
                    <th style={{ padding: "8px 12px", color: "var(--text-secondary)", fontWeight: 500 }}>Application</th>
                    <th style={{ padding: "8px 12px", color: "var(--text-secondary)", fontWeight: 500 }}>Category</th>
                  </tr>
                </thead>
                <tbody>
                  {timeline.map((block: any, idx: number) => (
                    <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "8px 12px", color: "var(--text-tertiary)" }}>
                        {formatTime(block.start)}
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        <span style={{
                          fontSize: 10,
                          fontWeight: 600,
                          padding: "2px 6px",
                          borderRadius: "var(--radius-md)",
                          color: block.activity_type === "active" ? "var(--accent-text)" : "var(--text-secondary)",
                          background: block.activity_type === "active" ? "var(--accent-subtle)" : "var(--bg-secondary)",
                          textTransform: "uppercase"
                        }}>
                          {block.activity_type}
                        </span>
                      </td>
                      <td style={{ padding: "8px 12px", color: "var(--text-primary)", fontWeight: 500 }}>
                        {block.app || "—"}
                      </td>
                      <td style={{ padding: "8px 12px", color: "var(--text-secondary)" }}>
                        {block.app_category || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
