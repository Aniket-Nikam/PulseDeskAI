/**
 * PulseDesk Action Items Management Page
 * Track coaching action items across all employees
 */

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, Trash2, Filter } from "lucide-react";
import { api } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";

interface Employee {
  id: string;
  full_name: string;
  email: string;
}

interface ActionItem {
  id: string;
  employee_id: string;
  action_text: string;
  is_completed: boolean;
  priority: string;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "rgba(239,68,68,0.1)", text: "var(--danger)" },
  medium: { bg: "rgba(245,158,11,0.1)", text: "var(--warning)" },
  low: { bg: "rgba(34,197,94,0.1)", text: "var(--success)" },
};

export function ActionItemsPage() {
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [filterCompleted, setFilterCompleted] = useState<"all" | "pending" | "completed">("all");
  const [items, setItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch employees
  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => api.get("/employees").then(r => r.data),
  });

  // Set first employee on load
  useEffect(() => {
    if (employees.length > 0 && !selectedEmployee) {
      setSelectedEmployee(employees[0].id);
    }
  }, [employees]);

  // Fetch action items
  useEffect(() => {
    if (!selectedEmployee) return;

    const loadItems = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/actions/employee/${selectedEmployee}`, {
          params: { limit: 100 },
        });
        setItems(res.data || []);
      } catch (err) {
        console.error("Failed to load action items:", err);
        setItems([]);
      } finally {
        setLoading(false);
      }
    };

    loadItems();
  }, [selectedEmployee]);

  // Filter items
  const filteredItems = items.filter(item => {
    if (filterCompleted === "pending") return !item.is_completed;
    if (filterCompleted === "completed") return item.is_completed;
    return true;
  });

  // Toggle completion
  const handleToggle = async (item: ActionItem) => {
    try {
      await api.patch(`/actions/${item.id}`, {
        is_completed: !item.is_completed,
      });
      setItems(prev =>
        prev.map(i =>
          i.id === item.id
            ? {
                ...i,
                is_completed: !i.is_completed,
                completed_at: !i.is_completed ? new Date().toISOString() : null,
              }
            : i
        )
      );
    } catch (err) {
      console.error("Failed to toggle item:", err);
    }
  };

  // Delete item
  const handleDelete = async (itemId: string) => {
    if (!confirm("Delete this action item?")) return;
    try {
      await api.delete(`/actions/${itemId}`);
      setItems(prev => prev.filter(i => i.id !== itemId));
    } catch (err) {
      console.error("Failed to delete item:", err);
    }
  };

  const selectedEmployeeName =
    employees.find(e => e.id === selectedEmployee)?.full_name || "Select Employee";

  return (
    <div style={{ padding: "var(--space-8)" }}>
      <PageHeader
        title="Action Items"
        subtitle="Track coaching recommendations and track completion across your team"
      />

      <div style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-6)", flexWrap: "wrap" }}>
        {/* Employee selector */}
        <div style={{ flex: 1, minWidth: 250 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 8, display: "block" }}>
            Employee
          </label>
          <select
            value={selectedEmployee}
            onChange={e => setSelectedEmployee(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: "var(--bg-secondary)",
              color: "var(--text-primary)",
              fontSize: 13.5,
              cursor: "pointer",
            }}
          >
            {employees.map(emp => (
              <option key={emp.id} value={emp.id}>
                {emp.full_name}
              </option>
            ))}
          </select>
        </div>

        {/* Filter buttons */}
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          {(["all", "pending", "completed"] as const).map(status => (
            <button
              key={status}
              onClick={() => setFilterCompleted(status)}
              style={{
                padding: "10px 16px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-default)",
                background: filterCompleted === status ? "var(--bg-primary)" : "transparent",
                color: filterCompleted === status ? "var(--text-primary)" : "var(--text-secondary)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {items.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)", marginBottom: "var(--space-6)" }}>
          <div style={{ padding: "var(--space-4)", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 4 }}>TOTAL</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{items.length}</div>
          </div>
          <div style={{ padding: "var(--space-4)", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 4 }}>COMPLETED</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--success)" }}>
              {items.filter(i => i.is_completed).length}
            </div>
          </div>
          <div style={{ padding: "var(--space-4)", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", marginBottom: 4 }}>PENDING</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--warning)" }}>
              {items.filter(i => !i.is_completed).length}
            </div>
          </div>
        </div>
      )}

      {/* Items list */}
      {loading ? (
        <div style={{ textAlign: "center", padding: "var(--space-12)", color: "var(--text-tertiary)" }}>
          Loading action items...
        </div>
      ) : filteredItems.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "var(--space-12)",
            background: "var(--bg-secondary)",
            borderRadius: "var(--radius-lg)",
            color: "var(--text-tertiary)",
          }}
        >
          No {filterCompleted === "pending" ? "pending" : filterCompleted === "completed" ? "completed" : ""} action items
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {filteredItems.map(item => (
            <div
              key={item.id}
              style={{
                display: "flex",
                gap: "var(--space-4)",
                alignItems: "flex-start",
                padding: "var(--space-4)",
                background: "var(--bg-primary)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-md)",
                opacity: item.is_completed ? 0.6 : 1,
              }}
            >
              {/* Toggle checkbox */}
              <button
                onClick={() => handleToggle(item)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  marginTop: 2,
                  display: "flex",
                }}
              >
                {item.is_completed ? (
                  <CheckCircle2 size={20} color="var(--success)" />
                ) : (
                  <Circle size={20} color="var(--text-tertiary)" />
                )}
              </button>

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: "var(--text-primary)",
                    textDecoration: item.is_completed ? "line-through" : "none",
                    marginBottom: 6,
                    lineHeight: 1.5,
                  }}
                >
                  {item.action_text}
                </div>

                {/* Meta */}
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {/* Priority badge */}
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "var(--radius-full)",
                      background: PRIORITY_COLORS[item.priority]?.bg || PRIORITY_COLORS.low.bg,
                      color: PRIORITY_COLORS[item.priority]?.text || PRIORITY_COLORS.low.text,
                      textTransform: "capitalize",
                    }}
                  >
                    {item.priority}
                  </span>

                  {/* Due date */}
                  {item.due_date && (
                    <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                      Due:{" "}
                      {new Date(item.due_date).toLocaleDateString("en", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  )}

                  {/* Completed date */}
                  {item.is_completed && item.completed_at && (
                    <span style={{ fontSize: 11, color: "var(--success)" }}>
                      ✓ Completed:{" "}
                      {new Date(item.completed_at).toLocaleDateString("en", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  )}

                  {/* Created date */}
                  <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                    Added:{" "}
                    {new Date(item.created_at).toLocaleDateString("en", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
              </div>

              {/* Delete button */}
              <button
                onClick={() => handleDelete(item.id)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 4,
                  color: "var(--text-tertiary)",
                  display: "flex",
                  marginTop: 2,
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
