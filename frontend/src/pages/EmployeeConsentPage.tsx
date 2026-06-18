import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Download, Trash2, CheckCircle2, XCircle } from "lucide-react";
import { employeePortalApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { Dialog } from "../components/ui/Dialog";

export function EmployeeConsentPage() {
  const queryClient = useQueryClient();
  const [erasing, setErasing] = useState(false);
  const [showConfirmErasure, setShowConfirmErasure] = useState(false);

  // Fetch Consent Status
  const { data: consentData, isLoading } = useQuery({
    queryKey: ["employeeConsent"],
    queryFn: employeePortalApi.consent,
  });

  // Toggle Consent Mutation
  const toggleConsentMutation = useMutation({
    mutationFn: (consentGiven: boolean) => employeePortalApi.toggleConsent(consentGiven),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employeeConsent"] });
    },
  });

  // Erase Data Mutation
  const eraseDataMutation = useMutation({
    mutationFn: employeePortalApi.eraseData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employeeConsent"] });
      queryClient.invalidateQueries({ queryKey: ["employeeDashboard"] });
      queryClient.invalidateQueries({ queryKey: ["employeeTimeline"] });
      setShowConfirmErasure(false);
      setErasing(false);
      Dialog.alert("All your tracking data has been permanently erased. Devices suspended.", "Data Erased");
    },
    onError: (err) => {
      setErasing(false);
      Dialog.alert("Failed to erase data. Please try again.", "Error");
    }
  });

  const handleExport = async () => {
    try {
      const data = await employeePortalApi.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pulsedesk_gdpr_export_${consentData?.employee_id || "data"}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      await Dialog.alert("Failed to export data.", "Export Failed");
    }
  };

  const handleErasure = () => {
    setErasing(true);
    eraseDataMutation.mutate();
  };

  if (isLoading) {
    return (
      <div style={{ padding: "var(--space-8)" }}>
        <PageHeader title="Privacy & GDPR Consent" subtitle="Manage your monitoring consent and data rights" />
        <div className="card skeleton" style={{ height: 200 }} />
      </div>
    );
  }

  const consentGiven = consentData?.consent_given || false;

  return (
    <div style={{ padding: "var(--space-8)", maxWidth: 800, margin: "0 auto" }}>
      <PageHeader
        title="Privacy & GDPR Consent"
        subtitle="Manage your right of access, erasure, and active tracking consent status."
      />

      {/* Consent Status Card */}
      <div className="card" style={{ padding: 24, marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          {consentGiven ? (
            <CheckCircle2 size={32} color="var(--success)" />
          ) : (
            <XCircle size={32} color="var(--error)" />
          )}
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
              Monitoring is {consentGiven ? "ACTIVE" : "SUSPENDED"}
            </h3>
            <p style={{ margin: "2px 0 0 0", fontSize: 12, color: "var(--text-tertiary)" }}>
              {consentGiven
                ? `Consent recorded on: ${new Date(consentData.consent_given_at).toLocaleString()}`
                : consentData?.consent_revoked_at
                ? `Consent revoked on: ${new Date(consentData.consent_revoked_at).toLocaleString()}`
                : "Consent has not been given yet."}
            </p>
          </div>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 20px 0" }}>
          By granting consent, you allow the PulseDesk agent installed on your work device to track active 
          applications, window titles, and input counters during work sessions. You can revoke this consent at 
          any time, which will immediately suspend all monitoring services on your registered devices.
        </p>

        <button
          onClick={() => toggleConsentMutation.mutate(!consentGiven)}
          disabled={toggleConsentMutation.isPending}
          className={`btn ${consentGiven ? "btn-danger" : "btn-primary"}`}
          style={{ width: "100%", justifyContent: "center" }}
        >
          {consentGiven ? "Revoke My Consent (Suspend Tracking)" : "Grant Consent (Resume Tracking)"}
        </button>
      </div>

      {/* GDPR Data Rights Panel */}
      <div className="card" style={{ padding: 24 }}>
        <h3 style={{ margin: "0 0 16px 0", fontSize: 14, fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 8 }}>
          <Shield size={16} color="var(--accent)" />
          GDPR Rights Management
        </h3>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Article 15: Right of Access */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <h4 style={{ margin: "0 0 4px 0", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                GDPR Article 15: Right of Access (Export)
              </h4>
              <p style={{ margin: 0, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                Request and download a complete archive of all active activity telemetry, window logs, daily summaries, 
                and anomaly logs registered under your profile.
              </p>
            </div>
            <button
              onClick={handleExport}
              className="btn btn-secondary"
              style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}
            >
              <Download size={14} />
              Export My Data
            </button>
          </div>

          {/* Article 17: Right to Erasure */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <h4 style={{ margin: "0 0 4px 0", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                GDPR Article 17: Right to Erasure (Delete)
              </h4>
              <p style={{ margin: 0, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                Permanently erase all historical telemetry logs, screenshots, summaries, and work sessions. 
                This action is irreversible and automatically revokes your monitoring consent.
              </p>
            </div>
            <button
              onClick={() => setShowConfirmErasure(true)}
              className="btn btn-danger"
              style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}
            >
              <Trash2 size={14} />
              Erase My Data
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Erasure */}
      {showConfirmErasure && (
        <div style={{
          position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000
        }}>
          <div className="card" style={{ maxWidth: 440, padding: 24, margin: 16 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
              ⚠️ Are you absolutely sure?
            </h3>
            <p style={{ margin: "0 0 20px 0", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
              This will <strong>permanently erase</strong> all your activity tracking data, screenshots, summaries, and 
              work sessions from the server database. This action cannot be undone, and your tracking devices 
              will be immediately suspended.
            </p>
            <div style={{ display: "flex", justifySelf: "flex-end", gap: 10 }}>
              <button
                className="btn btn-secondary"
                disabled={erasing}
                onClick={() => setShowConfirmErasure(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                disabled={erasing}
                onClick={handleErasure}
              >
                {erasing ? "Erasing..." : "Yes, Erase My Data"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
