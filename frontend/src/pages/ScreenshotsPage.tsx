import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Shield, X, ZoomIn, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { analyticsApi, employeesApi, screenshotsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Employee } from "../types";
import { formatDate } from "../utils/format";

export function ScreenshotsPage() {
  const qc = useQueryClient();
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [policyForm, setPolicyForm] = useState({ name: "", policy_type: "interval", interval_minutes: "10", applies_to_all: false });

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: policies = [] } = useQuery({
    queryKey: ["policies"],
    queryFn: analyticsApi.screenshotPolicies,
  });

  const createPolicy = useMutation({
    mutationFn: () => analyticsApi.createPolicy({
      name: policyForm.name,
      policy_type: policyForm.policy_type,
      interval_minutes: policyForm.policy_type === "interval" ? parseInt(policyForm.interval_minutes) : undefined,
      applies_to_all: policyForm.applies_to_all,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["policies"] }); setShowPolicyForm(false); },
  });

  const togglePolicy = useMutation({
    mutationFn: (id: string) => analyticsApi.togglePolicy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });

  const deletePolicy = useMutation({
    mutationFn: (id: string) => analyticsApi.deletePolicy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Screenshots"
        subtitle="Policy-based screenshot capture"
        action={
          <button className="btn btn-primary" onClick={() => setShowPolicyForm((s) => !s)}>
            <Shield size={14} /> Manage policies
          </button>
        }
      />

      {/* Policy notice */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        padding: "12px 16px",
        background: "var(--accent-subtle)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-lg)",
        marginBottom: 24,
      }}>
        <Shield size={16} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
        <div style={{ fontSize: 13, color: "var(--accent-text)" }}>
          Screenshots are only captured when an active policy is enabled. Employees are notified of monitoring per your company policy.
          Screenshots are stored locally on your server.
        </div>
      </div>

      {/* Policy form */}
      {showPolicyForm && (
        <div className="card" style={{ padding: "var(--space-6)", marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>New screenshot policy</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Policy name</label>
              <input className="input" value={policyForm.name} onChange={(e) => setPolicyForm((f) => ({ ...f, name: e.target.value }))} placeholder="All employees - interval" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Type</label>
              <select className="input" value={policyForm.policy_type} onChange={(e) => setPolicyForm((f) => ({ ...f, policy_type: e.target.value }))}>
                <option value="disabled">Disabled</option>
                <option value="interval">Interval</option>
                <option value="on_anomaly">On anomaly only</option>
              </select>
            </div>
            {policyForm.policy_type === "interval" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label>Every (minutes)</label>
                <input className="input" type="number" min="5" max="60" value={policyForm.interval_minutes} onChange={(e) => setPolicyForm((f) => ({ ...f, interval_minutes: e.target.value }))} />
              </div>
            )}
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, cursor: "pointer" }}>
            <input type="checkbox" checked={policyForm.applies_to_all} onChange={(e) => setPolicyForm((f) => ({ ...f, applies_to_all: e.target.checked }))} />
            Apply to all employees
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={() => createPolicy.mutate()} disabled={!policyForm.name || createPolicy.isPending}>
              {createPolicy.isPending ? "Creating…" : "Create policy"}
            </button>
            <button className="btn btn-ghost" onClick={() => setShowPolicyForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Active policies */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--text-primary)" }}>Policies</h2>
        {policies.length === 0 ? (
          <div className="card empty-state" style={{ padding: "var(--space-8)" }}>
            <div className="empty-state-icon"><Shield size={28} /></div>
            <div className="empty-state-title">No policies configured</div>
            <div className="empty-state-body">Screenshots are disabled by default. Create a policy to enable capture.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {policies.map((p: any) => (
              <div key={p.id} className="card" style={{ padding: "var(--space-4) var(--space-5)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <Shield size={16} style={{ color: !p.is_active ? "var(--text-tertiary)" : "var(--accent)" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                      {p.policy_type === "interval" ? `Every ${p.interval_minutes} minutes` : p.policy_type}
                      {p.applies_to_all ? " · All employees" : ""}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={`badge ${!p.is_active ? "badge-gray" : "badge-green"}`}>
                    {p.is_active ? "Active" : "Disabled"}
                  </span>
                  <button
                    className={`btn btn-sm ${p.is_active ? "btn-secondary" : "btn-primary"}`}
                    onClick={() => togglePolicy.mutate(p.id)}
                    disabled={togglePolicy.isPending}
                    title={p.is_active ? "Disable policy" : "Enable policy"}
                    style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}
                  >
                    {p.is_active ? <><ToggleRight size={14} /> Disable</> : <><ToggleLeft size={14} /> Enable</>}
                  </button>
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => { if (confirm(`Delete policy "${p.name}"?`)) deletePolicy.mutate(p.id); }}
                    disabled={deletePolicy.isPending}
                    title="Delete policy"
                    style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Screenshot viewer */}
      <div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>View screenshots</h2>
          <select className="input" style={{ width: "auto" }} value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)}>
            <option value="">Select employee…</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
          </select>
        </div>
        {!selectedEmployee ? (
          <div className="card empty-state" style={{ padding: "var(--space-8)" }}>
            <div className="empty-state-icon"><Camera size={28} /></div>
            <div className="empty-state-title">Select an employee</div>
            <div className="empty-state-body">Choose an employee to view their screenshots.</div>
          </div>
        ) : (
          <ScreenshotGallery employeeId={selectedEmployee} />
        )}
      </div>
    </div>
  );
}

function ScreenshotGallery({ employeeId }: { employeeId: string }) {
  const qc = useQueryClient();
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("desc");
  const [dateFilter, setDateFilter] = useState("");
  const limit = 21;

  const { data, isLoading } = useQuery({
    queryKey: ["screenshots", employeeId, page, sort, dateFilter],
    queryFn: () => {
      let url = `/screenshots/${employeeId}?limit=${limit}&skip=${(page - 1) * limit}&sort=${sort}`;
      if (dateFilter) url += `&date=${dateFilter}`;
      return import("../api/client").then((m) => m.api.get(url)).then((r) => r.data);
    },
  });

  const deleteScreenshot = useMutation({
    mutationFn: screenshotsApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["screenshots", employeeId] }); }
  });

  const screenshots = data?.items || [];
  const totalPages = data?.pages || 1;
  const total = data?.total || 0;

  if (isLoading) return <div className="skeleton" style={{ height: 160, borderRadius: "var(--radius-xl)" }} />;

  if (screenshots.length === 0 && page === 1 && !dateFilter) {
    return (
      <div className="card empty-state" style={{ padding: "var(--space-8)" }}>
        <div className="empty-state-icon"><Camera size={28} /></div>
        <div className="empty-state-title">No screenshots</div>
        <div className="empty-state-body">No screenshots captured for this employee yet.</div>
      </div>
    );
  }

  const imageUrl = (url: string) => `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;

  return (
    <>
      {/* Toolbar: date filter + count + sort + pagination */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="date"
            className="input"
            style={{ width: "auto", padding: "4px 8px", fontSize: 12 }}
            value={dateFilter}
            onChange={(e) => { setDateFilter(e.target.value); setPage(1); }}
          />
          {dateFilter && (
            <button className="btn btn-sm btn-ghost" onClick={() => { setDateFilter(""); setPage(1); }} style={{ fontSize: 11 }}>
              ✕ Clear date
            </button>
          )}
          <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {total} screenshot{total !== 1 ? "s" : ""} {dateFilter ? `on ${dateFilter}` : ""} · Page {page}/{totalPages}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select className="input" style={{ width: "auto", padding: "4px 8px", fontSize: 12 }} value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>
          <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      </div>

      {/* No results for date filter */}
      {screenshots.length === 0 && dateFilter && (
        <div className="card empty-state" style={{ padding: "var(--space-6)" }}>
          <div className="empty-state-icon"><Camera size={24} /></div>
          <div className="empty-state-title">No screenshots for {dateFilter}</div>
          <div className="empty-state-body">Try a different date or clear the filter.</div>
        </div>
      )}

      {/* Grid — flex layout so last-row items stretch to fill gaps */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {screenshots.map((s: any) => (
          <div key={s.id} style={{ flex: "1 1 180px", maxWidth: "calc(100% / 3)", minWidth: 160 }}>
            <ScreenshotCard
              screenshot={s}
              imageUrl={imageUrl(s.url)}
              onExpand={() => setExpandedUrl(imageUrl(s.url))}
              onDelete={() => { if (confirm("Delete this screenshot?")) deleteScreenshot.mutate(s.id); }}
              isDeleting={deleteScreenshot.isPending && deleteScreenshot.variables === s.id}
            />
          </div>
        ))}
      </div>

      {/* Bottom pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 16 }}>
          <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(1)}>First</button>
          <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span style={{ fontSize: 13, color: "var(--text-secondary)", padding: "0 8px" }}>Page {page} of {totalPages}</span>
          <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
          <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(totalPages)}>Last</button>
        </div>
      )}

      {/* Lightbox modal */}
      {expandedUrl && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 9999,
            background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
          onClick={() => setExpandedUrl(null)}
        >
          <button
            onClick={() => setExpandedUrl(null)}
            style={{
              position: "absolute", top: 16, right: 16,
              background: "rgba(255,255,255,0.15)", border: "none",
              borderRadius: "50%", width: 36, height: 36,
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", color: "#fff",
            }}
          >
            <X size={20} />
          </button>
          <img
            src={expandedUrl}
            alt="Screenshot expanded"
            style={{
              maxWidth: "90vw", maxHeight: "90vh",
              borderRadius: 8,
              boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}

function ScreenshotCard({ screenshot, imageUrl, onExpand, onDelete, isDeleting }: { screenshot: any; imageUrl: string; onExpand: () => void; onDelete: () => void; isDeleting?: boolean }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <div
      className="card"
      style={{ padding: "var(--space-3)", cursor: "pointer", position: "relative" }}
      onClick={onExpand}
    >
      <div style={{
        height: 110, background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
        marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "center",
        overflow: "hidden", position: "relative",
      }}>
        {!error ? (
          <>
            {!loaded && (
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Camera size={24} style={{ color: "var(--text-tertiary)", opacity: 0.5 }} />
              </div>
            )}
            <img
              src={imageUrl}
              alt={`Screenshot from ${formatDate(screenshot.captured_at)}`}
              onLoad={() => setLoaded(true)}
              onError={() => setError(true)}
              style={{
                width: "100%", height: "100%",
                objectFit: "cover",
                opacity: loaded ? 1 : 0,
                transition: "opacity 0.3s ease",
              }}
            />
          </>
        ) : (
          <Camera size={24} style={{ color: "var(--text-tertiary)" }} />
        )}

        {/* Hover overlay with zoom icon */}
        <div style={{
          position: "absolute", inset: 0,
          background: "rgba(0,0,0,0.3)",
          opacity: 0, transition: "opacity 0.2s ease",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 12,
          borderRadius: "var(--radius-md)",
        }}
          className="screenshot-hover-overlay"
        >
          <button onClick={(e) => { e.stopPropagation(); onExpand(); }} style={{ background: "transparent", border: "none", cursor: "pointer" }}>
            <ZoomIn size={20} style={{ color: "#fff" }} />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onDelete(); }} style={{ background: "transparent", border: "none", cursor: isDeleting ? "not-allowed" : "pointer" }} disabled={isDeleting}>
            <Trash2 size={20} style={{ color: "var(--danger)" }} />
          </button>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{formatDate(screenshot.captured_at)}</div>
      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{screenshot.trigger} · {(screenshot.file_size_bytes / 1024).toFixed(0)}KB</div>

      <style>{`
        .screenshot-hover-overlay { opacity: 0 !important; }
        .card:hover .screenshot-hover-overlay { opacity: 1 !important; }
      `}</style>
    </div>
  );
}
