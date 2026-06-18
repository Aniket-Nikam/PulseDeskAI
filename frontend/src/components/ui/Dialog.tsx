import React, { useState, useEffect } from "react";
import { AlertTriangle, Info, HelpCircle } from "lucide-react";

type DialogType = "alert" | "confirm";

interface DialogConfig {
  id: string;
  type: DialogType;
  title?: string;
  message: string;
  resolve: (value: boolean) => void;
}

let listeners: ((dialog: DialogConfig | null) => void)[] = [];
let currentDialog: DialogConfig | null = null;

const notifyListeners = () => {
  listeners.forEach((listener) => listener(currentDialog));
};

export const Dialog = {
  alert(message: string, title?: string): Promise<boolean> {
    return new Promise((resolve) => {
      currentDialog = {
        id: Math.random().toString(),
        type: "alert",
        title,
        message,
        resolve: (val) => {
          currentDialog = null;
          notifyListeners();
          resolve(val);
        },
      };
      notifyListeners();
    });
  },

  confirm(message: string, title?: string): Promise<boolean> {
    return new Promise((resolve) => {
      currentDialog = {
        id: Math.random().toString(),
        type: "confirm",
        title,
        message,
        resolve: (val) => {
          currentDialog = null;
          notifyListeners();
          resolve(val);
        },
      };
      notifyListeners();
    });
  },
};

export function DialogContainer() {
  const [dialog, setDialog] = useState<DialogConfig | null>(null);

  useEffect(() => {
    const handleUpdate = (newDialog: DialogConfig | null) => {
      setDialog(newDialog);
    };
    listeners.push(handleUpdate);
    // Initialize if already exists
    if (currentDialog) {
      setDialog(currentDialog);
    }
    return () => {
      listeners = listeners.filter((l) => l !== handleUpdate);
    };
  }, []);

  if (!dialog) return null;

  const isConfirm = dialog.type === "confirm";
  const title = dialog.title || (isConfirm ? "Confirm Action" : "Notice");

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      zIndex: 99999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "var(--space-4)",
      background: "rgba(0, 0, 0, 0.45)",
      backdropFilter: "blur(4px)",
      animation: "dialog-fade-in 0.15s ease",
    }}>
      <div 
        className="card"
        style={{
          width: "100%",
          maxWidth: 420,
          background: "var(--bg-primary)",
          border: "1px solid var(--border-strong)",
          boxShadow: "var(--shadow-lg)",
          padding: "var(--space-6)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          animation: "dialog-slide-in 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            borderRadius: "var(--radius-md)",
            background: isConfirm ? "var(--accent-subtle)" : "var(--warning-subtle)",
            color: isConfirm ? "var(--accent)" : "var(--warning)",
            flexShrink: 0,
          }}>
            {isConfirm ? <HelpCircle size={20} /> : <AlertTriangle size={20} />}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{
              fontSize: 15,
              fontWeight: 600,
              color: "var(--text-primary)",
              marginBottom: 4,
            }}>
              {title}
            </h3>
            <p style={{
              fontSize: 13,
              color: "var(--text-secondary)",
              lineHeight: 1.5,
              wordBreak: "break-word",
              whiteSpace: "pre-line",
            }}>
              {dialog.message}
            </p>
          </div>
        </div>

        <div style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginTop: 4,
        }}>
          {isConfirm && (
            <button
              className="btn btn-secondary"
              onClick={() => dialog.resolve(false)}
            >
              Cancel
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={() => dialog.resolve(true)}
            autoFocus
          >
            {isConfirm ? "Confirm" : "OK"}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes dialog-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes dialog-slide-in {
          from { transform: scale(0.96) translateY(8px); opacity: 0; }
          to { transform: scale(1) translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
