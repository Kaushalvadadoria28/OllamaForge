import { useCallback } from "react";
import { useAppContext } from "@/context/AppContext";
import { useApi } from "./useApi";
import { API_ENDPOINTS } from "@/config/api";

export const useChat = () => {
  const {
    sessionId, messages, addMessage, updateLastAssistantMessage,
    systemPrompt, temperature, isStreaming, setIsStreaming,
    setIsLoading, streamEnabled,
  } = useAppContext();
  const { apiFetch } = useApi();

  const sendMessage = useCallback(async (content: string) => {
    if (!sessionId || !content.trim()) return;

    addMessage({ role: "user", content: content.trim(), timestamp: new Date() });

    const useStream = streamEnabled;
    setIsLoading(true);

    try {
      if (useStream) {
        // SSE streaming
        const res = await fetch(API_ENDPOINTS.CHAT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message: content.trim(),
            stream: true,
            system_prompt: systemPrompt,
            temperature,
          }),
        });

        if (!res.ok) throw new Error("Stream failed");
        if (!res.body) throw new Error("No response body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";
        let buffer = "";
        let hasStartedStreaming = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");

          // Keep the last partial line in the buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith("data: ")) {
              try {
                const jsonStr = line.slice(6);
                const parsed = JSON.parse(jsonStr);
                if (parsed.content) {
                  if (!hasStartedStreaming) {
                    addMessage({ role: "assistant", content: "", timestamp: new Date() });
                    setIsStreaming(true);
                    hasStartedStreaming = true;
                  }
                  accumulated += parsed.content;
                  updateLastAssistantMessage(accumulated);
                }
              } catch (e) {
                console.error("Error parsing SSE JSON:", e);
              }
            }
          }
        }

        setIsStreaming(false);
      } else {
        // Standard request
        const res = await apiFetch(API_ENDPOINTS.CHAT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message: content.trim(),
            stream: false,
            system_prompt: systemPrompt,
            temperature,
          }),
        });

        const data = await res.json();
        addMessage({ role: "assistant", content: data.response, timestamp: new Date() });
      }
    } catch {
      if (!useStream) {
        addMessage({ role: "assistant", content: "⚠️ Failed to get a response. Is the backend running?", timestamp: new Date() });
      }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
    }
  }, [sessionId, streamEnabled, systemPrompt, temperature, addMessage, updateLastAssistantMessage, setIsStreaming, setIsLoading, apiFetch]);

  const stopStreaming = useCallback(() => {
    setIsStreaming(false);
  }, [setIsStreaming]);

  return { sendMessage, stopStreaming };
};
