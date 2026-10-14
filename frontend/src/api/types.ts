// The contract with the backend. Keep in sync with backend/app/core/schemas.py.

export interface Option {
  value: string;
  label: string;
}

export interface Link {
  label: string;
  href: string;
}

export interface CheckboxBlock {
  type: "checkbox";
  id: string;
  label: string;
  section_label?: string | null;
  required: boolean;
}

export interface ChoiceBlock {
  type: "choice";
  id: string;
  label: string;
  options: Option[];
  required: boolean;
}

export interface FormField {
  id: string;
  label: string;
  input: "text" | "date";
  required: boolean;
}

export interface FormBlock {
  type: "form";
  fields: FormField[];
}

export interface AlertBlock {
  type: "alert";
  variant: "warning" | "success";
  title: string;
  message: string;
  link?: Link | null;
}

export interface SummaryItem {
  label: string;
  value: string;
}

export interface SummaryBlock {
  type: "summary";
  items: SummaryItem[];
}

export type Block = CheckboxBlock | ChoiceBlock | FormBlock | AlertBlock | SummaryBlock;

export interface Action {
  id: string;
  label: string;
  kind: "submit" | "back" | "cancel" | "close";
  variant: "primary" | "secondary";
  progress_label?: string | null;
}

export type Values = Record<string, unknown>;

export interface Screen {
  step: string;
  title: string;
  heading?: string | null;
  description?: string | null;
  blocks: Block[];
  actions: Action[];
  values: Values;
  errors: Record<string, string>;
}

export interface CompletedStep {
  title: string;
  items: SummaryItem[];
}

export type SessionStatus = "active" | "verifying" | "completed" | "stopped" | "cancelled";

export interface SessionView {
  session_id: string;
  agent: string;
  status: SessionStatus;
  screen?: Screen | null;
  completed_steps: CompletedStep[];
}
