import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Plus, Trash2, ToggleLeft, ToggleRight, AlertTriangle, Download } from "lucide-react";
import { api } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";

interface BlockedDomain {
  id: string;
  domain: string;
  reason: string;
  category: string;
  severity: "low" | "medium" | "high";
  is_active: boolean;
  violation_count: number;
  created_at: string;
}

const CATEGORIES = [
  { value: "social", label: "Social media", color: "#f59e0b" },
  { value: "streaming", label: "Streaming", color: "#ef4444" },
  { value: "gaming", label: "Gaming", color: "#8b5cf6" },
  { value: "adult", label: "Adult content", color: "#dc2626" },
  { value: "illegal", label: "Illegal content", color: "#991b1b" },
  { value: "custom", label: "Custom", color: "#6b7280" },
];

const SEVERITY_COLORS = {
  low: { bg: "var(--warning-subtle)", text: "var(--warning)" },
  medium: { bg: "#fff7ed", text: "#c2410c" },
  high: { bg: "var(--danger-subtle)", text: "var(--danger)" },
};

export function BlockerPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    domain: "", reason: "", category: "social", severity: "medium", applies_to_all: true,
  });

  const { data: domains = [], isLoading } = useQuery<BlockedDomain[]>({
    queryKey: ["blocked-domains"],
    queryFn: () => api.get("/blocker/domains").then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: violations = [] } = useQuery<any[]>({
    queryKey: ["violations"],
    queryFn: () => api.get("/blocker/violations/summary").then(r => r.data),
    refetchInterval: 60_000,
  });

  const addDomain = useMutation({
    mutationFn: (data: any) => api.post("/blocker/domains", data).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["blocked-domains"] }); setShowForm(false); setForm({ domain: "", reason: "", category: "social", severity: "medium", applies_to_all: true }); },
  });

  const removeDomain = useMutation({
    mutationFn: (id: string) => api.delete(`/blocker/domains/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["blocked-domains"] }),
  });

  const toggleDomain = useMutation({
    mutationFn: (id: string) => api.patch(`/blocker/domains/${id}/toggle`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["blocked-domains"] }),
  });

  const loadDefaults = useMutation({
    mutationFn: () => api.post("/blocker/load-defaults").then(r => r.data),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["blocked-domains"] }); alert(`✓ Loaded ${data.added} default blocks`); },
  });

  const active = domains.filter(d => d.is_active).length;
  const totalViolations = violations.reduce((s, v) => s + v.count, 0);

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Website blocker"
        subtitle="Block domains across your team. Agent enforces in real-time."
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => loadDefaults.mutate()} disabled={loadDefaults.isPending}>
              <Download size={13} /> Load defaults
            </button>
            <button className="btn btn-primary" onClick={() => setShowForm(s => !s)}>
              <Plus size={14} /> Block domain
            </button>
          </div>
        }
      />

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Active blocks", value: active, color: "var(--danger)" },
          { label: "Total domains", value: domains.length, color: "var(--text-primary)" },
          { label: "Violations today", value: totalViolations, color: totalViolations > 0 ? "var(--warning)" : "var(--text-tertiary)" },
        ].map(({ label, value, color }) => (
          <div key={label} className="card" style={{ padding: "var(--space-4) var(--space-5)" }}>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 600, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Add form */}
      {showForm && (
        <div className="card" style={{ padding: "var(--space-5)", marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 14, color: "var(--text-primary)" }}>Block a domain</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Domain</label>
              <input className="input" value={form.domain} onChange={e => setForm(f => ({ ...f, domain: e.target.value }))} placeholder="youtube.com" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Category</label>
              <select className="input" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Severity</label>
              <select className="input" value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
                <option value="low">Low — note and review weekly</option>
                <option value="medium">Medium — review today</option>
                <option value="high">High — immediate action</option>
              </select>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "1 / -1" }}>
              <label>Reason (shown in violation report)</label>
              <input className="input" value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} placeholder="Not work related / Security risk / Policy violation" />
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={() => addDomain.mutate(form)} disabled={!form.domain || !form.reason || addDomain.isPending}>
              {addDomain.isPending ? "Adding…" : "Block domain"}
            </button>
            <button className="btn btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Violations summary */}
      {violations.length > 0 && (
        <div className="card" style={{ padding: "var(--space-5)", marginBottom: 16, border: "1px solid var(--warning)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <AlertTriangle size={16} style={{ color: "var(--warning)" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Recent violations</span>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {violations.map((v: any) => (
              <div key={v.domain} style={{
                padding: "4px 12px", borderRadius: "var(--radius-full)",
                background: "var(--danger-subtle)", color: "var(--danger)", fontSize: 12, fontWeight: 500,
              }}>
                {v.domain} ({v.count}×)
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Domain list */}
      <div className="card" style={{ overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ padding: "var(--space-8)" }}>
            {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 44, marginBottom: 8, borderRadius: "var(--radius-md)" }} />)}
          </div>
        ) : domains.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon"><Shield size={32} /></div>
            <div className="empty-state-title">No domains blocked</div>
            <div className="empty-state-body">
              Click "Load defaults" to block common social media, gaming, and streaming sites, or add your own.
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>Category</th>
                <th>Reason</th>
                <th>Severity</th>
                <th>Violations</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {domains.map(d => {
                const cat = CATEGORIES.find(c => c.value === d.category);
                const sev = SEVERITY_COLORS[d.severity] ?? SEVERITY_COLORS.medium;
                return (
                  <tr key={d.id} style={{ opacity: d.is_active ? 1 : 0.5 }}>
                    <td>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500 }}>{d.domain}</span>
                    </td>
                    <td>
                      <span style={{ fontSize: 11, fontWeight: 500, color: cat?.color ?? "#666" }}>{cat?.label ?? d.category}</span>
                    </td>
                    <td style={{ color: "var(--text-secondary)", fontSize: 12, maxWidth: 200 }}>{d.reason}</td>
                    <td>
                      <span className="badge" style={{ background: sev.bg, color: sev.text }}>{d.severity}</span>
                    </td>
                    <td>
                      {d.violation_count > 0
                        ? <span className="badge badge-red">{d.violation_count}</span>
                        : <span style={{ color: "var(--text-tertiary)", fontSize: 12 }}>0</span>
                      }
                    </td>
                    <td>
                      <span className={`badge ${d.is_active ? "badge-green" : "badge-gray"}`}>
                        {d.is_active ? "Active" : "Paused"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => toggleDomain.mutate(d.id)} title={d.is_active ? "Pause" : "Enable"}>
                          {d.is_active ? <ToggleRight size={14} style={{ color: "var(--success)" }} /> : <ToggleLeft size={14} />}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => { if (confirm(`Remove ${d.domain}?`)) removeDomain.mutate(d.id); }}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
