import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import BcWorkflows from "./BcWorkflows";
import type { SessionView } from "./api/types";

const CANCEL = { id: "cancel", label: "Cancel", kind: "cancel", variant: "secondary" } as const;
const CONTINUE = { id: "continue", label: "Continue", kind: "submit", variant: "primary" } as const;

const prevalidation: SessionView = {
  session_id: "s1",
  agent: "verify_check",
  status: "active",
  completed_steps: [],
  screen: {
    step: "prevalidation",
    title: "Verify check",
    heading: "Pre-validation",
    description: "Complete these checks with the individual before starting verification.",
    blocks: [
      {
        type: "checkbox",
        id: "identity_verified",
        section_label: "Identity verification",
        label: "I've verified the individual's identity",
        required: true,
      },
      {
        type: "choice",
        id: "wf_issued",
        label: "Was the check issued by Wells Fargo?",
        options: [
          { value: "yes", label: "Yes" },
          { value: "no", label: "No" },
        ],
        required: true,
      },
    ],
    actions: [CANCEL, CONTINUE],
    values: {},
    errors: {},
  },
};

const stopped: SessionView = {
  session_id: "s1",
  agent: "verify_check",
  status: "stopped",
  completed_steps: [{ title: "Pre-validation", items: [{ label: "Issued by Wells Fargo", value: "No" }] }],
  screen: {
    step: "stopped",
    title: "Verify check",
    blocks: [
      {
        type: "alert",
        variant: "warning",
        title: "Follow the standard procedure",
        message: "Only checks issued by Wells Fargo can be verified in this workflow.",
        link: { label: "Contact the Banker Connection Team", href: "https://bc.test/contact" },
      },
    ],
    actions: [{ id: "close", label: "Close", kind: "close", variant: "primary" }],
    values: {},
    errors: {},
  },
};

const details: SessionView = {
  session_id: "s1",
  agent: "verify_check",
  status: "active",
  completed_steps: [],
  screen: {
    step: "check_details",
    title: "Verify check",
    heading: "Check details",
    blocks: [
      {
        type: "form",
        fields: [
          { id: "serial_number", label: "Serial #", input: "text", required: true },
          { id: "issued_date", label: "Check issued date", input: "date", required: true },
        ],
      },
    ],
    actions: [
      CANCEL,
      {
        id: "continue",
        label: "Verify check",
        kind: "submit",
        variant: "primary",
        progress_label: "Running OBCV verification…",
      },
    ],
    values: {},
    errors: {},
  },
};

function mockBackend(...responses: SessionView[]) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => {
    const body = responses.shift();
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestBody(fetchMock: ReturnType<typeof mockBackend>, call: number) {
  return JSON.parse(fetchMock.mock.calls[call][1]!.body as string);
}

test("home shows both workflows and Stop payment is coming soon", async () => {
  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  expect(screen.getByRole("heading", { name: "BC workflows" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stop payment" }));
  expect(screen.getByText("Stop payment is coming soon.")).toBeInTheDocument();
});

test("Verify check starts a session and shows Pre-validation", async () => {
  const fetchMock = mockBackend(prevalidation);
  render(<BcWorkflows apiBaseUrl="http://api.test" authToken="tok" user={{ id: "banker-7" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));

  expect(await screen.findByRole("heading", { name: "Pre-validation" })).toBeInTheDocument();
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("http://api.test/api/v1/sessions");
  expect(requestBody(fetchMock, 0)).toEqual({ intent: "verify_check" });
  const headers = init!.headers as Record<string, string>;
  expect(headers.Authorization).toBe("Bearer tok");
  expect(headers["X-Banker-Id"]).toBe("banker-7");
  expect(headers["X-Correlation-ID"]).toBeTruthy();
});

test("Continue without answers shows required errors and does not call the backend", async () => {
  const fetchMock = mockBackend(prevalidation);
  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  await userEvent.click(await screen.findByRole("button", { name: "Continue" }));

  expect(screen.getAllByText("This field is required.")).toHaveLength(2);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("answers are submitted and a stop screen links to the Banker Connection team", async () => {
  const onClose = vi.fn();
  const fetchMock = mockBackend(prevalidation, stopped);
  render(<BcWorkflows apiBaseUrl="http://api.test" onClose={onClose} />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  await userEvent.click(await screen.findByLabelText("I've verified the individual's identity"));
  await userEvent.click(screen.getByRole("button", { name: "No" }));
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(await screen.findByText("Follow the standard procedure")).toBeInTheDocument();
  expect(requestBody(fetchMock, 1)).toEqual({
    step: "prevalidation",
    action: "continue",
    values: { identity_verified: true, wf_issued: "no" },
  });
  expect(screen.getByRole("link", { name: /Contact the Banker Connection Team/ })).toHaveAttribute(
    "href",
    "https://bc.test/contact",
  );

  await userEvent.click(screen.getByRole("button", { name: "Completed steps" }));
  expect(screen.getByText("Issued by Wells Fargo")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.getByRole("heading", { name: "BC workflows" })).toBeInTheDocument();
  expect(onClose).toHaveBeenCalledOnce();
});

test("Verify check shows OBCV progress and locks the fields while waiting", async () => {
  let release: (r: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => (release = resolve));
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(details)))
    .mockReturnValueOnce(pending);
  vi.stubGlobal("fetch", fetchMock);

  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  await userEvent.type(await screen.findByLabelText("Serial #"), "12");
  // Date inputs take the ISO value.
  const date = screen.getByLabelText("Check issued date") as HTMLInputElement;
  await userEvent.type(date, "2026-10-02");
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));

  expect(await screen.findByText("Running OBCV verification…")).toBeInTheDocument();
  expect(screen.getByLabelText("Serial #")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();

  release(new Response(JSON.stringify(stopped)));
  await waitFor(() => expect(screen.getByText("Follow the standard procedure")).toBeInTheDocument());
});

test("Cancel ends the session and returns home", async () => {
  const fetchMock = mockBackend(prevalidation, { ...prevalidation, status: "cancelled", screen: null });
  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));

  expect(await screen.findByRole("heading", { name: "BC workflows" })).toBeInTheDocument();
  expect(requestBody(fetchMock, 1).action).toBe("cancel");
});

test("Back sends what was typed, without required-field checks", async () => {
  const withBack: SessionView = {
    ...details,
    screen: {
      ...details.screen!,
      actions: [{ id: "back", label: "Back", kind: "back", variant: "secondary" }, ...details.screen!.actions],
    },
  };
  const fetchMock = mockBackend(withBack, prevalidation);
  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  await userEvent.type(await screen.findByLabelText("Serial #"), "12");
  await userEvent.click(screen.getByRole("button", { name: "Back" }));

  expect(await screen.findByRole("heading", { name: "Pre-validation" })).toBeInTheDocument();
  expect(screen.queryByText("This field is required.")).not.toBeInTheDocument();
  expect(requestBody(fetchMock, 1)).toEqual({
    step: "check_details",
    action: "back",
    values: { serial_number: "12" },
  });
});

test("a backend failure on start shows a message and stays on home", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
  render(<BcWorkflows apiBaseUrl="http://api.test" />);
  await userEvent.click(screen.getByRole("button", { name: "Verify check" }));
  expect(await screen.findByText("Verify check is unavailable right now. Please try again.")).toBeInTheDocument();
});
