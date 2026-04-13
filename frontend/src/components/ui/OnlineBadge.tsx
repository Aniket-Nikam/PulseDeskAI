import React from "react";

interface OnlineBadgeProps {
  online: boolean;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function OnlineBadge({ online, showLabel = true, size = "md" }: OnlineBadgeProps) {
  const dotSize = size === "sm" ? 6 : 8;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{
        width: dotSize, height: dotSize,
        borderRadius: "50%",
        background: online ? "var(--success)" : "var(--border-default)",
        flexShrink: 0,
        ...(online ? { boxShadow: "0 0 0 2px var(--success-subtle)" } : {}),
      }} />
      {showLabel && (
        <span style={{ fontSize: 12, color: online ? "var(--success)" : "var(--text-tertiary)" }}>
          {online ? "Online" : "Offline"}
        </span>
      )}
    </span>
  );
}
