import React, { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Monitor, RefreshCw, Maximize2, X } from "lucide-react";
import { employeesApi, api } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { OnlineBadge } from "../components/ui/OnlineBadge";
import { analyticsApi } from "../api/client";
import type { EmployeeStatus } from "../types";
import { formatTime } from "../utils/format";

export function LiveScreensPage() {
  const [selected, setSelected] = useState<{ url: string; name: string } | null>(null);
  const [tick, setTick] = useState(0);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(interval);
  }, []);

  const { data: overview = [] } = useQuery<EmployeeStatus[]>({
    queryKey: ["overview"],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  const online = overview.filter((e) => e.is_online);

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Live screens"
        subtitle={`${online.length} machine${online.length !== 1 ? "s" : ""} online`}
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              Auto-refreshes every 30s
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => setTick((t) => t + 1)}>
              <RefreshCw size={13} /> Refresh now
            </button>
          </div>
        }
      />

      {online.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon"><Monitor size={32} /></div>
          <div className="empty-state-title">No machines online</div>
          <div className="empty-state-body">
            Screenshots appear here when employees are active. Make sure agents are running and approved.
          </div>
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 16,
        }}>
          {online.map((emp) => (
            <ScreenCard
              key={emp.employee_id}
              employee={emp}
              tick={tick}
              onExpand={(url) => setSelected({ url, name: emp.employee_name })}
            />
          ))}
        </div>
      )}

      {/* Full-screen modal */}
      {selected && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 1000,
            background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 24,
          }}
          onClick={() => setSelected(null)}
        >
          <div
            style={{ position: "relative", maxWidth: "90vw", maxHeight: "90vh" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              marginBottom: 8,
            }}>
              <span style={{ color: "#fff", fontSize: 14, fontWeight: 500 }}>
                {selected.name}
              </span>
              <button
                onClick={() => setSelected(null)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#fff", padding: 4 }}
              >
                <X size={20} />
              </button>
            </div>
            <img
              src={selected.url}
              alt={selected.name}
              style={{
                maxWidth: "85vw", maxHeight: "80vh",
                borderRadius: 8,
                display: "block",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ScreenCard({
  employee, tick, onExpand,
}: {
  employee: EmployeeStatus;
  tick: number;
  onExpand: (url: string) => void;
}) {
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    api.get(`/screenshots/${employee.employee_id}?limit=1&sort=desc`)
      .then(async (r) => {
        if (cancelled) return;
        const shots = r.data?.items || r.data || [];
        if (shots.length > 0 && shots[0].file_exists !== false) {
          // Fetch image via authenticated API as blob to bypass cookie issues
          try {
            const imgResp = await api.get(`/screenshots/view/${shots[0].id}`, {
              responseType: "blob",
            });
            if (cancelled) return;
            const blobUrl = URL.createObjectURL(imgResp.data);
            setScreenshotUrl(blobUrl);
          } catch {
            if (!cancelled) setScreenshotUrl(null);
          }
        } else {
          setScreenshotUrl(null);
        }
        if (!cancelled) setLoading(false);
      })
      .catch(() => {
        if (!cancelled) { setError(true); setLoading(false); }
      });

    return () => {
      cancelled = true;
      // Clean up previous blob URL
      setScreenshotUrl((prev) => { if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev); return null; });
    };
  }, [employee.employee_id, tick]);

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px",
        borderBottom: "1px solid var(--border-subtle)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <OnlineBadge online={employee.is_online} showLabel={false} size="sm" />
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
              {employee.employee_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
              {employee.active_app ?? "No app detected"}
            </div>
          </div>
        </div>
        {screenshotUrl && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => onExpand(screenshotUrl)}
            title="View full size"
          >
            <Maximize2 size={13} />
          </button>
        )}
      </div>

      {/* Screenshot area */}
      <div style={{
        aspectRatio: "16/9",
        background: "var(--bg-secondary)",
        position: "relative",
        overflow: "hidden",
        cursor: screenshotUrl ? "pointer" : "default",
      }}
        onClick={() => screenshotUrl && onExpand(screenshotUrl)}
      >
        {loading ? (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div className="skeleton" style={{ width: "80%", height: "60%", borderRadius: 8 }} />
          </div>
        ) : screenshotUrl ? (
          <img
            src={screenshotUrl}
            alt={employee.employee_name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={() => setError(true)}
          />
        ) : (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            gap: 8,
          }}>
            <Monitor size={28} style={{ color: "var(--text-tertiary)", opacity: 0.4 }} />
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              No screenshot yet
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", textAlign: "center", maxWidth: 180 }}>
              Enable screenshot policy to capture screens
            </div>
          </div>
        )}

        {/* Activity overlay */}
        {employee.activity_type && (
          <div style={{
            position: "absolute", bottom: 8, right: 8,
            background: "rgba(0,0,0,0.6)",
            color: "#fff",
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: 99,
            backdropFilter: "blur(4px)",
          }}>
            {employee.activity_type}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: "8px 14px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {employee.last_seen ? `Last seen ${formatTime(employee.last_seen)}` : "No data"}
        </div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {employee.department_name ?? ""}
        </div>
      </div>
    </div>
  );
}
