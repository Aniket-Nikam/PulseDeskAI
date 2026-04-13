import React from "react";
import type { HourlyHeatmap } from "../../types";
import { clamp } from "../../utils/format";

interface ActivityHeatmapProps {
  data: HourlyHeatmap;
}

const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function ActivityHeatmap({ data }: ActivityHeatmapProps) {
  const values = HOURS.map((h) => data.hours[String(h)] ?? 0);
  const maxVal = Math.max(...values, 1);

  function formatHour(h: number): string {
    if (h === 0) return "12a";
    if (h < 12) return `${h}a`;
    if (h === 12) return "12p";
    return `${h - 12}p`;
  }

  function intensity(secs: number): number {
    return clamp(secs / maxVal, 0, 1);
  }

  return (
    <div>
      <div style={{ display: "flex", gap: "6px", alignItems: "flex-end", height: "120px", marginBottom: "12px" }}>
        {HOURS.map((h) => {
          const secs = values[h];
          const alpha = intensity(secs);
          const mins = Math.round(secs / 60);
          const barHeight = alpha > 0 ? Math.max(12, alpha * 100) + "%" : "8px";
          return (
            <div
              key={h}
              title={`${formatHour(h)}: ${mins}m active`}
              style={{
                flex: 1,
                height: barHeight,
                borderRadius: "var(--radius-sm)",
                background: alpha < 0.05
                  ? "var(--bg-tertiary)"
                  : `rgba(37, 99, 235, ${0.4 + alpha * 0.6})`,
                cursor: "pointer",
                position: "relative",
                transition: "all 0.2s ease",
                minHeight: "8px",
                boxShadow: alpha > 0.2 ? "0 2px 4px rgba(37, 99, 235, 0.2)" : "none",
              }}
            />
          );
        })}
      </div>
      {/* Hour labels — show every 3 hours */}
      <div style={{ display: "flex", marginTop: 4 }}>
        {HOURS.map((h) => (
          <div key={h} style={{ flex: 1, textAlign: "center" }}>
            {h % 3 === 0 && (
              <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                {formatHour(h)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
