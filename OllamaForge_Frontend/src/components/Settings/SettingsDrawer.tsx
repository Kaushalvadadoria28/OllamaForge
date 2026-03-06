import { X } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useSession } from "@/hooks/useSession";
import { PERSONA_OPTIONS } from "@/config/constants";
import { useState } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
}

const SettingsDrawer = ({ open, onClose }: Props) => {
  const {
    systemPrompt, setSystemPrompt,
    temperature, setTemperature,
    sessionId, isConnected,
  } = useAppContext();
  const { resetSession, testConnection } = useSession();
  const [customPrompt, setCustomPrompt] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);

  const currentPersona = PERSONA_OPTIONS.find(p => p.value === systemPrompt)?.label
    || (systemPrompt ? "Custom" : "Default");

  const handlePersonaChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "__custom__") {
      setSystemPrompt(customPrompt || null);
    } else if (val === "") {
      setSystemPrompt(null);
    } else {
      setSystemPrompt(val);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    const ok = await testConnection();
    setTestResult(ok);
    setTesting(false);
    setTimeout(() => setTestResult(null), 3000);
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-background/60 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-80 bg-secondary border-l border-border z-50 flex flex-col animate-fade-in">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h3 className="font-semibold text-foreground">Settings</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-card" aria-label="Close settings">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-6">
          {/* Persona */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">AI Persona</label>
            <select
              value={systemPrompt === null ? "" : (PERSONA_OPTIONS.find(p => p.value === systemPrompt) ? systemPrompt : "__custom__")}
              onChange={handlePersonaChange}
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {PERSONA_OPTIONS.map(p => (
                <option key={p.label} value={p.value ?? ""}>{p.label}</option>
              ))}
            </select>
            {currentPersona === "Custom" && (
              <textarea
                value={customPrompt}
                onChange={e => {
                  setCustomPrompt(e.target.value);
                  setSystemPrompt(e.target.value || null);
                }}
                placeholder="Enter custom system prompt..."
                rows={3}
                className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            )}
          </div>

          {/* Temperature */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Response Creativity
            </label>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>🎯 Precise</span>
              <span className="font-mono text-primary">{temperature.toFixed(1)}</span>
              <span>🎨 Creative</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={e => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          {/* Session Info */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Session</label>
            <div className="bg-card border border-border rounded-lg px-3 py-2 font-mono text-xs text-muted-foreground break-all">
              {sessionId || "No session"}
            </div>
            <button
              onClick={resetSession}
              className="w-full bg-destructive/10 text-destructive rounded-lg px-3 py-2 text-sm font-medium hover:bg-destructive/20 transition-colors"
            >
              Reset Session
            </button>
          </div>

          {/* Connection Status */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Connection</label>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? "bg-success pulse-glow" : "bg-destructive"}`} />
              <span className="text-sm text-foreground">
                {isConnected ? "Backend Connected" : "Backend Offline"}
              </span>
            </div>
            <button
              onClick={handleTest}
              disabled={testing}
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors disabled:opacity-50"
            >
              {testing ? "Testing..." : "Test Connection"}
            </button>
            {testResult !== null && (
              <p className={`text-xs ${testResult ? "text-success" : "text-destructive"}`}>
                {testResult ? "✅ Connection OK" : "❌ Connection failed"}
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default SettingsDrawer;
