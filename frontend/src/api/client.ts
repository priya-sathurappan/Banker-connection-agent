import type { SessionView, Values } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface ApiOptions {
  baseUrl: string;
  authToken?: string;
  bankerId?: string;
  correlationId: string;
}

export interface WorkflowApi {
  startSession(intent: string): Promise<SessionView>;
  submit(
    sessionId: string,
    step: string,
    action: "continue" | "back" | "cancel",
    values: Values,
  ): Promise<SessionView>;
}

export function createApi(options: ApiOptions): WorkflowApi {
  const base = options.baseUrl.replace(/\/$/, "");

  async function request(path: string, body: unknown): Promise<SessionView> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Correlation-ID": options.correlationId,
    };
    if (options.authToken) headers.Authorization = `Bearer ${options.authToken}`;
    if (options.bankerId) headers["X-Banker-Id"] = options.bankerId;

    const response = await fetch(`${base}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new ApiError(response.status, detail?.detail ?? `Request failed (${response.status})`);
    }
    return response.json();
  }

  return {
    startSession: (intent) => request("/api/v1/sessions", { intent }),
    submit: (sessionId, step, action, values) =>
      request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/submit`, { step, action, values }),
  };
}
