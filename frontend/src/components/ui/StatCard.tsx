import React from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon?: React.ReactNode;
}

export function StatCard({ label, value, sub, color, icon }: StatCardProps) {
  return (
    <div className="card" style={{ padding: "var(--space-5)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
            {label}
          </div>
          <div style={{ fontSize: 26, fontWeight: 600, color: color ?? "var(--text-primary)", letterSpacing: "-0.02em", lineHeight: 1 }}>
            {value}
          </div>
          {sub && (
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>{sub}</div>
          )}
        </div>
        {icon && (
          <div style={{
            width: 32, height: 32, borderRadius: "var(--radius-md)",
            background: "var(--bg-secondary)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--text-tertiary)",
          }}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
