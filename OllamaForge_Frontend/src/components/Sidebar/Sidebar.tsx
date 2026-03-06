import { MessageSquare, FileText, Database, BookOpen, Globe } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useSession } from "@/hooks/useSession";
import { SOURCE_OPTIONS, type SourceMode } from "@/config/constants";
import IngestionPanel from "./IngestionPanel";

const iconMap: Record<string, React.ElementType> = {
  MessageSquare,
  FileText,
  Database,
  BookOpen,
  Globe,
};

const Sidebar = () => {
  const { activeMode, isStreaming, isLoading } = useAppContext();
  const { setSource } = useSession();
  const busy = isStreaming || isLoading;

  const handleModeClick = (mode: SourceMode) => {
    if (busy) return;
    setSource(mode);
  };

  return (
    <aside className="w-64 shrink-0 border-r border-border bg-secondary flex flex-col h-full overflow-hidden max-md:hidden">
      <div className="p-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 px-2">
          Intelligence Mode
        </p>
        <div className="flex flex-col gap-1">
          {SOURCE_OPTIONS.map(opt => {
            const Icon = iconMap[opt.icon];
            const isActive = activeMode === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => handleModeClick(opt.value)}
                disabled={busy}
                title={busy ? "Wait for current response to finish" : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left
                  ${isActive
                    ? "bg-primary/15 text-primary border-l-2 border-primary"
                    : "text-muted-foreground hover:bg-card hover:text-foreground border-l-2 border-transparent"
                  }
                  ${busy ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
                `}
                aria-label={`Switch to ${opt.label} mode`}
              >
                {Icon && <Icon className="w-4 h-4" />}
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 border-t border-border">
        <IngestionPanel />
      </div>
    </aside>
  );
};

export default Sidebar;
