/**
 * PulseDesk AI Insights Page
 * Three features: Chat Analyst, Team Pulse Summary, Work Recommendations
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Bot, Send, Zap, RefreshCw,
  Sparkles, Shield,
  Brain, User, TrendingUp,
  AlertCircle, BarChart3, Award, Target, ArrowUpRight, ArrowDownRight, Minus,
  FileText, Calendar, ChevronRight,
} from "lucide-react";
import { api, weeklySummariesApi } from "../api/client";
import { Dialog } from "../components/ui/Dialog";
import { EmployeeSearchDropdown } from "../components/ui/EmployeeSearchDropdown";

// ── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface Employee {
  id: string;
  full_name: string;
  email: string;
  department_id: string | null;
}

interface WorkRecommendationData {
  employee_id: string;
  employee_name: string;
  current_state: string;
  recommendation: string;
  priority: string;
  rationale: string[];
}

interface TeamPulseEmployee {
  name: string;
  department: string;
  avg_score: number;
  avg_active_hours: number;
  anomalies: number;
  trend: "up" | "down" | "stable";
}

interface TeamPulseData {
  total_employees: number;
  avg_team_score: number;
  team_trend: "up" | "down" | "stable";
  total_anomalies: number;
  avg_active_hours: number;
  top_performers: TeamPulseEmployee[];
  needs_attention: TeamPulseEmployee[];
  ai_summary: string;
  generated_at: string;
}

// ── Quick prompts ─────────────────────────────────────────────────────────────

const QUICK_PROMPTS = [
  "Who is underperforming this week and why?",
  "Which employees are working after hours — is it a concern?",
  "Compare productivity across departments",
  "Who had the most anomalies this week?",
  "Give me an executive summary of team health",
  "Who should I check in with today?",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function categoryIcon(cat: string) {
  const map: Record<string, string> = {
    software_development: "💻", data_analysis: "📊", design: "🎨",
    writing: "✍️", communication: "💬", research: "🔍",
    entertainment: "🎬", social_media: "📱", gaming: "🎮",
    system_admin: "⚙️", video_call: "📹", idle: "😴", other: "📋",
  };
  return map[cat] ?? "📋";
}

function scoreColor(score: number): string {
  if (score >= 75) return "var(--success)";
  if (score >= 50) return "var(--warning)";
  return "var(--danger)";
}

function scoreBg(score: number): string {
  if (score >= 75) return "rgba(34,197,94,0.10)";
  if (score >= 50) return "rgba(245,158,11,0.10)";
  return "rgba(239,68,68,0.10)";
}

function trendIcon(trend: "up" | "down" | "stable") {
  if (trend === "up") return <ArrowUpRight size={14} color="var(--success)" />;
  if (trend === "down") return <ArrowDownRight size={14} color="var(--danger)" />;
  return <Minus size={14} color="var(--text-tertiary)" />;
}

function trendLabel(trend: "up" | "down" | "stable") {
  if (trend === "up") return "Improving";
  if (trend === "down") return "Declining";
  return "Stable";
}

// Simple markdown→HTML for bold/bullets
function renderMarkdown(text: string) {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const trimmedLine = line.trim();
    if (trimmedLine === "") return <div key={i} style={{ height: 8 }} />;

    let isHeader = false;
    let headerLevel = 0;
    let content = trimmedLine;

    if (trimmedLine.startsWith("### ")) {
      isHeader = true; headerLevel = 3; content = trimmedLine.slice(4);
    } else if (trimmedLine.startsWith("## ")) {
      isHeader = true; headerLevel = 2; content = trimmedLine.slice(3);
    } else if (trimmedLine.startsWith("# ")) {
      isHeader = true; headerLevel = 1; content = trimmedLine.slice(2);
    }

    let isBullet = false;
    let isNumbered = false;
    let bulletPrefix = "";
    
    if (!isHeader) {
      if (trimmedLine.startsWith("- ") || trimmedLine.startsWith("• ") || trimmedLine.startsWith("* ")) {
        isBullet = true;
        content = trimmedLine.slice(2);
      } else {
        const match = trimmedLine.match(/^(\d+\.)\s+(.*)/);
        if (match) {
          isNumbered = true;
          bulletPrefix = match[1];
          content = match[2];
        }
      }
    }

    // Bold **text**
    const parts = content.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((p, j) =>
      p.startsWith("**") && p.endsWith("**")
        ? <strong key={j}>{p.slice(2, -2)}</strong>
        : p
    );

    if (isHeader) {
      const fontSize = headerLevel === 1 ? 16 : headerLevel === 2 ? 15 : 14;
      const margin = headerLevel === 1 ? "16px 0 8px 0" : "12px 0 6px 0";
      return (
        <div key={i} style={{ fontWeight: 600, color: "var(--text-primary)", fontSize, margin }}>
          {rendered}
        </div>
      );
    }

    if (isBullet) {
      return (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
          <span style={{ color: "var(--accent)", marginTop: 1 }}>•</span>
          <span>{rendered}</span>
        </div>
      );
    }

    if (isNumbered) {
      return (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
          <span style={{ color: "var(--text-tertiary)", marginTop: 1, fontWeight: 500 }}>{bulletPrefix}</span>
          <span>{rendered}</span>
        </div>
      );
    }

    return <div key={i} style={{ marginBottom: 4, lineHeight: 1.6 }}>{rendered}</div>;
  });
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "chat" | "pulse" | "recommendations" | "weekly_reports";

export function AIInsightsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <div style={{ padding: "var(--space-6)", maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, background: "linear-gradient(135deg, #6366f1, #3b82f6)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Sparkles size={20} color="white" />
          </div>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
              AI Insights
            </h1>
            <p style={{ margin: 0, fontSize: 13, color: "var(--text-tertiary)" }}>
              Powered by Groq AI · Live data analysis
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 4, background: "var(--bg-tertiary)",
        padding: 4, borderRadius: "var(--radius-lg)", marginBottom: "var(--space-6)",
        width: "fit-content",
      }}>
        {([
          { id: "chat" as Tab, icon: Bot, label: "AI Chat Analyst" },
          { id: "pulse" as Tab, icon: BarChart3, label: "Team Pulse Summary" },
          { id: "recommendations" as Tab, icon: Zap, label: "Work Recommendations" },
          { id: "weekly_reports" as Tab, icon: FileText, label: "Weekly AI Reports" },
        ] as const).map(({ id, icon: Icon, label }) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{
            display: "flex", alignItems: "center", gap: 7,
            padding: "8px 16px", borderRadius: "var(--radius-md)",
            border: "none", cursor: "pointer", fontSize: 13, fontWeight: 500,
            background: activeTab === id ? "var(--bg-primary)" : "transparent",
            color: activeTab === id ? "var(--text-primary)" : "var(--text-tertiary)",
            boxShadow: activeTab === id ? "var(--shadow-sm)" : "none",
            transition: "all 0.15s",
          }}>
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Panels */}
      {activeTab === "chat"            && <ChatPanel />}
      {activeTab === "pulse"           && <TeamPulsePanel />}
      {activeTab === "recommendations" && <WorkRecommendationsPanel />}
      {activeTab === "weekly_reports"  && <WeeklyAIReportsPanel />}
    </div>
  );
}

// ── Chat Panel ────────────────────────────────────────────────────────────────

function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    const newMessages: ChatMessage[] = [...messages, { role: "user", content: msg }];
    setMessages(newMessages);
    setLoading(true);
    try {
      const history = newMessages.slice(0, -1).map(m => ({ role: m.role, content: m.content }));
      const { data } = await api.post("/ai/chat", { message: msg, history });
      setMessages([...newMessages, { role: "assistant", content: data.reply }]);
    } catch {
      setMessages([...newMessages, {
        role: "assistant",
        content: "⚠️ AI service is currently unavailable. Please check backend logs.",
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {/* Chat Window */}
      <div style={{
        background: "var(--bg-primary)", border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-xl)", overflow: "hidden",
        boxShadow: "var(--shadow-md)",
      }}>
        {/* Messages */}
        <div style={{
          height: 440, overflowY: "auto", padding: "var(--space-5)",
          display: "flex", flexDirection: "column", gap: "var(--space-4)",
        }}>
          {messages.length === 0 && (
            <div style={{
              flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", gap: 12,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 16,
                background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(59,130,246,0.15))",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Brain size={26} color="var(--accent)" />
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                  Ask me anything about your team
                </div>
                <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>
                  I have access to live productivity data, anomalies, and activity patterns.
                </div>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} style={{
              display: "flex", gap: 10,
              flexDirection: m.role === "user" ? "row-reverse" : "row",
            }}>
              {/* Avatar */}
              <div style={{
                width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                background: m.role === "assistant"
                  ? "linear-gradient(135deg, #6366f1, #3b82f6)"
                  : "var(--bg-tertiary)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {m.role === "assistant"
                  ? <Sparkles size={15} color="white" />
                  : <User size={15} color="var(--text-secondary)" />
                }
              </div>
              {/* Bubble */}
              <div style={{
                maxWidth: "78%",
                padding: "10px 14px",
                borderRadius: m.role === "user" ? "12px 4px 12px 12px" : "4px 12px 12px 12px",
                background: m.role === "user" ? "var(--accent)" : "var(--bg-secondary)",
                color: m.role === "user" ? "white" : "var(--text-primary)",
                fontSize: 13.5, lineHeight: 1.6,
              }}>
                {m.role === "assistant" ? renderMarkdown(m.content) : m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: "flex", gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                background: "linear-gradient(135deg, #6366f1, #3b82f6)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Sparkles size={15} color="white" />
              </div>
              <div style={{
                padding: "10px 14px", borderRadius: "4px 12px 12px 12px",
                background: "var(--bg-secondary)", display: "flex", gap: 4, alignItems: "center",
              }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 6, height: 6, borderRadius: "50%", background: "var(--accent)",
                    animation: `pulse 1s ease-in-out ${i * 0.2}s infinite`,
                    opacity: 0.6,
                  }} />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "var(--space-3) var(--space-4)",
          display: "flex", gap: "var(--space-2)",
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Ask about your team..."
            style={{
              flex: 1, border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)",
              padding: "9px 13px", fontSize: 13.5, background: "var(--bg-secondary)",
              color: "var(--text-primary)", outline: "none",
            }}
          />
          <button onClick={() => send()} disabled={loading || !input.trim()} style={{
            padding: "9px 14px", borderRadius: "var(--radius-md)", border: "none",
            background: "var(--accent)", color: "white", cursor: "pointer",
            opacity: loading || !input.trim() ? 0.5 : 1, display: "flex", alignItems: "center",
          }}>
            <Send size={15} />
          </button>
        </div>
      </div>

      {/* Quick Prompts */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Quick questions
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {QUICK_PROMPTS.map(p => (
            <button key={p} onClick={() => send(p)} disabled={loading} style={{
              padding: "7px 12px", borderRadius: "var(--radius-full)",
              border: "1px solid var(--border-default)", background: "var(--bg-primary)",
              color: "var(--text-secondary)", fontSize: 12.5, cursor: "pointer",
              opacity: loading ? 0.5 : 1, transition: "all 0.15s",
            }}>
              {p}
            </button>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0.4; }
          50% { transform: scale(1.3); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ── Team Pulse Summary Panel ──────────────────────────────────────────────────

function TeamPulsePanel() {
  const [data, setData] = useState<TeamPulseData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPulse = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Use the chat endpoint with a structured query to get team pulse
      const { data: res } = await api.post("/ai/chat", {
        message: "Give me a brief executive team health summary in 2-3 sentences. Include overall productivity assessment, any concerns, and one key recommendation.",
        history: [],
      });

      // Also fetch employee data for metrics
      const { data: employees } = await api.get("/employees");
      const employeeList = Array.isArray(employees) ? employees : [];

      // Fetch diagnostics for real metrics
      let diagnostics: any = null;
      try {
        const { data: diag } = await api.get("/ai/diagnostics/data-status");
        diagnostics = diag;
      } catch {
        // diagnostics endpoint may not be available
      }

      // Build team pulse from multiple data sources
      const topPerformers: TeamPulseEmployee[] = [];
      const needsAttention: TeamPulseEmployee[] = [];

      // Try to get individual scores via work-recommendations for each employee
      const employeeMetrics: { name: string; score: number; hours: number; anomalies: number }[] = [];

      for (const emp of employeeList.slice(0, 10)) {
        try {
          const { data: report } = await api.get(`/ai/work-recommendations/${emp.id}`);
          if (report?.metrics) {
            employeeMetrics.push({
              name: emp.full_name,
              score: report.metrics.productivity_score || 0,
              hours: report.metrics.avg_active_hours || 0,
              anomalies: report.metrics.anomalies || 0,
            });
          }
        } catch {
          // skip
        }
      }

      // Sort and categorize
      employeeMetrics.sort((a, b) => b.score - a.score);

      for (const m of employeeMetrics.slice(0, 3)) {
        topPerformers.push({
          name: m.name,
          department: "Team",
          avg_score: m.score,
          avg_active_hours: m.hours,
          anomalies: m.anomalies,
          trend: m.score >= 70 ? "up" : m.score >= 50 ? "stable" : "down",
        });
      }

      for (const m of employeeMetrics.filter(m => m.score < 60).slice(0, 3)) {
        needsAttention.push({
          name: m.name,
          department: "Team",
          avg_score: m.score,
          avg_active_hours: m.hours,
          anomalies: m.anomalies,
          trend: m.score < 40 ? "down" : "stable",
        });
      }

      const avgScore = employeeMetrics.length > 0
        ? employeeMetrics.reduce((s, m) => s + m.score, 0) / employeeMetrics.length
        : 0;
      const avgHours = employeeMetrics.length > 0
        ? employeeMetrics.reduce((s, m) => s + m.hours, 0) / employeeMetrics.length
        : 0;
      const totalAnomalies = employeeMetrics.reduce((s, m) => s + m.anomalies, 0);

      setData({
        total_employees: employeeList.length,
        avg_team_score: Math.round(avgScore * 10) / 10,
        team_trend: avgScore >= 65 ? "up" : avgScore >= 45 ? "stable" : "down",
        total_anomalies: totalAnomalies,
        avg_active_hours: Math.round(avgHours * 10) / 10,
        top_performers: topPerformers,
        needs_attention: needsAttention,
        ai_summary: res.reply,
        generated_at: new Date().toLocaleString(),
      });
    } catch (err: any) {
      console.error("Team pulse error:", err);
      setError("Failed to generate team pulse. Ensure the backend and AI service are running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPulse(); }, [fetchPulse]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {/* Header card */}
      <div style={{
        background: "linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.08))",
        border: "1px solid rgba(59,130,246,0.15)", borderRadius: "var(--radius-xl)",
        padding: "var(--space-5)", display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: "rgba(59,130,246,0.12)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <BarChart3 size={22} color="var(--accent)" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "var(--text-primary)" }}>
              Team Pulse Summary
            </div>
            <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>
              Real-time AI-generated team health overview · Last 7 days
            </div>
          </div>
        </div>
        <button onClick={fetchPulse} disabled={loading} style={{
          display: "flex", alignItems: "center", gap: 7, padding: "8px 14px",
          borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)",
          background: "var(--bg-primary)", color: "var(--text-secondary)",
          fontSize: 13, fontWeight: 500, cursor: "pointer", opacity: loading ? 0.6 : 1,
        }}>
          <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          Refresh
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", padding: "var(--space-12)", gap: 16,
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%",
            border: "3px solid var(--border-default)",
            borderTopColor: "var(--accent)",
            animation: "spin 1s linear infinite",
          }} />
          <div style={{ fontSize: 13.5, color: "var(--text-tertiary)" }}>
            Generating team pulse summary...
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div style={{
          padding: "var(--space-4)", background: "var(--danger-subtle)",
          border: "1px solid rgba(220,38,38,0.2)", borderRadius: "var(--radius-lg)",
          fontSize: 13.5, color: "var(--danger)", display: "flex", gap: 8, alignItems: "flex-start",
        }}>
          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>{error}</div>
        </div>
      )}

      {/* Data display */}
      {data && !loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {/* Metric Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-3)" }}>
            {/* Team Score */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
              borderTop: `3px solid ${scoreColor(data.avg_team_score)}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
                  Team Score
                </div>
                {trendIcon(data.team_trend)}
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: scoreColor(data.avg_team_score), lineHeight: 1 }}>
                {data.avg_team_score}%
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                {trendLabel(data.team_trend)} trend
              </div>
            </div>

            {/* Employees */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
              borderTop: "3px solid var(--accent)",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 8 }}>
                Active Employees
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "var(--accent)", lineHeight: 1 }}>
                {data.total_employees}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                Currently tracked
              </div>
            </div>

            {/* Avg Active Hours */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
              borderTop: "3px solid #8b5cf6",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 8 }}>
                Avg Daily Hours
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#8b5cf6", lineHeight: 1 }}>
                {data.avg_active_hours}h
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                Per employee
              </div>
            </div>

            {/* Anomalies */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
              borderTop: "3px solid #f97316",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 8 }}>
                Total Anomalies
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#f97316", lineHeight: 1 }}>
                {data.total_anomalies}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                Last 7 days
              </div>
            </div>
          </div>

          {/* AI Summary */}
          <div style={{
            background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(59,130,246,0.06))",
            border: "1px solid rgba(99,102,241,0.15)", borderRadius: "var(--radius-lg)",
            padding: "var(--space-5)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: "linear-gradient(135deg, #6366f1, #3b82f6)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Sparkles size={14} color="white" />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                AI Analysis
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: "auto" }}>
                {data.generated_at}
              </div>
            </div>
            <div style={{ fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.7 }}>
              {renderMarkdown(data.ai_summary)}
            </div>
          </div>

          {/* Two-column layout: Top Performers + Needs Attention */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            {/* Top Performers */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", overflow: "hidden",
            }}>
              <div style={{
                padding: "var(--space-4) var(--space-5)",
                borderBottom: "1px solid var(--border-subtle)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <Award size={16} color="var(--success)" />
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  Top Performers
                </span>
              </div>
              <div style={{ padding: "var(--space-2)" }}>
                {data.top_performers.length === 0 ? (
                  <div style={{ padding: "var(--space-4)", textAlign: "center", fontSize: 13, color: "var(--text-tertiary)" }}>
                    No performance data yet
                  </div>
                ) : (
                  data.top_performers.map((emp, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 12,
                      padding: "10px var(--space-3)", borderRadius: "var(--radius-md)",
                      background: i === 0 ? "rgba(34,197,94,0.06)" : "transparent",
                    }}>
                      {/* Rank */}
                      <div style={{
                        width: 28, height: 28, borderRadius: "50%",
                        background: i === 0 ? "var(--success)" : "var(--bg-tertiary)",
                        color: i === 0 ? "white" : "var(--text-secondary)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 12, fontWeight: 700, flexShrink: 0,
                      }}>
                        {i + 1}
                      </div>
                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {emp.name}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                          {emp.avg_active_hours}h/day · {emp.anomalies} anomalies
                        </div>
                      </div>
                      {/* Score */}
                      <div style={{
                        fontSize: 14, fontWeight: 700, color: scoreColor(emp.avg_score),
                        background: scoreBg(emp.avg_score),
                        padding: "3px 10px", borderRadius: "var(--radius-full)",
                      }}>
                        {emp.avg_score}%
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Needs Attention */}
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", overflow: "hidden",
            }}>
              <div style={{
                padding: "var(--space-4) var(--space-5)",
                borderBottom: "1px solid var(--border-subtle)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <Target size={16} color="#f97316" />
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  Needs Attention
                </span>
              </div>
              <div style={{ padding: "var(--space-2)" }}>
                {data.needs_attention.length === 0 ? (
                  <div style={{
                    padding: "var(--space-4)", textAlign: "center", fontSize: 13, color: "var(--text-tertiary)",
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                  }}>
                    <Shield size={20} color="var(--success)" />
                    <span>All employees are performing well!</span>
                  </div>
                ) : (
                  data.needs_attention.map((emp, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 12,
                      padding: "10px var(--space-3)", borderRadius: "var(--radius-md)",
                      background: i === 0 ? "rgba(249,115,22,0.06)" : "transparent",
                    }}>
                      {/* Warning icon */}
                      <div style={{
                        width: 28, height: 28, borderRadius: "50%",
                        background: "rgba(249,115,22,0.12)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        flexShrink: 0,
                      }}>
                        <AlertCircle size={14} color="#f97316" />
                      </div>
                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {emp.name}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                          {emp.avg_active_hours}h/day · {emp.anomalies} anomalies
                        </div>
                      </div>
                      {/* Score */}
                      <div style={{
                        fontSize: 14, fontWeight: 700, color: scoreColor(emp.avg_score),
                        background: scoreBg(emp.avg_score),
                        padding: "3px 10px", borderRadius: "var(--radius-full)",
                      }}>
                        {emp.avg_score}%
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ── Work Recommendations Panel ──────────────────────────────────────────────────

function WorkRecommendationsPanel() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionItemsState, setActionItemsState] = useState<Record<number, boolean>>({});
  const [savedActionItems, setSavedActionItems] = useState<Record<number, string>>({});

  useEffect(() => {
    const loadEmployees = async () => {
      try {
        const { data: emps } = await api.get("/employees");
        setEmployees(emps);
        if (emps.length > 0) {
          setSelectedEmployee(emps[0].id);
        }
      } catch (err) {
        setError("Failed to load employees list.");
      } finally {
        setLoadingEmployees(false);
      }
    };
    loadEmployees();
  }, []);

  useEffect(() => {
    if (selectedEmployee && !loadingEmployees) {
      generateReport();
    }
  }, [selectedEmployee, loadingEmployees]);

  const generateReport = useCallback(async () => {
    if (!selectedEmployee) return;
    setLoading(true);
    setError(null);
    setActionItemsState({}); // Reset action items state
    setSavedActionItems({}); // Reset saved items
    try {
      const { data: res } = await api.get(`/ai/work-recommendations/${selectedEmployee}`);
      if (res && res.summary) {
        setReport(res);
        setError(null);
      } else {
        setError("No report data available.");
        setReport(null);
      }
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || "Failed to generate weekly report.";
      setError(errorMsg);
      setReport(null);
      console.error("Weekly report error:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedEmployee]);

  const handleActionItemToggle = async (index: number, item: string, isChecked: boolean) => {
    if (!selectedEmployee) {
      console.error("No employee selected");
      return;
    }
    
    setActionItemsState(prev => ({ ...prev, [index]: isChecked }));
    
    if (isChecked && !savedActionItems[index]) {
      try {
        // Save action item to backend
        const response = await api.post("/actions", {
          employee_id: selectedEmployee,
          action_text: item,
          priority: "medium",
          report_id: `weekly-${new Date().toISOString().split('T')[0]}`,
        });
        
        const itemId = response?.data?.id;
        console.log("Action item created with ID:", itemId, "Response:", response);
        
        if (itemId) {
          setSavedActionItems(prev => ({ ...prev, [index]: itemId }));
        } else {
          console.error("No ID in response:", response);
          setActionItemsState(prev => ({ ...prev, [index]: false }));
        }
      } catch (err: any) {
        console.error("Failed to save action item:", err?.response?.data || err?.message || err);
        setActionItemsState(prev => ({ ...prev, [index]: false }));
      }
    } else if (!isChecked && savedActionItems[index]) {
      try {
        // Mark as completed
        const response = await api.patch(`/actions/${savedActionItems[index]}`, {
          is_completed: true,
        });
        console.log("Action item marked completed:", response);
      } catch (err: any) {
        console.error("Failed to update action item:", err?.response?.data || err?.message || err);
      }
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {/* Header */}
      <div style={{
        background: "linear-gradient(135deg, rgba(168,85,247,0.08), rgba(99,102,241,0.08))",
        border: "1px solid rgba(168,85,247,0.15)", borderRadius: "var(--radius-xl)",
        padding: "var(--space-5)", display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: "rgba(168,85,247,0.12)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Sparkles size={22} color="#a855f7" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "var(--text-primary)" }}>
              AI Weekly Performance Report
            </div>
            <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>
              AI-generated coaching and personalized insights
            </div>
          </div>
        </div>
        <button onClick={generateReport} disabled={loading} style={{
          display: "flex", alignItems: "center", gap: "7px", padding: "8px 14px",
          borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)",
          background: "var(--bg-primary)", color: "var(--text-secondary)",
          fontSize: 13, fontWeight: 500, cursor: "pointer", opacity: loading ? 0.6 : 1,
        }}>
          <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          Generate Report
        </button>
      </div>

      {/* Employee selector */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
          Select Employee
        </label>
        <EmployeeSearchDropdown
          selectedId={selectedEmployee}
          onChange={setSelectedEmployee}
          width="100%"
        />
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "var(--space-12)", gap: "16px" }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%",
            border: "3px solid var(--border-default)", borderTopColor: "var(--accent)",
            animation: "spin 1s linear infinite",
          }} />
          <div style={{ fontSize: 13.5, color: "var(--text-tertiary)" }}>
            AI is analyzing performance and generating personalized insights...
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div style={{
          padding: "var(--space-4)", background: "var(--danger-subtle)",
          border: "1px solid rgba(220,38,38,0.2)", borderRadius: "var(--radius-lg)",
          fontSize: 13.5, color: "var(--danger)", display: "flex", gap: "8px", alignItems: "flex-start",
        }}>
          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, marginBottom: "4px" }}>Unable to generate report</div>
            <div style={{ fontSize: 13 }}>{error}</div>
          </div>
        </div>
      )}

      {/* Report display */}
      {report && !loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {/* Title and period */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "4px" }}>
              Report Period
            </div>
            <div style={{ fontSize: 14, color: "var(--text-primary)" }}>
              {report.period || "This Week"}
            </div>
          </div>

          {/* Performance rating */}
          {report.performance_rating && (
            <div style={{
              background: "linear-gradient(135deg, rgba(168,85,247,0.1), rgba(99,102,241,0.1))",
              border: "1px solid rgba(168,85,247,0.2)", borderRadius: "var(--radius-lg)",
              padding: "var(--space-4)", borderLeft: "4px solid #a855f7",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "6px" }}>
                Performance Rating
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#a855f7" }}>
                {report.performance_rating}
              </div>
            </div>
          )}

          {/* Summary */}
          {report.summary && (
            <div style={{
              background: "var(--bg-primary)", border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "8px" }}>
                Summary
              </div>
              <div style={{ fontSize: 14, color: "var(--text-primary)", lineHeight: 1.6 }}>
                {report.summary}
              </div>
            </div>
          )}

          {/* Highlights (2 columns) */}
          {report.highlights && report.highlights.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--success)", textTransform: "uppercase", marginBottom: "10px" }}>
                Highlights & Achievements
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                {report.highlights.map((h: string, i: number) => (
                  <div key={i} style={{
                    background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)",
                    borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
                    fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "var(--success)", fontWeight: 600 }}>+</span> {h}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Focus areas (2 columns) */}
          {report.focus_areas && report.focus_areas.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--warning)", textTransform: "uppercase", marginBottom: "10px" }}>
                Focus Areas for Improvement
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                {report.focus_areas.map((f: string, i: number) => (
                  <div key={i} style={{
                    background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.15)",
                    borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
                    fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "var(--warning)", fontWeight: 600 }}>-&gt;</span> {f}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Coaching tips */}
          {report.coaching_tips && report.coaching_tips.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#a855f7", textTransform: "uppercase", marginBottom: "10px" }}>
                Coaching Tips for Next Week
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {report.coaching_tips.map((tip: string, i: number) => (
                  <div key={i} style={{
                    background: "rgba(168,85,247,0.08)", border: "1px solid rgba(168,85,247,0.15)",
                    borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
                    fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "#a855f7", fontWeight: 600 }}>#{i+1}</span> {tip}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action items — NOW FUNCTIONAL */}
          {report.action_items && report.action_items.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#ef4444", textTransform: "uppercase", marginBottom: "10px" }}>
                Action Items (Saved to Backend)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {report.action_items.map((item: string, i: number) => (
                  <div key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                    <input
                      type="checkbox"
                      checked={actionItemsState[i] ?? false}
                      onChange={(e) => handleActionItemToggle(i, item, e.target.checked)}
                      style={{ marginTop: "4px", cursor: "pointer" }}
                    />
                    <span style={{
                      fontSize: 13,
                      color: actionItemsState[i] ? "var(--text-tertiary)" : "var(--text-secondary)",
                      textDecoration: actionItemsState[i] ? "line-through" : "none",
                    }}>
                      {item}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Motivational message */}
          {report.motivational_message && (
            <div style={{
              background: "linear-gradient(135deg, rgba(34,197,94,0.1), rgba(16,185,129,0.1))",
              border: "1px dashed rgba(34,197,94,0.3)", borderRadius: "var(--radius-lg)",
              padding: "var(--space-4)", textAlign: "center",
              fontStyle: "italic", color: "var(--text-secondary)", fontSize: 14, lineHeight: 1.6,
            }}>
              {report.motivational_message}
            </div>
          )}

          {/* Metrics */}
          {report.metrics && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "10px" }}>
                Key Metrics
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-3)" }}>
                <div style={{
                  background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)", textAlign: "center",
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: "4px" }}>Active Hours</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent)" }}>
                    {report.metrics.avg_active_hours}h
                  </div>
                </div>
                <div style={{
                  background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)", textAlign: "center",
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: "4px" }}>Focus Hours</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#06b6d4" }}>
                    {report.metrics.avg_focus_hours}h
                  </div>
                </div>
                <div style={{
                  background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)", textAlign: "center",
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: "4px" }}>Productivity</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--success)" }}>
                    {report.metrics.productivity_score}%
                  </div>
                </div>
                <div style={{
                  background: "var(--bg-secondary)", borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)", textAlign: "center",
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: "4px" }}>Anomalies</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#f97316" }}>
                    {report.metrics.anomalies}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {!report && !loading && !error && selectedEmployee && (
        <div style={{
          padding: "var(--space-8)", textAlign: "center",
          background: "var(--bg-secondary)", borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-subtle)",
        }}>
          <div style={{ fontSize: 13.5, color: "var(--text-tertiary)" }}>
            Click "Generate Report" to see AI-powered performance coaching for this employee
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}


function WeeklyAIReportsPanel() {
  const [summaries, setSummaries] = useState<any[]>([]);
  const [selectedSummary, setSelectedSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split("T")[0]);
  const [error, setError] = useState<string | null>(null);

  const fetchSummaries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await weeklySummariesApi.list();
      setSummaries(data);
      if (data.length > 0) {
        setSelectedSummary(data[0]);
      }
    } catch (err) {
      setError("Failed to load weekly summaries.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummaries();
  }, [fetchSummaries]);

  const handleTrigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      const newSummary = await weeklySummariesApi.trigger(selectedDate);
      await Dialog.alert("Weekly summary generated successfully!", "Success");
      setSelectedSummary(newSummary);
      fetchSummaries();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Make sure telemetry data exists for the selected week.";
      await Dialog.alert(`Failed to trigger summary: ${detail}`, "Trigger Failed");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Trigger Control Panel */}
      <div className="card" style={{ padding: "var(--space-5)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 48, height: 48, borderRadius: "var(--radius-lg)", background: "var(--accent-subtle)",
            display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--accent-subtle)"
          }}>
            <FileText size={22} style={{ color: "var(--accent)" }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 16, color: "var(--text-primary)", marginBottom: 2 }}>Weekly AI Management Reports</div>
            <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>Aggregate telemetry summaries and generate executive recommendations weekly.</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 11, fontWeight: 500, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Target Date</label>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="input"
              style={{ padding: "8px 12px", width: 140 }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, alignSelf: "flex-end" }}>
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="btn btn-primary"
              style={{ display: "flex", alignItems: "center", gap: 8, height: 38 }}
            >
              {triggering ? <RefreshCw size={15} className="spin" /> : <Sparkles size={15} />}
              {triggering ? "Generating..." : "Compile Summary"}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="skeleton" style={{ height: 120, borderRadius: "var(--radius-xl)" }} />
          <div className="skeleton" style={{ height: 300, borderRadius: "var(--radius-xl)" }} />
        </div>
      ) : summaries.length === 0 ? (
        <div className="card empty-state" style={{ padding: "64px 24px", textAlign: "center" }}>
          <div className="empty-state-icon">📊</div>
          <div className="empty-state-title">No Weekly AI Reports Yet</div>
          <div className="empty-state-body">Select a date above and compile the first executive report!</div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "var(--space-6)" }}>
          {/* List Sidebar */}
          <div className="card" style={{ padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: 12, height: "fit-content" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.06em", padding: "0 4px" }}>
              Report History
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 600, overflowY: "auto", paddingRight: 4 }}>
              {summaries.map((s) => {
                const isSelected = selectedSummary?.id === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => setSelectedSummary(s)}
                    style={{
                      textAlign: "left",
                      padding: "12px 14px",
                      borderRadius: "var(--radius-md)",
                      border: isSelected ? "1px solid var(--accent)" : "1px solid transparent",
                      background: isSelected ? "var(--accent-subtle)" : "var(--bg-secondary)",
                      cursor: "pointer",
                      outline: "none",
                      width: "100%",
                      transition: "all 0.2s ease",
                      position: "relative",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = "var(--bg-tertiary)";
                        e.currentTarget.style.border = "1px solid var(--border-default)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = "var(--bg-secondary)";
                        e.currentTarget.style.border = "1px solid transparent";
                      }
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: isSelected ? "var(--accent-text)" : "var(--text-primary)", display: "flex", alignItems: "center", gap: 6 }}>
                      <Calendar size={14} style={{ color: isSelected ? "var(--accent)" : "var(--text-tertiary)" }} />
                      Week of {s.week_start}
                    </div>
                    <div style={{ fontSize: 11, color: isSelected ? "var(--accent-text)" : "var(--text-tertiary)", opacity: 0.8, paddingLeft: 20 }}>
                      to {s.week_end}
                    </div>
                    {isSelected && (
                      <div style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)" }}>
                        <ChevronRight size={16} color="var(--accent)" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Details Panel */}
          {selectedSummary && (
            <div className="card" style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: 24, boxShadow: "var(--shadow-sm)" }}>
              <div style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: 16 }}>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--text-primary)", marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
                  <Award size={20} style={{ color: "var(--accent)" }} />
                  Executive Weekly Summary
                </h3>
                <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13, color: "var(--text-secondary)" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <Calendar size={14} /> {selectedSummary.week_start} to {selectedSummary.week_end}
                  </span>
                  <span>•</span>
                  <span style={{ color: "var(--text-tertiary)" }}>Generated on {new Date(selectedSummary.created_at).toLocaleString()}</span>
                </div>
              </div>

              {/* Metrics grid for the week */}
              {selectedSummary.metrics && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
                    Key Performance Indicators
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 16 }}>
                    <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", padding: 16, borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: 500 }}>Active Hours</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent)", marginTop: 6 }}>{selectedSummary.metrics.total_active_hours}h</div>
                    </div>
                    <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", padding: 16, borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: 500 }}>Idle Hours</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--warning)", marginTop: 6 }}>{selectedSummary.metrics.total_idle_hours}h</div>
                    </div>
                    <div style={{ background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)", padding: 16, borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: 11, color: "var(--success)", textTransform: "uppercase", fontWeight: 600 }}>Avg Productivity</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--success)", marginTop: 6 }}>{selectedSummary.metrics.avg_productivity_score}%</div>
                    </div>
                    <div style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)", padding: 16, borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: 11, color: "var(--danger)", textTransform: "uppercase", fontWeight: 600 }}>Total Anomalies</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--danger)", marginTop: 6 }}>{selectedSummary.metrics.total_anomalies}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Weekly report markdown content */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
                  AI Analysis & Recommendations
                </div>
                <div style={{ 
                  fontSize: 14, 
                  color: "var(--text-secondary)", 
                  lineHeight: 1.7, 
                  background: "var(--bg-secondary)", 
                  padding: "20px 24px", 
                  borderRadius: "var(--radius-lg)", 
                  border: "1px solid var(--border-default)" 
                }}>
                  {renderMarkdown(selectedSummary.summary_text)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      
      <style>{`
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

