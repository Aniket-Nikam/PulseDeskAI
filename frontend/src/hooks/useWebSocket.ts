import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "../store/authStore";
import type { WsMessage } from "../types";
import { WS_BASE_URL } from "../config";
import { authApi } from "../api/client";

type MessageHandler = (msg: WsMessage) => void;

export function useWebSocket(onMessage: MessageHandler) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isAuthenticated = useAuthStore((s) => !!s.admin);

  // Store message handler in a ref to avoid reconnecting whenever it changes
  const onMessageRef = useRef<MessageHandler>(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (!isAuthenticated) return;

    const token = useAuthStore.getState().accessToken || '';
    const socket = new WebSocket(`${WS_BASE_URL}/ws/live?token=${token}`);
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
        if (msg.type) onMessageRef.current(msg);
      } catch {
        // pong or non-JSON keepalive
      }
    };

    socket.onclose = (event) => {
      console.debug("[WS] disconnected — code:", event.code);
      if (event.code === 4001) {
        console.debug("[WS] Auth error, attempting to refresh token...");
        authApi.refresh()
          .then((data) => {
            console.debug("[WS] Token refreshed successfully, reconnecting...");
            useAuthStore.setState({ accessToken: data.access_token });
            connect();
          })
          .catch((err) => {
            console.error("[WS] Token refresh failed:", err);
            useAuthStore.getState().logout();
            window.location.href = "/login";
          });
        return;
      }
      console.debug("[WS] reconnecting in 5s");
      reconnectTimer.current = setTimeout(connect, 5_000);
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [isAuthenticated]);

  useEffect(() => {
    connect();
    return () => {
      reconnectTimer.current && clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);
}
