"""Screens for the Verify check workflow, as UI blocks. All user-facing wording lives here."""

from typing import Any, Optional

from app.agents.verify_check import steps
from app.core.logging import mask
from app.core.schemas import (
    Action,
    AlertBlock,
    CheckboxBlock,
    ChoiceBlock,
    CompletedStep,
    FormBlock,
    FormField,
    Link,
    Option,
    Screen,
    SummaryBlock,
    SummaryItem,
)

TITLE = "Verify check"
YES_NO = [Option(value="yes", label="Yes"), Option(value="no", label="No")]
ACCOUNT_TYPES = [Option(value="deposit", label="Deposit"), Option(value="non_deposit", label="Non-deposit")]

BACK = Action(id="back", label="Back", kind="back")
CANCEL = Action(id="cancel", label="Cancel", kind="cancel")
CONTINUE = Action(id="continue", label="Continue", kind="submit", variant="primary")
VERIFY = Action(
    id="continue",
    label="Verify check",
    kind="submit",
    variant="primary",
    progress_label="Running OBCV verification…",
)

FIELD_LABELS = {
    "serial_number": "Serial #",
    "routing_number": "Routing #",
    "account_number": "Account #",
    "check_number": "Check #",
    "payee": "Payee",
    "amount": "Amount ($)",
    "issued_date": "Check issued date",
}

STOP_MESSAGES = {
    steps.NOT_WF_ISSUED: "Only checks issued by Wells Fargo can be verified in this workflow.",
    steps.NOT_PRESENTED: "Only checks issued by Wells Fargo can be verified in this workflow.",
    steps.DEPOSIT_ACCOUNT: "Checks associated with a deposit account can't be verified in this workflow.",
    steps.OBCV_REFER: "OBCV couldn't confirm this check, so it can't be negotiated through this workflow.",
    steps.OBCV_UNAVAILABLE: "OBCV verification is unavailable right now, so this check can't be verified in this workflow.",
}


def step_screen(step: str, values: dict[str, Any], errors: dict[str, str]) -> Screen:
    if step == steps.PREVALIDATION:
        return Screen(
            step=step,
            title=TITLE,
            heading="Pre-validation",
            description="Complete these checks with the individual before starting verification.",
            blocks=[
                CheckboxBlock(
                    id="identity_verified",
                    section_label="Identity verification",
                    label="I've verified the individual's identity",
                ),
                ChoiceBlock(id="wf_issued", label="Was the check issued by Wells Fargo?", options=YES_NO),
            ],
            actions=[CANCEL, CONTINUE],
            values=values,
            errors=errors,
        )
    if step == steps.ELIGIBILITY:
        return Screen(
            step=step,
            title=TITLE,
            heading="Eligibility",
            description="Confirm the check qualifies for verification in this workflow.",
            blocks=[
                ChoiceBlock(id="presented", label="Has the individual presented the instrument (check)?", options=YES_NO),
                ChoiceBlock(id="account_type", label="Is this a deposit or non-deposit account?", options=ACCOUNT_TYPES),
            ],
            actions=[BACK, CANCEL, CONTINUE],
            values=values,
            errors=errors,
        )
    if step == steps.CHECK_DETAILS:
        return Screen(
            step=step,
            title=TITLE,
            heading="Check details",
            description="Enter the details from the presented check, then continue to run OBCV verification.",
            blocks=[
                FormBlock(
                    fields=[
                        FormField(id=name, label=FIELD_LABELS[name], input="date" if name == "issued_date" else "text")
                        for name in steps.CHECK_DETAIL_FIELDS
                    ]
                )
            ],
            actions=[BACK, CANCEL, VERIFY],
            values=values,
            errors=errors,
        )
    raise ValueError(f"Unknown step {step}")


def stop_screen(outcome: str, bc_team_url: str) -> Screen:
    return Screen(
        step="stopped",
        title=TITLE,
        blocks=[
            AlertBlock(
                variant="warning",
                title="Follow the standard procedure",
                message=STOP_MESSAGES[outcome],
                link=Link(label="Contact the Banker Connection Team", href=bc_team_url),
            )
        ],
        actions=[Action(id="close", label="Close", kind="close", variant="primary")],
    )


def result_screen(details: dict[str, Any], obcv: dict[str, Any]) -> Screen:
    return Screen(
        step="complete",
        title=TITLE,
        heading="Verification complete",
        description="This verification has been marked complete and the session is closed.",
        blocks=[
            AlertBlock(variant="success", title="Ok to Negotiate", message=obcv["message"]),
            SummaryBlock(
                items=[
                    SummaryItem(label="Reference", value=obcv["reference"]),
                    SummaryItem(label="Check #", value=details["check_number"]),
                    SummaryItem(label="Payee", value=details["payee"]),
                    SummaryItem(label="Amount", value=format_amount(details["amount"])),
                    SummaryItem(label="Serial #", value=details["serial_number"]),
                    SummaryItem(label="Issued", value=format_date(details["issued_date"])),
                ]
            ),
        ],
        actions=[Action(id="done", label="Done", kind="close", variant="primary")],
    )


def completed_steps(answers: dict[str, dict[str, Any]], current_step: Optional[str]) -> list[CompletedStep]:
    """Summaries of the steps finished before `current_step` (all answered steps when None)."""
    done = steps.STEP_ORDER if current_step is None else steps.STEP_ORDER[: steps.STEP_ORDER.index(current_step)]
    result = []
    for step in done:
        values = answers.get(step)
        if not values:
            continue
        if step == steps.PREVALIDATION:
            result.append(
                CompletedStep(
                    title="Pre-validation",
                    items=[
                        SummaryItem(label="Identity verified", value=_yes_no(values["identity_verified"])),
                        SummaryItem(label="Issued by Wells Fargo", value=_label(YES_NO, values["wf_issued"])),
                    ],
                )
            )
        elif step == steps.ELIGIBILITY:
            result.append(
                CompletedStep(
                    title="Eligibility",
                    items=[
                        SummaryItem(label="Instrument presented", value=_label(YES_NO, values["presented"])),
                        SummaryItem(label="Account type", value=_label(ACCOUNT_TYPES, values["account_type"])),
                    ],
                )
            )
        elif step == steps.CHECK_DETAILS:
            result.append(
                CompletedStep(
                    title="Check details",
                    items=[
                        SummaryItem(label="Serial #", value=values["serial_number"]),
                        SummaryItem(label="Routing #", value=mask(values["routing_number"])),
                        SummaryItem(label="Account #", value=mask(values["account_number"])),
                        SummaryItem(label="Check #", value=values["check_number"]),
                        SummaryItem(label="Payee", value=values["payee"]),
                        SummaryItem(label="Amount", value=format_amount(values["amount"])),
                        SummaryItem(label="Issued", value=format_date(values["issued_date"])),
                    ],
                )
            )
    return result


def format_amount(raw: str) -> str:
    try:
        return f"${float(raw.replace(',', '').lstrip('$')):,.2f}"
    except ValueError:
        return raw


def format_date(raw: str) -> str:
    """YYYY-MM-DD -> MM/DD/YYYY; anything else is shown as entered."""
    parts = raw.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        return f"{parts[1]}/{parts[2]}/{parts[0]}"
    return raw


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _label(options: list[Option], value: Any) -> str:
    return next((o.label for o in options if o.value == value), "")
