// ── Time formatting ───────────────────────────────────────────────────────────

export function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function daysAgoISO(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// ── Productivity colors ───────────────────────────────────────────────────────

export function productivityColor(score: number | null): string {
  if (score === null) return "var(--color-text-tertiary)";
  if (score >= 75) return "#3d9a6a";
  if (score >= 50) return "#e9a94a";
  return "#d85a44";
}

export function activityColor(type: string | null): string {
  switch (type) {
    case "active": return "#3d9a6a";
    case "idle": return "#e9a94a";
    case "locked": return "#6b7280";
    case "away": return "#9ca3af";
    default: return "#d1d5db";
  }
}

export function categoryColor(category: string | null): string {
  const palette: Record<string, string> = {
    development: "#6366f1",
    design: "#ec4899",
    writing: "#3b82f6",
    communication: "#8b5cf6",
    email: "#06b6d4",
    data: "#f59e0b",
    presentation: "#10b981",
    "project management": "#84cc16",
    notes: "#a78bfa",
    documentation: "#60a5fa",
    entertainment: "#f87171",
    gaming: "#ef4444",
    "social media": "#fb923c",
    browser: "#94a3b8",
    system: "#6b7280",
    other: "#9ca3af",
  };
  return category ? (palette[category] ?? "#9ca3af") : "#9ca3af";
}

// ── Misc ──────────────────────────────────────────────────────────────────────

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function platformIcon(platform: string): string {
  switch (platform.toLowerCase()) {
    case "windows": return "⊞";
    case "darwin": return "";
    case "linux": return "🐧";
    default: return "🖥";
  }
}
