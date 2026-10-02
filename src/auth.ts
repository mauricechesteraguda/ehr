// type-10022026-Maurice: Browser-safe auth logger/tracer using injectable structured sink.
import { logger, type LogSink } from "./logger";
export type Role = "clinician" | "patient" | "admin";
export type TraceSink = (event: { event: "entry" | "exit" | "error"; function: string }) => void;
export const traceSink: TraceSink = () => undefined;

export function roleShellTitle(role: Role, trace: TraceSink = traceSink): string {
  trace({ event: "entry", function: "roleShellTitle" });
  try {
    const title = `${role[0].toUpperCase()}${role.slice(1)} workspace`;
    trace({ event: "exit", function: "roleShellTitle" });
    return title;
  } catch (error) {
    trace({ event: "error", function: "roleShellTitle" });
    throw error;
  }
}

export async function logout(fetcher: typeof fetch = fetch, trace: TraceSink = traceSink): Promise<void> {
  trace({ event: "entry", function: "logout" });
  try { await fetcher("/api/auth/logout/", { method: "POST", credentials: "include" }); trace({ event: "exit", function: "logout" }); }
  catch (error) { trace({ event: "error", function: "logout" }); throw error; }
}

function safeCorrelation(value: string | null): string {
  // type-10022026-Maurice: Keep response correlation metadata bounded and header-safe.
  return value && /^[A-Za-z0-9._:-]{1,80}$/.test(value) ? value : `browser-${crypto.randomUUID()}`;
}

export async function authRequest(
  url: string,
  init: RequestInit = {},
  fetcher: typeof fetch = fetch,
  sink: LogSink = () => undefined,
): Promise<Response> {
  // type-10022026-Maurice: Log auth HTTP outcomes only through the injected callback sink.
  const started = performance.now();
  const operationalLogger = logger(sink);
  const requestCorrelation = safeCorrelation(null);
  operationalLogger.info("auth.request.entry", { correlationId: requestCorrelation });
  try {
    const response = await fetcher(url, { ...init, credentials: "include", headers: { ...init.headers, "X-Correlation-ID": requestCorrelation } });
    const correlationId = safeCorrelation(response.headers.get("X-Correlation-ID"));
    const details = { outcome: response.ok ? "success" as const : "failure" as const, httpStatus: response.status, httpClass: `${Math.floor(response.status / 100)}xx`, durationMs: Math.round(performance.now() - started), correlationId };
    if (!response.ok) {
      operationalLogger.error("auth.request.failure", details);
      throw new Error(`Authentication request failed (${details.httpClass})`);
    }
    operationalLogger.info("auth.request.exit", details);
    return response;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("Authentication request failed")) throw error;
    operationalLogger.error("auth.request.failure", { outcome: "failure", durationMs: Math.round(performance.now() - started), correlationId: requestCorrelation });
    throw error;
  }
}
