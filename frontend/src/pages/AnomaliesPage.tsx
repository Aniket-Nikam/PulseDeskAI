import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle, Info, Shield, Clock, Zap, Globe } from "lucide-react";
import { analyticsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Anomaly } from "../types";
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

  const { data: anomalies = [], isLoading } = useQuery<Anomaly[]>({
    queryKey: ["anomalies", showReviewed],
    queryFn: () => analyticsApi.anomalies(showReviewed ? {} : { is_reviewed: false }),
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
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={showReviewed} onChange={e => setShowReviewed(e.target.checked)} />
            Show reviewed
          </label>
        }
      />

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
