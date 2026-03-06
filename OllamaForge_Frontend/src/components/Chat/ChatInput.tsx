import { useState, useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useChat } from "@/hooks/useChat";

const ChatInput = () => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { isLoading, isStreaming, activeMode, streamEnabled, setStreamEnabled } = useAppContext();
  const { sendMessage, stopStreaming } = useChat();
  const busy = isLoading || isStreaming;

  const handleSend = () => {
    if (!input.trim() || busy) return;
    sendMessage(input);
    setInput("");
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
    }
  }, [input]);

  // Refocus after sending
  useEffect(() => {
    if (!busy && textareaRef.current) textareaRef.current.focus();
  }, [busy]);

  const modeLabels: Record<string, string> = {
    "Direct Chat": "💬 Direct",
    RAG: "📄 RAG",
    Database: "🗄️ Database",
    Wikipedia: "📖 Wikipedia",
    Website: "🌐 Website",
  };

  return (
    <div className="border-t border-border bg-secondary p-3 space-y-2">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything... (Shift+Enter for new line)"
          rows={1}
          disabled={busy}
          className="flex-1 resize-none bg-card border border-border rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 scrollbar-thin"
          aria-label="Chat message input"
        />
        {isStreaming ? (
          <button
            onClick={stopStreaming}
            className="shrink-0 p-3 rounded-xl bg-destructive text-destructive-foreground hover:opacity-90 transition-opacity"
            aria-label="Stop streaming"
          >
            <Square className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || busy}
            className="shrink-0 p-3 rounded-xl bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-40 transition-opacity"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full">
          {modeLabels[activeMode] || activeMode}
        </span>
        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={streamEnabled}
            onChange={e => setStreamEnabled(e.target.checked)}
            className="accent-primary w-3.5 h-3.5"
          />
          Stream response
        </label>
      </div>
    </div>
  );
};

export default ChatInput;
