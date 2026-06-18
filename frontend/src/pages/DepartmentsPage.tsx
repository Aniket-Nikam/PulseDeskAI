import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { analyticsApi, departmentsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import type { Department, DepartmentComparisonRow } from "../types";
import { Dialog } from "../components/ui/Dialog";
import { formatSeconds, productivityColor, todayISO } from "../utils/format";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export function DepartmentsPage() {
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data: departments = [], isLoading } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: departmentsApi.list,
  });

  const { data: comparison = [] } = useQuery<DepartmentComparisonRow[]>({
    queryKey: ["dept-comparison", todayISO()],
    queryFn: () => analyticsApi.departmentComparison(todayISO()),
    refetchInterval: 60_000,
  });

  const create = useMutation({
    mutationFn: () => departmentsApi.create({ name: newName }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["departments"] }); setNewName(""); setShowForm(false); },
  });

  const deleteDept = useMutation({
    mutationFn: departmentsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });

  const comparisonChartData = comparison.map((d) => {
    const scoreRaw = Number(d.avg_productivity_score);
    const activeRaw = Number(d.avg_active_seconds);
    const score = Number.isFinite(scoreRaw) ? Math.max(0, Math.min(100, Math.round(scoreRaw))) : 0;
    const activeHours = Number.isFinite(activeRaw) ? Math.max(0, Math.round((activeRaw / 3600) * 10) / 10) : 0;
    const noActivity = score === 0 && activeHours === 0;
    return {
      name: d.department_name,
      score,
      active: activeHours,
      noActivity,
      employeeCount: d.employee_count,
      color: productivityColor(score),
    };
  });
  const hasMeaningfulComparison = comparisonChartData.some((d) => d.score > 0 || d.active > 0);

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Departments"
        subtitle="Team structure and comparison"
        action={
          <button className="btn btn-primary" onClick={() => setShowForm((s) => !s)}>
            <Plus size={14} /> Add department
          </button>
        }
      />

      {showForm && (
        <div className="card" style={{ padding: "var(--space-5)", marginBottom: 20, display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label>Department name</label>
            <input className="input" style={{ marginTop: 4 }} value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Engineering" />
          </div>
          <button className="btn btn-primary" onClick={() => create.mutate()} disabled={!newName.trim() || create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </button>
          <button className="btn btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
        </div>
      )}

      {/* Department cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 24 }}>
        {departments.map((d) => {
          const comp = comparison.find((c) => c.department_id === d.id);
          return (
            <div key={d.id} className="card" style={{ padding: "var(--space-5)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Building2 size={16} style={{ color: "var(--text-tertiary)" }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{d.name}</span>
                </div>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={async () => { if (await Dialog.confirm(`Delete ${d.name}?`, "Delete Department")) deleteDept.mutate(d.id); }}
                  style={{ padding: "2px 6px", fontSize: 11 }}
                >
                  ✕
                </button>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: comp ? 10 : 0 }}>
                {d.employee_count} employee{d.employee_count !== 1 ? "s" : ""}
              </div>
              {comp && (
                <div style={{ display: "flex", gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Online</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--success)" }}>{comp.online_count}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Avg score</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: productivityColor(comp.avg_productivity_score) }}>
                      {Math.round(comp.avg_productivity_score)}%
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {departments.length === 0 && !isLoading && (
          <div className="card empty-state" style={{ gridColumn: "1 / -1" }}>
            <div className="empty-state-icon"><Building2 size={28} /></div>
            <div className="empty-state-title">No departments yet</div>
            <div className="empty-state-body">Create departments to organize your team.</div>
          </div>
        )}
      </div>

      {/* Comparison chart */}
      {departments.length > 0 && (
        <section className="card" style={{ padding: "var(--space-6)" }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            Today's department comparison
          </h2>
          {hasMeaningfulComparison ? (
            <>
              <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={comparisonChartData}
                    margin={{ top: 4, right: 4, bottom: 4, left: -20 }}
                  >
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} tickLine={false} axisLine={false} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ background: "var(--bg-primary)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", fontSize: 12, boxShadow: "var(--shadow-md)" }}
                      formatter={(v: number, _name, item: { payload?: { noActivity?: boolean; employeeCount?: number } }) => {
                        const noActivity = Boolean(item?.payload?.noActivity);
                        const employeeCount = Number(item?.payload?.employeeCount ?? 0);
                        if (noActivity) {
                          return [employeeCount > 0 ? "No tracked activity yet" : "No employees in department", "Status"];
                        }
                        return [`${v}%`, "Avg productivity"];
                      }}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]} minPointSize={6}>
                      {comparisonChartData.map((d, i) => (
                        <Cell
                          key={i}
                          fill={d.noActivity ? "var(--border-default)" : d.color}
                          fillOpacity={d.noActivity ? 0.75 : 0.85}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
                Gray bars indicate departments with no tracked activity for today.
              </div>
            </>
          ) : (
            <div className="empty-state" style={{ minHeight: 200 }}>
              <div className="empty-state-icon"><Building2 size={28} /></div>
              <div className="empty-state-title">Not enough activity data yet</div>
              <div className="empty-state-body">
                Comparison will appear after departments start generating tracked work data.
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
