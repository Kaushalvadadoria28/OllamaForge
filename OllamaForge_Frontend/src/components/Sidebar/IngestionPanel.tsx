import { useState, useRef } from "react";
import { Upload, Link, Database as DbIcon, MessageSquare, BookOpen } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useApi } from "@/hooks/useApi";
import { API_ENDPOINTS } from "@/config/api";

const IngestionPanel = () => {
  const { activeMode, sessionId, ingestionStatus, setIngestionStatus } = useAppContext();
  const { apiFetch } = useApi();
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [dbPath, setDbPath] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const status = ingestionStatus[activeMode];

  const handleFileUpload = async (file: File) => {
    if (!sessionId) return;
    setUploading(true);
    const ext = file.name.split(".").pop()?.toLowerCase();
    const endpoint = ext === "pdf" ? API_ENDPOINTS.UPLOAD_PDF : API_ENDPOINTS.UPLOAD_DOCX;

    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("file", file);

    try {
      await apiFetch(endpoint, { method: "POST", body: formData });
      setIngestionStatus("RAG", { ready: true, label: `✅ ${file.name} — Ready` });
    } catch {
      setIngestionStatus("RAG", { ready: false, label: `❌ Failed to process ${file.name}` });
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleUrlSubmit = async () => {
    if (!sessionId || !urlInput.trim()) return;
    setUploading(true);
    try {
      await apiFetch(API_ENDPOINTS.UPLOAD_WEBSITE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, url: urlInput.trim() }),
      });
      setIngestionStatus("Website", { ready: true, label: "✅ URL loaded" });
    } catch {
      setIngestionStatus("Website", { ready: false, label: "❌ Failed to load URL" });
    } finally {
      setUploading(false);
    }
  };

  const handleDbConnect = async () => {
    if (!sessionId || !dbPath.trim()) return;
    setUploading(true);
    try {
      const res = await apiFetch(API_ENDPOINTS.INIT_DATABASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, db_path: dbPath.trim() }),
      });
      const data = await res.json();
      setIngestionStatus("Database", { ready: true, label: `✅ Connected: ${data.db_uri || "OK"}` });
    } catch {
      setIngestionStatus("Database", { ready: false, label: "❌ Connection failed" });
    } finally {
      setUploading(false);
    }
  };

  if (activeMode === "Direct Chat") {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg bg-card text-sm text-muted-foreground">
        <MessageSquare className="w-4 h-4 mt-0.5 shrink-0 text-primary" />
        <span>💬 Ready to chat directly with the LLM.</span>
      </div>
    );
  }

  if (activeMode === "Wikipedia") {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg bg-card text-sm text-muted-foreground">
        <BookOpen className="w-4 h-4 mt-0.5 shrink-0 text-primary" />
        <span>📖 The AI will search Wikipedia to answer your questions.</span>
      </div>
    );
  }

  if (activeMode === "RAG") {
    return (
      <div className="space-y-3">
        <div
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-border rounded-lg p-6 flex flex-col items-center gap-2 cursor-pointer hover:border-primary/50 transition-colors"
        >
          <Upload className="w-6 h-6 text-muted-foreground" />
          <p className="text-xs text-muted-foreground text-center">Upload PDF or DOCX</p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
          />
        </div>
        {uploading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground animate-pulse">
            <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            Processing document...
          </div>
        )}
        {status && <p className={`text-xs ${status.ready ? "text-success" : "text-destructive"}`}>{status.label}</p>}
      </div>
    );
  }

  if (activeMode === "Website") {
    return (
      <div className="space-y-3">
        <input
          type="url"
          value={urlInput}
          onChange={e => setUrlInput(e.target.value)}
          placeholder="https://example.com"
          className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={handleUrlSubmit}
          disabled={uploading || !urlInput.trim()}
          className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-lg px-3 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          <Link className="w-4 h-4" />
          Set URL
        </button>
        {uploading && <p className="text-xs text-muted-foreground animate-pulse">Loading website...</p>}
        {status && <p className={`text-xs ${status.ready ? "text-success" : "text-destructive"}`}>{status.label}</p>}
      </div>
    );
  }

  if (activeMode === "Database") {
    return (
      <div className="space-y-3">
        <input
          type="text"
          value={dbPath}
          onChange={e => setDbPath(e.target.value)}
          placeholder="Path to .db or .sql file"
          className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={handleDbConnect}
          disabled={uploading || !dbPath.trim()}
          className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-lg px-3 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          <DbIcon className="w-4 h-4" />
          Connect Database
        </button>
        {uploading && <p className="text-xs text-muted-foreground animate-pulse">Connecting...</p>}
        {status && <p className={`text-xs ${status.ready ? "text-success" : "text-destructive"}`}>{status.label}</p>}
      </div>
    );
  }

  return null;
};

export default IngestionPanel;
