import React, { useState, useEffect } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { Eye, EyeOff, Activity } from "lucide-react";
import { authApi } from "../api/client";
import { useAuthStore, selectIsAuthenticated } from "../store/authStore";

export function SignupPage() {
  const [fullName, setFullName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const navigate = useNavigate();
  const location = useLocation();
  const plan = location.state?.plan || "Community";

  useEffect(() => {
    if (isAuthenticated) navigate("/dashboard", { replace: true });
  }, [isAuthenticated]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 10) {
      setError("Password must be at least 10 characters long.");
      return;
    }

    const strengthChecks = [
      /[a-z]/.test(password),
      /[A-Z]/.test(password),
      /[0-9]/.test(password),
      /[^a-zA-Z0-9]/.test(password),
    ];
    if (strengthChecks.filter(Boolean).length < 3) {
      setError("Password must include at least three of the following: uppercase character, lowercase character, number, and special character/symbol.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      // Call public signup endpoint
      const signupData = await authApi.signup(email, password, fullName, businessName);
      
      // Get logged in user data
      const me = await authApi.me();
      
      // Update local state store
      setAuth(me, signupData.access_token);
      
      // Navigate to dashboard root
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (err?.response?.status === 429) {
        setError("Rate limit exceeded. Please try again in a minute.");
      } else if (!err?.response) {
        setError("Cannot reach server. Check backend connectivity and API base URL.");
      } else {
        setError("Registration failed. Please check your credentials and try again.");
      }
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
        className="signup-left-panel"
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
            Host your own secure analytics instance in minutes.
          </div>
          <div style={{ fontSize: 15, color: "rgba(255,255,255,0.72)", lineHeight: 1.65 }}>
            Create your Super Admin account to begin organizing departments, approving devices, and collecting secure activity streams.
          </div>

          {/* Core values */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 28 }}>
            {[
              "🔒 Absolute privacy: Zero data leaves your server",
              "🚀 Lightweight agent with automated updates",
              "📊 Comprehensive PDF productivity reporting"
            ].map(f => (
              <div key={f} style={{
                fontSize: 13,
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
          PulseDesk — SaaS Self-Hosted Setup
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
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>
                Create Admin Account
              </h1>
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--accent-text)",
                background: "var(--accent-subtle)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "100px",
                padding: "2px 8px",
                textTransform: "capitalize"
              }}>
                {plan} Plan
              </span>
            </div>
            <p style={{ fontSize: 14, color: "var(--text-tertiary)" }}>
              Set up your self-hosted organization admin space.
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="fullName" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Full Name
              </label>
              <input
                id="fullName" type="text" className="input"
                value={fullName} onChange={e => setFullName(e.target.value)}
                placeholder="Nikam Aniket"
                required autoFocus
                style={{ fontSize: 14, padding: "10px 12px" }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="businessName" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Business or School Name
              </label>
              <input
                id="businessName" type="text" className="input"
                value={businessName} onChange={e => setBusinessName(e.target.value)}
                placeholder="PulseDesk Academy / Acme Corp"
                required
                style={{ fontSize: 14, padding: "10px 12px" }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="accountType" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Account Type
              </label>
              <input
                id="accountType" type="text" className="input"
                value="Admin"
                disabled
                style={{ fontSize: 14, padding: "10px 12px", background: "var(--bg-secondary)", cursor: "not-allowed", opacity: 0.8 }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="email" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Email address
              </label>
              <input
                id="email" type="email" className="input"
                value={email} onChange={e => setEmail(e.target.value)}
                placeholder="admin@yourcompany.com"
                required autoComplete="email"
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
                  placeholder="At least 8 characters" required
                  autoComplete="new-password"
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

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label htmlFor="confirmPassword" style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Confirm Password
              </label>
              <input
                id="confirmPassword" type={showPw ? "text" : "password"}
                className="input" value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="••••••••" required
                autoComplete="new-password"
                style={{ fontSize: 14, padding: "10px 12px" }}
              />
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
              disabled={loading || !fullName || !businessName || !email || !password || !confirmPassword}
              style={{ justifyContent: "center", padding: "11px 16px", fontSize: 14, fontWeight: 600, marginTop: 4 }}>
              {loading ? (
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    width: 15, height: 15, border: "2px solid rgba(255,255,255,0.3)",
                    borderTop: "2px solid #fff", borderRadius: "50%",
                    animation: "spin 0.8s linear infinite", display: "inline-block",
                  }}/>
                  Creating Admin Account…
                </span>
              ) : "Get Started Free →"}
            </button>
          </form>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "24px 0" }}>
            <div style={{ flex: 1, height: 1, background: "var(--border-subtle)" }}/>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>OR</span>
            <div style={{ flex: 1, height: 1, background: "var(--border-subtle)" }}/>
          </div>

          {/* Sign in box */}
          <div style={{
            textAlign: "center",
            fontSize: 13,
            color: "var(--text-secondary)",
          }}>
            Already have an account?{" "}
            <Link to="/login" style={{
              color: "var(--accent)",
              fontWeight: 600,
              textDecoration: "none",
            }}>
              Sign in
            </Link>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) {
          .signup-left-panel { display: none !important; }
        }
      `}</style>
    </div>
  );
}
