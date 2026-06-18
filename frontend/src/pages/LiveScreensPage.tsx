import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Monitor, RefreshCw, Maximize2, X, Play, Square, Search } from "lucide-react";
import { api, analyticsApi, liveStreamApi } from "../api/client";
import { PageHeader } from "../components/ui/PageHeader";
import { OnlineBadge } from "../components/ui/OnlineBadge";
import { WS_BASE_URL } from "../config";
import type { EmployeeStatus } from "../types";
import { formatTime } from "../utils/format";
import { useAuthStore } from "../store/authStore";

export function LiveScreensPage() {
  const [selected, setSelected] = useState<{ streamFrame: string | null; fallbackUrl: string | null; name: string; employeeId: string } | null>(null);
  const [tick, setTick] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");

  // Auto-refresh employee list every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(interval);
  }, []);

  const { data: overview = [], refetch } = useQuery<EmployeeStatus[]>({
    queryKey: ["overview", tick],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  const online = overview.filter((e) => e.is_online);

  const filteredOnline = online.filter((emp) => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return true;
    return (
      emp.employee_name.toLowerCase().includes(query) ||
      (emp.department_name && emp.department_name.toLowerCase().includes(query)) ||
      (emp.active_app && emp.active_app.toLowerCase().includes(query))
    );
  });

  return (
    <div style={{ padding: "var(--space-8)", minHeight: "100vh", background: "var(--bg-primary)" }}>
      <PageHeader
        title="Live Screen Broadcasting"
        subtitle={`${online.length} machine${online.length !== 1 ? "s" : ""} online — streaming live video`}
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              Auto-refreshes every 30s
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => { setTick((t) => t + 1); refetch(); }}>
              <RefreshCw size={13} style={{ marginRight: 4 }} /> Refresh now
            </button>
          </div>
        }
      />

      {/* Search Bar */}
      <div style={{
        marginBottom: "var(--space-6)",
        position: "relative",
        maxWidth: "400px",
        width: "100%",
      }}>
        <div style={{
          position: "absolute",
          left: 12,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--text-tertiary)",
          display: "flex",
          alignItems: "center",
          pointerEvents: "none",
        }}>
          <Search size={15} />
        </div>
        <input
          type="text"
          placeholder="Search employee by name, department..."
          className="input"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            paddingLeft: 34,
            paddingRight: searchQuery ? 30 : 12,
          }}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            style={{
              position: "absolute",
              right: 10,
              top: "50%",
              transform: "translateY(-50%)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-tertiary)",
              padding: 4,
              display: "flex",
              alignItems: "center",
            }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {online.length === 0 ? (
        <div className="card empty-state" style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-12)",
          textAlign: "center",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-subtle)",
          background: "var(--bg-secondary)"
        }}>
          <div className="empty-state-icon" style={{
            background: "rgba(239, 68, 68, 0.1)",
            color: "var(--error)",
            padding: 16,
            borderRadius: "50%",
            marginBottom: 16
          }}><Monitor size={36} /></div>
          <div className="empty-state-title" style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}>No employees online</div>
          <div className="empty-state-body" style={{ color: "var(--text-secondary)", maxWidth: 400, marginTop: 8 }}>
            Live video feeds appear here when employees are active. Make sure agents are running and approved.
          </div>
        </div>
      ) : filteredOnline.length === 0 ? (
        <div className="card empty-state" style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-12)",
          textAlign: "center",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-subtle)",
          background: "var(--bg-secondary)"
        }}>
          <div className="empty-state-icon" style={{
            background: "var(--accent-subtle)",
            color: "var(--accent)",
            padding: 16,
            borderRadius: "50%",
            marginBottom: 16
          }}><Search size={36} /></div>
          <div className="empty-state-title" style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)" }}>No matching employees</div>
          <div className="empty-state-body" style={{ color: "var(--text-secondary)", maxWidth: 400, marginTop: 8 }}>
            No online employees match your search query: "{searchQuery}".
          </div>
          <button className="btn btn-secondary btn-sm" style={{ marginTop: 16 }} onClick={() => setSearchQuery("")}>
            Clear search
          </button>
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          gap: 20,
        }}>
          {filteredOnline.map((emp, index) => (
            <LiveStreamCard
              key={emp.employee_id}
              employee={emp}
              tick={tick}
              connectDelay={index * 200}
              onExpand={(streamFrame, fallbackUrl) => setSelected({ streamFrame, fallbackUrl, name: emp.employee_name, employeeId: emp.employee_id })}
            />
          ))}
        </div>
      )}

      {/* Full-screen stream modal */}
      {selected && (
        <LiveStreamModal
          selected={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Canvas-based video renderer — draws frames on <canvas> for guaranteed repaint
// ─────────────────────────────────────────────────────────────────────────────
function VideoCanvas({
  frameDataUrl,
  style,
  objectFit = "contain",
}: {
  frameDataUrl: string | null;
  style?: React.CSSProperties;
  objectFit?: "contain" | "cover";
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!frameDataUrl) return;

    // Reuse the same Image object to avoid GC pressure
    if (!imgRef.current) {
      imgRef.current = new Image();
    }
    const img = imgRef.current;

    img.onload = () => {
      // Cancel any pending rAF to avoid stacking draws
      if (rafRef.current) cancelAnimationFrame(rafRef.current);

      rafRef.current = requestAnimationFrame(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        // Match canvas internal resolution to image size for crisp rendering
        if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
        }

        ctx.drawImage(img, 0, 0);
      });
    };

    img.src = frameDataUrl;

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [frameDataUrl]);

  if (!frameDataUrl) return null;

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: "100%",
        height: "100%",
        objectFit,
        display: "block",
        background: "#000",
        ...style,
      }}
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LiveStreamModal — Full-screen real-time video viewer
// ─────────────────────────────────────────────────────────────────────────────
function LiveStreamModal({ selected, onClose }: { selected: { streamFrame: string | null; fallbackUrl: string | null; name: string; employeeId: string }; onClose: () => void }) {
  const [modalFrame, setModalFrame] = useState<string | null>(selected.streamFrame);
  const [fps, setFps] = useState(24);
  const [quality, setQuality] = useState(50);
  const [isStreaming, setIsStreaming] = useState(true);
  const [frameCount, setFrameCount] = useState(0);
  const [connecting, setConnecting] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch active stream config from backend on mount
  useEffect(() => {
    liveStreamApi.getStreamConfig(selected.employeeId)
      .then((cfg) => {
        if (cfg) {
          setFps(cfg.fps ?? 24);
          setQuality(cfg.quality ?? 50);
          setIsStreaming(cfg.enabled ?? true);
        }
      })
      .catch(console.error);
  }, [selected.employeeId]);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pingInterval: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    const maxBackoff = 10_000;

    function connect() {
      if (cancelled) return;
      // Open WebSocket to receive stream frames in real-time
      const token = useAuthStore.getState().accessToken || '';
      const wsUrl = `${WS_BASE_URL}/ws/screen-view/${selected.employeeId}?token=${token}`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        setConnecting(false);
        // Send keepalive pings every 30s
        pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 30_000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "screen_frame" && data.frame) {
            setModalFrame(`data:image/jpeg;base64,${data.frame}`);
            setFrameCount((c) => c + 1);
          }
        } catch {
          // ignore non-JSON (e.g., pong responses)
        }
      };

      ws.onclose = () => {
        if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
        // Reconnect with exponential backoff
        if (!cancelled) {
          const delay = Math.min(1000 * Math.pow(1.5, attempt), maxBackoff);
          attempt++;
          reconnectTimer = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        setConnecting(false);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingInterval) clearInterval(pingInterval);
      if (ws) ws.close();
    };
  }, [selected.employeeId]);

  const handleToggleStream = async () => {
    const nextState = !isStreaming;
    setIsStreaming(nextState);
    await liveStreamApi.updateStreamConfig(selected.employeeId, nextState, fps, quality).catch(console.error);
  };

  const handleFpsChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newFps = Number(e.target.value);
    setFps(newFps);
    await liveStreamApi.updateStreamConfig(selected.employeeId, isStreaming, newFps, quality).catch(console.error);
  };

  const handleQualityChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newQuality = Number(e.target.value);
    setQuality(newQuality);
    await liveStreamApi.updateStreamConfig(selected.employeeId, isStreaming, fps, newQuality).catch(console.error);
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(10, 10, 12, 0.92)",
        display: "flex", alignItems: "center", justifyContent: "center",
        backdropFilter: "blur(8px)",
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          position: "relative",
          width: "90vw",
          maxWidth: "1200px",
          background: "var(--bg-secondary)",
          borderRadius: 16,
          border: "1px solid var(--border-subtle)",
          padding: 20,
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: 16,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ color: "var(--text-primary)", fontSize: 16, fontWeight: 600 }}>
              Live Stream — {selected.name}
            </span>
            {isStreaming && (
              <span className="live-indicator" style={{
                background: "rgba(239, 68, 68, 0.1)",
                color: "#ef4444",
                padding: "2px 8px",
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 4
              }}>
                <span className="pulsing-dot" /> LIVE
              </span>
            )}
            {frameCount > 0 && (
              <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                {frameCount} frames received
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* FPS Control */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <span style={{ color: "var(--text-secondary)" }}>FPS:</span>
              <select
                value={fps}
                onChange={handleFpsChange}
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)",
                  borderRadius: 4,
                  padding: "2px 6px"
                }}
              >
                <option value={1}>1 FPS</option>
                <option value={3}>3 FPS</option>
                <option value={5}>5 FPS</option>
                <option value={8}>8 FPS</option>
                <option value={10}>10 FPS</option>
                <option value={15}>15 FPS</option>
                <option value={24}>24 FPS (Default)</option>
                <option value={30}>30 FPS</option>
                <option value={60}>60 FPS (⚠ High bandwidth)</option>
              </select>
            </div>

            {/* Quality Control */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <span style={{ color: "var(--text-secondary)" }}>Quality:</span>
              <select
                value={quality}
                onChange={handleQualityChange}
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)",
                  borderRadius: 4,
                  padding: "2px 6px"
                }}
              >
                <option value={30}>Low</option>
                <option value={50}>Medium</option>
                <option value={70}>High</option>
                <option value={85}>Ultra</option>
              </select>
            </div>

            <button
              className={`btn btn-sm ${isStreaming ? "btn-secondary" : "btn-primary"}`}
              onClick={handleToggleStream}
              style={{ display: "flex", alignItems: "center", gap: 4 }}
            >
              {isStreaming ? (
                <><Square size={12} /> Pause</>
              ) : (
                <><Play size={12} /> Resume</>
              )}
            </button>

            <button
              onClick={onClose}
              style={{
                background: "none", border: "none", cursor: "pointer",
                color: "var(--text-secondary)", padding: 4,
                display: "flex", alignItems: "center"
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Video Display */}
        <div style={{
          aspectRatio: "16/9",
          background: "#000",
          borderRadius: 8,
          overflow: "hidden",
          position: "relative"
        }}>
          {modalFrame ? (
            <VideoCanvas
              frameDataUrl={modalFrame}
              objectFit="contain"
            />
          ) : connecting ? (
            <div style={{
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              height: "100%", gap: 12, color: "var(--text-tertiary)"
            }}>
              <div className="skeleton" style={{ width: 48, height: 48, borderRadius: "50%" }} />
              <span style={{ fontSize: 14 }}>Connecting to live video feed...</span>
            </div>
          ) : selected.fallbackUrl ? (
            <div style={{ width: "100%", height: "100%", position: "relative" }}>
              <img
                src={selected.fallbackUrl}
                alt={selected.name}
                style={{
                  width: "100%", height: "100%",
                  objectFit: "contain",
                  opacity: 0.4
                }}
              />
              <div style={{
                position: "absolute", inset: 0,
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                color: "#fff", background: "rgba(0,0,0,0.5)",
                fontSize: 14, fontWeight: 500, gap: 8
              }}>
                <Monitor size={28} style={{ opacity: 0.6 }} />
                Waiting for agent to connect live video feed...
              </div>
            </div>
          ) : (
            <div style={{
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              height: "100%", gap: 12, color: "var(--text-tertiary)"
            }}>
              <Monitor size={36} style={{ opacity: 0.5 }} />
              <span>Waiting for live video stream...</span>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .pulsing-dot {
          width: 6px;
          height: 6px;
          background-color: #ef4444;
          border-radius: 50%;
          display: inline-block;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70% { transform: scale(1); opacity: 0.8; box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
          100% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
      `}</style>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LiveStreamCard — Grid card with always-on live video feed
// ─────────────────────────────────────────────────────────────────────────────
function LiveStreamCard({
  employee, tick, onExpand, connectDelay = 0,
}: {
  employee: EmployeeStatus;
  tick: number;
  connectDelay?: number;
  onExpand: (streamFrame: string | null, fallbackUrl: string | null) => void;
}) {
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [streamFrame, setStreamFrame] = useState<string | null>(null);
  const [streamingActive, setStreamingActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isVisible, setIsVisible] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Viewport-based streaming: only connect WebSocket when card is visible
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { rootMargin: "100px", threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fetch the latest screenshot as fallback
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    api.get(`/screenshots/${employee.employee_id}?limit=1&sort=desc`)
      .then(async (r) => {
        if (cancelled) return;
        const shots = r.data?.items || r.data || [];
        if (shots.length > 0 && shots[0].file_exists !== false) {
          try {
            const imgResp = await api.get(`/screenshots/view/${shots[0].id}`, {
              responseType: "blob",
            });
            if (cancelled) return;
            const blobUrl = URL.createObjectURL(imgResp.data);
            setScreenshotUrl(blobUrl);
          } catch {
            if (!cancelled) setScreenshotUrl(null);
          }
        } else {
          setScreenshotUrl(null);
        }
        if (!cancelled) setLoading(false);
      })
      .catch(() => {
        if (!cancelled) { setLoading(false); }
      });

    return () => {
      cancelled = true;
      setScreenshotUrl((prev) => { if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev); return null; });
    };
  }, [employee.employee_id, tick]);

  // Connect to the employee's screen-view WebSocket — only when card is visible in viewport
  useEffect(() => {
    if (!isVisible) {
      // Disconnect when not visible
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
        setStreamingActive(false);
      }
      return;
    }

    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pingInterval: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    const maxBackoff = 10_000;

    // Stagger connections to avoid connection storms when page loads
    const staggerTimer = setTimeout(() => {
      if (cancelled) return;
      connectWs();
    }, connectDelay);

    function connectWs() {
      if (cancelled) return;
      const token = useAuthStore.getState().accessToken || '';
      const wsUrl = `${WS_BASE_URL}/ws/screen-view/${employee.employee_id}?token=${token}`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        setStreamingActive(true);
        // Send keepalive pings every 30s to prevent proxy timeouts
        pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 30_000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "screen_frame" && data.frame) {
            setStreamFrame(`data:image/jpeg;base64,${data.frame}`);
            setStreamingActive(true);
          }
        } catch {
          // ignore non-JSON (e.g., pong responses)
        }
      };

      ws.onclose = () => {
        setStreamingActive(false);
        if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
        // Reconnect with exponential backoff
        if (!cancelled) {
          const delay = Math.min(1000 * Math.pow(1.5, attempt), maxBackoff);
          attempt++;
          reconnectTimer = setTimeout(connectWs, delay);
        }
      };

      ws.onerror = () => {
        // onclose will fire after onerror, which handles reconnection
      };
    }

    return () => {
      cancelled = true;
      clearTimeout(staggerTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingInterval) clearInterval(pingInterval);
      if (ws) ws.close();
    };
  }, [employee.employee_id, isVisible, connectDelay]);

  const handleCardClick = () => {
    onExpand(streamFrame, screenshotUrl);
  };

  return (
    <div ref={cardRef} className="card" style={{
      overflow: "hidden",
      borderRadius: 12,
      border: "1px solid var(--border-subtle)",
      background: "var(--bg-secondary)",
      boxShadow: "var(--shadow-sm)",
      transition: "transform 0.2s, box-shadow 0.2s",
      cursor: "pointer",
    }}
      onClick={handleCardClick}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "var(--shadow-md)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "none";
        e.currentTarget.style.boxShadow = "var(--shadow-sm)";
      }}
    >
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 16px",
        borderBottom: "1px solid var(--border-subtle)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <OnlineBadge online={employee.is_online} showLabel={false} size="sm" />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
              {employee.employee_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>
              {employee.active_app ?? "No app active"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }} onClick={(e) => e.stopPropagation()}>
          <button
            className="btn btn-ghost btn-icon"
            onClick={handleCardClick}
            style={{ padding: 6 }}
            title="Enlarge stream"
          >
            <Maximize2 size={13} />
          </button>
        </div>
      </div>

      {/* Live Video Display */}
      <div style={{
        aspectRatio: "16/9",
        background: "#141416",
        position: "relative",
        overflow: "hidden",
      }}>
        {streamFrame ? (
          <VideoCanvas
            frameDataUrl={streamFrame}
            objectFit="cover"
          />
        ) : loading ? (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div className="skeleton" style={{ width: "80%", height: "70%", borderRadius: 6 }} />
          </div>
        ) : screenshotUrl ? (
          <img
            src={screenshotUrl}
            alt={employee.employee_name}
            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.8 }}
          />
        ) : (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            gap: 8, padding: 12
          }}>
            <Monitor size={24} style={{ color: "var(--text-tertiary)", opacity: 0.3 }} />
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", textAlign: "center" }}>
              Connecting to video feed...
            </div>
          </div>
        )}

        {/* Streaming Status Badge Overlay */}
        <div style={{
          position: "absolute", bottom: 8, left: 8,
          display: "flex", gap: 6
        }}>
          {streamingActive && (
            <span style={{
              background: "rgba(239, 68, 68, 0.9)",
              color: "#fff",
              fontSize: 10,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
              display: "flex",
              alignItems: "center",
              gap: 4
            }}>
              <span className="pulsing-dot" style={{
                width: 5, height: 5, background: "#fff",
                borderRadius: "50%", display: "inline-block",
                animation: "pulse-dot 1.5s infinite"
              }} />
              LIVE
            </span>
          )}
          {employee.activity_type && (
            <span style={{
              background: "rgba(0,0,0,0.6)",
              color: "#fff",
              fontSize: 10,
              padding: "2px 8px",
              borderRadius: 4,
              textTransform: "capitalize"
            }}>
              {employee.activity_type}
            </span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        padding: "10px 16px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        borderTop: "1px solid var(--border-subtle)",
        background: "var(--bg-secondary)"
      }}>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
          {employee.last_seen ? `Seen ${formatTime(employee.last_seen)}` : "No data"}
        </div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500 }}>
          {employee.department_name ?? ""}
        </div>
      </div>

      <style>{`
        .pulsing-dot {
          width: 6px;
          height: 6px;
          background-color: #ef4444;
          border-radius: 50%;
          display: inline-block;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70% { transform: scale(1); opacity: 0.8; box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
          100% { transform: scale(0.9); opacity: 1; box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
      `}</style>
    </div>
  );
}
