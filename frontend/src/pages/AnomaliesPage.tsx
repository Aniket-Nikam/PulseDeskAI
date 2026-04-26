import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Clock,
  Globe,
  Save,
  Search,
  Settings,
  Shield,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { aiApi, analyticsApi, settingsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Anomaly, AnomalyRecommendation } from "../types";
import { formatDate } from "../utils/format";

type SeverityLevel = "low" | "medium" | "high";

interface AnomalyConfigEntry {
  icon: React.ReactNode;
  title: string;
  useCase: string;
  risk: string;
  action: string;
  severityDefault: SeverityLevel;
  color: string;
}

const ANOMALY_CONFIG: Record<string, AnomalyConfigEntry> = {
  excessive_idle: {
    icon: <Clock size={16} />,
    title: "Excessive idle time",
    useCase: "No keyboard or mouse input for 45+ minutes during work hours.",
    risk: "Unattended devices increase security risk and can indicate disengagement.",
    action: "Check in with the employee and verify workload or break patterns.",
    severityDefault: "medium",
    color: "#f59e0b",
  },
  rapid_app_switching: {
    icon: <Zap size={16} />,
    title: "Rapid app switching",
    useCase: "Frequent app changes in short intervals indicating context switching.",
    risk: "Lower focus quality and lower task completion consistency.",
    action: "Support focused work blocks and reduce interruptions.",
    severityDefault: "low",
    color: "#6366f1",
  },
  after_hours_activity: {
    icon: <Shield size={16} />,
    title: "After-hours activity",
    useCase: "Sustained usage detected outside configured work hours.",
    risk: "Potential burnout risk or policy/security compliance concern.",
    action: "Validate overtime approval and check for recurring after-hours patterns.",
    severityDefault: "medium",
    color: "#2563eb",
  },
  unusual_app_usage: {
    icon: <Globe size={16} />,
    title: "Policy violation",
    useCase: "Blocked site access or repeated distraction category usage.",
    risk: "Productivity loss and possible policy non-compliance risk.",
    action: "Run policy coaching first, then escalate if the trend continues.",
    severityDefault: "medium",
    color: "#dc2626",
  },
};

const SEVERITY_STYLE: Record<SeverityLevel, { bg: string; text: string; label: string }> = {
  low: { bg: "#ecfdf5", text: "#047857", label: "Low" },
  medium: { bg: "#fffbeb", text: "#b45309", label: "Medium" },
  high: { bg: "#fef2f2", text: "#b91c1c", label: "High" },
};

interface EmployeeAnomalyGroup {
  employee_id: string;
  employee_name: string;
  violations: Anomaly[];
  violationCount: number;
  reviewedCount: number;
  unreviewedCount: number;
  severityCounts: Record<SeverityLevel, number>;
  hasHighSeverity: boolean;
  lastDetectedAt: string | null;
}

function getMetadataValue(metadata: Record<string, unknown> | null | undefined, key: string): unknown {
  return (metadata ?? {})[key];
}

function getMetadataString(metadata: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = getMetadataValue(metadata, key);
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function getBlockedDomains(metadata: Record<string, unknown> | null | undefined): string[] {
  const blockedDomains = getMetadataValue(metadata, "blocked_domains");
  if (Array.isArray(blockedDomains)) {
    return blockedDomains.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  const domain = getMetadataString(metadata, "domain");
  return domain ? [domain] : [];
}

function getSeverity(anomaly: Anomaly): SeverityLevel {
  const override = getMetadataString(anomaly.metadata, "severity_override");
  const severity = getMetadataString(anomaly.metadata, "severity");
  const fallback = ANOMALY_CONFIG[anomaly.anomaly_type]?.severityDefault ?? "medium";
  const normalized = (override ?? severity ?? fallback).toLowerCase();
  if (normalized === "low" || normalized === "high" || normalized === "medium") {
    return normalized;
  }
  return "medium";
}

function summarizeEmployeeViolations(
  employeeId: string,
  employeeName: string,
  violations: Anomaly[],
): EmployeeAnomalyGroup {
  const severityCounts: Record<SeverityLevel, number> = {
    low: 0,
    medium: 0,
    high: 0,
  };

  let reviewedCount = 0;
  let lastDetectedAt: string | null = null;

  for (const anomaly of violations) {
    const severity = getSeverity(anomaly);
    severityCounts[severity] += 1;
    if (anomaly.is_reviewed) reviewedCount += 1;

    if (!lastDetectedAt || anomaly.detected_at > lastDetectedAt) {
      lastDetectedAt = anomaly.detected_at;
    }
  }

  return {
    employee_id: employeeId,
    employee_name: employeeName,
    violations: [...violations].sort((a, b) => b.detected_at.localeCompare(a.detected_at)),
    violationCount: violations.length,
    reviewedCount,
    unreviewedCount: violations.length - reviewedCount,
    severityCounts,
    hasHighSeverity: severityCounts.high > 0,
    lastDetectedAt,
  };
}

function sortGroups(a: EmployeeAnomalyGroup, b: EmployeeAnomalyGroup): number {
  if (a.hasHighSeverity !== b.hasHighSeverity) {
    return a.hasHighSeverity ? -1 : 1;
  }
  if (a.unreviewedCount !== b.unreviewedCount) {
    return b.unreviewedCount - a.unreviewedCount;
  }
  if (a.violationCount !== b.violationCount) {
    return b.violationCount - a.violationCount;
  }
  return (b.lastDetectedAt ?? "").localeCompare(a.lastDetectedAt ?? "");
}

function buildHeuristicRecommendation(group: EmployeeAnomalyGroup): string {
  if (group.violationCount === 0) {
    return "No violations made. Continue regular monitoring.";
  }
  if (group.severityCounts.high >= 3 || group.unreviewedCount >= 8) {
    return "High risk trend. Schedule a manager check-in today and define a corrective plan with clear follow-up dates.";
  }
  if (group.severityCounts.high >= 1 || group.unreviewedCount >= 4) {
    return "Medium risk trend. Review policy expectations this week and monitor this employee daily for the next 7 days.";
  }
  if (group.violationCount >= 5) {
    return "Moderate recurring pattern. Run a coaching discussion and review progress in the next weekly sync.";
  }
  return "Low risk trend. Keep monitoring and reinforce expected behavior during regular check-ins.";
}

function formatDateTime(isoDate: string): string {
  return new Date(isoDate).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(isoDate: string): string {
  return new Date(isoDate).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface EmployeeViolationsCardProps {
  group: EmployeeAnomalyGroup;
  isExpanded: boolean;
  showReviewed: boolean;
  onToggle: () => void;
  onReview: (anomalyId: string) => void;
  reviewPending: boolean;
}

function EmployeeViolationsCard({
  group,
  isExpanded,
  showReviewed,
  onToggle,
  onReview,
  reviewPending,
}: EmployeeViolationsCardProps) {
  const [expandedViolation, setExpandedViolation] = useState<string | null>(null);

  useEffect(() => {
    if (!isExpanded) {
      setExpandedViolation(null);
    }
  }, [isExpanded]);

  const recommendation = useQuery<AnomalyRecommendation>({
    queryKey: [
      "anomaly-recommendation",
      group.employee_id,
      group.violationCount,
      group.severityCounts.high,
      group.severityCounts.medium,
      group.severityCounts.low,
      group.unreviewedCount,
    ],
    queryFn: () => aiApi.anomalyRecommendation(group.employee_id),
    enabled: isExpanded && group.violationCount > 0,
    staleTime: 3 * 60 * 1000,
    retry: 1,
  });

  const recommendationText = recommendation.data?.recommendation ?? buildHeuristicRecommendation(group);
  const recommendationSource = recommendation.data?.source ?? "heuristic";

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: "100%",
          border: "none",
          background: group.hasHighSeverity
            ? "linear-gradient(90deg, rgba(220, 38, 38, 0.08), rgba(220, 38, 38, 0.02))"
            : "linear-gradient(90deg, rgba(37, 99, 235, 0.08), rgba(37, 99, 235, 0.02))",
          padding: "14px 16px",
          borderLeft: `4px solid ${group.hasHighSeverity ? "var(--danger)" : "var(--accent)"}`,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)" }}>{group.employee_name}</span>
            <span className="badge badge-blue">
              {group.violationCount} violation{group.violationCount !== 1 ? "s" : ""}
            </span>
            {group.unreviewedCount > 0 && (
              <span className="badge badge-red">
                {group.unreviewedCount} unreviewed
              </span>
            )}
            {group.reviewedCount > 0 && (
              <span className="badge badge-green">
                {group.reviewedCount} reviewed
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 12 }}>
            <span className="badge" style={{ background: SEVERITY_STYLE.high.bg, color: SEVERITY_STYLE.high.text }}>
              High: {group.severityCounts.high}
            </span>
            <span className="badge" style={{ background: SEVERITY_STYLE.medium.bg, color: SEVERITY_STYLE.medium.text }}>
              Medium: {group.severityCounts.medium}
            </span>
            <span className="badge" style={{ background: SEVERITY_STYLE.low.bg, color: SEVERITY_STYLE.low.text }}>
              Low: {group.severityCounts.low}
            </span>
            {group.lastDetectedAt && (
              <span style={{ color: "var(--text-tertiary)" }}>
                Last violation: {formatDateTime(group.lastDetectedAt)}
              </span>
            )}
          </div>
        </div>
        <ChevronDown
          size={18}
          style={{
            color: "var(--text-secondary)",
            transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
            flexShrink: 0,
          }}
        />
      </button>

      {isExpanded && (
        <div style={{ padding: "16px", borderTop: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", gap: 14 }}>
          <div
            style={{
              padding: "12px 14px",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(37, 99, 235, 0.22)",
              background: "linear-gradient(120deg, rgba(37, 99, 235, 0.08), rgba(37, 99, 235, 0.02))",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, color: "var(--accent-text)" }}>
                <Sparkles size={14} />
                Recommended action
              </div>
              <span className="badge badge-gray" style={{ fontSize: 10 }}>
                Source: {recommendationSource}
              </span>
            </div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {recommendationText}
            </div>
            {recommendation.isError && (
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--warning)" }}>
                AI recommendation unavailable right now. Showing heuristic fallback.
              </div>
            )}
          </div>

          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Violation details
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {group.violations.map((anomaly) => {
              const config = ANOMALY_CONFIG[anomaly.anomaly_type];
              const severity = getSeverity(anomaly);
              const severityStyle = SEVERITY_STYLE[severity];
              const blockedDomains = getBlockedDomains(anomaly.metadata);
              const isViolationExpanded = expandedViolation === anomaly.id;
              const risk = getMetadataString(anomaly.metadata, "risk") ?? config?.risk ?? "Review anomaly details.";
              const recommendedAction =
                getMetadataString(anomaly.metadata, "recommended_action") ??
                config?.action ??
                "Review and apply policy action.";

              return (
                <div
                  key={anomaly.id}
                  style={{
                    border: "1px solid var(--border-subtle)",
                    borderLeft: `3px solid ${config?.color ?? "var(--accent)"}`,
                    borderRadius: "var(--radius-md)",
                    background: isViolationExpanded ? "var(--bg-secondary)" : "var(--bg-primary)",
                    overflow: "hidden",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setExpandedViolation(isViolationExpanded ? null : anomaly.id)}
                    style={{
                      width: "100%",
                      border: "none",
                      background: "transparent",
                      padding: "11px 12px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ color: config?.color ?? "var(--accent)", flexShrink: 0 }}>
                      {config?.icon ?? <AlertTriangle size={16} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 3 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                          {config?.title ?? anomaly.anomaly_type}
                        </span>
                        <span className="badge" style={{ background: severityStyle.bg, color: severityStyle.text }}>
                          {severityStyle.label}
                        </span>
                        {anomaly.is_reviewed && <span className="badge badge-green">Reviewed</span>}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{anomaly.description}</div>
                    </div>
                    <div style={{ textAlign: "right", fontSize: 11, color: "var(--text-tertiary)", flexShrink: 0 }}>
                      <div>{formatDate(anomaly.detected_at)}</div>
                      <div>{formatTime(anomaly.detected_at)}</div>
                    </div>
                  </button>

                  {isViolationExpanded && (
                    <div style={{ borderTop: "1px solid var(--border-subtle)", padding: "10px 12px 12px 40px" }}>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                          gap: 10,
                          marginBottom: 10,
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>Detected at</div>
                          <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>
                            {formatDateTime(anomaly.detected_at)}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>Status</div>
                          <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>
                            {anomaly.is_reviewed ? "Reviewed" : "Pending review"}
                          </div>
                        </div>
                        {blockedDomains.length > 0 && (
                          <div>
                            <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>Blocked site(s)</div>
                            <div style={{ fontSize: 12, color: "var(--danger)", fontFamily: "var(--font-mono)" }}>
                              {blockedDomains.join(", ")}
                            </div>
                          </div>
                        )}
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                        <div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>What happened</div>
                          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                            {config?.useCase ?? "Behavioral anomaly detected."}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>Risk</div>
                          <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{risk}</div>
                        </div>
                        <div style={{ gridColumn: "1 / -1" }}>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 2 }}>Recommended action</div>
                          <div
                            style={{
                              fontSize: 12,
                              color: "var(--accent-text)",
                              lineHeight: 1.55,
                              background: "var(--accent-subtle)",
                              border: "1px solid rgba(37, 99, 235, 0.2)",
                              borderRadius: "var(--radius-md)",
                              padding: "8px 10px",
                            }}
                          >
                            {recommendedAction}
                          </div>
                        </div>
                      </div>

                      {!anomaly.is_reviewed && !showReviewed && (
                        <button
                          className="btn btn-sm btn-secondary"
                          style={{ marginTop: 10 }}
                          onClick={(event) => {
                            event.stopPropagation();
                            onReview(anomaly.id);
                          }}
                          disabled={reviewPending}
                        >
                          <CheckCircle size={13} />
                          Mark as reviewed
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export function AnomaliesPage() {
  const queryClient = useQueryClient();
  const [showReviewed, setShowReviewed] = useState(false);
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  const anomaliesQuery = useQuery<Anomaly[]>({
    queryKey: ["anomalies", "grouped", showReviewed],
    queryFn: () =>
      analyticsApi.anomalies({
        is_reviewed: showReviewed,
        limit: 1000,
      }),
    refetchInterval: 15_000,
  });

  const reviewMutation = useMutation({
    mutationFn: analyticsApi.reviewAnomaly,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["anomalies"] });
    },
  });

  const anomalies = anomaliesQuery.data ?? [];

  const employeeGroups = useMemo(() => {
    const grouped = new Map<string, { employeeName: string; violations: Anomaly[] }>();
    for (const anomaly of anomalies) {
      const employeeId = anomaly.employee_id;
      if (!employeeId) continue;
      const employeeName = anomaly.employee_name?.trim() || "Unknown employee";
      const existing = grouped.get(employeeId);
      if (!existing) {
        grouped.set(employeeId, { employeeName, violations: [anomaly] });
      } else {
        existing.violations.push(anomaly);
      }
    }

    const groups: EmployeeAnomalyGroup[] = [];
    for (const [employeeId, value] of grouped.entries()) {
      groups.push(summarizeEmployeeViolations(employeeId, value.employeeName, value.violations));
    }
    return groups.sort(sortGroups);
  }, [anomalies]);

  const filteredGroups = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    const result = employeeGroups
      .map((group) => {
        const filteredViolations = group.violations.filter((anomaly) => {
          if (filterType !== "all" && anomaly.anomaly_type !== filterType) {
            return false;
          }
          if (filterSeverity !== "all" && getSeverity(anomaly) !== filterSeverity) {
            return false;
          }
          if (!query) {
            return true;
          }
          const blockedDomains = getBlockedDomains(anomaly.metadata).join(" ").toLowerCase();
          return (
            group.employee_name.toLowerCase().includes(query) ||
            anomaly.description.toLowerCase().includes(query) ||
            anomaly.anomaly_type.toLowerCase().includes(query) ||
            blockedDomains.includes(query)
          );
        });

        if (filteredViolations.length === 0) {
          return null;
        }
        return summarizeEmployeeViolations(group.employee_id, group.employee_name, filteredViolations);
      })
      .filter((group): group is EmployeeAnomalyGroup => Boolean(group));

    return result.sort(sortGroups);
  }, [employeeGroups, filterType, filterSeverity, searchQuery]);

  useEffect(() => {
    setExpandedEmployee(null);
  }, [showReviewed, filterType, filterSeverity, searchQuery]);

  const overview = useMemo(() => {
    const severityTotals: Record<SeverityLevel, number> = { low: 0, medium: 0, high: 0 };
    let reviewed = 0;

    for (const anomaly of anomalies) {
      severityTotals[getSeverity(anomaly)] += 1;
      if (anomaly.is_reviewed) reviewed += 1;
    }

    return {
      totalViolations: anomalies.length,
      employees: employeeGroups.length,
      highSeverity: severityTotals.high,
      reviewed,
      unreviewed: anomalies.length - reviewed,
      severityTotals,
    };
  }, [anomalies, employeeGroups.length]);

  const countsByType = useMemo(() => {
    return anomalies.reduce<Record<string, number>>((accumulator, anomaly) => {
      accumulator[anomaly.anomaly_type] = (accumulator[anomaly.anomaly_type] ?? 0) + 1;
      return accumulator;
    }, {});
  }, [anomalies]);

  return (
    <div style={{ padding: "var(--space-8)", display: "flex", flexDirection: "column", gap: 16 }}>
      <PageHeader
        title="Anomalies"
        subtitle="Violations grouped by employee for easier manager and admin review."
        action={
          <button
            className="btn btn-secondary"
            onClick={() => setShowSettings(true)}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Settings size={14} />
            Configure thresholds
          </button>
        }
      />

      {showSettings && <AnomalySettingsModal onClose={() => setShowSettings(false)} />}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(185px, 1fr))", gap: 10 }}>
        <div className="card" style={{ padding: "12px 14px" }}>
          <div className="stat-label">Violations in View</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>{overview.totalViolations}</div>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {showReviewed ? "Reviewed violations only" : "Unreviewed violations only"}
          </div>
        </div>
        <div className="card" style={{ padding: "12px 14px" }}>
          <div className="stat-label">Employees Impacted</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>{overview.employees}</div>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            Employees with at least one violation
          </div>
        </div>
        <div className="card" style={{ padding: "12px 14px" }}>
          <div className="stat-label">High Severity</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--danger)" }}>{overview.highSeverity}</div>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            Needs immediate manager attention
          </div>
        </div>
        <div className="card" style={{ padding: "12px 14px" }}>
          <div className="stat-label">Review Status</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 2 }}>
            <span className="badge badge-green">{overview.reviewed} reviewed</span>
            <span className="badge badge-red">{overview.unreviewed} pending</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 6 }}>
            Track completion by manager/admin
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 10 }}>
        {Object.entries(ANOMALY_CONFIG).map(([type, config]) => {
          const severityStyle = SEVERITY_STYLE[config.severityDefault];
          return (
            <div
              key={type}
              className="card"
              style={{
                padding: "12px",
                borderLeft: `3px solid ${config.color}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", color: config.color }}>
                  {config.icon}
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{config.title}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span className="badge badge-red">{countsByType[type] ?? 0}</span>
                  <span className="badge" style={{ background: severityStyle.bg, color: severityStyle.text }}>
                    {severityStyle.label}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{config.useCase}</div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ padding: 12 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          <div style={{ position: "relative", flex: "1 1 260px", minWidth: 220 }}>
            <Search size={15} style={{ position: "absolute", left: 10, top: 9, color: "var(--text-tertiary)" }} />
            <input
              className="input"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search employee or violation details..."
              style={{ paddingLeft: 34 }}
            />
          </div>
          <select className="input" value={filterType} onChange={(event) => setFilterType(event.target.value)} style={{ width: 190 }}>
            <option value="all">All violation types</option>
            {Object.entries(ANOMALY_CONFIG).map(([type, config]) => (
              <option key={type} value={type}>
                {config.title}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={filterSeverity}
            onChange={(event) => setFilterSeverity(event.target.value)}
            style={{ width: 160 }}
          >
            <option value="all">All severities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 0,
              fontSize: 13,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={showReviewed}
              onChange={(event) => setShowReviewed(event.target.checked)}
            />
            Show reviewed
          </label>
        </div>
      </div>

      {anomaliesQuery.isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="skeleton" style={{ height: 64, borderRadius: "var(--radius-md)" }} />
          ))}
        </div>
      ) : anomaliesQuery.isError ? (
        <div className="card" style={{ padding: "28px 18px", textAlign: "center" }}>
          <AlertTriangle size={28} style={{ color: "var(--danger)", marginBottom: 8 }} />
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Unable to load violations</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Please refresh this page or verify backend connectivity.
          </div>
        </div>
      ) : filteredGroups.length === 0 ? (
        <div className="card" style={{ padding: "30px 18px", textAlign: "center" }}>
          <AlertTriangle size={28} style={{ color: "var(--text-tertiary)", marginBottom: 8 }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
            {anomalies.length === 0 ? "No violations made" : "No violations match current filters"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {anomalies.length === 0
              ? showReviewed
                ? "No reviewed violations are available right now."
                : "No active violations are available right now."
              : "Try clearing search or changing filters."}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filteredGroups.map((group) => (
            <EmployeeViolationsCard
              key={group.employee_id}
              group={group}
              isExpanded={expandedEmployee === group.employee_id}
              showReviewed={showReviewed}
              onToggle={() => setExpandedEmployee(expandedEmployee === group.employee_id ? null : group.employee_id)}
              onReview={(anomalyId) => reviewMutation.mutate(anomalyId)}
              reviewPending={reviewMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const SETTINGS_GROUPS = [
  {
    title: "Idle and distraction",
    icon: <Clock size={14} />,
    color: "#f59e0b",
    fields: [
      {
        key: "excessive_idle_threshold_minutes",
        label: "Excessive idle threshold",
        unit: "min",
        desc: "Idle time before alert triggers during work hours",
        min: 5,
        max: 240,
      },
      {
        key: "distraction_threshold_minutes",
        label: "Distraction threshold",
        unit: "min",
        desc: "Time on distraction apps per batch before alert",
        min: 1,
        max: 120,
      },
      {
        key: "after_hours_min_active_minutes",
        label: "After-hours activity",
        unit: "min",
        desc: "Active time outside work hours before alert",
        min: 1,
        max: 60,
      },
    ],
  },
  {
    title: "Rapid app switching",
    icon: <Zap size={14} />,
    color: "#6366f1",
    fields: [
      {
        key: "rapid_switching_high_threshold",
        label: "High threshold",
        unit: "switches",
        desc: "Switches per window for medium severity",
        min: 1,
        max: 50,
      },
      {
        key: "rapid_switching_critical_threshold",
        label: "Critical threshold",
        unit: "switches",
        desc: "Switches per window for high severity",
        min: 1,
        max: 100,
      },
      {
        key: "rapid_switching_window_seconds",
        label: "Detection window",
        unit: "sec",
        desc: "Time window for measuring switch rate",
        min: 10,
        max: 600,
      },
    ],
  },
];

function AnomalySettingsModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, number>>({});
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const settingsQuery = useQuery<Record<string, number>>({
    queryKey: ["anomaly-settings"],
    queryFn: settingsApi.get,
  });

  useEffect(() => {
    if (settingsQuery.data) {
      setForm(settingsQuery.data);
    }
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      setMessage({ type: "success", text: "Settings saved successfully." });
      queryClient.invalidateQueries({ queryKey: ["anomaly-settings"] });
    },
    onError: (error: unknown) => {
      const errorText =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : "Failed to save settings.";
      setMessage({ type: "error", text: errorText ?? "Failed to save settings." });
    },
  });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          width: 540,
          maxWidth: "100%",
          maxHeight: "88vh",
          overflow: "auto",
          padding: 0,
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 18px",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", display: "flex", gap: 6, alignItems: "center" }}>
              <Settings size={15} />
              Anomaly detection settings
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 2 }}>
              Configure when anomaly alerts should trigger.
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              color: "var(--text-tertiary)",
              cursor: "pointer",
              padding: 2,
            }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: "16px 18px" }}>
          {settingsQuery.isLoading ? (
            <div style={{ padding: "24px 0", textAlign: "center", color: "var(--text-tertiary)" }}>Loading settings...</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {SETTINGS_GROUPS.map((group) => (
                <div key={group.title}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 12,
                      fontWeight: 700,
                      color: group.color,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      borderBottom: `2px solid ${group.color}33`,
                      paddingBottom: 6,
                      marginBottom: 8,
                    }}
                  >
                    {group.icon}
                    {group.title}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                    {group.fields.map((field, index) => (
                      <div
                        key={field.key}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 11px",
                          borderRadius: "var(--radius-sm)",
                          background: index % 2 === 0 ? "var(--bg-secondary)" : "transparent",
                        }}
                      >
                        <div style={{ flex: 1, marginRight: 12 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{field.label}</div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>{field.desc}</div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <input
                            type="number"
                            min={field.min}
                            max={field.max}
                            className="input"
                            style={{ width: 74, textAlign: "center", padding: "4px 6px", fontSize: 13 }}
                            value={form[field.key] ?? ""}
                            onChange={(event) =>
                              setForm((previous) => ({
                                ...previous,
                                [field.key]: Number.parseInt(event.target.value, 10) || 0,
                              }))
                            }
                          />
                          <span style={{ fontSize: 10, color: "var(--text-tertiary)", width: 52 }}>{field.unit}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {message && (
                <div
                  style={{
                    padding: "9px 11px",
                    borderRadius: "var(--radius-md)",
                    fontSize: 13,
                    color: message.type === "success" ? "var(--success)" : "var(--danger)",
                    background: message.type === "success" ? "var(--success-subtle)" : "var(--danger-subtle)",
                  }}
                >
                  {message.text}
                </div>
              )}
            </div>
          )}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            borderTop: "1px solid var(--border-subtle)",
            padding: "12px 18px",
          }}
        >
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={() => {
              setMessage(null);
              saveMutation.mutate(form);
            }}
            disabled={saveMutation.isPending}
          >
            <Save size={14} />
            {saveMutation.isPending ? "Saving..." : "Save settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
