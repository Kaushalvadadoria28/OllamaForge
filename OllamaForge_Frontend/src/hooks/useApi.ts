import { useCallback } from "react";
import { useAppContext } from "@/context/AppContext";
import { toast } from "sonner";

export const useApi = () => {
  const { setIsConnected } = useAppContext();

  const apiFetch = useCallback(async (url: string, options?: RequestInit) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5m timeout for LLM responses
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      setIsConnected(true);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMsg =
          res.status === 400
            ? errorData.error || "Bad request"
            : res.status >= 500
              ? "⚠️ Server error. Check the backend console."
              : `Error ${res.status}`;
        toast.error(errorMsg);
        throw new Error(errorMsg);
      }

      clearTimeout(timeoutId);
      return res;
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError" || err.message?.includes("fetch") || err.name === "TypeError") {
        setIsConnected(false);
        toast.error("❌ Network error — is the backend running?");
      }
      throw err;
    }
  }, [setIsConnected]);

  return { apiFetch };
};
