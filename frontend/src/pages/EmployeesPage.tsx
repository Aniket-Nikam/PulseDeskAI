import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Search, Trash2, UserX, UserCheck, Link2, X, Copy, Check } from "lucide-react";
import { employeesApi, departmentsApi, enrollApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { OnlineBadge } from "../components/ui/OnlineBadge";
import type { Employee, Department } from "../types";
import { formatDate } from "../utils/format";
import { api } from "../api/client";
import { APP_ORIGIN } from "../config";

export function EmployeesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [enrollTarget, setEnrollTarget] = useState<Employee | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Employee | null>(null);
  const [form, setForm] = useState({ email: "", full_name: "", job_title: "", department_id: "", timezone: "UTC" });
  const [formError, setFormError] = useState("");

  const { data: employees = [], isLoading } = useQuery<Employee[]>({
    queryKey: ["employees", search],
    queryFn: () => employeesApi.list({ search: search || undefined, is_active: true }),
    refetchInterval: 30_000,
  });

  const { data: inactive = [] } = useQuery<Employee[]>({
    queryKey: ["employees-inactive"],
    queryFn: () => employeesApi.list({ is_active: false }),
  });

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: departmentsApi.list,
  });

  const create = useMutation({
    mutationFn: (data: typeof form) =>
      employeesApi.create({ ...data, department_id: data.department_id || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      setShowForm(false);
      setForm({ email: "", full_name: "", job_title: "", department_id: "", timezone: "UTC" });
      setFormError("");
    },
    onError: (err: any) => setFormError(err?.response?.data?.detail ?? "Failed to create employee"),
  });

  const deactivate = useMutation({
    mutationFn: (id: string) => employeesApi.deactivate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["employees-inactive"] });
    },
  });

  const reactivate = useMutation({
    mutationFn: (id: string) => api.patch(`/employees/${id}`, { is_active: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["employees-inactive"] });
    },
  });

  const hardDelete = useMutation({
    mutationFn: (id: string) => api.delete(`/employees/${id}/permanent`).catch(() => api.delete(`/employees/${id}`)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["employees-inactive"] });
      setConfirmDelete(null);
    },
  });

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Employees"
        subtitle={`${employees.length} active${inactive.length > 0 ? ` · ${inactive.length} inactive` : ""}`}
        action={
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <UserPlus size={14} /> Add employee
          </button>
        }
      />

      {showForm && (
        <div className="card" style={{ padding: "var(--space-6)", marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>New employee</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => { setShowForm(false); setFormError(""); }}><X size={14} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {[
              { key: "full_name", label: "Full name *", placeholder: "Aniket Sharma", type: "text" },
              { key: "email", label: "Email *", placeholder: "aniket@company.com", type: "email" },
              { key: "job_title", label: "Job title", placeholder: "Software Engineer", type: "text" },
            ].map(({ key, label, placeholder, type }) => (
              <div key={key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label>{label}</label>
                <input type={type} className="input" placeholder={placeholder}
                  value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
              </div>
            ))}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Department</label>
              <select className="input" value={form.department_id} onChange={e => setForm(f => ({ ...f, department_id: e.target.value }))}>
                <option value="">No department</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          </div>
          {formError && (
            <div style={{ padding: "8px 12px", background: "var(--danger-subtle)", color: "var(--danger)", borderRadius: "var(--radius-md)", fontSize: 13, marginBottom: 12 }}>
              {formError}
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={() => { setFormError(""); create.mutate(form); }}
              disabled={create.isPending || !form.email || !form.full_name}>
              {create.isPending ? "Creating…" : "Create employee"}
            </button>
            <button className="btn btn-ghost" onClick={() => { setShowForm(false); setFormError(""); }}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ position: "relative", marginBottom: 16, maxWidth: 320 }}>
        <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)" }} />
        <input type="text" className="input" placeholder="Search employees…" value={search}
          onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 32 }} />
      </div>

      <div className="card" style={{ overflow: "hidden", marginBottom: 24 }}>
        {isLoading ? (
          <div style={{ padding: "var(--space-8)" }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 52, marginBottom: 8, borderRadius: "var(--radius-md)" }} />
            ))}
          </div>
        ) : employees.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-title">{search ? `No results for "${search}"` : "No employees yet"}</div>
            <div className="empty-state-body">Click "Add employee" to get started.</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Department</th>
                <th>Job title</th>
                <th>Devices</th>
                <th>Status</th>
                <th>Added</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {employees.map(e => (
                <tr key={e.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{e.full_name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{e.email}</div>
                  </td>
                  <td style={{ color: "var(--text-secondary)" }}>{e.department_name ?? "—"}</td>
                  <td style={{ color: "var(--text-secondary)" }}>{e.job_title ?? "—"}</td>
                  <td><span className="badge badge-gray">{e.device_count} device{e.device_count !== 1 ? "s" : ""}</span></td>
                  <td><OnlineBadge online={e.is_online} size="sm" /></td>
                  <td style={{ color: "var(--text-tertiary)", fontSize: 12 }}>{formatDate(e.created_at)}</td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                      <button className="btn btn-sm btn-primary" onClick={() => setEnrollTarget(e)} title="Get join code">
                        <Link2 size={12} /> Enroll device
                      </button>
                      <button className="btn btn-sm btn-secondary"
                        onClick={() => { if (confirm(`Deactivate ${e.full_name}? Data is kept, they can rejoin later.`)) deactivate.mutate(e.id); }}
                        title="Deactivate — keeps all data">
                        <UserX size={12} />
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => setConfirmDelete(e)} title="Delete permanently">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {inactive.length > 0 && (
        <div>
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Inactive employees ({inactive.length})
          </h3>
          <div className="card" style={{ overflow: "hidden" }}>
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Added</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {inactive.map(e => (
                  <tr key={e.id} style={{ opacity: 0.65 }}>
                    <td>
                      <div style={{ fontWeight: 500, color: "var(--text-secondary)" }}>{e.full_name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{e.email}</div>
                    </td>
                    <td style={{ color: "var(--text-tertiary)" }}>{e.department_name ?? "—"}</td>
                    <td style={{ color: "var(--text-tertiary)", fontSize: 12 }}>{formatDate(e.created_at)}</td>
                    <td style={{ textAlign: "right" }}>
                      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                        <button className="btn btn-sm btn-secondary" onClick={() => reactivate.mutate(e.id)} title="Reactivate">
                          <UserCheck size={12} /> Reactivate
                        </button>
                        <button className="btn btn-sm btn-danger" onClick={() => setConfirmDelete(e)} title="Delete permanently">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {enrollTarget && <EnrollModal employee={enrollTarget} onClose={() => setEnrollTarget(null)} />}
      {confirmDelete && (
        <DeleteModal employee={confirmDelete}
          onConfirm={() => hardDelete.mutate(confirmDelete.id)}
          onClose={() => setConfirmDelete(null)}
          loading={hardDelete.isPending} />
      )}
    </div>
  );
}

function EnrollModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const [serverUrl, setServerUrl] = useState(APP_ORIGIN);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function generate() {
    setLoading(true); setError("");
    try {
      const data = await enrollApi.generateLink(employee.id, serverUrl);
      setResult(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to generate join link. Make sure enrollment route is registered.");
    } finally { setLoading(false); }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      onClick={onClose}>
      <div className="card" style={{ width: "100%", maxWidth: 500, padding: "var(--space-6)" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)" }}>Enroll device — {employee.full_name}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={14} /></button>
        </div>

        {!result ? (
          <>
            <p style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 16, lineHeight: 1.6 }}>
              Generate a join code. The employee visits a URL in their browser, enters the code, downloads and runs one file. No technical knowledge needed.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 16 }}>
              <label>Server URL (reachable from employee's machine)</label>
              <input className="input" value={serverUrl} onChange={e => setServerUrl(e.target.value)} placeholder="http://192.168.1.5:8000" />
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                Same machine: use <code>http://localhost:8000</code>. Another machine on same WiFi: use your LAN IP from <code>ipconfig</code>.
              </div>
            </div>
            {error && <div style={{ padding: "8px 12px", background: "var(--danger-subtle)", color: "var(--danger)", borderRadius: "var(--radius-md)", fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={generate} disabled={loading}>
                {loading ? "Generating…" : "Generate join code"}
              </button>
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            </div>
          </>
        ) : (
          <>
            <div style={{ background: "var(--success-subtle)", border: "1px solid var(--success)", borderRadius: "var(--radius-lg)", padding: "var(--space-5)", marginBottom: 16, textAlign: "center" }}>
              <div style={{ fontSize: 12, color: "var(--success)", fontWeight: 500, marginBottom: 8 }}>Join code for {employee.full_name}</div>
              <div style={{ fontSize: 48, fontWeight: 700, letterSpacing: "0.25em", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                {result.code}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 8 }}>Valid for 48 hours</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Instructions for {employee.full_name}:
              </div>
              {[
                `Step 1: Open this in your browser → ${result.join_url}`,
                `Step 2: Enter code → ${result.code}`,
                `Step 3: Click Download → Extract the ZIP file`,
                `Step 4: Double-click install_windows.bat (once only)`,
                `Step 5: Double-click start_windows.bat — done!`,
              ].map((s, i) => (
                <div key={i} style={{ padding: "7px 12px", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)", fontSize: 12, color: "var(--text-secondary)" }}>
                  {s}
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={() => copy(
                `Hi ${employee.full_name},\n\nTo set up monitoring on your device:\n\n1. Open in browser: ${result.join_url}\n2. Enter code: ${result.code}\n3. Click Download → Extract ZIP\n4. Run install_windows.bat (once)\n5. Run start_windows.bat\n\nThat's all!`
              )}>
                {copied ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy to send</>}
              </button>
              <button className="btn btn-ghost" onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function DeleteModal({ employee, onConfirm, onClose, loading }: { employee: Employee; onConfirm: () => void; onClose: () => void; loading: boolean }) {
  const [typed, setTyped] = useState("");
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      onClick={onClose}>
      <div className="card" style={{ width: "100%", maxWidth: 420, padding: "var(--space-6)" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <div style={{ width: 40, height: 40, borderRadius: "var(--radius-lg)", background: "var(--danger-subtle)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Trash2 size={18} style={{ color: "var(--danger)" }} />
          </div>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>Delete permanently?</h2>
            <p style={{ fontSize: 13, color: "var(--text-tertiary)", lineHeight: 1.5 }}>
              All data for <strong>{employee.full_name}</strong> will be deleted — activity logs, sessions, screenshots. Cannot be undone.
            </p>
          </div>
        </div>
        <div style={{ padding: "10px 12px", background: "var(--warning-subtle)", border: "1px solid var(--warning)", borderRadius: "var(--radius-md)", fontSize: 12, color: "var(--warning)", marginBottom: 16 }}>
          Tip: Use <strong>Deactivate</strong> (the X button) if you want to temporarily remove access while keeping their data.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: "var(--text-secondary)" }}>Type <strong>{employee.full_name}</strong> to confirm</label>
          <input className="input" value={typed} onChange={e => setTyped(e.target.value)} placeholder={employee.full_name} />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-danger" onClick={onConfirm} disabled={typed !== employee.full_name || loading}>
            {loading ? "Deleting…" : "Delete permanently"}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
