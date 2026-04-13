// ── Auth ─────────────────────────────────────────────────────────────────────
export interface Admin {
  id: string;
  email: string;
  full_name: string;
  role: "super_admin" | "admin" | "manager";
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  admin_id: string;
  full_name: string;
  role: string;
}

// ── Department ────────────────────────────────────────────────────────────────
export interface Department {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  employee_count: number;
}

// ── Employee ──────────────────────────────────────────────────────────────────
export interface Employee {
  id: string;
  email: string;
  full_name: string;
  department_id: string | null;
  department_name: string | null;
  job_title: string | null;
  timezone: string;
  work_start_hour: number;
  work_end_hour: number;
  is_active: boolean;
  created_at: string;
  device_count: number;
  is_online: boolean;
}

// ── Device ────────────────────────────────────────────────────────────────────
export type DeviceStatus = "pending" | "approved" | "revoked" | "suspended";

export interface Device {
  id: string;
  employee_id: string;
  employee_name: string | null;
  hostname: string;
  platform: string;
  os_version: string | null;
  agent_version: string | null;
  status: DeviceStatus;
  last_heartbeat: string | null;
  enrolled_at: string | null;
  created_at: string;
  is_online: boolean;
}

// ── Activity ──────────────────────────────────────────────────────────────────
export type ActivityType = "active" | "idle" | "locked" | "away";

export interface EmployeeStatus {
  employee_id: string;
  employee_name: string;
  department_name: string | null;
  is_online: boolean;
  activity_type: ActivityType | null;
  active_app: string | null;
  active_window_title: string | null;
  idle_seconds: number;
  session_started_at: string | null;
  today_active_seconds: number;
  today_productivity_score: number | null;
  last_seen: string | null;
}

// ── Timeline ──────────────────────────────────────────────────────────────────
export interface TimelineBlock {
  start: string;
  end: string;
  activity_type: ActivityType;
  app_name: string | null;
  duration_seconds: number;
}

export interface WorkdayTimeline {
  employee_id: string;
  date: string;
  blocks: TimelineBlock[];
  total_active_seconds: number;
  total_idle_seconds: number;
  focus_sessions: number;
}

// ── Analytics ─────────────────────────────────────────────────────────────────
export interface AppUsageStat {
  app_name: string;
  app_category: string | null;
  total_seconds: number;
  percentage: number;
}

export interface HourlyHeatmap {
  employee_id: string;
  date: string;
  hours: Record<string, number>; // "0".."23" → seconds
}

export interface DepartmentComparisonRow {
  department_id: string;
  department_name: string;
  employee_count: number;
  avg_active_seconds: number;
  avg_productivity_score: number;
  avg_focus_sessions: number;
  avg_app_switches: number;
  online_count: number;
}

export interface DailySummary {
  id: string;
  employee_id: string;
  date: string;
  total_tracked_seconds: number;
  active_seconds: number;
  idle_seconds: number;
  focus_seconds: number;
  productivity_score: number;
  focus_sessions: number;
  app_switches: number;
  top_app: string | null;
  top_category: string | null;
  hourly_active_seconds: Record<string, number> | null;
  anomaly_count: number;
}

export interface Anomaly {
  id: string;
  employee_id: string;
  employee_name: string | null;
  device_id: string;
  anomaly_type: string;
  detected_at: string;
  description: string;
  metadata: Record<string, unknown> | null;
  is_reviewed: boolean;
}

export interface ReportRow {
  employee_id: string;
  employee_name: string;
  department_name: string | null;
  total_days: number;
  avg_active_seconds: number;
  avg_productivity_score: number;
  total_focus_sessions: number;
  total_anomalies: number;
  top_app: string | null;
}

// ── WS Messages ───────────────────────────────────────────────────────────────
export interface WsEmployeeUpdate {
  type: "employee_update";
  data: {
    employee_id: string;
    activity_type: ActivityType;
    active_app: string | null;
    active_window_title: string | null;
    idle_seconds: number;
    timestamp: string;
  };
}

export interface WsAnomalyAlert {
  type: "anomaly";
  data: {
    employee_id: string;
    type: string;
    description: string;
  };
}

export type WsMessage = WsEmployeeUpdate | WsAnomalyAlert;
