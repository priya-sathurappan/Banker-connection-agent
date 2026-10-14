"""Verify check steps: the fields each step accepts and its business rules.

These rules are deterministic on purpose: eligibility for check verification is a
banking control, so it is never decided by an LLM.
"""

from typing import Any, Optional

REQUIRED = "This field is required."

PREVALIDATION = "prevalidation"
ELIGIBILITY = "eligibility"
CHECK_DETAILS = "check_details"
STEP_ORDER = [PREVALIDATION, ELIGIBILITY, CHECK_DETAILS]

# Field kinds: "checked" (a box that must be ticked), "text" (non-empty), or a set
# of allowed choice values.
CHECK_DETAIL_FIELDS = [
    "serial_number",
    "routing_number",
    "account_number",
    "check_number",
    "payee",
    "amount",
    "issued_date",
]

STEP_FIELDS: dict[str, dict[str, Any]] = {
    PREVALIDATION: {"identity_verified": "checked", "wf_issued": {"yes", "no"}},
    ELIGIBILITY: {"presented": {"yes", "no"}, "account_type": {"deposit", "non_deposit"}},
    CHECK_DETAILS: {name: "text" for name in CHECK_DETAIL_FIELDS},
}

# Outcomes that end the workflow.
NOT_WF_ISSUED = "not_wf_issued"
NOT_PRESENTED = "not_presented"
DEPOSIT_ACCOUNT = "deposit_account"
OBCV_REFER = "obcv_refer"
OBCV_UNAVAILABLE = "obcv_unavailable"
OK_TO_NEGOTIATE = "ok"


def clean(step: str, raw: Any) -> tuple[dict[str, Any], dict[str, str]]:
    """Keep only the step's known fields and report the missing required ones.

    Phase 1 checks presence only; per-field format rules come later.
    """
    raw = raw if isinstance(raw, dict) else {}
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name, kind in STEP_FIELDS[step].items():
        value = raw.get(name)
        if kind == "checked":
            ok = value is True
            values[name] = ok
        elif kind == "text":
            value = value.strip() if isinstance(value, str) else ""
            ok = bool(value)
            values[name] = value
        else:
            ok = value in kind
            values[name] = value if ok else None
        if not ok:
            errors[name] = REQUIRED
    return values, errors


def knockout(step: str, values: dict[str, Any]) -> Optional[str]:
    """Return the outcome that stops the workflow at this step, if any."""
    if step == PREVALIDATION and values["wf_issued"] == "no":
        return NOT_WF_ISSUED
    if step == ELIGIBILITY:
        if values["presented"] == "no":
            return NOT_PRESENTED
        if values["account_type"] == "deposit":
            return DEPOSIT_ACCOUNT
    return None
