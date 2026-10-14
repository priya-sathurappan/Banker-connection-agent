"""The contract between the backend and the MFE.

The backend describes each screen as typed UI blocks; the MFE only renders them.
Keep this file in sync with frontend/src/api/types.ts.
"""

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class Option(BaseModel):
    value: str
    label: str


class Link(BaseModel):
    label: str
    href: str


class CheckboxBlock(BaseModel):
    type: Literal["checkbox"] = "checkbox"
    id: str
    label: str
    section_label: Optional[str] = None
    required: bool = True


class ChoiceBlock(BaseModel):
    type: Literal["choice"] = "choice"
    id: str
    label: str
    options: list[Option]
    required: bool = True


class FormField(BaseModel):
    id: str
    label: str
    input: Literal["text", "date"] = "text"
    required: bool = True


class FormBlock(BaseModel):
    type: Literal["form"] = "form"
    fields: list[FormField]


class AlertBlock(BaseModel):
    type: Literal["alert"] = "alert"
    variant: Literal["warning", "success"]
    title: str
    message: str
    link: Optional[Link] = None


class SummaryItem(BaseModel):
    label: str
    value: str


class SummaryBlock(BaseModel):
    type: Literal["summary"] = "summary"
    items: list[SummaryItem]


Block = Annotated[
    Union[CheckboxBlock, ChoiceBlock, FormBlock, AlertBlock, SummaryBlock],
    Field(discriminator="type"),
]


class Action(BaseModel):
    id: str
    label: str
    # submit: send values to the backend; back: return to the previous step (no validation);
    # cancel: end the session; close: return to home.
    kind: Literal["submit", "back", "cancel", "close"]
    variant: Literal["primary", "secondary"] = "secondary"
    # Shown while a submit is in flight (e.g. "Running OBCV verification…").
    progress_label: Optional[str] = None


class Screen(BaseModel):
    step: str
    title: str
    heading: Optional[str] = None
    description: Optional[str] = None
    blocks: list[Block]
    actions: list[Action]
    values: dict[str, Any] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)


class CompletedStep(BaseModel):
    title: str
    items: list[SummaryItem]


SessionStatus = Literal["active", "verifying", "completed", "stopped", "cancelled"]


class SessionView(BaseModel):
    session_id: str
    agent: str
    status: SessionStatus
    screen: Optional[Screen] = None
    completed_steps: list[CompletedStep] = Field(default_factory=list)


class StartSessionRequest(BaseModel):
    intent: Optional[str] = Field(default=None, description="Explicit agent name, e.g. verify_check")
    text: Optional[str] = Field(default=None, description="Free text, routed by intent")


class SubmitRequest(BaseModel):
    step: str = Field(description="The step the values belong to; stale steps are ignored")
    action: Literal["continue", "back", "cancel"] = "continue"
    values: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    name: str
    title: str
    description: str
