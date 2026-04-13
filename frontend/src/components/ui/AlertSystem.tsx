import React, { useState, useEffect, useCallback, useRef } from "react";
import { AlertTriangle, X, Bell, BellOff } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { WsMessage } from "../../types";

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
};

export function AlertSystem() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Request browser notification permission
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "granted") {
      setNotificationsEnabled(true);
    }
  }, []);

  async function enableNotifications() {
    if (!("Notification" in window)) return;
    const perm = await Notification.requestPermission();
    setNotificationsEnabled(perm === "granted");
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

  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type !== "anomaly") return;

    const alert: Alert = {
      id: Date.now().toString(),
      type: msg.data.type,
      description: msg.data.description,
      timestamp: new Date().toISOString(),
    };

    setAlerts((prev) => [alert, ...prev].slice(0, 10));
    setUnreadCount((n) => n + 1);
    playAlertSound();

    // Browser notification
    if (notificationsEnabled && Notification.permission === "granted") {
      new Notification("PulseDesk Alert", {
        body: alert.description,
        icon: "/favicon.ico",
        tag: alert.id,
      });
    }
  }, [notificationsEnabled]);

  useWebSocket(handleWsMessage);

  function dismissAlert(id: string) {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  function clearAll() {
    setAlerts([]);
    setUnreadCount(0);
  }

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
        {alerts.slice(0, 5).map((alert) => (
          <div
            key={alert.id}
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--danger)",
              borderLeft: "3px solid var(--danger)",
              borderRadius: "var(--radius-lg)",
              padding: "12px 14px",
              boxShadow: "var(--shadow-lg)",
              display: "flex", gap: 10,
              animation: "slideIn 0.2s ease",
            }}
          >
            <AlertTriangle size={16} style={{ color: "var(--danger)", flexShrink: 0, marginTop: 1 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", marginBottom: 2 }}>
                {ANOMALY_LABELS[alert.type] ?? alert.type}
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
        ))}
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
