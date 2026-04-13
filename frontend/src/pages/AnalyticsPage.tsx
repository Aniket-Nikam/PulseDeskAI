import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { analyticsApi, employeesApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Employee, AppUsageStat, DailySummary } from "../types";
import { formatSeconds, todayISO, categoryColor, productivityColor } from "../utils/format";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from "recharts";

const ACTIVITY_COLORS: Record<string, string> = {
  active: "#3d9a6a",
  idle:   "#e9a94a",
  locked: "#94a3b8",
  away:   "#cbd5e1",
};

function TimelineBar({ timeline }: { timeline: any }) {
  if (!timeline?.blocks?.length) {
    return (
      <div style={{
        height: 52, display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
        fontSize: 13, color: "var(--text-tertiary)",
      }}>
        No data for this day — make sure the agent is running.
      </div>
    );
  }

  const blocks = timeline.blocks;
  const start = new Date(blocks[0].start).getTime();
  const end   = new Date(blocks[blocks.length - 1].end).getTime();
  const total = Math.max(end - start, 1);

  const fmt = (secs: number) =>
    secs >= 3600
      ? `${Math.floor(secs/3600)}h ${Math.floor((secs%3600)/60)}m`
      : `${Math.floor(secs/60)}m`;

  return (
    <div>
      {/* Stats */}
      <div style={{ display: "flex", gap: 24, marginBottom: 14, flexWrap: "wrap" }}>
        {[
          { label: "Active",   value: fmt(timeline.active_seconds ?? 0),  color: ACTIVITY_COLORS.active },
          { label: "Idle",     value: fmt(timeline.idle_seconds ?? 0),     color: ACTIVITY_COLORS.idle },
          { label: "Score",    value: `${Math.round(timeline.productivity_score ?? 0)}%`,
            color: productivityColor(timeline.productivity_score ?? 0) },
          { label: "Sessions", value: fmt(timeline.total_tracked_seconds ?? 0), color: "var(--text-tertiary)" },
        ].map(({ label, value, color }) => (
          <div key={label}>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 3 }}>
              {label}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color, letterSpacing: "-0.01em" }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Bar */}
      <div className="timeline-bar">
        {blocks.map((b: any, i: number) => {
          const w = ((new Date(b.end).getTime() - new Date(b.start).getTime()) / total) * 100;
          const startTime = new Date(b.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          return (
            <div
              key={i}
              className="timeline-segment"
              title={`${b.activity_type}${b.app ? ` — ${b.app}` : ""} (${startTime})`}
              style={{ width: `${Math.max(w, 0.2)}%`, background: ACTIVITY_COLORS[b.activity_type] ?? "#94a3b8" }}
            />
          );
        })}
      </div>

      {/* Time labels */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 10, color: "var(--text-tertiary)" }}>
        <span>{new Date(blocks[0].start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        <span>{new Date(blocks[blocks.length-1].end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 14, marginTop: 10 }}>
        {Object.entries(ACTIVITY_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-tertiary)" }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            <span style={{ textTransform: "capitalize" }}>{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeatmapChart24Hr({ heatmapData }: { heatmapData: { hours: Record<string, number> } | null }) {
  if (!heatmapData) {
    return (
      <div style={{
        padding: "20px", textAlign: "center", fontSize: 13, color: "var(--text-tertiary)",
        background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
      }}>
        Loading heatmap data...
      </div>
    );
  }

  const hours = Object.entries(heatmapData.hours || {})
    .map(([h, seconds]) => ({ hour: parseInt(h), seconds: seconds as number }))
    .sort((a, b) => a.hour - b.hour);

  const maxSeconds = Math.max(...hours.map(h => h.seconds), 1);

  const getColor = (seconds: number) => {
    const pct = seconds / maxSeconds;
    if (pct >= 0.75) return "#22c55e"; // Green
    if (pct >= 0.5) return "#10b981";  // Teal
    if (pct >= 0.25) return "#f59e0b"; // Amber
    if (pct > 0) return "#ef4444";     // Red
    return "#e5e7eb";                   // Gray
  };

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "8px", marginBottom: "16px" }}>
        {hours.map((h) => {
          const mins = Math.round(h.seconds / 60);
          const color = getColor(h.seconds);
          const hour12 = h.hour === 0 ? "12 AM" : h.hour < 12 ? `${h.hour} AM` : h.hour === 12 ? "12 PM" : `${h.hour - 12} PM`;
          return (
            <div
              key={h.hour}
              title={`${hour12}: ${mins} minutes`}
              style={{
                padding: "12px 8px",
                background: color,
                borderRadius: "var(--radius-sm)",
                textAlign: "center",
                cursor: "pointer",
                transition: "all 0.2s ease",
                opacity: h.seconds > 0 ? 1 : 0.5,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: h.seconds > 0 ? "#fff" : "var(--text-tertiary)" }}>
                {h.hour}
              </div>
              <div style={{ fontSize: 9, color: h.seconds > 0 ? "rgba(255,255,255,0.7)" : "var(--text-tertiary)", marginTop: "2px" }}>
                {mins}m
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", paddingTop: 8, borderTop: "1px solid var(--border-color)" }}>
        {[
          { label: "High", color: "#22c55e" },
          { label: "Med-High", color: "#10b981" },
          { label: "Medium", color: "#f59e0b" },
          { label: "Low", color: "#ef4444" },
        ].map(({ label, color }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>
            <div style={{ width: 8, height: 8, borderRadius: 1, background: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const [params, setParams] = useSearchParams();
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const employeeId = params.get("employee") ?? "";

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const selected = employees.find(e => e.id === employeeId) ?? employees[0];

  const { data: timeline, isLoading: tlLoading } = useQuery({
    queryKey: ["timeline", selected?.id, selectedDate],
    queryFn: () => analyticsApi.timeline(selected!.id, selectedDate),
    enabled: !!selected,
  });

  const { data: appUsage = [] } = useQuery<AppUsageStat[]>({
    queryKey: ["app-usage", selected?.id, selectedDate],
    queryFn: () => analyticsApi.appUsage(selected!.id, selectedDate),
    enabled: !!selected,
  });

  const { data: summaries = [] } = useQuery<DailySummary[]>({
    queryKey: ["summaries", selected?.id],
    queryFn: () => analyticsApi.summaries(selected!.id, 14),
    enabled: !!selected,
  });

  const { data: heatmap } = useQuery({
    queryKey: ["heatmap", selected?.id, selectedDate],
    queryFn: () => analyticsApi.heatmap(selected!.id, selectedDate),
    enabled: !!selected,
  });

  if (!employees.length) {
    return (
      <div style={{ padding: "var(--space-8)" }}>
        <PageHeader title="Analytics" />
        <div className="card empty-state">
          <div className="empty-state-icon">📈</div>
          <div className="empty-state-title">No employees to analyze</div>
          <div className="empty-state-body">Add employees and start the agent to see analytics here.</div>
        </div>
      </div>
    );
  }

  const trendData = [...summaries].reverse().map(s => ({
    date: new Date(s.date).toLocaleDateString("en", { month: "short", day: "numeric" }),
    score: Math.round(s.productivity_score),
  }));

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader title="Analytics" subtitle="Deep-dive into individual productivity" />

      <div style={{ display: "flex", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
        <select className="input" style={{ width: "auto", minWidth: 200 }}
          value={selected?.id ?? ""} onChange={e => setParams({ employee: e.target.value })}>
          {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
        </select>
        <input type="date" className="input" style={{ width: "auto" }}
          value={selectedDate} max={todayISO()}
          onChange={e => setSelectedDate(e.target.value)} />
      </div>

      {selected && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Timeline */}
          <div className="card" style={{ padding: "var(--space-6)" }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 18, color: "var(--text-primary)" }}>
              Workday timeline
            </h2>
            {tlLoading
              ? <div className="skeleton" style={{ height: 80 }} />
              : <TimelineBar timeline={timeline} />}
          </div>

          {/* 24-hour Heatmap + App usage */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

            <div className="card" style={{ padding: "var(--space-6)" }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
                24-hour activity heatmap
              </h2>
              <HeatmapChart24Hr heatmapData={heatmap} />
            </div>

            <div className="card" style={{ padding: "var(--space-6)" }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
                App usage today
              </h2>{appUsage.length === 0 ? (
                <div style={{ padding: "20px 0", textAlign: "center", fontSize: 13, color: "var(--text-tertiary)" }}>
                  No app data yet — agent is collecting.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {appUsage.slice(0, 8).map(app => (
                    <div key={app.app_name} className="app-bar-row">
                      <div className="app-bar-dot" style={{ background: categoryColor(app.app_category) }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="app-bar-name">{app.app_name}</span>
                          <div style={{ display: "flex", gap: 8, flexShrink: 0, marginLeft: 8 }}>
                            <span className="app-bar-time">{formatSeconds(app.total_seconds)}</span>
                            <span className="app-bar-pct">{app.percentage}%</span>
                          </div>
                        </div>
                        <div className="app-bar-track">
                          <div className="app-bar-fill"
                            style={{ width: `${app.percentage}%`, background: categoryColor(app.app_category) }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 14-day trend */}
          <div className="card" style={{ padding: "var(--space-6)" }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
              14-day productivity trend
            </h2>
            {trendData.length === 0 ? (
              <div style={{ padding: "28px 0", textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 6 }}>
                  Historical data builds up over multiple days.
                </div>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                  Today's live score:{" "}
                  <strong style={{ color: productivityColor(timeline?.productivity_score ?? 0) }}>
                    {Math.round(timeline?.productivity_score ?? 0)}%
                  </strong>
                </div>
              </div>
            ) : (
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendData} margin={{ top: 4, right: 4, bottom: 4, left: -22 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-tertiary)" }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-tertiary)" }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                    <Tooltip
                      cursor={{ fill: "var(--bg-secondary)" }}
                      contentStyle={{ background: "var(--bg-primary)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", fontSize: 12, boxShadow: "var(--shadow-md)" }}
                      formatter={(v: number) => [`${v}%`, "Productivity"]}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                      {trendData.map((d, i) => (
                        <Cell key={i} fill={productivityColor(d.score)} fillOpacity={0.88} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}
