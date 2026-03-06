import { useRef, useEffect } from "react";
import { Trash2, Flame } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useChat } from "@/hooks/useChat";
import MessageBubble from "./MessageBubble";
import ThinkingIndicator from "./ThinkingIndicator";
import ChatInput from "./ChatInput";

const SUGGESTIONS = [
  "Summarize a document",
  "Query my database",
  "Chat freely about anything",
];

const ChatArea = () => {
  const { messages, clearMessages, isLoading, isStreaming } = useAppContext();
  const { sendMessage } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);
  const showThinking = isLoading && !isStreaming;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-secondary">
        <h2 className="text-sm font-semibold text-foreground">Chat</h2>
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive transition-colors"
            aria-label="Clear chat"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-4">
        {messages.length === 0 && !showThinking ? (
          <div className="flex-1 flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <Flame className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-1">How can I help you today?</h3>
            <p className="text-sm text-muted-foreground mb-6">Choose a mode and start chatting</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-4 py-2 rounded-full border border-border text-sm text-muted-foreground hover:bg-card hover:text-foreground transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            {showThinking && <ThinkingIndicator />}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput />
    </div>
  );
};

export default ChatArea;
