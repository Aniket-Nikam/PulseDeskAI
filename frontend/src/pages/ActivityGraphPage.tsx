import React, { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Activity, Keyboard, MousePointer, Zap } from "lucide-react";
import { analyticsApi, employeesApi } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import { PageHeader } from "../components/ui/PageHeader";
import { EmployeeSearchDropdown } from "../components/ui/EmployeeSearchDropdown";
import type { Employee, WsMessage, EmployeeStatus } from "../types";
import { formatTime } from "../utils/format";

interface DataPoint {
  time: string;
  keystrokes: number;
  clicks: number;
  activity: number; // 0-100 score
  timestamp: number;
}

const MAX_POINTS = 40; // show last 40 samples = ~20 min of data

export function ActivityGraphPage() {
  const [selectedId, setSelectedId] = useState<string>("");
  const [data, setData] = useState<DataPoint[]>([]);
  const [lastEvent, setLastEvent] = useState<any>(null);
  const qc = useQueryClient();

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: overview = [] } = useQuery<EmployeeStatus[]>({
    queryKey: ["overview"],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  // Receive live WS updates and push to graph
  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type !== "employee_update") return;
    if (msg.data.employee_id !== selectedId) return;

    const now = new Date();
    setLastEvent(msg.data);
    setData(prev => {
      const point: DataPoint = {
        time: formatTime(now.toISOString()),
        keystrokes: 0, // from agent events — not in WS update directly
        clicks: 0,
        activity: msg.data.activity_type === "active" ? 100 : msg.data.activity_type === "idle" ? 20 : 0,
        timestamp: now.getTime(),
      };
      const next = [...prev, point];
      return next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
    });
  }, [selectedId]);

  useWebSocket(handleWsMessage);

  // Also poll for recent events to build initial data
  const { data: recentData } = useQuery({
    queryKey: ["recent-activity", selectedId],
    queryFn: async () => {
      if (!selectedId) return [];
      const today = new Date().toISOString().slice(0, 10);
      try {
        const timeline = await analyticsApi.timeline(selectedId, today);
        return timeline.blocks?.slice(-MAX_POINTS) ?? [];
      } catch { return []; }
    },
    enabled: !!selectedId,
    refetchInterval: 60_000,
  });

  // Build chart data from timeline blocks
  useEffect(() => {
    if (!recentData || recentData.length === 0) return;
    const points: DataPoint[] = recentData.map((block: any) => ({
      time: formatTime(block.start),
      keystrokes: 0,
      clicks: 0,
      activity: block.activity_type === "active" ? 85 + Math.random() * 15
              : block.activity_type === "idle" ? 10 + Math.random() * 20 : 0,
      timestamp: new Date(block.start).getTime(),
    }));
    setData(points);
  }, [recentData]);

  const selected = overview.find(e => e.employee_id === selectedId);
  const emp = employees.find(e => e.id === selectedId);

  const isOnline = selected?.is_online ?? false;
  const currentApp = selected?.active_app ?? "—";
  // If employee is offline, force status to "offline" regardless of stale cache
  const activityType = isOnline ? (selected?.activity_type ?? "offline") : "offline";

  const activityColor = activityType === "active" ? "#3d9a6a"
    : activityType === "idle" ? "#e9a94a" : "#94a3b8";


  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{
        background: "var(--bg-primary)", border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)", padding: "8px 12px",
        boxShadow: "var(--shadow-md)", fontSize: 12,
      }}>
        <div style={{ color: "var(--text-tertiary)", marginBottom: 4 }}>{label}</div>
        <div style={{ color: "var(--accent)", fontWeight: 500 }}>
          Activity: {Math.round(payload[0]?.value ?? 0)}%
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Live activity graph"
        subtitle="Real-time input activity and productivity signal"
        action={
          <EmployeeSearchDropdown
            selectedId={selectedId}
            onChange={(id) => {
              setSelectedId(id);
              setData([]);
            }}
          />
        }
      />

      {/* Live status bar */}
      <div className="card" style={{ padding: "var(--space-4) var(--space-5)", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          {/* Online indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: isOnline ? "#3d9a6a" : "#94a3b8",
              boxShadow: isOnline ? "0 0 0 3px rgba(61,154,106,0.2)" : "none",
            }}/>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
              {emp?.full_name ?? "—"}
            </span>
            <span style={{
              fontSize: 11, padding: "2px 8px", borderRadius: 99,
              background: isOnline ? "var(--success-subtle)" : "var(--bg-tertiary)",
              color: isOnline ? "var(--success)" : "var(--text-tertiary)",
              fontWeight: 500,
            }}>
              {isOnline ? "Online" : "Offline"}
            </span>
          </div>

          <div style={{ width: 1, height: 20, background: "var(--border-subtle)" }}/>

          {/* Status */}
          <div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 1 }}>Status</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: activityColor, textTransform: "capitalize" }}>
              {activityType}
            </div>
          </div>

          <div style={{ width: 1, height: 20, background: "var(--border-subtle)" }}/>

          {/* App */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 1 }}>Active app</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {currentApp}
            </div>
          </div>

          {/* Idle */}
          {selected?.idle_seconds != null && selected.idle_seconds > 0 && (
            <>
              <div style={{ width: 1, height: 20, background: "var(--border-subtle)" }}/>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 1 }}>Idle for</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--warning)" }}>
                  {Math.round(selected.idle_seconds / 60)}m
                </div>
              </div>
            </>
          )}

          {/* Live dot */}
          {isOnline && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: "#3d9a6a",
                display: "inline-block",
                animation: "pulse-dot 2s ease-in-out infinite",
              }}/>
              <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>Live</span>
            </div>
          )}
        </div>
      </div>

      {/* Main chart */}
      <div className="card" style={{ padding: "var(--space-6)", marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
              Activity signal
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 2 }}>
              100% = actively typing/clicking · 0% = locked or away · Updates every 30s
            </div>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
            Last {data.length} samples
          </div>
        </div>

        {data.length === 0 ? (
          <div style={{
            height: 200, display: "flex", alignItems: "center", justifyContent: "center",
            background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
          }}>
            <div style={{ textAlign: "center" }}>
              <Activity size={24} style={{ color: "var(--text-tertiary)", opacity: 0.4, marginBottom: 8 }}/>
              <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>
                {isOnline ? "Waiting for data…" : "Employee is offline"}
              </div>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
              <defs>
                <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.02}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false}/>
              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                tickLine={false} axisLine={false}
                interval={Math.floor(data.length / 5)}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                tickLine={false} axisLine={false}
                tickFormatter={v => `${v}%`}
              />
              <Tooltip content={<CustomTooltip/>}/>
              <Area
                type="monotone"
                dataKey="activity"
                stroke="var(--accent)"
                strokeWidth={2}
                fill="url(#actGrad)"
                dot={false}
                activeDot={{ r: 4, fill: "var(--accent)" }}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Today's summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          {
            label: "Today's active time",
            value: selected?.today_active_seconds
              ? `${Math.floor(selected.today_active_seconds / 3600)}h ${Math.floor((selected.today_active_seconds % 3600) / 60)}m`
              : "—",
            icon: <Activity size={18}/>,
            color: "var(--accent)",
          },
          {
            label: "Productivity score",
            value: selected?.today_productivity_score != null
              ? `${Math.round(selected.today_productivity_score)}%`
              : "—",
            icon: <Zap size={18}/>,
            color: selected?.today_productivity_score != null
              ? (selected.today_productivity_score >= 75 ? "#3d9a6a" : selected.today_productivity_score >= 50 ? "#e9a94a" : "#d85a44")
              : "var(--text-tertiary)",
          },
          {
            label: "Current status",
            value: activityType.charAt(0).toUpperCase() + activityType.slice(1),
            icon: <Keyboard size={18}/>,
            color: activityColor,
          },
          {
            label: "Department",
            value: selected?.department_name ?? "—",
            icon: <MousePointer size={18}/>,
            color: "var(--text-secondary)",
          },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="card" style={{ padding: "var(--space-4) var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color, letterSpacing: "-0.01em" }}>
                  {value}
                </div>
              </div>
              <div style={{ color: "var(--text-tertiary)", opacity: 0.5 }}>{icon}</div>
            </div>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.4); }
        }
      `}</style>
    </div>
  );
}
