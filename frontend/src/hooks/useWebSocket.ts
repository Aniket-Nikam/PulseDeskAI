import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "../store/authStore";
import type { WsMessage } from "../types";

type MessageHandler = (msg: WsMessage) => void;

export function useWebSocket(onMessage: MessageHandler) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accessToken = useAuthStore((s) => s.accessToken);

  const connect = useCallback(() => {
    if (!accessToken) return;

    const wsBase =
      (import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1")
        .replace("http://", "ws://")
        .replace("https://", "wss://");

    const socket = new WebSocket(`${wsBase}/ws/live?token=${accessToken}`);
    ws.current = socket;

    socket.onopen = () => {
      console.debug("[WS] connected");
      // Keepalive ping every 30s
      const ping = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send("ping");
      }, 30_000);
      socket.addEventListener("close", () => clearInterval(ping));
    };

    socket.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        if (msg.type) onMessage(msg);
      } catch {
        // pong or non-JSON keepalive
      }
    };

    socket.onclose = () => {
      console.debug("[WS] disconnected — reconnecting in 5s");
      reconnectTimer.current = setTimeout(connect, 5_000);
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [accessToken, onMessage]);

  useEffect(() => {
    connect();
    return () => {
      reconnectTimer.current && clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);
}
