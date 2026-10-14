import { createRoot } from "react-dom/client";
import BcWorkflows, { type BcWorkflowsProps } from "./BcWorkflows";

/** Framework-agnostic entry: for parents that do not render React components directly.
 * Returns a function that unmounts the MFE. */
export function mount(element: HTMLElement, props: BcWorkflowsProps = {}): () => void {
  const root = createRoot(element);
  root.render(<BcWorkflows {...props} />);
  return () => root.unmount();
}

export default mount;
