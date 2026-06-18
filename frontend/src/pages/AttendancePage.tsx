import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  MapPin, Clock, Calendar, Users, Settings as SettingsIcon, 
  Coffee, Compass, Search, Filter, ArrowUpDown, Plus, Trash2, 
  Edit2, Check, X, AlertCircle, HelpCircle, Shield, GraduationCap,
  Briefcase, CheckCircle2, RefreshCw
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { attendanceApi, employeesApi } from "../api/client";
import { formatDate } from "../utils/format";
import { Dialog } from "../components/ui/Dialog";

type TabType = "overview" | "records" | "locations" | "settings";

export function AttendancePage() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabType>("overview");

  // State for Wizard Setup
  const [setupMode, setSetupMode] = useState<"employee" | "student" | "both">("employee");
  const [setupStep, setSetupStep] = useState(1);

  // Queries
  const { data: settings, isLoading: loadingSettings } = useQuery({
    queryKey: ["attendance-settings"],
    queryFn: attendanceApi.getSettings,
  });

  // Setup Mutation
  const setupMutation = useMutation({
    mutationFn: (mode: string) => attendanceApi.setup(mode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-settings"] });
      setSetupStep(1);
    }
  });

  if (loadingSettings) {
    return (
      <div style={{ padding: "var(--space-8)", display: "flex", justifyContent: "center", alignItems: "center", minHeight: "50vh" }}>
        <div style={{ textAlign: "center" }}>
          <RefreshCw className="animate-spin" size={24} style={{ animation: "spin 1s linear infinite", color: "var(--accent)" }} />
          <p style={{ marginTop: 12, color: "var(--text-secondary)" }}>Loading attendance system settings...</p>
        </div>
      </div>
    );
  }

  // Wizard state: settings not configured
  if (!settings || !settings.configured) {
    return (
      <div style={{ padding: "var(--space-8)", maxWidth: 640, margin: "40px auto" }}>
        <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
          <div style={{ 
            width: 56, height: 56, borderRadius: "50%", 
            background: "var(--accent-subtle)", color: "var(--accent)", 
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 20px"
          }}>
            <MapPin size={28} />
          </div>
          
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>
            Configure Attendance System
          </h2>
          <p style={{ color: "var(--text-tertiary)", fontSize: 14, lineHeight: 1.6, marginBottom: 28 }}>
            PulseDesk location-based attendance system tracks employee/student presence, check-in and checkout times, and breaks based on physical coordinates.
          </p>

          <div style={{ textAlign: "left", marginBottom: 32 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 12 }}>
              Choose attendance tracking audience
            </label>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
              {[
                { 
                  id: "employee" as const, 
                  title: "Employees Only", 
                  desc: "Tracks professional shifts, lunch breaks, timers, and work hours.",
                  icon: <Briefcase size={18} />
                },
                { 
                  id: "student" as const, 
                  title: "Students Only", 
                  desc: "Tracks academic presence, lectures, and checking in/out on campus.",
                  icon: <GraduationCap size={18} />
                },
                { 
                  id: "both" as const, 
                  title: "Both Employees & Students", 
                  desc: "Tracks professional & academic attendance under separate rules.",
                  icon: <Users size={18} />
                }
              ].map(opt => (
                <div 
                  key={opt.id}
                  onClick={() => setSetupMode(opt.id)}
                  style={{
                    border: `1.5px solid ${setupMode === opt.id ? "var(--accent)" : "var(--border-default)"}`,
                    background: setupMode === opt.id ? "var(--accent-subtle)" : "var(--bg-primary)",
                    borderRadius: "var(--radius-lg)",
                    padding: 16,
                    cursor: "pointer",
                    display: "flex",
                    gap: 16,
                    alignItems: "flex-start",
                    transition: "all 0.15s ease"
                  }}
                >
                  <div style={{ 
                    marginTop: 2, 
                    color: setupMode === opt.id ? "var(--accent)" : "var(--text-secondary)"
                  }}>
                    {opt.icon}
                  </div>
                  <div>
                    <div style={{ 
                      fontSize: 14, 
                      fontWeight: 600, 
                      color: setupMode === opt.id ? "var(--accent-text)" : "var(--text-primary)",
                      marginBottom: 2
                    }}>
                      {opt.title}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                      {opt.desc}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button 
            className="btn btn-primary btn-lg" 
            style={{ width: "100%", justifyContent: "center" }}
            onClick={() => setupMutation.mutate(setupMode)}
            disabled={setupMutation.isPending}
          >
            {setupMutation.isPending ? "Setting up..." : "Activate Attendance System"}
          </button>
        </div>
      </div>
    );
  }

  const mode = settings.mode;

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader 
        title="Attendance Management" 
        subtitle={`Location-based check-ins and break tracking configured for: ${
          mode === "employee" ? "Employees" : mode === "student" ? "Students" : "Employees & Students"
        }`} 
      />

      {/* Tabs Menu */}
      <div style={{ 
        display: "flex", 
        gap: 4, 
        borderBottom: "1px solid var(--border-subtle)", 
        marginBottom: 24,
        paddingBottom: 0 
      }}>
        {[
          { id: "overview", label: "Today's Live", icon: <Clock size={14} /> },
          { id: "records", label: "Attendance Records", icon: <Calendar size={14} /> },
          { id: "locations", label: "Geofences & Locations", icon: <MapPin size={14} /> },
          { id: "settings", label: "Configuration Settings", icon: <SettingsIcon size={14} /> }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as TabType)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "10px 16px",
              fontSize: 13,
              fontWeight: activeTab === t.id ? 500 : 400,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: activeTab === t.id ? "var(--accent)" : "var(--text-secondary)",
              borderBottom: `2px solid ${activeTab === t.id ? "var(--accent)" : "transparent"}`,
              marginBottom: -1,
              fontFamily: "inherit",
              transition: "all 0.12s"
            }}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tabs Content */}
      {activeTab === "overview" && <OverviewTab settings={settings} />}
      {activeTab === "records" && <RecordsTab settings={settings} />}
      {activeTab === "locations" && <LocationsTab />}
      {activeTab === "settings" && <SettingsTab settings={settings} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. OVERVIEW / TODAY TAB
// ─────────────────────────────────────────────────────────────────────────────

function OverviewTab({ settings }: { settings: any }) {
  const qc = useQueryClient();
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [selectedSimLocation, setSelectedSimLocation] = useState<string>("current");
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState("");
  const [simulationResult, setSimulationResult] = useState<any>(null);

  const { data: locations = [] } = useQuery({
    queryKey: ["attendance-locations"],
    queryFn: attendanceApi.getLocations
  });

  // Queries
  const { data: todayData, isLoading: loadingToday } = useQuery({
    queryKey: ["attendance-today"],
    queryFn: attendanceApi.getToday,
    refetchInterval: 15_000,
  });

  const { data: users = [] } = useQuery({
    queryKey: ["employees-list-attendance"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const checkInMutation = useMutation({
    mutationFn: ({ userId, lat, lng }: { userId: string, lat?: number, lng?: number }) => 
      attendanceApi.checkIn(userId, lat, lng),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
      setSimulationResult({ type: "check-in", data });
      setGpsError("");
    },
    onError: (err: any) => {
      setGpsError(err?.response?.data?.detail ?? "Check-in failed.");
      setSimulationResult(null);
    }
  });

  const checkOutMutation = useMutation({
    mutationFn: ({ userId, lat, lng }: { userId: string, lat?: number, lng?: number }) => 
      attendanceApi.checkOut(userId, lat, lng),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
      setSimulationResult({ type: "check-out", data });
      setGpsError("");
    },
    onError: (err: any) => {
      setGpsError(err?.response?.data?.detail ?? "Check-out failed.");
      setSimulationResult(null);
    }
  });

  const startLunchMutation = useMutation({
    mutationFn: (userId: string) => attendanceApi.startLunch(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
      setSimulationResult({ type: "lunch-start", data: { success: true } });
    },
    onError: (err: any) => { Dialog.alert(err?.response?.data?.detail ?? "Failed to start break.", "Break Action Failed"); }
  });

  const endLunchMutation = useMutation({
    mutationFn: (userId: string) => attendanceApi.endLunch(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
      setSimulationResult({ type: "lunch-end", data: { success: true } });
    },
    onError: (err: any) => { Dialog.alert(err?.response?.data?.detail ?? "Failed to end break.", "Break Action Failed"); }
  });

  const handleSimulate = (action: "check-in" | "check-out") => {
    if (!selectedUser) {
      setGpsError("Please select a person to simulate.");
      return;
    }
    setGpsLoading(true);
    setGpsError("");
    setSimulationResult(null);

    if (selectedSimLocation !== "current") {
      const loc = locations.find((l: any) => l.id === selectedSimLocation);
      if (loc) {
        setGpsLoading(false);
        if (action === "check-in") {
          checkInMutation.mutate({ userId: selectedUser, lat: loc.latitude, lng: loc.longitude });
        } else {
          checkOutMutation.mutate({ userId: selectedUser, lat: loc.latitude, lng: loc.longitude });
        }
        return;
      }
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsLoading(false);
        const { latitude, longitude } = pos.coords;
        if (action === "check-in") {
          checkInMutation.mutate({ userId: selectedUser, lat: latitude, lng: longitude });
        } else {
          checkOutMutation.mutate({ userId: selectedUser, lat: latitude, lng: longitude });
        }
      },
      (err) => {
        setGpsLoading(false);
        // Fallback to coordinates-less or settings check
        if (settings.allow_remote_checkin) {
          if (action === "check-in") {
            checkInMutation.mutate({ userId: selectedUser });
          } else {
            checkOutMutation.mutate({ userId: selectedUser });
          }
        } else {
          setGpsError(`Geolocation error: ${err.message}. Location must be enabled/supported.`);
        }
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "present": return <span className="badge badge-green">Present</span>;
      case "late": return <span className="badge badge-amber">Late Check-in</span>;
      case "half_day": return <span className="badge badge-amber">Half Day</span>;
      case "absent": return <span className="badge badge-red">Absent</span>;
      default: return <span className="badge badge-gray">{status}</span>;
    }
  };

  if (loadingToday) {
    return <p style={{ color: "var(--text-tertiary)" }}>Loading live records...</p>;
  }

  const { present = 0, late = 0, absent = 0, checked_in = 0, checked_out = 0, on_lunch = 0, records = [] } = todayData || {};

  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
      {/* Left Column: Live list and stats */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        
        {/* Statistics Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 14 }}>
          {[
            { label: "Present / Checked In", val: present, color: "var(--success)" },
            { label: "Late Arrival", val: late, color: "var(--warning)" },
            { label: "On Lunch Break", val: on_lunch, color: "var(--accent)" },
            { label: "Estimated Absent", val: absent, color: "var(--danger)" },
          ].map((c, i) => (
            <div key={i} className="stat-card">
              <div className="stat-label">{c.label}</div>
              <div className="stat-value" style={{ color: c.color }}>{c.val}</div>
            </div>
          ))}
        </div>

        {/* Live List Card */}
        <div className="card" style={{ padding: "var(--space-5)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Today's Presence log</h3>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {records.length} records active today
            </span>
          </div>

          {records.length === 0 ? (
            <div className="empty-state" style={{ padding: "var(--space-8) 0" }}>
              <div className="empty-state-icon">⏰</div>
              <div className="empty-state-title">No check-ins today yet</div>
              <div className="empty-state-body">Simulate a check-in on the right panel to begin.</div>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Status</th>
                    <th>Check In</th>
                    <th>Check Out</th>
                    <th>Hours Worked</th>
                    <th>Fenced</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r: any) => {
                    const durationHrs = r.effective_work_seconds 
                      ? `${(r.effective_work_seconds / 3600).toFixed(1)} hrs` 
                      : r.check_in_time && !r.check_out_time ? "Active Shift" : "-";
                    return (
                      <tr key={r.id}>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <div style={{ fontWeight: 500 }}>{r.employee_name}</div>
                            {r.on_lunch && (
                              <span 
                                className="badge" 
                                style={{ 
                                  fontSize: 10, 
                                  display: "flex", 
                                  alignItems: "center", 
                                  gap: 3,
                                  background: "rgba(217, 119, 6, 0.15)",
                                  color: "#d97706",
                                  border: "1px solid rgba(217, 119, 6, 0.3)",
                                  padding: "1px 6px",
                                  borderRadius: 4
                                }}
                                title={r.lunch_started_at ? `Started break at ${new Date(r.lunch_started_at).toLocaleTimeString()}` : "On Break"}
                              >
                                <Coffee size={10} /> Break
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{r.employee_email}</div>
                        </td>
                        <td>{getStatusBadge(r.status)}</td>
                        <td style={{ fontSize: 12 }}>
                          {r.check_in_time ? new Date(r.check_in_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-"}
                        </td>
                        <td style={{ fontSize: 12 }}>
                          {r.check_out_time ? new Date(r.check_out_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-"}
                        </td>
                        <td style={{ fontSize: 12, fontWeight: 500 }}>{durationHrs}</td>
                        <td>
                          {r.check_in_location_name ? (
                            <span style={{ color: "var(--success)", fontSize: 11, display: "flex", alignItems: "center", gap: 3 }} title={`Geofence: ${r.check_in_location_name}`}>
                              <CheckCircle2 size={12} /> Yes ({r.check_in_location_name})
                            </span>
                          ) : r.within_geofence ? (
                            <span style={{ color: "var(--success)", fontSize: 11, display: "flex", alignItems: "center", gap: 3 }}>
                              <CheckCircle2 size={12} /> Yes
                            </span>
                          ) : r.is_remote ? (
                            <span style={{ color: "var(--warning)", fontSize: 11 }}>Remote</span>
                          ) : (
                            <span style={{ color: "var(--danger)", fontSize: 11 }}>No</span>
                          )}
                        </td>
                      </tr>

                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Portal Check-In Simulator */}
      <div>
        <div className="card" style={{ padding: "var(--space-6)", position: "sticky", top: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <Compass size={16} color="var(--accent)" />
            Fenced Check-In Portal
          </h3>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 16 }}>
            Perform a simulated GPS-verified check-in or checkout. It grabs coordinates via HTML5 Geolocation and matches them with settings.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            <div>
              <label>Select Employee / Student</label>
              <select 
                className="input"
                value={selectedUser}
                onChange={e => {
                  setSelectedUser(e.target.value);
                  setSimulationResult(null);
                  setGpsError("");
                }}
              >
                <option value="">-- Choose target --</option>
                {users.map((u: any) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label>Simulated Geofence / Location</label>
              <select
                className="input"
                value={selectedSimLocation}
                onChange={e => setSelectedSimLocation(e.target.value)}
              >
                <option value="current">-- Use My Actual GPS Coordinates --</option>
                {locations.map((loc: any) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.latitude.toFixed(4)}, {loc.longitude.toFixed(4)})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button 
                className="btn btn-primary" 
                style={{ flex: 1, justifyContent: "center" }}
                disabled={gpsLoading || checkInMutation.isPending || !selectedUser}
                onClick={() => handleSimulate("check-in")}
              >
                {gpsLoading ? "Locating..." : "Check In"}
              </button>
              
              <button 
                className="btn btn-secondary" 
                style={{ flex: 1, justifyContent: "center" }}
                disabled={gpsLoading || checkOutMutation.isPending || !selectedUser}
                onClick={() => handleSimulate("check-out")}
              >
                Check Out
              </button>
            </div>

            {settings.lunch_break_enabled && (
              <div style={{ display: "flex", gap: 8, marginTop: 4, padding: "8px 0", borderTop: "1px dashed var(--border-subtle)" }}>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ flex: 1, gap: 4 }}
                  disabled={!selectedUser}
                  onClick={() => startLunchMutation.mutate(selectedUser)}
                >
                  <Coffee size={12} /> Out to Lunch
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ flex: 1, gap: 4 }}
                  disabled={!selectedUser}
                  onClick={() => endLunchMutation.mutate(selectedUser)}
                >
                  <Clock size={12} /> Back from Lunch
                </button>
              </div>
            )}
          </div>

          {gpsError && (
            <div style={{ 
              padding: "10px 12px", 
              background: "var(--danger-subtle)", 
              color: "var(--danger)", 
              borderRadius: "var(--radius-md)", 
              fontSize: 12,
              marginBottom: 10,
              lineHeight: 1.4
            }}>
              <AlertCircle size={13} style={{ display: "inline", marginRight: 5, verticalAlign: "middle" }} />
              {gpsError}
            </div>
          )}

          {simulationResult && (
            <div style={{ 
              padding: 12, 
              background: "var(--success-subtle)", 
              color: "var(--success)", 
              borderRadius: "var(--radius-md)",
              fontSize: 12,
              lineHeight: 1.4
            }}>
              <strong>Success:</strong> {
                simulationResult.type === "check-in" 
                  ? `Checked in successfully (Status: ${simulationResult.data.status})`
                  : simulationResult.type === "check-out"
                  ? `Checked out. Total active: ${((simulationResult.data.effective_work_seconds || 0) / 3600).toFixed(1)} hrs`
                  : "Break action recorded!"
              }
            </div>
          )}

          <div style={{ 
            background: "var(--bg-secondary)", 
            padding: 12, 
            borderRadius: "var(--radius-md)", 
            fontSize: 11, 
            color: "var(--text-tertiary)",
            marginTop: 12,
            lineHeight: 1.4
          }}>
            <strong>Security Notice:</strong> Users checking in outside settings radius will receive an error unless "Allow Remote Check-Ins" is active under Configuration settings.
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. RECORDS TAB
// ─────────────────────────────────────────────────────────────────────────────

function RecordsTab({ settings }: { settings: any }) {
  const qc = useQueryClient();
  const [filterUser, setFilterUser] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [editRecord, setEditRecord] = useState<any>(null);
  const [editNotes, setEditNotes] = useState("");
  const [editStatus, setEditStatus] = useState("");
  const [editCheckIn, setEditCheckIn] = useState("");
  const [editCheckOut, setEditCheckOut] = useState("");
  const [editIsRemote, setEditIsRemote] = useState(false);
  const [editCheckInCount, setEditCheckInCount] = useState<number>(1);

  const { data: users = [] } = useQuery({
    queryKey: ["employees-list-attendance"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: recordsData, isLoading } = useQuery({
    queryKey: ["attendance-records", filterUser, filterStatus, sortBy, sortOrder, page],
    queryFn: () => attendanceApi.getRecords({
      employee_id: filterUser || undefined,
      status: filterStatus || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      page,
      page_size: 15
    })
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string, data: any }) => attendanceApi.updateRecord(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-records"] });
      setEditRecord(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => attendanceApi.deleteRecord(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-records"] });
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
    }
  });

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(o => o === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const toDatetimeLocal = (isoStr: string | null) => {
    if (!isoStr) return "";
    const date = new Date(isoStr);
    const pad = (num: number) => String(num).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const openEdit = (record: any) => {
    setEditRecord(record);
    setEditNotes(record.notes || "");
    setEditStatus(record.status);
    setEditCheckIn(toDatetimeLocal(record.check_in_time));
    setEditCheckOut(toDatetimeLocal(record.check_out_time));
    setEditIsRemote(record.is_remote || false);
    setEditCheckInCount(record.check_in_count ?? 1);
  };

  const saveEdit = () => {
    if (editRecord) {
      updateMutation.mutate({
        id: editRecord.id,
        data: {
          status: editStatus,
          notes: editNotes,
          check_in_time: editCheckIn ? new Date(editCheckIn).toISOString() : null,
          check_out_time: editCheckOut ? new Date(editCheckOut).toISOString() : null,
          is_remote: editIsRemote,
          check_in_count: editCheckInCount,
        }
      });
    }
  };

  const handleDelete = async (id: string, name: string, date: string) => {
    if (await Dialog.confirm(`Are you sure you want to permanently delete the attendance record for ${name} on ${new Date(date).toLocaleDateString()}?`, "Delete Record")) {
      deleteMutation.mutate(id);
    }
  };


  const handleExport = async () => {
    try {
      const blob = await attendanceApi.exportRecords({
        employee_id: filterUser || undefined,
        status: filterStatus || undefined,
        sort_by: sortBy,
        sort_order: sortOrder
      });
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `attendance_export_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      await Dialog.alert("Failed to export records to CSV.", "Export Failed");
    }
  };

  return (
    <div className="card" style={{ padding: "var(--space-6)" }}>
      {/* Filtering Header */}
      <div style={{ 
        display: "flex", 
        flexWrap: "wrap", 
        gap: 12, 
        justifyContent: "space-between", 
        alignItems: "center",
        marginBottom: 20 
      }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div>
            <label style={{ fontSize: 11, marginBottom: 2 }}>Filter by Person</label>
            <select 
              className="input btn-sm" 
              style={{ width: 180 }}
              value={filterUser} 
              onChange={e => { setFilterUser(e.target.value); setPage(1); }}
            >
              <option value="">All People</option>
              {users.map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, marginBottom: 2 }}>Filter by Status</label>
            <select 
              className="input btn-sm" 
              style={{ width: 140 }}
              value={filterStatus} 
              onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
            >
              <option value="">All Statuses</option>
              <option value="present">Present</option>
              <option value="late">Late Arrival</option>
              <option value="half_day">Half Day</option>
              <option value="absent">Absent</option>
            </select>
          </div>
        </div>

        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={handleExport}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            📥 Export to CSV
          </button>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            Showing page {page} of {recordsData?.pages || 1} ({recordsData?.total || 0} total records)
          </div>
        </div>
      </div>

      {/* Records Table */}
      {isLoading ? (
        <div className="skeleton" style={{ height: 300 }} />
      ) : !recordsData || recordsData.items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">No attendance records found</div>
          <div className="empty-state-body">Adjust filters or create simulation check-ins to view logs.</div>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ cursor: "pointer" }} onClick={() => toggleSort("date")}>
                  Date <ArrowUpDown size={11} style={{ display: "inline", marginLeft: 4 }} />
                </th>
                <th>Name</th>
                <th>Check In</th>
                <th style={{ textAlign: "center" }}>Check-ins</th>
                <th>Check Out</th>
                <th>Work Hours</th>
                {settings.lunch_break_enabled && <th>Break deducted</th>}
                <th>Status</th>
                <th>Check-in Location</th>
                <th style={{ textAlign: "right" }}>Edit</th>
              </tr>
            </thead>
            <tbody>
              {recordsData.items.map((r: any) => (
                <tr key={r.id}>
                  <td style={{ fontSize: 12, fontWeight: 500 }}>
                    {new Date(r.date).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{r.employee_name}</div>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {r.check_in_time ? new Date(r.check_in_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "-"}
                  </td>
                  <td style={{ fontSize: 12, textAlign: "center", fontWeight: 600 }}>
                    {r.check_in_count ?? 1}
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {r.check_out_time ? new Date(r.check_out_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "-"}
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {r.effective_work_seconds ? `${(r.effective_work_seconds / 3600).toFixed(1)} hrs` : "-"}
                  </td>
                  {settings.lunch_break_enabled && (
                    <td style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      {r.lunch_deducted_seconds ? `${Math.round(r.lunch_deducted_seconds / 60)} mins` : "-"}
                    </td>
                  )}
                  <td>
                    {r.status === "present" && <span className="badge badge-green">Present</span>}
                    {r.status === "late" && <span className="badge badge-amber">Late</span>}
                    {r.status === "half_day" && <span className="badge badge-amber">Half Day</span>}
                    {r.status === "absent" && <span className="badge badge-red">Absent</span>}
                  </td>
                  <td>
                    {r.check_in_location_name ? (
                      <span className="badge badge-blue" title={`Latitude: ${r.check_in_latitude ?? 'N/A'}, Longitude: ${r.check_in_longitude ?? 'N/A'}`}>
                        {r.check_in_location_name}
                      </span>
                    ) : r.check_in_within_geofence ? (
                      <span className="badge badge-blue">Verified Office</span>
                    ) : r.is_remote ? (
                      <span className="badge badge-gray">Remote Check</span>
                    ) : (
                      <span className="badge badge-red">Out of fence</span>
                    )}
                    {r.notes && (
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4, fontStyle: "italic" }}>
                        Note: {r.notes}
                      </div>
                    )}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(r)}>
                      <Edit2 size={12} style={{ marginRight: 4 }} /> Override
                    </button>
                    <button 
                      className="btn btn-ghost btn-sm text-danger" 
                      onClick={() => handleDelete(r.id, r.employee_name, r.date)}
                      style={{ color: "var(--danger)", marginLeft: 6 }}
                    >
                      <Trash2 size={12} style={{ marginRight: 4 }} /> Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
            <button 
              className="btn btn-secondary btn-sm" 
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <button 
              className="btn btn-secondary btn-sm" 
              disabled={page >= (recordsData?.pages || 1)}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Override Modal */}
      {editRecord && (
        <div style={{ 
          position: "fixed", inset: 0, zIndex: 1000, 
          background: "rgba(0,0,0,0.45)", display: "flex", 
          alignItems: "center", justifyContent: "center", padding: 24 
        }} onClick={() => setEditRecord(null)}>
          <div className="card" style={{ width: "100%", maxWidth: 460, padding: "var(--space-6)" }} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600 }}>Attendance Record Override</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setEditRecord(null)}><X size={14} /></button>
            </div>
            
            <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 14 }}>
              Manually modify the attendance details for <strong>{editRecord.employee_name}</strong> on {new Date(editRecord.date).toLocaleDateString()}.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 20 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600 }}>Check-in Time</label>
                  <input 
                    type="datetime-local" 
                    className="input" 
                    value={editCheckIn} 
                    onChange={e => setEditCheckIn(e.target.value)} 
                  />
                </div>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600 }}>Check-out Time</label>
                  <input 
                    type="datetime-local" 
                    className="input" 
                    value={editCheckOut} 
                    onChange={e => setEditCheckOut(e.target.value)} 
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                <input 
                  type="checkbox" 
                  id="edit_is_remote"
                  checked={editIsRemote} 
                  onChange={e => setEditIsRemote(e.target.checked)} 
                />
                <label htmlFor="edit_is_remote" style={{ margin: 0, cursor: "pointer", fontSize: 12, fontWeight: 500 }}>Check-in remote (outside geofence)</label>
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600 }}>Set Status</label>
                <select className="input" value={editStatus} onChange={e => setEditStatus(e.target.value)}>
                  <option value="present">Present</option>
                  <option value="late">Late Arrival</option>
                  <option value="half_day">Half Day</option>
                  <option value="absent">Absent</option>
                  <option value="on_leave">On Leave</option>
                  <option value="holiday">Holiday</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600 }}>Check-in Count</label>
                <input 
                  type="number" 
                  className="input" 
                  min={1}
                  value={editCheckInCount} 
                  onChange={e => setEditCheckInCount(parseInt(e.target.value, 10) || 1)} 
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 600 }}>Admin notes / Reason</label>
                <textarea 
                  className="input" 
                  rows={3} 
                  value={editNotes} 
                  onChange={e => setEditNotes(e.target.value)}
                  placeholder="e.g. Approved medical leave / system adjustment" 
                />
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setEditRecord(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveEdit} disabled={updateMutation.isPending}>
                Save override
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. GEOFENCES & LOCATIONS TAB
// ─────────────────────────────────────────────────────────────────────────────

function LocationsTab() {
  const qc = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    latitude: "",
    longitude: "",
    radius_meters: "200",
    applies_to: "all"
  });
  const [errorMsg, setErrorMsg] = useState("");
  const [mapReady, setMapReady] = useState(false);

  const mapRef = React.useRef<any>(null);
  const markerRef = React.useRef<any>(null);
  const circleRef = React.useRef<any>(null);
  const existingCirclesRef = React.useRef<any[]>([]);

  const { data: locations = [], isLoading } = useQuery({
    queryKey: ["attendance-locations"],
    queryFn: attendanceApi.getLocations
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => attendanceApi.createLocation(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-locations"] });
      setShowAddForm(false);
      setForm({ name: "", latitude: "", longitude: "", radius_meters: "200", applies_to: "all" });
      setErrorMsg("");
    },
    onError: (err: any) => setErrorMsg(err?.response?.data?.detail ?? "Failed to create location.")
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => attendanceApi.deleteLocation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance-locations"] }),
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? "Failed to delete location. It may be referenced by attendance records.";
      Dialog.alert(detail, "Delete Location Failed");
    }
  });

  // Load Leaflet dynamically
  useEffect(() => {
    if ((window as any).L) {
      setMapReady(true);
      return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.async = true;
    script.onload = () => {
      const L = (window as any).L;
      // Fix default marker icon issue in Leaflet
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });
      setMapReady(true);
    };
    document.head.appendChild(script);
  }, []);

  // Initialize Map
  useEffect(() => {
    if (!mapReady) return;
    const container = document.getElementById("geofence-leaflet-map");
    if (!container || mapRef.current) return;

    const L = (window as any).L;
    // Initial map center: use the first geofence if it exists, otherwise default to Mumbai
    const lat = locations[0]?.latitude || 19.0748;
    const lng = locations[0]?.longitude || 72.8856;

    const map = L.map("geofence-leaflet-map").setView([lat, lng], 13);
    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Active edit marker & circle (draggable)
    const marker = L.marker([lat, lng], { draggable: true });
    markerRef.current = marker;

    const circle = L.circle([lat, lng], {
      color: "#ef4444",
      fillColor: "#f87171",
      fillOpacity: 0.3,
      radius: 200
    });
    circleRef.current = circle;

    marker.on("dragend", () => {
      const pos = marker.getLatLng();
      setForm((f: any) => ({
        ...f,
        latitude: pos.lat.toFixed(6),
        longitude: pos.lng.toFixed(6)
      }));
      circle.setLatLng(pos);
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [mapReady]);

  // Pan to first location once loaded
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || locations.length === 0) return;
    if (mapRef.current._pannedToFirst) return;
    mapRef.current._pannedToFirst = true;

    const lat = locations[0]?.latitude;
    const lng = locations[0]?.longitude;
    if (lat && lng) {
      map.setView([lat, lng], 13);
    }
  }, [locations, mapReady]);

  // Synchronize edit marker/circle layer visibility & inputs with Form
  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    const circle = circleRef.current;
    if (!map || !marker || !circle) return;

    if (showAddForm) {
      if (!map.hasLayer(marker)) marker.addTo(map);
      if (!map.hasLayer(circle)) circle.addTo(map);

      const lat = parseFloat(form.latitude);
      const lng = parseFloat(form.longitude);
      const rad = parseInt(form.radius_meters, 10);

      const L = (window as any).L;

      if (!isNaN(lat) && !isNaN(lng)) {
        const newLatLng = new L.LatLng(lat, lng);
        marker.setLatLng(newLatLng);
        circle.setLatLng(newLatLng);
        if (!isNaN(rad)) {
          circle.setRadius(rad);
        }
        map.setView(newLatLng, 13);
      }
    } else {
      if (map.hasLayer(marker)) marker.remove();
      if (map.hasLayer(circle)) circle.remove();
    }
  }, [form.latitude, form.longitude, form.radius_meters, showAddForm]);

  // Handle map click events to set coords
  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    const circle = circleRef.current;
    if (!map || !marker || !circle) return;

    const onMapClick = (e: any) => {
      if (!showAddForm) return;
      const pos = e.latlng;
      marker.setLatLng(pos);
      circle.setLatLng(pos);
      setForm((f: any) => ({
        ...f,
        latitude: pos.lat.toFixed(6),
        longitude: pos.lng.toFixed(6)
      }));
    };

    map.on("click", onMapClick);
    return () => {
      map.off("click", onMapClick);
    };
  }, [showAddForm]);

  // Draw existing geofences
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const L = (window as any).L;

    existingCirclesRef.current.forEach(c => c.remove());
    existingCirclesRef.current = [];

    locations.forEach((loc: any) => {
      if (
        showAddForm &&
        Math.abs(loc.latitude - parseFloat(form.latitude)) < 0.0001 &&
        Math.abs(loc.longitude - parseFloat(form.longitude)) < 0.0001
      ) {
        return;
      }

      const existingCircle = L.circle([loc.latitude, loc.longitude], {
        color: "#4f46e5",
        fillColor: "#818cf8",
        fillOpacity: 0.15,
        radius: loc.radius_meters
      }).addTo(map);

      const existingMarker = L.marker([loc.latitude, loc.longitude])
        .addTo(map)
        .bindPopup(`<b>${loc.name}</b><br>Radius: ${loc.radius_meters}m<br>Target: ${loc.applies_to}`);

      existingCirclesRef.current.push(existingCircle);
      existingCirclesRef.current.push(existingMarker);
    });
  }, [locations, mapReady, showAddForm]);

  const fillCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setForm(f => ({
            ...f,
            latitude: pos.coords.latitude.toFixed(6),
            longitude: pos.coords.longitude.toFixed(6)
          }));
        },
        (err) => {
          Dialog.alert(`Could not fetch location: ${err.message}`, "Geolocation Error");
        }
      );
    }
  };

  const handleSave = () => {
    if (!form.name || !form.latitude || !form.longitude) {
      setErrorMsg("All location coordinates are required.");
      return;
    }
    createMutation.mutate({
      name: form.name,
      latitude: parseFloat(form.latitude),
      longitude: parseFloat(form.longitude),
      radius_meters: parseInt(form.radius_meters, 10),
      applies_to: form.applies_to
    });
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: showAddForm ? "1fr 1fr 1.2fr" : "1fr 1.5fr", gap: 20, alignItems: "flex-start" }}>
      
      {/* Locations List */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600 }}>Approved Geofences</h3>
          <button 
            className="btn btn-primary btn-sm" 
            onClick={() => {
              const defaultLat = locations[0]?.latitude ? locations[0].latitude.toFixed(6) : "19.0748";
              const defaultLng = locations[0]?.longitude ? locations[0].longitude.toFixed(6) : "72.8856";
              setShowAddForm(true);
              setForm(f => ({
                ...f,
                latitude: f.latitude || defaultLat,
                longitude: f.longitude || defaultLng
              }));
            }}
          >
            <Plus size={13} /> Add Location
          </button>
        </div>

        {isLoading ? (
          <div className="skeleton" style={{ height: 200 }} />
        ) : locations.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🗺️</div>
            <div className="empty-state-title">No geofences set up</div>
            <div className="empty-state-body">Create a location fence. Employees/students must check-in inside approved fences.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {locations.map((loc: any) => (
              <div 
                key={loc.id} 
                className="card"
                style={{ 
                  padding: 14, 
                  display: "flex", 
                  justifyContent: "space-between", 
                  alignItems: "center",
                  background: "var(--bg-secondary)"
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{loc.name}</div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    GPS: {loc.latitude.toFixed(6)}, {loc.longitude.toFixed(6)}
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    <span className="badge badge-blue">Radius: {loc.radius_meters}m</span>
                    <span className="badge badge-gray">Target: {loc.applies_to}</span>
                  </div>
                </div>
                <button 
                  className="btn btn-danger btn-sm"
                  onClick={async () => {
                    if (await Dialog.confirm(`Remove geofence "${loc.name}"?`, "Remove Geofence")) {
                      deleteMutation.mutate(loc.id);
                    }
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Geofence Form */}
      {showAddForm && (
        <div className="card" style={{ padding: "var(--space-6)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Create Geofence Zone</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowAddForm(false)}><X size={14} /></button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            <div>
              <label>Location / Office Name</label>
              <input 
                type="text" 
                className="input" 
                placeholder="HQ / Main Campus" 
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label>Latitude</label>
                <input 
                  type="number" 
                  className="input" 
                  step="0.000001"
                  placeholder="e.g. 28.6139" 
                  value={form.latitude}
                  onChange={e => setForm(f => ({ ...f, latitude: e.target.value }))}
                />
              </div>
              <div>
                <label>Longitude</label>
                <input 
                  type="number" 
                  className="input" 
                  step="0.000001"
                  placeholder="e.g. 77.2090" 
                  value={form.longitude}
                  onChange={e => setForm(f => ({ ...f, longitude: e.target.value }))}
                />
              </div>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button 
                type="button" 
                className="btn btn-secondary btn-sm" 
                style={{ flex: 1, justifyContent: "center" }}
                onClick={fillCurrentLocation}
              >
                Use My Current GPS
              </button>
            </div>

            <div>
              <label>Fence Radius (meters)</label>
              <select 
                className="input" 
                value={form.radius_meters}
                onChange={e => setForm(f => ({ ...f, radius_meters: e.target.value }))}
              >
                <option value="100">100 meters (Tight fence)</option>
                <option value="200">200 meters (Standard office/building)</option>
                <option value="500">500 meters (Large campus / block)</option>
                <option value="1000">1000 meters (Wide perimeter)</option>
              </select>
            </div>

            <div>
              <label>Applies to</label>
              <select 
                className="input" 
                value={form.applies_to}
                onChange={e => setForm(f => ({ ...f, applies_to: e.target.value }))}
              >
                <option value="all">Everyone</option>
                <option value="employee">Employees only</option>
                <option value="student">Students only</option>
              </select>
            </div>
          </div>

          {errorMsg && (
            <div style={{ 
              padding: "8px 12px", 
              background: "var(--danger-subtle)", 
              color: "var(--danger)", 
              borderRadius: "var(--radius-md)", 
              fontSize: 12, 
              marginBottom: 12 
            }}>
              {errorMsg}
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button 
              className="btn btn-primary" 
              onClick={handleSave} 
              disabled={createMutation.isPending}
            >
              Save location geofence
            </button>
            <button className="btn btn-ghost" onClick={() => setShowAddForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Geofence Map Preview Column */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
          {showAddForm ? "Geofence Editor Map" : "Geofence Coverage Overview"}
        </h3>
        <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 12 }}>
          {showAddForm 
            ? "Drag the red marker or click anywhere on the map to set the geofence center." 
            : "Review active geofences (blue zones) configured across the system."}
        </p>

        <div 
          id="geofence-leaflet-map" 
          style={{ 
            height: 380, 
            borderRadius: "var(--radius-lg)", 
            border: "1px solid var(--border-default)",
            zIndex: 1
          }} 
        />
      </div>

    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. CONFIGURATION SETTINGS TAB
// ─────────────────────────────────────────────────────────────────────────────

function SettingsTab({ settings }: { settings: any }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    mode: settings.mode,
    work_start_time: settings.work_start_time || "09:00",
    work_end_time: settings.work_end_time || "18:00",
    lunch_break_enabled: settings.lunch_break_enabled,
    lunch_break_duration_minutes: settings.lunch_break_duration_minutes || 60,
    auto_deduct_lunch: settings.auto_deduct_lunch,
    late_threshold_minutes: settings.late_threshold_minutes || 15,
    allow_remote_checkin: settings.allow_remote_checkin,
    require_location_for_checkout: settings.require_location_for_checkout,
    break_alert_enabled: settings.break_alert_enabled !== false,
    break_alert_grace_minutes: settings.break_alert_grace_minutes || 5
  });

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const saveMutation = useMutation({
    mutationFn: (data: any) => attendanceApi.updateSettings(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-settings"] });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveMutation.mutate(form);
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 540 }}>
      <div className="card" style={{ padding: "var(--space-5)", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: "var(--accent-text)" }}>General & Audience Settings</h3>
        
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <label>Attendance Mode</label>
            <select 
              className="input" 
              value={form.mode}
              onChange={e => setForm(f => ({ ...f, mode: e.target.value }))}
            >
              <option value="employee">Employees tracking (Inc. Lunch Breaks, shifts)</option>
              <option value="student">Students tracking (Classroom presence)</option>
              <option value="both">Both (Employees & Students enabled)</option>
            </select>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Work/Class Start Time</label>
              <input 
                type="text" 
                className="input" 
                placeholder="09:00" 
                value={form.work_start_time}
                onChange={e => setForm(f => ({ ...f, work_start_time: e.target.value }))}
              />
            </div>
            <div>
              <label>Work/Class End Time</label>
              <input 
                type="text" 
                className="input" 
                placeholder="18:00" 
                value={form.work_end_time}
                onChange={e => setForm(f => ({ ...f, work_end_time: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <label>Late threshold buffer (minutes)</label>
            <input 
              type="number" 
              className="input" 
              value={form.late_threshold_minutes}
              onChange={e => setForm(f => ({ ...f, late_threshold_minutes: parseInt(e.target.value, 10) }))}
            />
          </div>
        </div>
      </div>

      {form.mode !== "student" && (
        <div className="card" style={{ padding: "var(--space-5)", marginBottom: 12 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: "var(--accent-text)" }}>Lunch Break & Alert Settings</h3>
          
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input 
                type="checkbox" 
                id="lunch_break_enabled"
                checked={form.lunch_break_enabled}
                onChange={e => setForm(f => ({ ...f, lunch_break_enabled: e.target.checked }))}
              />
              <label htmlFor="lunch_break_enabled" style={{ margin: 0, cursor: "pointer" }}>Enable Lunch break timers & trackers</label>
            </div>

            {form.lunch_break_enabled && (
              <>
                <div>
                  <label>Lunch Break duration (minutes)</label>
                  <input 
                    type="number" 
                    className="input" 
                    value={form.lunch_break_duration_minutes}
                    onChange={e => setForm(f => ({ ...f, lunch_break_duration_minutes: parseInt(e.target.value, 10) }))}
                  />
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <input 
                    type="checkbox" 
                    id="auto_deduct_lunch"
                    checked={form.auto_deduct_lunch}
                    onChange={e => setForm(f => ({ ...f, auto_deduct_lunch: e.target.checked }))}
                  />
                  <label htmlFor="auto_deduct_lunch" style={{ margin: 0, cursor: "pointer" }}>Auto-deduct lunch break from total hours worked</label>
                </div>

                <div style={{ borderTop: "1px dashed var(--border-subtle)", marginTop: 6, paddingTop: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <input 
                      type="checkbox" 
                      id="break_alert_enabled"
                      checked={form.break_alert_enabled}
                      onChange={e => setForm(f => ({ ...f, break_alert_enabled: e.target.checked }))}
                    />
                    <label htmlFor="break_alert_enabled" style={{ margin: 0, cursor: "pointer" }}>Enable extended break warnings (real-time alerts)</label>
                  </div>
                </div>

                {form.break_alert_enabled && (
                  <div>
                    <label>Break alert grace period (minutes)</label>
                    <input 
                      type="number" 
                      className="input" 
                      value={form.break_alert_grace_minutes}
                      onChange={e => setForm(f => ({ ...f, break_alert_grace_minutes: parseInt(e.target.value, 10) }))}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}


      <div className="card" style={{ padding: "var(--space-5)", marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: "var(--accent-text)" }}>Security & Fencing</h3>
        
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input 
              type="checkbox" 
              id="allow_remote_checkin"
              checked={form.allow_remote_checkin}
              onChange={e => setForm(f => ({ ...f, allow_remote_checkin: e.target.checked }))}
            />
            <label htmlFor="allow_remote_checkin" style={{ margin: 0, cursor: "pointer" }}>Allow Remote check-ins (outside geofence)</label>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input 
              type="checkbox" 
              id="require_location_for_checkout"
              checked={form.require_location_for_checkout}
              onChange={e => setForm(f => ({ ...f, require_location_for_checkout: e.target.checked }))}
            />
            <label htmlFor="require_location_for_checkout" style={{ margin: 0, cursor: "pointer" }}>Require Geolocation verify for Check Out</label>
          </div>
        </div>
      </div>

      {success && (
        <div style={{ 
          padding: "8px 12px", 
          background: "var(--success-subtle)", 
          color: "var(--success)", 
          borderRadius: "var(--radius-md)", 
          fontSize: 12, 
          marginBottom: 12 
        }}>
          Configuration settings updated successfully.
        </div>
      )}

      <button className="btn btn-primary" type="submit" disabled={saveMutation.isPending}>
        {saveMutation.isPending ? "Saving..." : "Save Settings"}
      </button>
    </form>
  );
}
