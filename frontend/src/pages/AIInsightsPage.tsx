/**
 * PulseDesk AI Insights Page
 * Four features: Chat Analyst, Burnout Risk Engine, Activity Patterns, Work Recommendations
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Bot, Send, Zap, AlertTriangle, RefreshCw,
  Sparkles, TrendingDown, Clock, Shield,
  ChevronDown, ChevronUp, Brain, User, Flame, TrendingUp,
  AlertCircle,
} from "lucide-react";
import { api } from "../api/client";
import type { Employee } from "../types";

// ── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Removed Burnout and Activity types

interface WorkRecommendationData {
  employee_id: string;
  employee_name: string;
  current_state: string;
  recommendation: string;
  priority: string;
  rationale: string[];
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

function riskColor(level: string) {
  if (level === "critical") return "var(--danger)";
  if (level === "high")     return "#f97316";
  if (level === "medium")   return "var(--warning)";
  return "var(--success)";
}

function riskBg(level: string) {
  if (level === "critical") return "rgba(239,68,68,0.10)";
  if (level === "high")     return "rgba(249,115,22,0.10)";
  if (level === "medium")   return "rgba(245,158,11,0.10)";
  return "rgba(34,197,94,0.10)";
}

function categoryIcon(cat: string) {
  const map: Record<string, string> = {
    software_development: "💻", data_analysis: "📊", design: "🎨",
    writing: "✍️", communication: "💬", research: "🔍",
    entertainment: "🎬", social_media: "📱", gaming: "🎮",
    system_admin: "⚙️", video_call: "📹", idle: "😴", other: "📋",
  };
  return map[cat] ?? "📋";
}

function productivityColor(level: string) {
  if (level === "focused")    return "var(--success)";
  if (level === "distracted") return "var(--danger)";
  if (level === "idle")       return "var(--text-tertiary)";
  return "var(--warning)";
}

// Simple markdown→HTML for bold/bullets
function renderMarkdown(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    // Bold **text**
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((p, j) =>
      p.startsWith("**") && p.endsWith("**")
        ? <strong key={j}>{p.slice(2, -2)}</strong>
        : p
    );
    // Bullet points
    if (line.startsWith("- ") || line.startsWith("• ")) {
      return (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 2 }}>
          <span style={{ color: "var(--accent)", marginTop: 1 }}>•</span>
          <span>{rendered.slice(1)}</span>
        </div>
      );
    }
    if (line === "") return <div key={i} style={{ height: 8 }} />;
    return <div key={i}>{rendered}</div>;
  });
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "chat" | "recommendations";

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
          { id: "recommendations" as Tab, icon: Zap, label: "Work Recommendations" },
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
      {activeTab === "recommendations" && <WorkRecommendationsPanel />}
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
        
        const itemId = response?.data?.id || (response as any)?.id;
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
        <select
          value={selectedEmployee}
          onChange={e => setSelectedEmployee(e.target.value)}
          disabled={loadingEmployees}
          style={{
            padding: "10px 12px", borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-default)", background: "var(--bg-secondary)",
            color: "var(--text-primary)", fontSize: 13.5, cursor: "pointer",
          }}
        >
          {employees.map(emp => (
            <option key={emp.id} value={emp.id}>
              {emp.full_name}
            </option>
          ))}
        </select>
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
            AI is analyzing performance and generating personalized insights…
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
                ✨ Highlights & Achievements
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                {report.highlights.map((h: string, i: number) => (
                  <div key={i} style={{
                    background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)",
                    borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
                    fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "var(--success)", fontWeight: 600 }}>✓</span> {h}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Focus areas (2 columns) */}
          {report.focus_areas && report.focus_areas.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--warning)", textTransform: "uppercase", marginBottom: "10px" }}>
                📌 Focus Areas for Improvement
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                {report.focus_areas.map((f: string, i: number) => (
                  <div key={i} style={{
                    background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.15)",
                    borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
                    fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "var(--warning)", fontWeight: 600 }}>→</span> {f}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Coaching tips */}
          {report.coaching_tips && report.coaching_tips.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#a855f7", textTransform: "uppercase", marginBottom: "10px" }}>
                💡 Coaching Tips for Next Week
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
                ✓ Action Items (Saved to Backend)
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
              💪 {report.motivational_message}
            </div>
          )}

          {/* Metrics */}
          {report.metrics && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "10px" }}>
                📊 Key Metrics
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
