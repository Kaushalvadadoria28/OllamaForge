import { useEffect, useCallback } from "react";
import { useAppContext } from "@/context/AppContext";
import { useApi } from "./useApi";
import { API_ENDPOINTS } from "@/config/api";
import type { SourceMode } from "@/config/constants";

export const useSession = () => {
  const { sessionId, setSessionId, setIsSessionReady, setActiveMode, setIsConnected } = useAppContext();
  const { apiFetch } = useApi();

  const initSession = useCallback(async () => {
    const stored = localStorage.getItem("ollamaforge_session_id");
    if (stored) {
      setSessionId(stored);
      // Set default source
      try {
        await apiFetch(API_ENDPOINTS.SET_SOURCE, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: stored, source: "Direct Chat" }),
        });
        setIsConnected(true);
      } catch {
        // Backend might be offline
      }
      setIsSessionReady(true);
      return;
    }

    try {
      const res = await apiFetch(API_ENDPOINTS.INIT_SESSION, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      const sid = data.session_id;
      localStorage.setItem("ollamaforge_session_id", sid);
      setSessionId(sid);

      await apiFetch(API_ENDPOINTS.SET_SOURCE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, source: "Direct Chat" }),
      });

      setIsSessionReady(true);
      setIsConnected(true);
    } catch {
      setIsSessionReady(true); // Allow UI to show error state
    }
  }, [apiFetch, setSessionId, setIsSessionReady, setIsConnected]);

  const setSource = useCallback(async (source: SourceMode) => {
    if (!sessionId) return;
    setActiveMode(source);
    try {
      await apiFetch(API_ENDPOINTS.SET_SOURCE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, source }),
      });
    } catch { /* handled by useApi */ }
  }, [sessionId, apiFetch, setActiveMode]);

  const setModel = useCallback(async (model: string) => {
    if (!sessionId) return;
    try {
      await apiFetch(API_ENDPOINTS.SET_MODEL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, model }),
      });
    } catch { /* handled by useApi */ }
  }, [sessionId, apiFetch]);

  const resetSession = useCallback(() => {
    localStorage.removeItem("ollamaforge_session_id");
    setSessionId(null);
    setIsSessionReady(false);
    initSession();
  }, [initSession, setSessionId, setIsSessionReady]);

  const testConnection = useCallback(async () => {
    try {
      await apiFetch(API_ENDPOINTS.HEALTH);
      setIsConnected(true);
      return true;
    } catch {
      setIsConnected(false);
      return false;
    }
  }, [apiFetch, setIsConnected]);

  useEffect(() => {
    initSession();
  }, []);

  return { setSource, setModel, resetSession, testConnection };
};
