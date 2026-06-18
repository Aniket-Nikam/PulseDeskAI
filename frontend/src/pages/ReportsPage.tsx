import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, Download, Users, User } from "lucide-react";
import { employeesApi, departmentsApi, reportsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { EmployeeSearchDropdown } from "../components/ui/EmployeeSearchDropdown";
import type { Employee, Department } from "../types";
import { Dialog } from "../components/ui/Dialog";

export function ReportsPage() {
  const [mode, setMode] = useState<"employee" | "team">("team");
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [selectedDept, setSelectedDept] = useState("");
  const [days, setDays] = useState(7);
  const [generating, setGenerating] = useState(false);

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: departmentsApi.list,
  });

  async function downloadReport() {
    setGenerating(true);
    try {
      let blob: Blob;
      let filename: string;

      if (mode === "employee" && selectedEmployee) {
        blob = await reportsApi.downloadEmployeePDF(selectedEmployee, days);
        const emp = employees.find((employee) => employee.id === selectedEmployee);
        filename = `pulsedesk_${emp?.full_name.replace(/\s/g, "_") ?? "report"}_${new Date().toISOString().split("T")[0]}.pdf`;
      } else {
        blob = await reportsApi.downloadTeamPDF(days, selectedDept || undefined);
        filename = `pulsedesk_team_report_${new Date().toISOString().split("T")[0]}.pdf`;
      }

      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e: any) {
      const errorMsg = e?.response?.data?.detail || e?.message || "Failed to generate report";
      await Dialog.alert(errorMsg, "Generate Report Failed");
      console.error("PDF generation error:", e);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Reports"
        subtitle="Generate PDF productivity reports"
      />

      <div style={{ display: "flex", gap: 24, maxWidth: 1100, width: "100%", flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* Report type selector - Left Column */}
        <div className="card" style={{ padding: "var(--space-6)", flex: 5, minWidth: 450 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            Report type
          </h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {[
              { id: "team", label: "Team report", icon: <Users size={14} />, desc: "All employees in a table" },
              { id: "employee", label: "Employee report", icon: <User size={14} />, desc: "Deep-dive for one person" },
            ].map(({ id, label, icon, desc }) => (
              <div
                key={id}
                onClick={() => setMode(id as "employee" | "team")}
                style={{
                  flex: 1,
                  padding: "var(--space-4)",
                  border: `1px solid ${mode === id ? "var(--accent)" : "var(--border-default)"}`,
                  borderRadius: "var(--radius-lg)",
                  cursor: "pointer",
                  background: mode === id ? "var(--accent-subtle)" : "var(--bg-secondary)",
                  transition: "all 0.12s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, color: mode === id ? "var(--accent-text)" : "var(--text-primary)", fontWeight: 500, fontSize: 13 }}>
                  {icon} {label}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{desc}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label>Period</label>
              <select className="input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>Last 7 days</option>
                <option value={14}>Last 14 days</option>
                <option value={30}>Last 30 days</option>
              </select>
            </div>

            {mode === "employee" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label>Employee</label>
                <EmployeeSearchDropdown
                  selectedId={selectedEmployee}
                  onChange={setSelectedEmployee}
                  allowEmpty={true}
                  placeholder="Select employee..."
                  width="100%"
                />
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label>Department (optional)</label>
                <select className="input" value={selectedDept} onChange={(e) => setSelectedDept(e.target.value)}>
                  <option value="">All departments</option>
                  {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
                </select>
              </div>
            )}
          </div>

          <button
            className="btn btn-primary btn-lg"
            onClick={downloadReport}
            disabled={generating || (mode === "employee" && !selectedEmployee)}
            style={{ display: "flex", alignItems: "center", gap: 8 }}
          >
            {generating
              ? <><span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTop: "2px solid #fff", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} /> Generating PDF...</>
              : <><Download size={14} /> Download PDF report</>
            }
          </button>
        </div>

        {/* What's included - Right Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, flex: 3, minWidth: 320 }}>
          <div className="card" style={{ padding: "var(--space-5)" }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "var(--text-primary)" }}>
              Employee report includes
            </h3>
            {[
              "Productivity score with color rating",
              "Day-by-day breakdown table",
              "Top 5 applications used",
              "Total active time & focus sessions",
              "Anomaly count summary",
              "Professional PDF format",
            ].map((item) => (
              <div key={item} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12, color: "var(--text-secondary)" }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)", flexShrink: 0 }} />
                {item}
              </div>
            ))}
          </div>

          <div className="card" style={{ padding: "var(--space-5)" }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "var(--text-primary)" }}>
              Team report includes
            </h3>
            {[
              "Ranked leaderboard by productivity",
              "Average active hours per person",
              "Focus session totals",
              "Anomaly counts per employee",
              "Color-coded score column",
              "One page, printable format",
            ].map((item) => (
              <div key={item} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12, color: "var(--text-secondary)" }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--success)", flexShrink: 0 }} />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
