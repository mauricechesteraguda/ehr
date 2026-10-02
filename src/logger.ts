// type-10022026-Maurice: Structured frontend operational logger without console or browser persistence.
export type LogSink = (record: { level: "info" | "error"; event: string; outcome?: "success" | "failure"; httpStatus?: number; httpClass?: string; durationMs?: number; correlationId?: string }) => void;
export const logger = (sink: LogSink = () => undefined) => ({
  // type-10022026-Maurice: Route informational records only to the callback sink.
  info: (event: string, details: Omit<Parameters<LogSink>[0], "level" | "event"> = {}) => sink({ level: "info", event, ...details }),
  // type-10022026-Maurice: Route failure records only to the callback sink.
  error: (event: string, details: Omit<Parameters<LogSink>[0], "level" | "event"> = {}) => sink({ level: "error", event, ...details }),
});
