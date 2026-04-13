import React from "react";
import type { WorkdayTimeline, TimelineBlock } from "../../types";
import { activityColor, formatTime, formatSeconds } from "../../utils/format";

interface WorkdayTimelineProps {
  timeline: WorkdayTimeline;
  workStart?: number; // hour, e.g. 9
  workEnd?: number;   // hour, e.g. 18
}

export function WorkdayTimelineChart({ timeline, workStart = 8, workEnd = 20 }: WorkdayTimelineProps) {
  const dayStart = new Date(`${timeline.date}T00:00:00Z`);
  const dayStartMs = new Date(`${timeline.date}T${String(workStart).padStart(2, "0")}:00:00Z`).getTime();
  const dayEndMs = new Date(`${timeline.date}T${String(workEnd).padStart(2, "0")}:00:00Z`).getTime();
  const windowMs = dayEndMs - dayStartMs;

  if (!timeline.blocks.length) {
    return (
      <div className="empty-state" style={{ padding: "var(--space-10)" }}>
        <div className="empty-state-icon">📊</div>
        <div className="empty-state-title">No activity recorded</div>
        <div className="empty-state-body">No monitoring data for this day.</div>
      </div>
    );
  }

  function toPercent(ts: string): number {
    const ms = new Date(ts).getTime() - dayStartMs;
    return Math.max(0, Math.min(100, (ms / windowMs) * 100));
  }

  function widthPercent(block: TimelineBlock): number {
    const startMs = Math.max(new Date(block.start).getTime(), dayStartMs);
    const endMs = Math.min(new Date(block.end).getTime(), dayEndMs);
    return Math.max(0, ((endMs - startMs) / windowMs) * 100);
  }

  // Hour markers
  const hours = Array.from({ length: workEnd - workStart + 1 }, (_, i) => workStart + i);

  return (
    <div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
        {["active", "idle", "locked", "away"].map((type) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--text-secondary)" }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: activityColor(type) }} />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </div>
        ))}
      </div>

      {/* Timeline bar */}
      <div style={{ position: "relative", height: 40, background: "var(--bg-secondary)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
        {timeline.blocks.map((block, i) => {
          const left = toPercent(block.start);
          const width = widthPercent(block);
          if (width < 0.1) return null;
          return (
            <div
              key={i}
              title={`${block.app_name ?? block.activity_type} — ${formatSeconds(block.duration_seconds)} (${formatTime(block.start)}–${formatTime(block.end)})`}
              style={{
                position: "absolute",
                top: 0, bottom: 0,
                left: `${left}%`,
                width: `${width}%`,
                background: activityColor(block.activity_type),
                opacity: block.activity_type === "active" ? 0.85 : 0.45,
                cursor: "default",
              }}
            />
          );
        })}
      </div>

      {/* Hour markers */}
      <div style={{ display: "flex", position: "relative", marginTop: 4 }}>
        {hours.map((h) => {
          const pct = ((h - workStart) / (workEnd - workStart)) * 100;
          return (
            <div
              key={h}
              style={{
                position: "absolute",
                left: `${pct}%`,
                fontSize: 10,
                color: "var(--text-tertiary)",
                transform: "translateX(-50%)",
              }}
            >
              {h === 12 ? "12p" : h > 12 ? `${h - 12}p` : `${h}a`}
            </div>
          );
        })}
      </div>

      {/* Summary row */}
      <div style={{
        display: "flex", gap: 20, marginTop: 20,
        flexWrap: "wrap",
      }}>
        {[
          { label: "Active", value: formatSeconds(timeline.total_active_seconds), color: activityColor("active") },
          { label: "Idle", value: formatSeconds(timeline.total_idle_seconds), color: activityColor("idle") },
          { label: "Focus sessions", value: String(timeline.focus_sessions), color: "var(--accent)" },
        ].map(({ label, value, color }) => (
          <div key={label}>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
            <div style={{ fontSize: 16, fontWeight: 600, color, marginTop: 2 }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
