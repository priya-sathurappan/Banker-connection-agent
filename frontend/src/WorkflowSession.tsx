import { useEffect, useState } from "react";
import type { Action, SessionView, Values } from "./api/types";
import type { WorkflowApi } from "./api/client";
import { BlockView, requiredErrors } from "./blocks/Blocks";
import s from "./styles.module.css";

interface Props {
  session: SessionView;
  api: WorkflowApi;
  onUpdate: (session: SessionView) => void;
  /** The workflow is over for the banker: cancelled, or a final screen was closed. */
  onExit: (reason: "cancelled" | "closed", session: SessionView) => void;
}

export function WorkflowSession({ session, api, onUpdate, onExit }: Props) {
  const screen = session.screen;
  const [values, setValues] = useState<Values>(screen?.values ?? {});
  const [errors, setErrors] = useState<Record<string, string>>(screen?.errors ?? {});
  const [busy, setBusy] = useState<Action | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(false);

  // A new screen from the backend replaces the local answers and errors.
  useEffect(() => {
    setValues(screen?.values ?? {});
    setErrors(screen?.errors ?? {});
    setBusy(null);
    setShowCompleted(false);
  }, [session.session_id, screen?.step, screen]);

  if (!screen) return null;

  const change = (id: string, value: unknown) => {
    setValues((current) => ({ ...current, [id]: value }));
    setErrors(({ [id]: _cleared, ...rest }) => rest);
  };

  const run = async (action: Action) => {
    setFailure(null);
    if (action.kind === "close") {
      onExit("closed", session);
      return;
    }
    if (action.kind === "cancel") {
      setBusy(action);
      try {
        await api.submit(session.session_id, screen.step, "cancel", {});
      } catch {
        // Leaving is always allowed; an abandoned session simply expires.
      }
      onExit("cancelled", session);
      return;
    }
    // Back sends what was typed so far without checking it; Continue requires every field.
    const back = action.kind === "back";
    if (!back) {
      const missing = requiredErrors(screen.blocks, values);
      if (Object.keys(missing).length) {
        setErrors(missing);
        return;
      }
    }
    setBusy(action);
    try {
      onUpdate(await api.submit(session.session_id, screen.step, back ? "back" : "continue", values));
    } catch {
      setBusy(null);
      setFailure("Something went wrong. Please try again.");
    }
  };

  const disabled = busy !== null;

  return (
    <section aria-labelledby="bcw-page-title">
      <h1 className={s.pageTitle} id="bcw-page-title">
        {screen.title}
      </h1>

      {session.completed_steps.length > 0 && (
        <div className={s.completedBar}>
          <button
            type="button"
            className={s.linkButton}
            aria-expanded={showCompleted}
            onClick={() => setShowCompleted((open) => !open)}
          >
            Completed steps
          </button>
          {showCompleted && (
            <div className={s.completedList}>
              {session.completed_steps.map((step) => (
                <div key={step.title} className={s.completedStep}>
                  <h3>{step.title}</h3>
                  <dl className={s.summary}>
                    {step.items.map((item) => (
                      <div key={item.label}>
                        <dt>{item.label}</dt>
                        <dd>{item.value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className={s.panel}>
        {failure && (
          <div className={s.banner} role="alert">
            {failure}
          </div>
        )}
        {screen.heading && <h2 className={s.heading}>{screen.heading}</h2>}
        {screen.description && <p className={s.description}>{screen.description}</p>}

        {screen.blocks.map((block, index) => (
          <BlockView
            key={`${screen.step}-${index}`}
            block={block}
            values={values}
            errors={errors}
            disabled={disabled}
            onChange={change}
          />
        ))}

        {busy?.progress_label && (
          <div className={s.progress} role="status">
            <span className={s.dots} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            {busy.progress_label}
          </div>
        )}

        {!busy?.progress_label && (
          <div className={s.actions}>
            {screen.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                className={`${s.button} ${action.variant === "primary" ? s.primary : s.secondary} ${
                  action.kind === "back" ? s.backButton : ""
                }`}
                disabled={disabled}
                onClick={() => run(action)}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
