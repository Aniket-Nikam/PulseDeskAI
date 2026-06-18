import React, { useState, useEffect, useCallback, useRef } from "react";
import { AlertTriangle, X, Bell } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { WsMessage } from "../../types";
import { Dialog } from "./Dialog";

interface Alert {
  id: string;
  employee_name?: string;
  type: string;
  description: string;
  timestamp: string;
}

const ANOMALY_LABELS: Record<string, string> = {
  excessive_idle: "Excessive idle detected",
  rapid_app_switching: "Rapid app switching",
  after_hours_activity: "After-hours activity",
  unusual_app_usage: "Unusual app usage",
  excessive_break: "Break limit exceeded",
};

export function AlertSystem() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAnomalyRef = useRef<{ key: string; at: number } | null>(null);

  // Request browser notification permission
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "granted") {
      setNotificationsEnabled(true);
    }
  }, []);

  async function enableNotifications() {
    if (!("Notification" in window)) {
      await Dialog.alert("Browser notification alerts require a secure context (HTTPS) or localhost.\n\nIn-app alerts and sound effects will still trigger automatically.", "Browser Notifications");
      return;
    }
    
    if (Notification.permission === "denied") {
      await Dialog.alert("Desktop alerts are blocked by your browser settings.\n\nPlease reset/allow notifications in your browser's site settings to enable desktop alerts.", "Notifications Blocked");
      return;
    }

    try {
      const perm = await Notification.requestPermission();
      setNotificationsEnabled(perm === "granted");
      if (perm !== "granted") {
        await Dialog.alert("Notification permission was not granted.", "Permission Denied");
      }
    } catch (err) {
      console.error("Failed to request notification permission:", err);
    }
  }

  function playAlertSound() {
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.4);
    } catch {}
  }

  function playBreakAlertSound() {
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      // Lower double-beep chime
      osc.frequency.setValueAtTime(523.25, ctx.currentTime);
      osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.35);
    } catch {}
  }

  function clearDismissTimer() {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }

  function buildAlertId() {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type !== "anomaly" && msg.type !== "break_alert") return;

    const isBreakAlert = msg.type === "break_alert";
    const alertType = isBreakAlert ? "excessive_break" : (msg.data.type || "anomaly");
    const alertDesc = isBreakAlert ? msg.data.description : msg.data.description;
    const empName = isBreakAlert ? msg.data.employee_name : (msg.data.employee_name ?? undefined);

    const dedupeKey = `${alertType}|${alertDesc}`;
    const now = Date.now();
    if (lastAnomalyRef.current && lastAnomalyRef.current.key === dedupeKey && now - lastAnomalyRef.current.at < 4000) {
      return;
    }
    lastAnomalyRef.current = { key: dedupeKey, at: now };

    const alert: Alert = {
      id: buildAlertId(),
      employee_name: empName,
      type: alertType,
      description: alertDesc,
      timestamp: new Date().toISOString(),
    };

    // Keep exactly one in-app toast visible at a time.
    setAlerts([alert]);
    setUnreadCount((n) => n + 1);

    if (isBreakAlert) {
      playBreakAlertSound();
    } else {
      playAlertSound();
    }

    clearDismissTimer();
    dismissTimerRef.current = setTimeout(() => {
      setAlerts((prev) => prev.filter((a) => a.id !== alert.id));
      dismissTimerRef.current = null;
    }, 10000);

    // Browser notification
    if (notificationsEnabled && Notification.permission === "granted") {
      new Notification(isBreakAlert ? "⏰ PulseDesk Break Alert" : "PulseDesk Anomaly Alert", {
        body: alert.description,
        icon: "/favicon.ico",
        tag: alert.id,
      });
    }
  }, [notificationsEnabled]);

  useWebSocket(handleWsMessage);

  function dismissAlert(id: string) {
    clearDismissTimer();
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  function clearAll() {
    clearDismissTimer();
    setAlerts([]);
    setUnreadCount(0);
  }

  useEffect(() => () => clearDismissTimer(), []);

  return (
    <>
      {/* Notification permission button — show if not enabled */}
      {!notificationsEnabled && (
        <button
          onClick={enableNotifications}
          title="Enable browser notifications"
          style={{
            position: "fixed", bottom: 20, right: 20, zIndex: 900,
            background: "var(--bg-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "8px 14px",
            display: "flex", alignItems: "center", gap: 6,
            fontSize: 12, color: "var(--text-secondary)",
            cursor: "pointer", boxShadow: "var(--shadow-md)",
          }}
        >
          <Bell size={14} /> Enable alerts
        </button>
      )}

      {/* Alert toasts */}
      <div style={{
        position: "fixed", top: 16, right: 16, zIndex: 1000,
        display: "flex", flexDirection: "column", gap: 8,
        maxWidth: 360, width: "100%",
        pointerEvents: alerts.length ? "auto" : "none",
      }}>
        {alerts.slice(0, 1).map((alert) => {
          const isBreak = alert.type === "excessive_break";
          const borderStyle = isBreak ? "1px solid #d97706" : "1px solid var(--danger)";
          const borderLeftStyle = isBreak ? "3px solid #d97706" : "3px solid var(--danger)";
          const label = isBreak ? "Break Limit Exceeded" : (ANOMALY_LABELS[alert.type] ?? alert.type);
          const iconColor = isBreak ? "#d97706" : "var(--danger)";

          return (
            <div
              key={alert.id}
              style={{
                background: "var(--bg-primary)",
                border: borderStyle,
                borderLeft: borderLeftStyle,
                borderRadius: "var(--radius-lg)",
                padding: "12px 14px",
                boxShadow: "var(--shadow-lg)",
                display: "flex", gap: 10,
                animation: "slideIn 0.2s ease",
              }}
            >
              <AlertTriangle size={16} style={{ color: iconColor, flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 2 }}>
                  {alert.employee_name ? `${alert.employee_name} - ` : ""}{label}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {alert.description}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 }}>
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </div>
              </div>
              <button
                onClick={() => dismissAlert(alert.id)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 2, flexShrink: 0 }}
              >
                <X size={13} />
              </button>
            </div>
          );
        })}
        {alerts.length > 1 && (
          <button
            onClick={clearAll}
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "6px 12px",
              fontSize: 11, color: "var(--text-secondary)",
              cursor: "pointer", textAlign: "center",
            }}
          >
            Clear all {alerts.length} alerts
          </button>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </>
  );
}
