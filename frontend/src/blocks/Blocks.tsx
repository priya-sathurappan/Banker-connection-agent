import type { AlertBlock, Block, CheckboxBlock, ChoiceBlock, FormBlock, SummaryBlock, Values } from "../api/types";
import s from "../styles.module.css";

interface InputProps {
  values: Values;
  errors: Record<string, string>;
  disabled: boolean;
  onChange: (id: string, value: unknown) => void;
}

/** Renders one UI block sent by the backend. Unknown block types are skipped, so an older
 * MFE keeps working when the backend adds a new type. */
export function BlockView({ block, ...props }: InputProps & { block: Block }) {
  switch (block.type) {
    case "checkbox":
      return <CheckboxView block={block} {...props} />;
    case "choice":
      return <ChoiceView block={block} {...props} />;
    case "form":
      return <FormView block={block} {...props} />;
    case "alert":
      return <AlertView block={block} />;
    case "summary":
      return <SummaryView block={block} />;
    default:
      return null;
  }
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p className={s.error} id={`${id}-error`} role="alert">
      <span className={s.errorIcon} aria-hidden="true">
        !
      </span>
      {message}
    </p>
  );
}

function CheckboxView({ block, values, errors, disabled, onChange }: InputProps & { block: CheckboxBlock }) {
  const error = errors[block.id];
  return (
    <div className={s.block}>
      {block.section_label && <span className={s.sectionLabel}>{block.section_label}</span>}
      <label className={s.checkboxRow}>
        <input
          type="checkbox"
          checked={values[block.id] === true}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={error ? `${block.id}-error` : undefined}
          onChange={(e) => onChange(block.id, e.target.checked)}
        />
        {block.label}
      </label>
      <FieldError id={block.id} message={error} />
    </div>
  );
}

function ChoiceView({ block, values, errors, disabled, onChange }: InputProps & { block: ChoiceBlock }) {
  const error = errors[block.id];
  const labelId = `${block.id}-label`;
  return (
    <div className={s.block}>
      <span className={s.questionLabel} id={labelId}>
        {block.label}
      </span>
      <div
        className={s.choiceRow}
        role="group"
        aria-labelledby={labelId}
        aria-describedby={error ? `${block.id}-error` : undefined}
      >
        {block.options.map((option) => {
          const selected = values[block.id] === option.value;
          return (
            <button
              key={option.value}
              type="button"
              className={`${s.choice} ${selected ? s.choiceSelected : ""}`}
              aria-pressed={selected}
              disabled={disabled}
              onClick={() => onChange(block.id, option.value)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <FieldError id={block.id} message={error} />
    </div>
  );
}

function FormView({ block, values, errors, disabled, onChange }: InputProps & { block: FormBlock }) {
  return (
    <div className={`${s.block} ${s.fieldGrid}`}>
      {block.fields.map((field) => {
        const error = errors[field.id];
        const inputId = `bcw-field-${field.id}`;
        return (
          <div key={field.id} className={`${s.field} ${error ? s.fieldInvalid : ""}`}>
            <label htmlFor={inputId}>{field.label}</label>
            <input
              id={inputId}
              type={field.input === "date" ? "date" : "text"}
              value={typeof values[field.id] === "string" ? (values[field.id] as string) : ""}
              disabled={disabled}
              aria-invalid={!!error}
              aria-describedby={error ? `${field.id}-error` : undefined}
              onChange={(e) => onChange(field.id, e.target.value)}
            />
            <FieldError id={field.id} message={error} />
          </div>
        );
      })}
    </div>
  );
}

function AlertView({ block }: { block: AlertBlock }) {
  const warning = block.variant === "warning";
  return (
    <div className={`${s.block} ${s.alert} ${warning ? s.alertWarning : s.alertSuccess}`} role="status">
      <span className={s.alertIcon} aria-hidden="true">
        <span>{warning ? "!" : "✓"}</span>
      </span>
      <div>
        <p className={s.alertTitle}>{block.title}</p>
        <p className={s.alertMessage}>{block.message}</p>
        {block.link && (
          <a className={s.alertLink} href={block.link.href} target="_blank" rel="noreferrer">
            {block.link.label} ›
          </a>
        )}
      </div>
    </div>
  );
}

function SummaryView({ block }: { block: SummaryBlock }) {
  return (
    <dl className={`${s.block} ${s.summary}`}>
      {block.items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Client-side mirror of the backend's required-field check, for instant feedback.
 * The backend remains the authority. */
export function requiredErrors(blocks: Block[], values: Values): Record<string, string> {
  const errors: Record<string, string> = {};
  const required = "This field is required.";
  for (const block of blocks) {
    if (block.type === "checkbox" && block.required && values[block.id] !== true) errors[block.id] = required;
    if (block.type === "choice" && block.required && !block.options.some((o) => o.value === values[block.id]))
      errors[block.id] = required;
    if (block.type === "form")
      for (const field of block.fields) {
        const value = values[field.id];
        if (field.required && !(typeof value === "string" && value.trim())) errors[field.id] = required;
      }
  }
  return errors;
}
