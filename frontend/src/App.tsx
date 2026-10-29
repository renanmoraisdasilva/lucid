import { useEffect, useState } from "react";

type ApiStatus = "checking" | "ok" | "unreachable";

interface HealthResponse {
  status: string;
}

/**
 * Milestone 1 shell: proves the frontend can reach the backend.
 * The chat experience lands in later milestones.
 */
export default function App() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const response = await fetch("/api/health", { signal: controller.signal });
        if (!response.ok) {
          setStatus("unreachable");
          return;
        }
        const body = (await response.json()) as HealthResponse;
        setStatus(body.status === "ok" ? "ok" : "unreachable");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setStatus("unreachable");
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, []);

  const statusStyles: Record<ApiStatus, string> = {
    checking: "bg-slate-200 text-slate-700",
    ok: "bg-emerald-100 text-emerald-800",
    unreachable: "bg-red-100 text-red-800",
  };

  return (
    <main className="flex min-h-full flex-col items-center justify-center gap-4 bg-slate-50 p-8">
      <h1 className="text-2xl font-semibold text-slate-900">Lucid</h1>
      <p className="max-w-md text-center text-sm text-slate-600">
        Project foundation. Chat, streaming, and persistence arrive in later milestones.
      </p>
      <p
        className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyles[status]}`}
        data-testid="api-status"
      >
        API: {status}
      </p>
    </main>
  );
}
