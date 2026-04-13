import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Monitor, RefreshCw } from "lucide-react";
import { devicesApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { OnlineBadge } from "../components/ui/OnlineBadge";
import type { Device } from "../types";
import { formatDate, platformIcon } from "../utils/format";

export function DevicesPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"all" | "pending">("all");

  const { data: allDevices = [], isLoading } = useQuery<Device[]>({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
    refetchInterval: 30_000,
  });

  const { data: pending = [] } = useQuery<Device[]>({
    queryKey: ["devices-pending"],
    queryFn: devicesApi.pending,
    refetchInterval: 10_000,
  });

  const approve = useMutation({
    mutationFn: devicesApi.approve,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["devices"] }); qc.invalidateQueries({ queryKey: ["devices-pending"] }); },
  });

  const revoke = useMutation({
    mutationFn: devicesApi.revoke,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["devices"] }); },
  });

  const shown = tab === "pending" ? pending : allDevices;

  function statusBadge(d: Device) {
    const map: Record<string, string> = {
      approved: "badge-green",
      pending: "badge-amber",
      revoked: "badge-red",
      suspended: "badge-gray",
    };
    return <span className={`badge ${map[d.status] ?? "badge-gray"}`}>{d.status}</span>;
  }

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Devices"
        subtitle="Enrolled devices and enrollment requests"
        action={
          <button className="btn btn-secondary btn-sm" onClick={() => qc.invalidateQueries({ queryKey: ["devices"] })}>
            <RefreshCw size={13} /> Refresh
          </button>
        }
      />

      {/* Pending banner */}
      {pending.length > 0 && (
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "10px 16px",
          background: "var(--warning-subtle)",
          border: "1px solid var(--warning)",
          borderRadius: "var(--radius-lg)",
          marginBottom: 20,
          fontSize: 13,
          color: "var(--warning)",
        }}>
          <span style={{ fontWeight: 600 }}>{pending.length} device{pending.length > 1 ? "s" : ""} awaiting approval</span>
          <button className="btn btn-sm" style={{ background: "var(--warning)", color: "#fff", border: "none", marginLeft: "auto" }}
            onClick={() => setTab("pending")}>
            Review
          </button>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {(["all", "pending"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`btn ${tab === t ? "btn-primary" : "btn-ghost"} btn-sm`}>
            {t === "all" ? `All devices (${allDevices.length})` : `Pending (${pending.length})`}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ padding: "var(--space-8)" }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 44, marginBottom: 8, borderRadius: "var(--radius-md)" }} />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon"><Monitor size={32} /></div>
            <div className="empty-state-title">
              {tab === "pending" ? "No pending devices" : "No devices enrolled"}
            </div>
            <div className="empty-state-body">
              {tab === "pending"
                ? "All enrollment requests have been handled."
                : "Install the PulseDesk agent on an employee's machine to enroll a device."}
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Device</th>
                <th>Employee</th>
                <th>Platform</th>
                <th>Status</th>
                <th>Last heartbeat</th>
                <th>Agent</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((d) => (
                <tr key={d.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <OnlineBadge online={d.is_online} showLabel={false} size="sm" />
                      <span style={{ fontWeight: 500 }}>{d.hostname}</span>
                    </div>
                  </td>
                  <td style={{ color: "var(--text-secondary)" }}>{d.employee_name ?? "—"}</td>
                  <td>
                    <span style={{ fontSize: 13 }}>
                      {platformIcon(d.platform)} {d.platform}
                    </span>
                  </td>
                  <td>{statusBadge(d)}</td>
                  <td style={{ color: "var(--text-tertiary)", fontSize: 12 }}>
                    {d.last_heartbeat ? formatDate(d.last_heartbeat) : "Never"}
                  </td>
                  <td style={{ color: "var(--text-tertiary)", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                    {d.agent_version ?? "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      {d.status === "pending" && (
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => approve.mutate(d.id)}
                          disabled={approve.isPending}
                        >
                          <CheckCircle size={12} /> Approve
                        </button>
                      )}
                      {d.status === "approved" && (
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => { if (confirm("Revoke this device?")) revoke.mutate(d.id); }}
                          disabled={revoke.isPending}
                        >
                          <XCircle size={12} /> Revoke
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
