import React, { useState, useEffect, useRef, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Search } from "lucide-react";
import { employeesApi, analyticsApi } from "../../api/client";
import type { Employee, EmployeeStatus } from "../../types";

interface EmployeeSearchDropdownProps {
  selectedId: string;
  onChange: (id: string) => void;
  allowEmpty?: boolean;
  placeholder?: string;
  width?: string | number;
}

export function EmployeeSearchDropdown({
  selectedId,
  onChange,
  allowEmpty = false,
  placeholder = "Select Employee",
  width = 250,
}: EmployeeSearchDropdownProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list({ is_active: true }),
  });

  const { data: overview = [] } = useQuery<EmployeeStatus[]>({
    queryKey: ["overview"],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  // Sort and enhance employees with live online status
  const sortedEmployees = useMemo(() => {
    const statusMap = new Map(overview.map(o => [o.employee_id, o]));
    return employees.map(emp => {
      const statusObj = statusMap.get(emp.id);
      return {
        ...emp,
        is_online: statusObj?.is_online ?? false,
        department_name: emp.department_name || statusObj?.department_name || "—",
      };
    }).sort((a, b) => {
      if (a.is_online && !b.is_online) return -1;
      if (!a.is_online && b.is_online) return 1;
      return a.full_name.localeCompare(b.full_name);
    });
  }, [employees, overview]);

  // Click outside listener for dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Auto-select first employee prioritizing online ones if empty and not allowEmpty
  useEffect(() => {
    if (!allowEmpty && !selectedId && sortedEmployees.length > 0) {
      onChange(sortedEmployees[0].id);
    }
  }, [sortedEmployees, selectedId, allowEmpty, onChange]);

  const selectedEmp = sortedEmployees.find(e => e.id === selectedId);
  const isOnline = selectedEmp?.is_online ?? false;

  const filteredEmployees = sortedEmployees.filter(emp =>
    emp.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (emp.department_name && emp.department_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const selectEmployee = (id: string) => {
    onChange(id);
    setDropdownOpen(false);
    setSearchTerm("");
  };

  return (
    <div ref={dropdownRef} style={{ position: "relative", width, zIndex: 100 }}>
      <button
        onClick={() => setDropdownOpen(!dropdownOpen)}
        className="input"
        type="button"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          background: "var(--bg-primary)",
          border: "1px solid var(--border-default)",
          cursor: "pointer",
          textAlign: "left",
          height: 38,
          width: "100%",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
          {selectedId ? (
            <>
              <span style={{
                width: 8, height: 8, borderRadius: "50%",
                background: isOnline ? "var(--success)" : "var(--border-strong)",
                flexShrink: 0,
                boxShadow: isOnline ? "0 0 0 2px var(--success-subtle)" : "none",
              }} />
              <span className="truncate" style={{ fontWeight: 500 }}>
                {selectedEmp?.full_name ?? "Select Employee"}
              </span>
            </>
          ) : (
            <span style={{ color: "var(--text-placeholder)" }}>{placeholder}</span>
          )}
        </div>
        <ChevronDown size={14} style={{ opacity: 0.6, flexShrink: 0 }} />
      </button>

      {dropdownOpen && (
        <div
          className="card"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            right: 0,
            width: "100%",
            maxHeight: 280,
            overflowY: "auto",
            background: "var(--bg-primary)",
            border: "1px solid var(--border-strong)",
            boxShadow: "var(--shadow-lg)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-2)",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {/* Search Bar */}
          <div style={{ position: "relative", margin: "2px 2px 6px" }}>
            <Search size={13} style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-tertiary)",
            }} />
            <input
              type="text"
              className="input"
              placeholder="Search employee..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              autoFocus
              style={{
                paddingLeft: 28,
                fontSize: 12,
                height: 32,
              }}
            />
          </div>

          {/* List Items */}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, overflowY: "auto", maxHeight: 200 }}>
            {allowEmpty && (
              <button
                onClick={() => selectEmployee("")}
                type="button"
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "8px 10px",
                  borderRadius: "var(--radius-md)",
                  background: !selectedId ? "var(--accent-subtle)" : "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "100%",
                  textAlign: "left",
                  fontSize: 12.5,
                  color: !selectedId ? "var(--accent-text)" : "var(--text-secondary)",
                }}
              >
                {placeholder}
              </button>
            )}

            {filteredEmployees.length === 0 ? (
              <div style={{
                padding: "16px var(--space-3)",
                textAlign: "center",
                fontSize: 12,
                color: "var(--text-tertiary)",
              }}>
                No employees found
              </div>
            ) : (
              filteredEmployees.map(e => {
                const empIsOnline = e.is_online;
                const isSelected = e.id === selectedId;
                return (
                  <button
                    key={e.id}
                    onClick={() => selectEmployee(e.id)}
                    type="button"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      padding: "8px 10px",
                      borderRadius: "var(--radius-md)",
                      background: isSelected ? "var(--accent-subtle)" : "transparent",
                      border: "none",
                      cursor: "pointer",
                      width: "100%",
                      textAlign: "left",
                      transition: "background 0.1s",
                    }}
                    onMouseEnter={el => {
                      if (!isSelected) {
                        el.currentTarget.style.background = "var(--bg-hover)";
                      }
                    }}
                    onMouseLeave={el => {
                      if (!isSelected) {
                        el.currentTarget.style.background = "transparent";
                      }
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden", flex: 1 }}>
                      <span style={{
                        width: 7, height: 7, borderRadius: "50%",
                        background: empIsOnline ? "var(--success)" : "var(--border-default)",
                        flexShrink: 0,
                        boxShadow: empIsOnline ? "0 0 0 2px var(--success-subtle)" : "none",
                      }} />
                      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                        <span className="truncate" style={{
                          fontSize: 12.5,
                          fontWeight: isSelected ? 600 : 500,
                          color: isSelected ? "var(--accent-text)" : "var(--text-primary)",
                        }}>
                          {e.full_name}
                        </span>
                        <span className="truncate" style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                          {e.department_name}
                        </span>
                      </div>
                    </div>
                    {empIsOnline && (
                      <span className="badge badge-green" style={{ fontSize: 9, padding: "1px 5px" }}>
                        Online
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
