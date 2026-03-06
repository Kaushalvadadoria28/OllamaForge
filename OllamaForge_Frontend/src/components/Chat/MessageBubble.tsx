import { Copy, Check } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import type { ChatMessage } from "@/context/AppContext";

interface Props {
  message: ChatMessage;
}

const MessageBubble = ({ message }: Props) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const time = message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in group`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 relative ${isUser
          ? "bg-user-bubble text-user-bubble-foreground rounded-br-md shadow-sm"
          : "bg-assistant-bubble text-assistant-bubble-foreground rounded-bl-md shadow-sm border border-border/50"
          }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none text-sm break-words
            [&_ul]:list-disc [&_ul]:ml-6 [&_ul]:my-3
            [&_ol]:list-decimal [&_ol]:ml-6 [&_ol]:my-3
            [&_li]:my-1.5 [&_li>p]:my-0
            [&_p]:my-3 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0
            [&_pre]:bg-zinc-950/50 [&_pre]:rounded-xl [&_pre]:p-4 [&_pre]:my-4 [&_pre]:border [&_pre]:border-white/10 [&_pre]:shadow-inner
            [&_code]:text-accent [&_code]:font-mono [&_code]:text-[13px] [&_code]:bg-white/5 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-md
            [&_h1]:text-xl [&_h1]:font-bold [&_h1]:mb-6 [&_h1]:mt-2
            [&_h2]:text-lg [&_h2]:font-bold [&_h2]:mb-4 [&_h2]:mt-2
            [&_h3]:text-base [&_h3]:font-bold [&_h3]:mb-3 [&_h3]:mt-1
            [&_strong]:text-foreground [&_strong]:font-bold
            [&_blockquote]:border-l-4 [&_blockquote]:border-primary/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:my-4
            [&_hr]:my-6 [&_hr]:border-white/10">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{message.content}</ReactMarkdown>
          </div>
        )}

        <div className={`flex items-center gap-2 mt-1.5 ${isUser ? "justify-end" : "justify-between"}`}>
          <span className="text-[10px] text-muted-foreground/60">{time}</span>
          {!isUser && message.content && (
            <button
              onClick={handleCopy}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-card"
              aria-label="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-success" />
              ) : (
                <Copy className="w-3 h-3 text-muted-foreground" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
