import { ServerCrash, ShieldAlert, WifiOff } from "lucide-react";
import { ApiError } from "@/lib/api";

/** Server-rendered explanation for *expected* API failures, so the user knows what to fix. */
export function ApiProblem({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : new ApiError("server", null, "Unexpected error");
  const Icon = e.kind === "network" ? WifiOff : e.kind === "auth" ? ShieldAlert : ServerCrash;
  const hint =
    e.kind === "network" ? "Start the backend:  cd backend && uvicorn app.main:app --reload"
    : e.kind === "auth" ? "Set the same API_TOKEN in backend/.env and frontend/.env.local, then restart both."
    : "Check the backend logs.";
  return (
    <div role="alert" className="mx-auto max-w-lg rounded-lg border border-warn/30 bg-warn/5 p-6">
      <Icon className="mb-3 size-6 text-warn" />
      <h2 className="font-semibold">Can&apos;t load data from the API</h2>
      <p className="mt-1 text-sm text-muted-foreground">{e.message}</p>
      <pre className="mt-3 overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs text-muted-foreground">{hint}</pre>
    </div>
  );
}
