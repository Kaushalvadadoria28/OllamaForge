import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";
import type { SourceMode } from "@/config/constants";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface AppState {
  sessionId: string | null;
  activeMode: SourceMode;
  messages: ChatMessage[];
  selectedModel: string;
  systemPrompt: string | null;
  temperature: number;
  isStreaming: boolean;
  isLoading: boolean;
  isConnected: boolean;
  isSessionReady: boolean;
  ingestionStatus: Record<string, { ready: boolean; label: string }>;
  streamEnabled: boolean;
}

interface AppContextType extends AppState {
  setSessionId: (id: string | null) => void;
  setActiveMode: (mode: SourceMode) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistantMessage: (content: string) => void;
  clearMessages: () => void;
  setSelectedModel: (model: string) => void;
  setSystemPrompt: (prompt: string | null) => void;
  setTemperature: (temp: number) => void;
  setIsStreaming: (v: boolean) => void;
  setIsLoading: (v: boolean) => void;
  setIsConnected: (v: boolean) => void;
  setIsSessionReady: (v: boolean) => void;
  setIngestionStatus: (source: string, status: { ready: boolean; label: string }) => void;
  setStreamEnabled: (v: boolean) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<SourceMode>("Direct Chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [temperature, setTemperature] = useState(0.5);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isSessionReady, setIsSessionReady] = useState(true);
  const [ingestionStatus, setIngestionStatusState] = useState<Record<string, { ready: boolean; label: string }>>({});
  const [streamEnabled, setStreamEnabled] = useState(true);

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  const updateLastAssistantMessage = useCallback((content: string) => {
    setMessages(prev => {
      const updated = [...prev];
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === "assistant") {
          updated[i] = { ...updated[i], content };
          break;
        }
      }
      return updated;
    });
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  const setIngestionStatus = useCallback((source: string, status: { ready: boolean; label: string }) => {
    setIngestionStatusState(prev => ({ ...prev, [source]: status }));
  }, []);

  return (
    <AppContext.Provider
      value={{
        sessionId, setSessionId,
        activeMode, setActiveMode,
        messages, addMessage, updateLastAssistantMessage, clearMessages,
        selectedModel, setSelectedModel,
        systemPrompt, setSystemPrompt,
        temperature, setTemperature,
        isStreaming, setIsStreaming,
        isLoading, setIsLoading,
        isConnected, setIsConnected,
        isSessionReady, setIsSessionReady,
        ingestionStatus, setIngestionStatus,
        streamEnabled, setStreamEnabled,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
};
