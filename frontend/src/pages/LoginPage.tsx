import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Activity } from "lucide-react";
import { authApi } from "../api/client";
import { useAuthStore, selectIsAuthenticated } from "../store/authStore";
import { BACKEND_ROOT } from "../config";

export function LoginPage() {
  const portalUrl = `${BACKEND_ROOT}/join`;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.login(email, password);
      const me = await authApi.me();
      setAuth(me);
      navigate("/", { replace: true });
    } catch (err: any) {
      const s = err?.response?.status;
      if (s === 401 || s === 422) setError("Invalid email or password.");
      else if (!err?.response) setError("Cannot reach server. Check backend connectivity and API base URL.");
      else setError(err?.response?.data?.detail ?? "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      background: "var(--bg-tertiary)",
    }}>
      {/* ── Left panel ── */}
      <div style={{
        width: "42%",
        background: "var(--accent)",
        padding: "48px 52px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
        className="login-left-panel"
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: "rgba(255,255,255,0.18)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Activity size={18} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: 17, fontWeight: 700, color: "#fff", letterSpacing: "-0.01em" }}>
            PulseDesk
          </span>
        </div>

        {/* Center text */}
        <div>
          <div style={{
            fontSize: 32, fontWeight: 700, color: "#fff",
            lineHeight: 1.25, marginBottom: 14, letterSpacing: "-0.02em",
          }}>
            Know what's happening across your team,<br />in real time.
          </div>
          <div style={{ fontSize: 15, color: "rgba(255,255,255,0.72)", lineHeight: 1.65 }}>
            Activity monitoring, productivity analytics,
            and behavioral insights — all in one place.
          </div>

          {/* Feature pills */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 28 }}>
            {[
              "Live screen monitoring",
              "App usage tracking",
              "Anomaly detection",
              "PDF reports",
              "Site blocker",
              "Productivity leaderboard",
            ].map(f => (
              <div key={f} style={{
                padding: "5px 12px",
                background: "rgba(255,255,255,0.15)",
                borderRadius: 99,
                fontSize: 12,
                color: "rgba(255,255,255,0.9)",
                fontWeight: 500,
              }}>
                {f}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>
          PulseDesk — Employee Monitoring System v3.0
        </div>
      </div>

      {/* ── Right panel ── */}
      <div style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 40,
      }}>
        <div style={{ width: "100%", maxWidth: 380 }}>
          <div style={{ marginBottom: 32 }}>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", marginBottom: 6 }}>
              Admin sign in
            </h1>
            <p style={{ fontSize: 14, color: "var(--text-tertiary)" }}>
              Sign in to your admin dashboard.
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="email" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Email address
              </label>
              <input
                id="email" type="email" className="input"
                value={email} onChange={e => setEmail(e.target.value)}
                placeholder="admin@yourcompany.com"
                required autoFocus autoComplete="email"
                style={{ fontSize: 14, padding: "10px 12px" }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="password" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Password
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="password" type={showPw ? "text" : "password"}
                  className="input" value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••" required
                  autoComplete="current-password"
                  style={{ fontSize: 14, padding: "10px 12px", paddingRight: 44 }}
                />
                <button type="button" onClick={() => setShowPw(s => !s)} style={{
                  position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                  background: "none", border: "none", cursor: "pointer",
                  color: "var(--text-tertiary)", display: "flex", padding: 2,
                }}>
                  {showPw ? <EyeOff size={16}/> : <Eye size={16}/>}
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                padding: "10px 14px",
                background: "var(--danger-subtle)",
                color: "var(--danger)",
                borderRadius: "var(--radius-md)",
                fontSize: 13, lineHeight: 1.5,
              }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary"
              disabled={loading || !email || !password}
              style={{ justifyContent: "center", padding: "11px 16px", fontSize: 14, fontWeight: 600, marginTop: 4 }}>
              {loading ? (
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    width: 15, height: 15, border: "2px solid rgba(255,255,255,0.3)",
                    borderTop: "2px solid #fff", borderRadius: "50%",
                    animation: "spin 0.8s linear infinite", display: "inline-block",
                  }}/>
                  Signing in…
                </span>
              ) : "Sign in →"}
            </button>
          </form>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "24px 0" }}>
            <div style={{ flex: 1, height: 1, background: "var(--border-subtle)" }}/>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>OR</span>
            <div style={{ flex: 1, height: 1, background: "var(--border-subtle)" }}/>
          </div>

          {/* Employee box */}
          <div style={{
            padding: "14px 16px",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-lg)",
          }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", marginBottom: 4 }}>
              Setting up your device?
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", lineHeight: 1.6, marginBottom: 10 }}>
              Ask your admin for a 6-digit join code, then visit the employee portal to get set up in 2 minutes — no technical knowledge needed.
            </div>
            <a href={portalUrl} target="_blank" rel="noopener noreferrer"
              className="btn btn-secondary btn-sm"
              style={{ textDecoration: "none", display: "inline-flex" }}>
              Open employee portal →
            </a>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) {
          .login-left-panel { display: none !important; }
        }
      `}</style>
    </div>
  );
}
