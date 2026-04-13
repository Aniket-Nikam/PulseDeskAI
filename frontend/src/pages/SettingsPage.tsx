import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { User, Lock, Bell, Shield, Server } from "lucide-react";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { PageHeader } from "../components/ui/PageHeader";

export function SettingsPage() {
  const { admin } = useAuthStore();
  const [tab, setTab] = useState<"profile" | "security" | "system">("profile");

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader title="Settings" subtitle="Manage your account and system preferences" />

      {/* Tab nav */}
      <div style={{ display: "flex", gap: 2, marginBottom: 24, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 0 }}>
        {[
          { id: "profile", label: "Profile", icon: <User size={14}/> },
          { id: "security", label: "Security", icon: <Lock size={14}/> },
          { id: "system", label: "System", icon: <Server size={14}/> },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id as any)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "8px 14px", fontSize: 13,
              background: "none", border: "none", cursor: "pointer",
              color: tab === t.id ? "var(--accent)" : "var(--text-secondary)",
              borderBottom: `2px solid ${tab === t.id ? "var(--accent)" : "transparent"}`,
              marginBottom: -1, fontFamily: "inherit",
              fontWeight: tab === t.id ? 500 : 400,
            }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "profile" && <ProfileTab admin={admin} />}
      {tab === "security" && <SecurityTab />}
      {tab === "system" && <SystemTab />}
    </div>
  );
}

function ProfileTab({ admin }: { admin: any }) {
  return (
    <div style={{ maxWidth: 520 }}>
      <div className="card" style={{ padding: "var(--space-6)", marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
          Account information
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {[
            { label: "Full name", value: admin?.full_name ?? "—" },
            { label: "Email address", value: admin?.email ?? "—" },
            { label: "Role", value: admin?.role?.replace("_", " ") ?? "—" },
            { label: "Account status", value: admin?.is_active ? "Active" : "Inactive" },
            { label: "Last login", value: admin?.last_login ? new Date(admin.last_login).toLocaleString() : "—" },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{label}</span>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", textTransform: "capitalize" }}>{value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: "var(--space-5)", background: "var(--accent-subtle)", borderColor: "var(--border-subtle)" }}>
        <div style={{ fontSize: 12, color: "var(--accent-text)", lineHeight: 1.6 }}>
          <strong>Admin tip:</strong> To change your name or email, ask another super admin to update your account via the API at <code style={{ fontSize: 11 }}>/api/docs</code>.
        </div>
      </div>
    </div>
  );
}

function SecurityTab() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const change = useMutation({
    mutationFn: () => api.post("/auth/change-password", {
      current_password: form.current,
      new_password: form.next,
    }),
    onSuccess: () => {
      setMsg({ type: "success", text: "Password changed successfully." });
      setForm({ current: "", next: "", confirm: "" });
    },
    onError: (err: any) => {
      setMsg({ type: "error", text: err?.response?.data?.detail ?? "Failed to change password." });
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (form.next !== form.confirm) {
      setMsg({ type: "error", text: "New passwords don't match." });
      return;
    }
    if (form.next.length < 8) {
      setMsg({ type: "error", text: "Password must be at least 8 characters." });
      return;
    }
    change.mutate();
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
          Change password
        </h3>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {[
            { id: "current", label: "Current password", key: "current" as const },
            { id: "next", label: "New password", key: "next" as const },
            { id: "confirm", label: "Confirm new password", key: "confirm" as const },
          ].map(({ id, label, key }) => (
            <div key={id} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)" }}>{label}</label>
              <input type="password" className="input" value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                placeholder="••••••••" required
              />
            </div>
          ))}
          {msg && (
            <div style={{
              padding: "9px 12px", fontSize: 13, borderRadius: "var(--radius-md)",
              background: msg.type === "success" ? "var(--success-subtle)" : "var(--danger-subtle)",
              color: msg.type === "success" ? "var(--success)" : "var(--danger)",
            }}>
              {msg.text}
            </div>
          )}
          <button type="submit" className="btn btn-primary" disabled={change.isPending} style={{ alignSelf: "flex-start" }}>
            {change.isPending ? "Changing…" : "Change password"}
          </button>
        </form>
      </div>

      <div className="card" style={{ padding: "var(--space-5)", marginTop: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--text-primary)" }}>
          Session info
        </h3>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
          Your session token is valid for <strong>8 hours</strong>. After that, it auto-refreshes using your refresh token (valid 30 days). You will only need to log in again after 30 days of inactivity.
        </div>
      </div>
    </div>
  );
}

function SystemTab() {
  const checks = [
    { label: "Backend API", status: "online", detail: "http://localhost:8000" },
    { label: "WebSocket", status: "online", detail: "Real-time updates active" },
    { label: "Database", status: "online", detail: "PostgreSQL connected" },
    { label: "Screenshot dir", status: "ok", detail: "./screenshots" },
  ];

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="card" style={{ padding: "var(--space-6)", marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>System status</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {checks.map(c => (
            <div key={c.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>{c.label}</div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{c.detail}</div>
              </div>
              <span className="badge badge-green">{c.status}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: "var(--space-6)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Quick links</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { label: "API documentation", url: "http://localhost:8000/api/docs" },
            { label: "Employee join portal", url: "http://localhost:8000/join" },
            { label: "OpenAPI schema", url: "http://localhost:8000/api/openapi.json" },
          ].map(({ label, url }) => (
            <a key={url} href={url} target="_blank" rel="noopener noreferrer"
              style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "8px 10px", background: "var(--bg-secondary)",
                borderRadius: "var(--radius-md)", textDecoration: "none",
                fontSize: 13, color: "var(--accent)",
              }}>
              {label}
              <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>↗</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
