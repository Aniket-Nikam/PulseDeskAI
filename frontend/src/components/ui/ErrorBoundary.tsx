import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", height: "100%", padding: 24, textAlign: "center"
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%", background: "var(--danger-subtle)",
            display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16
          }}>
            <AlertTriangle size={24} style={{ color: "var(--danger)" }} />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
            Something went wrong
          </h2>
          <p style={{ fontSize: 14, color: "var(--text-tertiary)", maxWidth: 400, marginBottom: 24 }}>
            {this.state.error?.message || "An unexpected error occurred in this view. Please try refreshing or going back."}
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => {
              this.setState({ hasError: false });
              window.location.reload();
            }}
          >
            Reload page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
