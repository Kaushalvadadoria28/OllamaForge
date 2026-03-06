import { useAppContext } from "@/context/AppContext";
import { THINKING_LABELS } from "@/config/constants";

const ThinkingIndicator = () => {
  const { activeMode } = useAppContext();
  const label = THINKING_LABELS[activeMode];

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="bg-assistant-bubble rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-3">
        <div className="flex gap-1">
          <span className="w-2 h-2 rounded-full bg-primary dot-bounce-1" />
          <span className="w-2 h-2 rounded-full bg-primary dot-bounce-2" />
          <span className="w-2 h-2 rounded-full bg-primary dot-bounce-3" />
        </div>
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
    </div>
  );
};

export default ThinkingIndicator;
