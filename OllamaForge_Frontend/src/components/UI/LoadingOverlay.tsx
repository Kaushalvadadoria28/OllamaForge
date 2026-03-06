import { Flame } from "lucide-react";

const LoadingOverlay = () => (
  <div className="fixed inset-0 bg-background z-50 flex flex-col items-center justify-center gap-4">
    <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center animate-pulse">
      <Flame className="w-8 h-8 text-primary" />
    </div>
    <p className="text-sm text-muted-foreground">Connecting to backend...</p>
  </div>
);

export default LoadingOverlay;
