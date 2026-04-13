import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Trophy, TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react";
import { api, analyticsApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { formatSeconds, productivityColor } from "../utils/format";

interface LeaderboardEntry {
  rank: number;
  employee_id: string;
  employee_name: string;
  department_name: string | null;
  avg_score: number;
  total_active_seconds: number;
  trend: "up" | "down" | "same";
  days_with_data: number;
}

const MEDAL = ["🥇", "🥈", "🥉"];
const MEDAL_COLORS = ["#f59e0b", "#94a3b8", "#b45309"];

export function LeaderboardPage() {
  const [period, setPeriod] = useState<7 | 14 | 30>(7);

  // Single API call to backend leaderboard endpoint
  const { data: rows = [], isLoading, refetch, isFetching } = useQuery<LeaderboardEntry[]>({
    queryKey: ["leaderboard-v2", period],
    queryFn: () => api.get(`/analytics/leaderboard?days=${period}`).then(r => r.data),
    staleTime: 60_000,
  });

  const top3 = rows.slice(0, 3);
  const rest = rows.slice(3);

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Leaderboard"
        subtitle="Team productivity rankings — live data"
        action={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 2 }}>
              {([7, 14, 30] as const).map(d => (
                <button key={d} onClick={() => setPeriod(d)}
                  className={`btn btn-sm ${period === d ? "btn-primary" : "btn-ghost"}`}>
                  {d}d
                </button>
              ))}
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw size={13} style={{ animation: isFetching ? "spin 1s linear infinite" : "none" }} />
            </button>
          </div>
        }
      />

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 60, borderRadius: "var(--radius-lg)" }} />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon"><Trophy size={32} /></div>
          <div className="empty-state-title">No data yet</div>
          <div className="empty-state-body">
            The agent needs to run for at least 30 minutes before scores appear here.
            Make sure the agent is running and sending events to the backend.
          </div>
        </div>
      ) : (
        <>
          {/* Podium — top 3 */}
          {top3.length >= 2 && (
            <div style={{
              display: "flex", justifyContent: "center", alignItems: "flex-end",
              gap: 12, marginBottom: 32,
            }}>
              {[top3[1], top3[0], top3[2]].filter(Boolean).map((r, i) => {
                const isFirst = i === 1;
                const heights = [130, 170, 110];
                return (
                  <div key={r.employee_id} style={{ textAlign: "center", width: 140 }}>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4 }}>
                      {r.employee_name}
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: productivityColor(r.avg_score), marginBottom: 8 }}>
                      {r.avg_score}%
                    </div>
                    <div style={{
                      height: heights[i],
                      background: isFirst ? "var(--accent)" : "var(--bg-secondary)",
                      border: `1px solid ${isFirst ? "var(--accent)" : "var(--border-default)"}`,
                      borderRadius: "var(--radius-lg) var(--radius-lg) 0 0",
                      display: "flex", flexDirection: "column",
                      alignItems: "center", justifyContent: "center", gap: 4,
                    }}>
                      <span style={{ fontSize: 28 }}>{MEDAL[isFirst ? 0 : i === 0 ? 1 : 2]}</span>
                      <span style={{ fontSize: 16, fontWeight: 700, color: isFirst ? "#fff" : "var(--text-secondary)" }}>
                        #{isFirst ? 1 : i === 0 ? 2 : 3}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Full table */}
          <div className="card" style={{ overflow: "hidden" }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 52 }}>Rank</th>
                  <th>Employee</th>
                  <th>Score</th>
                  <th>Active time</th>
                  <th>Trend</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.employee_id}>
                    <td>
                      {r.rank <= 3 ? (
                        <span style={{ fontSize: 18 }}>{MEDAL[r.rank - 1]}</span>
                      ) : (
                        <span style={{ fontSize: 13, color: "var(--text-tertiary)", fontWeight: 600 }}>
                          #{r.rank}
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 500, fontSize: 13 }}>{r.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                        {r.department_name ?? "No department"} · {r.days_with_data}d data
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{
                          width: 64, height: 6, background: "var(--bg-tertiary)",
                          borderRadius: 3, overflow: "hidden",
                        }}>
                          <div style={{
                            width: `${r.avg_score}%`, height: "100%",
                            background: productivityColor(r.avg_score), borderRadius: 3,
                          }} />
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 700, color: productivityColor(r.avg_score) }}>
                          {r.avg_score}%
                        </span>
                      </div>
                    </td>
                    <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                      {formatSeconds(r.total_active_seconds)}
                    </td>
                    <td>
                      {r.trend === "up"
                        ? <TrendingUp size={15} style={{ color: "var(--success)" }} />
                        : r.trend === "down"
                        ? <TrendingDown size={15} style={{ color: "var(--danger)" }} />
                        : <Minus size={15} style={{ color: "var(--text-tertiary)" }} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
