import React, { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Shield, Trash2, X, ZoomIn } from "lucide-react";
import { analyticsApi, employeesApi, api } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Employee } from "../types";
import { formatDate } from "../utils/format";

const MIN_CARD_WIDTH = 220;
const GRID_GAP = 10;
const TARGET_ROWS = 3;

type ScreenshotItem = {
  id: string;
  captured_at: string;
  trigger: string;
  file_size_bytes: number;
  url: string;
  file_exists?: boolean;
};

type ScreenshotPageResponse = {
  items: ScreenshotItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

type ScreenshotCleanupResponse = {
  status: string;
  removed: number;
};

type SortOrder = "desc" | "asc";
type PolicyType = "disabled" | "interval" | "on_anomaly";

type ScreenshotPolicy = {
  id: string;
  name: string;
  policy_type: PolicyType;
  interval_minutes: number | null;
  applies_to_all: boolean;
  is_active: boolean;
};

function getPolicyBadge(policy: ScreenshotPolicy): { label: string; className: string } {
  if (!policy.is_active) return { label: "Inactive", className: "badge-gray" };
  if (policy.policy_type === "disabled") return { label: "Disabled", className: "badge-gray" };
  return { label: "Active", className: "badge-green" };
}

export function ScreenshotsPage() {
  const qc = useQueryClient();
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [policyForm, setPolicyForm] = useState({ name: "", policy_type: "interval", interval_minutes: "10", applies_to_all: false });

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: policies = [] } = useQuery<ScreenshotPolicy[]>({
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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["policies"] }); },
  });

  const deletePolicy = useMutation({
    mutationFn: (id: string) => analyticsApi.deletePolicy(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["policies"] }); },
  });

  const handleTogglePolicy = (policy: ScreenshotPolicy) => {
    const action = policy.is_active ? "disable" : "enable";
    if (!window.confirm(`Are you sure you want to ${action} "${policy.name}"?`)) return;
    togglePolicy.mutate(policy.id);
  };

  const handleDeletePolicy = (policy: ScreenshotPolicy) => {
    if (!window.confirm(`Delete policy "${policy.name}"? This cannot be undone.`)) return;
    deletePolicy.mutate(policy.id);
  };

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
              {createPolicy.isPending ? "Creating..." : "Create policy"}
            </button>
            <button className="btn btn-ghost" onClick={() => setShowPolicyForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Policies */}
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
            {policies.map((p) => {
              const badge = getPolicyBadge(p);
              return (
                <div key={p.id} className="card" style={{ padding: "var(--space-4) var(--space-5)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <Shield size={16} style={{ color: p.is_active && p.policy_type !== "disabled" ? "var(--accent)" : "var(--text-tertiary)" }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                        {p.policy_type === "interval" ? `Every ${p.interval_minutes} minutes` : p.policy_type}
                        {p.applies_to_all ? " - All employees" : ""}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleTogglePolicy(p)}
                      disabled={togglePolicy.isPending || deletePolicy.isPending}
                      title={p.is_active ? "Disable policy" : "Enable policy"}
                    >
                      {p.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleDeletePolicy(p)}
                      disabled={deletePolicy.isPending || togglePolicy.isPending}
                      title="Delete policy"
                      style={{ color: "var(--danger)" }}
                    >
                      <Trash2 size={14} /> Delete
                    </button>
                    <span className={`badge ${badge.className}`}>
                      {badge.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Screenshot viewer */}
      <div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>View screenshots</h2>
          <select className="input" style={{ width: "auto" }} value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)}>
            <option value="">Select employee...</option>
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
  const [selectedDate, setSelectedDate] = useState("");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [page, setPage] = useState(1);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [columnCount, setColumnCount] = useState(6);
  const pageSize = columnCount * TARGET_ROWS;

  useEffect(() => {
    const node = gridRef.current;
    if (!node) return;

    const updateColumns = () => {
      const width = node.clientWidth;
      const cols = Math.max(1, Math.floor((width + GRID_GAP) / (MIN_CARD_WIDTH + GRID_GAP)));
      setColumnCount((prev) => (prev === cols ? prev : cols));
    };

    updateColumns();

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(updateColumns);
      observer.observe(node);
      return () => observer.disconnect();
    }

    window.addEventListener("resize", updateColumns);
    return () => window.removeEventListener("resize", updateColumns);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [employeeId, selectedDate, sortOrder, pageSize]);

  useEffect(() => {
    setStatusMessage(null);
  }, [employeeId]);

  const { data, isLoading, isFetching } = useQuery<ScreenshotPageResponse>({
    queryKey: ["screenshots", employeeId, selectedDate, sortOrder, page, pageSize],
    queryFn: () =>
      api.get(`/screenshots/${employeeId}`, {
        params: {
          limit: pageSize,
          skip: (page - 1) * pageSize,
          sort: sortOrder,
          date: selectedDate || undefined,
        },
      }).then((r) => {
        if (Array.isArray(r.data)) {
          return {
            items: r.data,
            total: r.data.length,
            page: 1,
            page_size: r.data.length || pageSize,
            pages: 1,
          };
        }
        return {
          items: r.data?.items ?? [],
          total: r.data?.total ?? 0,
          page: r.data?.page ?? page,
          page_size: r.data?.page_size ?? pageSize,
          pages: r.data?.pages ?? 1,
        };
      }),
  });

  const cleanupMissing = useMutation({
    mutationFn: () => analyticsApi.cleanupMissingScreenshots() as Promise<ScreenshotCleanupResponse>,
    onSuccess: (result) => {
      const removed = result?.removed ?? 0;
      setStatusMessage(`Cleanup complete: removed ${removed} missing screenshot record${removed === 1 ? "" : "s"}.`);
      qc.invalidateQueries({ queryKey: ["screenshots", employeeId] });
    },
  });

  const deleteScreenshot = useMutation({
    mutationFn: (screenshotId: string) => analyticsApi.deleteScreenshot(screenshotId),
    onSuccess: () => {
      setStatusMessage("Screenshot deleted.");
      qc.invalidateQueries({ queryKey: ["screenshots", employeeId] });
    },
  });

  const handleCleanupMissing = () => {
    if (!window.confirm("Remove screenshot records whose image files are missing on disk?")) return;
    cleanupMissing.mutate();
  };

  const handleDeleteScreenshot = (screenshot: ScreenshotItem) => {
    if (!window.confirm("Delete this screenshot permanently? This cannot be undone.")) return;
    deleteScreenshot.mutate(screenshot.id);
  };

  const screenshots = data?.items ?? [];
  const currentPage = data?.page ?? 1;
  const totalPages = Math.max(data?.pages ?? 1, 1);
  const totalItems = data?.total ?? screenshots.length;

  if (isLoading) return <div className="skeleton" style={{ height: 160, borderRadius: "var(--radius-xl)" }} />;

  if (screenshots.length === 0 && !isFetching) {
    return (
      <>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <input
            type="date"
            className="input"
            style={{ width: 180 }}
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
          <select
            className="input"
            style={{ width: 180 }}
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          >
            <option value="desc">Newest to Oldest</option>
            <option value="asc">Oldest to Newest</option>
          </select>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setSelectedDate("")}
            disabled={!selectedDate || cleanupMissing.isPending}
          >
            Clear date
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCleanupMissing}
            disabled={cleanupMissing.isPending || isFetching}
          >
            {cleanupMissing.isPending ? "Cleaning..." : "Cleanup missing files"}
          </button>
        </div>
        <div className="card empty-state" style={{ padding: "var(--space-8)" }}>
          <div className="empty-state-icon"><Camera size={28} /></div>
          <div className="empty-state-title">No screenshots</div>
          <div className="empty-state-body">
            {selectedDate
              ? "No screenshots found for the selected date."
              : "No screenshots captured for this employee yet."}
          </div>
        </div>
      </>
    );
  }

  const imageUrl = (url: string) => `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="date"
            className="input"
            style={{ width: 180 }}
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
          <select
            className="input"
            style={{ width: 180 }}
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          >
            <option value="desc">Newest to Oldest</option>
            <option value="asc">Oldest to Newest</option>
          </select>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setSelectedDate("")}
            disabled={!selectedDate || cleanupMissing.isPending}
          >
            Clear date
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCleanupMissing}
            disabled={cleanupMissing.isPending || isFetching}
          >
            {cleanupMissing.isPending ? "Cleaning..." : "Cleanup missing files"}
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {totalItems} screenshot{totalItems !== 1 ? "s" : ""} - page {currentPage} of {totalPages}
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={currentPage <= 1 || isFetching}
          >
            Prev
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage >= totalPages || isFetching}
          >
            Next
          </button>
        </div>
      </div>
      {statusMessage && (
        <div
          style={{
            marginBottom: 10,
            fontSize: 12,
            color: "var(--text-secondary)",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "8px 10px",
          }}
        >
          {statusMessage}
        </div>
      )}

      <div ref={gridRef}>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`, gap: 10 }}>
          {screenshots.map((s) => (
            <ScreenshotCard
              key={s.id}
              screenshot={s}
              imageUrl={imageUrl(s.url)}
              onExpand={s.file_exists === false ? undefined : () => setExpandedUrl(imageUrl(s.url))}
              onDelete={() => handleDeleteScreenshot(s)}
              isDeleting={deleteScreenshot.isPending && deleteScreenshot.variables === s.id}
            />
          ))}
        </div>
      </div>
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

function ScreenshotCard({
  screenshot,
  imageUrl,
  onExpand,
  onDelete,
  isDeleting,
}: {
  screenshot: ScreenshotItem;
  imageUrl: string;
  onExpand?: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const canExpand = !error && !!onExpand;
  const isMissingFile = screenshot.file_exists === false;

  return (
    <div className="card screenshot-card" style={{ padding: "var(--space-3)", position: "relative" }}>
      <div style={{
        aspectRatio: "16 / 9",
        background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
        marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "center",
        overflow: "hidden", position: "relative",
        cursor: canExpand ? "zoom-in" : "default",
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
              onClick={onExpand}
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
        <div
          style={{
            position: "absolute", inset: 0,
            background: "rgba(0,0,0,0.35)",
            opacity: 0, transition: "opacity 0.2s ease",
            display: "flex", alignItems: "center", justifyContent: "center",
            borderRadius: "var(--radius-md)",
          }}
          className="screenshot-hover-overlay"
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {canExpand && (
              <button
                type="button"
                title="Expand screenshot"
                onClick={(e) => {
                  e.stopPropagation();
                  onExpand?.();
                }}
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: "999px",
                  border: "1px solid rgba(255,255,255,0.45)",
                  background: "rgba(255,255,255,0.16)",
                  color: "#fff",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
              >
                <ZoomIn size={18} />
              </button>
            )}
            <button
              type="button"
              title={isDeleting ? "Deleting screenshot..." : "Delete screenshot"}
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              disabled={isDeleting}
              style={{
                width: 34,
                height: 34,
                borderRadius: "999px",
                border: "1px solid rgba(255,86,86,0.85)",
                background: "rgba(255,86,86,0.22)",
                color: "#fff",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: isDeleting ? "not-allowed" : "pointer",
                opacity: isDeleting ? 0.6 : 1,
              }}
            >
              <Trash2 size={18} />
            </button>
          </div>
        </div>
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{formatDate(screenshot.captured_at)}</div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {screenshot.trigger} - {(screenshot.file_size_bytes / 1024).toFixed(0)}KB
        </div>
        {isMissingFile && (
          <div style={{ fontSize: 11, color: "var(--warning)" }}>File missing on disk</div>
        )}
      </div>

      <style>{`
        .screenshot-card .screenshot-hover-overlay { opacity: 0 !important; pointer-events: none; }
        .screenshot-card:hover .screenshot-hover-overlay { opacity: 1 !important; pointer-events: auto; }
      `}</style>
    </div>
  );
}

