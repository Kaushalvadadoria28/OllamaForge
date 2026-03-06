import { Flame, Settings } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useSession } from "@/hooks/useSession";
import { MODEL_OPTIONS } from "@/config/constants";
import { useState } from "react";
import SettingsDrawer from "@/components/Settings/SettingsDrawer";

const Navbar = () => {
  const { selectedModel, setSelectedModel, isConnected } = useAppContext();
  const { setModel } = useSession();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const model = e.target.value;
    setSelectedModel(model);
    setModel(model);
  };

  return (
    <>
      <nav className="flex items-center justify-between px-5 py-3 border-b border-border bg-secondary">
        <div className="flex items-center gap-2">
          <Flame className="w-7 h-7 text-primary" />
          <span className="text-xl font-bold gradient-text">OllamaForge</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedModel}
              onChange={handleModelChange}
              className="appearance-none bg-card border border-border rounded-lg px-4 py-2 pr-8 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
              aria-label="Select AI model"
            >
              <option value="">Select Model...</option>
              {MODEL_OPTIONS.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
              <svg className="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {!isConnected && (
            <div className="flex items-center gap-1.5 text-xs text-destructive">
              <span className="w-2 h-2 rounded-full bg-destructive" />
              Offline
            </div>
          )}
        </div>

        <button
          onClick={() => setSettingsOpen(true)}
          className="p-2 rounded-lg hover:bg-card transition-colors"
          aria-label="Open settings"
        >
          <Settings className="w-5 h-5 text-muted-foreground" />
        </button>
      </nav>
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
};

export default Navbar;
