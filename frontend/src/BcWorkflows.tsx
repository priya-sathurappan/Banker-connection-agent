import { useEffect, useMemo, useState } from "react";
import { createApi } from "./api/client";
import type { SessionView } from "./api/types";
import { newCorrelationId, resolveApiBaseUrl } from "./config";
import { WorkflowSession } from "./WorkflowSession";
import s from "./styles.module.css";

export interface BcWorkflowsEvent {
  type: "workflow_started" | "workflow_finished" | "workflow_cancelled";
  agent: string;
  sessionId: string;
  status?: string;
}

/** Props from the parent container. All optional: the MFE also runs standalone. */
export interface BcWorkflowsProps {
  /** Backend address. Defaults to config.json next to remoteEntry.js, then http://127.0.0.1:8000. */
  apiBaseUrl?: string;
  /** Forwarded to the backend as a bearer token. */
  authToken?: string;
  /** The signed-in banker, recorded for audit. */
  user?: { id?: string; name?: string };
  /** Called when the banker leaves a workflow (cancelled, or a final screen closed). */
  onClose?: () => void;
  /** Lifecycle events, e.g. for the parent's analytics. */
  onEvent?: (event: BcWorkflowsEvent) => void;
}

type View = { kind: "home" } | { kind: "session"; session: SessionView };

export default function BcWorkflows({ apiBaseUrl, authToken, user, onClose, onEvent }: BcWorkflowsProps) {
  const [baseUrl, setBaseUrl] = useState<string | null>(apiBaseUrl ?? null);
  const [view, setView] = useState<View>({ kind: "home" });
  const [starting, setStarting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [correlationId] = useState(newCorrelationId);

  useEffect(() => {
    let active = true;
    resolveApiBaseUrl(apiBaseUrl).then((url) => active && setBaseUrl(url));
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const api = useMemo(
    () => (baseUrl ? createApi({ baseUrl, authToken, bankerId: user?.id, correlationId }) : null),
    [baseUrl, authToken, user?.id, correlationId],
  );

  const startVerifyCheck = async () => {
    if (!api) return;
    setNotice(null);
    setStarting(true);
    try {
      const session = await api.startSession("verify_check");
      onEvent?.({ type: "workflow_started", agent: session.agent, sessionId: session.session_id });
      setView({ kind: "session", session });
    } catch {
      setNotice("Verify check is unavailable right now. Please try again.");
    } finally {
      setStarting(false);
    }
  };

  const update = (session: SessionView) => {
    if (session.status === "cancelled") {
      setView({ kind: "home" });
      return;
    }
    if (session.status === "completed" || session.status === "stopped")
      onEvent?.({
        type: "workflow_finished",
        agent: session.agent,
        sessionId: session.session_id,
        status: session.status,
      });
    setView({ kind: "session", session });
  };

  const exit = (reason: "cancelled" | "closed", session: SessionView) => {
    if (reason === "cancelled")
      onEvent?.({ type: "workflow_cancelled", agent: session.agent, sessionId: session.session_id });
    setView({ kind: "home" });
    onClose?.();
  };

  return (
    <div className={s.root}>
      {view.kind === "session" && api ? (
        <WorkflowSession session={view.session} api={api} onUpdate={update} onExit={exit} />
      ) : (
        <div className={s.homeCard}>
          <h2 className={s.homeTitle}>BC workflows</h2>
          <p className={s.homeText}>Complete Banker Connection requests without calling in.</p>
          <div className={s.homeActions}>
            <button
              type="button"
              className={`${s.button} ${s.secondary}`}
              disabled={!api || starting}
              onClick={startVerifyCheck}
            >
              Verify check
            </button>
            <button
              type="button"
              className={`${s.button} ${s.secondary}`}
              onClick={() => setNotice("Stop payment is coming soon.")}
            >
              Stop payment
            </button>
          </div>
          {notice && (
            <p className={s.notice} role="status">
              {notice}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
