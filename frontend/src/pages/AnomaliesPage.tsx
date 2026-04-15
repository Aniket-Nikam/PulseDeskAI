import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle, Info, Shield, Clock, Zap, Globe, Settings, X, Save } from "lucide-react";
import { analyticsApi, settingsApi, employeesApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Anomaly, Employee } from "../types";
import { formatDate } from "../utils/format";

const ANOMALY_CONFIG: Record<string, {
  icon: React.ReactNode;
  title: string;
  use_case: string;
  risk: string;
  action: string;
  severity_default: string;
  color: string;
}> = {
  excessive_idle: {
    icon: <Clock size={16} />,
    title: "Excessive idle time",
    use_case: "Employee away from desk for 45+ minutes during work hours with no keyboard or mouse input.",
    risk: "Unattended device is a security risk. May indicate disengagement or personal issues.",
    action: "Check in with the employee. If recurring, review break schedule and workload.",
    severity_default: "medium",
    color: "#f59e0b",
  },
  rapid_app_switching: {
    icon: <Zap size={16} />,
    title: "Rapid app switching",
    use_case: "Employee switching between 4+ different applications per minute — a pattern of distraction.",
    risk: "Indicates inability to focus. Reduces output quality. May indicate multitasking overload.",
    action: "Review task assignments. Schedule dedicated focus time. Reduce interruptions.",
    severity_default: "low",
    color: "#8b5cf6",
  },
  after_hours_activity: {
    icon: <Shield size={16} />,
    title: "After-hours activity",
    use_case: "Active computer use detected between 10PM and 6AM — outside normal working hours.",
    risk: "Burnout risk if recurring. Could indicate unauthorized access or compromised device.",
    action: "Verify if approved overtime. Cross-check with physical access logs if available.",
    severity_default: "medium",
    color: "#3b82f6",
  },
  unusual_app_usage: {
    icon: <Globe size={16} />,
    title: "Policy violation",
    use_case: "Time spent on entertainment, gaming, or social media. Or access to a blocked domain.",
    risk: "Lost productivity. Blocked sites may be data exfiltration vectors or security risks.",
    action: "First offense: informal conversation. Repeated: formal HR process per company policy.",
    severity_default: "medium",
    color: "#ef4444",
  },
};

const SEVERITY_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  low: { bg: "var(--warning-subtle)", text: "var(--warning)", label: "Low — review weekly" },
  medium: { bg: "#fff7ed", text: "#c2410c", label: "Medium — review today" },
  high: { bg: "var(--danger-subtle)", text: "var(--danger)", label: "High — immediate" },
};

export function AnomaliesPage() {
  const qc = useQueryClient();
  const [showReviewed, setShowReviewed] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [showSettings, setShowSettings] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState("");

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: anomalies = [], isLoading } = useQuery<Anomaly[]>({
    queryKey: ["anomalies", showReviewed, selectedEmployee],
    queryFn: () =>
      analyticsApi.anomalies({
        ...(showReviewed ? {} : { is_reviewed: false }),
        employee_id: selectedEmployee || undefined,
      }),
    refetchInterval: 15_000,
  });

  const review = useMutation({
    mutationFn: analyticsApi.reviewAnomaly,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["anomalies"] }),
  });

  const filtered = filter === "all" ? anomalies : anomalies.filter(a => a.anomaly_type === filter);
  const counts = anomalies.reduce((acc, a) => {
    acc[a.anomaly_type] = (acc[a.anomaly_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Anomalies"
        subtitle="Behavioral alerts — what they mean and what to do"
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn btn-secondary" onClick={() => setShowSettings(true)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Settings size={14} /> Configure thresholds
            </button>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "var(--text-secondary)" }}>
              <input type="checkbox" checked={showReviewed} onChange={e => setShowReviewed(e.target.checked)} />
              Show reviewed
            </label>
          </div>
        }
      />

      {/* Settings modal */}
      {showSettings && <AnomalySettingsModal onClose={() => setShowSettings(false)} />}

      {/* What is each anomaly — explainer cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 24 }}>
        {Object.entries(ANOMALY_CONFIG).map(([type, cfg]) => {
          const count = counts[type] || 0;
          const sev = SEVERITY_STYLE[cfg.severity_default];
          return (
            <div key={type} className="card" style={{ padding: "var(--space-4) var(--space-5)", borderLeft: `3px solid ${cfg.color}`, borderRadius: "0 var(--radius-xl) var(--radius-xl) 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, color: cfg.color }}>
                  {cfg.icon}
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{cfg.title}</span>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {count > 0 && <span className="badge badge-red">{count} active</span>}
                  <span className="badge" style={{ background: sev.bg, color: sev.text, fontSize: 10 }}>
                    {cfg.severity_default}
                  </span>
                </div>
              </div>
              <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 4 }}>
                {cfg.use_case}
              </p>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", fontStyle: "italic" }}>
                Action: {cfg.action}
              </div>
            </div>
          );
        })}
      </div>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, flexWrap: "wrap" }}>
        {[["all", "All"], ...Object.entries(ANOMALY_CONFIG).map(([k, v]) => [k, v.title])].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`btn btn-sm ${filter === key ? "btn-primary" : "btn-ghost"}`}
          >
            {label} {key !== "all" && counts[key] ? `(${counts[key]})` : ""}
          </button>
        ))}
      </div>

      <div style={{ marginBottom: 16, maxWidth: 340 }}>
        <select
          className="input"
          value={selectedEmployee}
          onChange={(event) => setSelectedEmployee(event.target.value)}
        >
          <option value="">All employees</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
      </div>

      {/* Anomaly list */}
      <div className="card" style={{ overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ padding: "var(--space-8)" }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 56, marginBottom: 8, borderRadius: "var(--radius-md)" }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon"><AlertTriangle size={32} /></div>
            <div className="empty-state-title">
              {showReviewed ? "No anomalies" : "No unreviewed anomalies"}
            </div>
            <div className="empty-state-body">
              {showReviewed
                ? "No behavioral anomalies have been detected yet. The system is watching."
                : "All anomalies reviewed. Toggle above to see history."}
            </div>
          </div>
        ) : (
          <div>
            {filtered.map(a => {
              const cfg = ANOMALY_CONFIG[a.anomaly_type];
              const meta = a.metadata as any ?? {};
              const severity = meta.severity_override ?? meta.severity ?? cfg?.severity_default ?? "medium";
              const sev = SEVERITY_STYLE[severity] ?? SEVERITY_STYLE.medium;
              const isOpen = expanded === a.id;

              return (
                <div
                  key={a.id}
                  style={{
                    borderBottom: "1px solid var(--border-subtle)",
                    opacity: a.is_reviewed ? 0.6 : 1,
                  }}
                >
                  {/* Main row */}
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer" }}
                    onClick={() => setExpanded(isOpen ? null : a.id)}
                  >
                    <div style={{ color: cfg?.color ?? "var(--warning)", flexShrink: 0 }}>
                      {cfg?.icon ?? <AlertTriangle size={16} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                          {a.employee_name ?? "Unknown"}
                        </span>
                        <span className="badge" style={{ background: sev.bg, color: sev.text, fontSize: 10 }}>
                          {sev.label}
                        </span>
                        {a.is_reviewed && <span className="badge badge-green" style={{ fontSize: 10 }}>Reviewed</span>}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {a.description}
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)", flexShrink: 0, textAlign: "right" }}>
                      <div>{formatDate(a.detected_at)}</div>
                      <div style={{ fontSize: 10, marginTop: 2 }}>{isOpen ? "▲ less" : "▼ more"}</div>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isOpen && (
                    <div style={{
                      padding: "0 16px 16px 44px",
                      background: "var(--bg-secondary)",
                      borderTop: "1px solid var(--border-subtle)",
                    }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, paddingTop: 12 }}>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>What happened</div>
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                            {cfg?.use_case ?? "Behavioral anomaly detected"}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Risk</div>
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                            {meta.risk ?? cfg?.risk ?? "See anomaly type description"}
                          </div>
                        </div>
                        <div style={{ gridColumn: "1 / -1" }}>
                          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Recommended action</div>
                          <div style={{
                            fontSize: 13, color: "var(--accent-text)",
                            background: "var(--accent-subtle)",
                            padding: "8px 12px", borderRadius: "var(--radius-md)", lineHeight: 1.5,
                          }}>
                            {meta.recommended_action ?? cfg?.action ?? "Review and take appropriate action"}
                          </div>
                        </div>
                      </div>
                      {!a.is_reviewed && (
                        <button
                          className="btn btn-sm btn-secondary"
                          style={{ marginTop: 12 }}
                          onClick={() => review.mutate(a.id)}
                          disabled={review.isPending}
                        >
                          <CheckCircle size={13} /> Mark as reviewed
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


/* ─── Anomaly Settings Modal ────────────────────────────────────────────────── */

const SETTINGS_GROUPS = [
  {
    title: "Idle & Distraction",
    icon: <Clock size={14} />,
    color: "#f59e0b",
    fields: [
      { key: "excessive_idle_threshold_minutes", label: "Excessive idle threshold", unit: "min", desc: "Idle time before alert triggers during work hours", min: 5, max: 240 },
      { key: "distraction_threshold_minutes", label: "Distraction threshold", unit: "min", desc: "Time on distraction apps per batch before alert", min: 1, max: 120 },
      { key: "after_hours_min_active_minutes", label: "After-hours activity", unit: "min", desc: "Active time outside work hours before alert", min: 1, max: 60 },
    ],
  },
  {
    title: "Rapid App Switching",
    icon: <Zap size={14} />,
    color: "#8b5cf6",
    fields: [
      { key: "rapid_switching_high_threshold", label: "High threshold", unit: "switches", desc: "Switches per window → low severity", min: 1, max: 50 },
      { key: "rapid_switching_critical_threshold", label: "Critical threshold", unit: "switches", desc: "Switches per window → high severity", min: 1, max: 100 },
      { key: "rapid_switching_window_seconds", label: "Detection window", unit: "sec", desc: "Time window for measuring switch rate", min: 10, max: 600 },
    ],
  },
];

function AnomalySettingsModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Record<string, number>>({});
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["anomaly-settings"],
    queryFn: settingsApi.get,
  });

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const save = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      setMsg({ type: "success", text: "Settings saved successfully." });
      qc.invalidateQueries({ queryKey: ["anomaly-settings"] });
    },
    onError: (err: any) => {
      setMsg({ type: "error", text: err?.response?.data?.detail ?? "Failed to save settings." });
    },
  });

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          width: 520, maxHeight: "85vh", overflow: "auto",
          padding: 0,
          boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "16px 20px", borderBottom: "1px solid var(--border-subtle)",
        }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <Settings size={16} />
              Anomaly Detection Settings
            </h2>
            <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: "2px 0 0 0" }}>
              Configure when anomalies are triggered
            </p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "16px 20px" }}>
          {isLoading ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-tertiary)" }}>Loading settings…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {SETTINGS_GROUPS.map(group => (
                <div key={group.title}>
                  {/* Group header */}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 6,
                    fontSize: 12, fontWeight: 600, color: group.color,
                    textTransform: "uppercase", letterSpacing: "0.04em",
                    marginBottom: 8, paddingBottom: 6,
                    borderBottom: `2px solid ${group.color}20`,
                  }}>
                    {group.icon}
                    {group.title}
                  </div>

                  {/* Fields */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                    {group.fields.map((f, i) => (
                      <div key={f.key} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "10px 12px",
                        background: i % 2 === 0 ? "var(--bg-secondary)" : "transparent",
                        borderRadius: "var(--radius-sm)",
                      }}>
                        <div style={{ flex: 1, marginRight: 16 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>{f.label}</div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 1 }}>{f.desc}</div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                          <input
                            type="number"
                            className="input"
                            style={{ width: 64, textAlign: "center", padding: "3px 6px", fontSize: 13 }}
                            min={f.min}
                            max={f.max}
                            value={form[f.key] ?? ""}
                            onChange={e => setForm(prev => ({ ...prev, [f.key]: parseInt(e.target.value) || 0 }))}
                          />
                          <span style={{ fontSize: 10, color: "var(--text-tertiary)", width: 48 }}>{f.unit}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {msg && (
                <div style={{
                  padding: "8px 12px", fontSize: 13, borderRadius: "var(--radius-md)",
                  background: msg.type === "success" ? "var(--success-subtle)" : "var(--danger-subtle)",
                  color: msg.type === "success" ? "var(--success)" : "var(--danger)",
                }}>
                  {msg.text}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", gap: 8, justifyContent: "flex-end",
          padding: "12px 20px", borderTop: "1px solid var(--border-subtle)",
        }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={() => { setMsg(null); save.mutate(form); }}
            disabled={save.isPending}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Save size={14} />
            {save.isPending ? "Saving…" : "Save settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
