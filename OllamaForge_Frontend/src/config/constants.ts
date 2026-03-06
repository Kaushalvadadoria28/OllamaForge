export type SourceMode = "Direct Chat" | "RAG" | "Database" | "Wikipedia" | "Website";

export const SOURCE_OPTIONS: { label: string; value: SourceMode; icon: string }[] = [
  { label: "Direct Chat", value: "Direct Chat", icon: "MessageSquare" },
  { label: "Document RAG", value: "RAG", icon: "FileText" },
  { label: "Database", value: "Database", icon: "Database" },
  { label: "Wikipedia", value: "Wikipedia", icon: "BookOpen" },
  { label: "Website", value: "Website", icon: "Globe" },
];

export const MODEL_OPTIONS = [
  "llama3",
  "mistral",
  "gemma",
  "phi3",
  "llama2",
  "codellama",
];

export type PersonaOption = {
  label: string;
  value: string | null;
};

export const PERSONA_OPTIONS: PersonaOption[] = [
  { label: "Default", value: null },
  { label: "Professional Assistant", value: "You are a professional, concise assistant." },
  { label: "Friendly Tutor", value: "You are a friendly, patient teacher who explains things simply." },
  { label: "Code Expert", value: "You are an expert programmer. Respond with clean, commented code." },
  { label: "Custom", value: "__custom__" },
];

export const THINKING_LABELS: Record<SourceMode, string> = {
  "Direct Chat": "Thinking...",
  "RAG": "Searching documents...",
  "Database": "Querying database...",
  "Wikipedia": "Searching Wikipedia...",
  "Website": "Analyzing website...",
};
