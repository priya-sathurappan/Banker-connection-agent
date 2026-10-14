"""Verify check agent.

Graph:
    ask_prevalidation -> ask_eligibility -> ask_check_details -> verify_obcv -> END
Each ask_* node pauses (interrupt) until the banker submits that step. Missing
required fields loop back to the same node; a knockout answer ends the graph.
Back returns to the previous ask_* node with every answer kept; once the graph
has ended (stop or OBCV result) there is no way back.
"""

import logging
from typing import Any, Callable, Optional, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.base import Agent, AgentDeps
from app.agents.verify_check import screens, steps
from app.core.logging import log
from app.core.schemas import CompletedStep, Screen
from app.tools.obcv import ObcvRequest, ObcvUnavailable

logger = logging.getLogger(__name__)


class VerifyCheckState(TypedDict, total=False):
    answers: dict[str, dict[str, Any]]
    errors: dict[str, str]
    outcome: Optional[str]
    obcv: Optional[dict[str, Any]]
    back: bool


def ask(step: str) -> Callable[[VerifyCheckState], dict[str, Any]]:
    def node(state: VerifyCheckState) -> dict[str, Any]:
        answers = state.get("answers", {})
        resumed = interrupt({"step": step, "values": answers.get(step, {}), "errors": state.get("errors", {})})
        submitted = resumed.get("values") if isinstance(resumed.get("values"), dict) else {}
        if resumed.get("action") == "back":
            # Keep what was typed on this step, unvalidated, so it is still there on return.
            # Fields not sent keep their earlier answer.
            values, _ = steps.clean(step, {**answers.get(step, {}), **submitted})
            return {"answers": {**answers, step: values}, "errors": {}, "outcome": None, "back": True}
        values, errors = steps.clean(step, submitted)
        return {
            "answers": {**answers, step: values},
            "errors": errors,
            "outcome": None if errors else steps.knockout(step, values),
            "back": False,
        }

    node.__name__ = f"ask_{step}"
    return node


def route(step_node: str, prev_node: Optional[str], next_node: str) -> Callable[[VerifyCheckState], str]:
    def decide(state: VerifyCheckState) -> str:
        if state.get("back"):
            # The first step has nowhere to go back to.
            return prev_node or step_node
        if state.get("errors"):
            return step_node
        if state.get("outcome"):
            return END
        return next_node

    return decide


class VerifyCheckAgent(Agent):
    name = "verify_check"
    title = "Verify check"
    description = "Verify a Wells Fargo-issued check presented by an individual, using OBCV."
    keywords = ("verify", "verification", "obcv", "check")

    def initial_state(self) -> dict[str, Any]:
        return {"answers": {}, "errors": {}, "outcome": None, "obcv": None, "back": False}

    def build_graph(self, deps: AgentDeps) -> StateGraph:
        def verify_obcv(state: VerifyCheckState, config: RunnableConfig) -> dict[str, Any]:
            session_id = config["configurable"]["thread_id"]
            details = state["answers"][steps.CHECK_DETAILS]

            # Only one server, in any datacenter, may call OBCV for this session.
            if deps.store.claim(session_id, "active", "verifying"):
                try:
                    result = deps.obcv.verify(ObcvRequest(**details), idempotency_key=session_id).model_dump()
                except ObcvUnavailable:
                    result = {"status": "UNAVAILABLE", "reference": "", "message": ""}
                deps.store.update(session_id, obcv_result=result)
                deps.store.add_event(session_id, {"type": "obcv", "status": result["status"], "reference": result["reference"]})
            else:
                log(logger, "obcv.already_claimed", session_id=session_id)
                result = deps.store.wait_for_obcv_result(session_id, deps.settings.obcv_wait_timeout_seconds)
                if result is None:
                    result = {"status": "UNAVAILABLE", "reference": "", "message": ""}

            outcome = {
                "OK_TO_NEGOTIATE": steps.OK_TO_NEGOTIATE,
                "REFER": steps.OBCV_REFER,
            }.get(result["status"], steps.OBCV_UNAVAILABLE)
            return {"obcv": result, "outcome": outcome}

        graph = StateGraph(VerifyCheckState)
        graph.add_node("ask_prevalidation", ask(steps.PREVALIDATION))
        graph.add_node("ask_eligibility", ask(steps.ELIGIBILITY))
        graph.add_node("ask_check_details", ask(steps.CHECK_DETAILS))
        graph.add_node("verify_obcv", verify_obcv)

        graph.add_edge(START, "ask_prevalidation")
        graph.add_conditional_edges(
            "ask_prevalidation",
            route("ask_prevalidation", None, "ask_eligibility"),
            ["ask_prevalidation", "ask_eligibility", END],
        )
        graph.add_conditional_edges(
            "ask_eligibility",
            route("ask_eligibility", "ask_prevalidation", "ask_check_details"),
            ["ask_prevalidation", "ask_eligibility", "ask_check_details", END],
        )
        graph.add_conditional_edges(
            "ask_check_details",
            route("ask_check_details", "ask_eligibility", "verify_obcv"),
            ["ask_eligibility", "ask_check_details", "verify_obcv", END],
        )
        graph.add_edge("verify_obcv", END)
        return graph

    def render(
        self, state: dict[str, Any], pending: Optional[dict[str, Any]], deps: AgentDeps
    ) -> tuple[Optional[Screen], list[CompletedStep]]:
        answers = state.get("answers", {})
        if pending is not None:
            step = pending["step"]
            return screens.step_screen(step, pending["values"], pending["errors"]), screens.completed_steps(answers, step)

        outcome = state.get("outcome")
        done = screens.completed_steps(answers, None)
        if outcome == steps.OK_TO_NEGOTIATE:
            return screens.result_screen(answers[steps.CHECK_DETAILS], state["obcv"]), done
        return screens.stop_screen(outcome, deps.settings.bc_team_url), done

    def final_status(self, state: dict[str, Any]) -> str:
        return "completed" if state.get("outcome") == steps.OK_TO_NEGOTIATE else "stopped"
