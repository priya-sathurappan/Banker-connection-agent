"""Session service: starts agents, resumes them with the banker's answers and
turns the graph's position into a SessionView.

Stateless by design: everything it needs is loaded from the session store and the
checkpointer on each call, so any server in any datacenter can handle any request.
"""

import logging
import uuid
from typing import Any, Optional

from langgraph.types import Command

from app.agents.base import Agent, AgentDeps
from app.core.logging import log
from app.core.schemas import SessionView
from app.core.session_store import SessionStore
from app.orchestrator.registry import AgentRegistry
from app.orchestrator.router import IntentRouter

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "stopped", "cancelled"}


class UnknownIntent(Exception):
    pass


class SessionService:
    def __init__(self, registry: AgentRegistry, router: IntentRouter, store: SessionStore, deps: AgentDeps):
        self._registry = registry
        self._router = router
        self._store = store
        self._deps = deps

    def resolve_agent(self, intent: Optional[str], text: Optional[str]) -> Agent:
        if intent:
            agent = self._registry.get(intent)
        elif text:
            agent = self._router.route(text, self._registry.all())
        else:
            agent = None
        if agent is None:
            raise UnknownIntent(intent or text or "")
        return agent

    def start(self, intent: Optional[str], text: Optional[str], started_by: Optional[str]) -> SessionView:
        agent = self.resolve_agent(intent, text)
        session_id = uuid.uuid4().hex
        self._store.create(session_id, agent.name, started_by)
        self._store.add_event(session_id, {"type": "started", "agent": agent.name})
        log(logger, "session.started", session_id=session_id, agent=agent.name)
        self._registry.graph(agent.name).invoke(agent.initial_state(), self._config(session_id))
        return self._after_run(session_id, agent)

    def get(self, session_id: str) -> SessionView:
        session = self._store.get(session_id)
        return self._view(session_id, session["agent"], session["status"])

    def submit(self, session_id: str, step: str, action: str, values: dict[str, Any]) -> SessionView:
        session = self._store.get(session_id)
        agent = self._registry.get(session["agent"])
        if session["status"] in TERMINAL:
            return self._view(session_id, agent.name, session["status"])

        pending = self._pending(session_id, agent.name)
        # A retried or duplicate request for a step that is already done changes nothing.
        if pending is None or pending["step"] != step:
            log(logger, "session.stale_submit", session_id=session_id, step=step)
            return self._view(session_id, agent.name, session["status"])

        if action == "cancel":
            self._store.update(session_id, status="cancelled")
            self._store.add_event(session_id, {"type": "cancelled", "step": step})
            log(logger, "session.cancelled", session_id=session_id, step=step)
            return self._view(session_id, agent.name, "cancelled")

        # Wrapped so an empty submit still resumes the graph (an empty resume value is ignored).
        resume = {"values": values, "action": action}
        self._registry.graph(agent.name).invoke(Command(resume=resume), self._config(session_id))
        self._store.add_event(session_id, {"type": "went_back" if action == "back" else "submitted", "step": step})
        return self._after_run(session_id, agent)

    # --- internals -------------------------------------------------------

    def _config(self, session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _pending(self, session_id: str, agent_name: str) -> Optional[dict[str, Any]]:
        snapshot = self._registry.graph(agent_name).get_state(self._config(session_id))
        return snapshot.interrupts[0].value if snapshot.interrupts else None

    def _after_run(self, session_id: str, agent: Agent) -> SessionView:
        snapshot = self._registry.graph(agent.name).get_state(self._config(session_id))
        if snapshot.interrupts:
            status = "active"
            self._store.update(session_id, step=snapshot.interrupts[0].value["step"])
        else:
            status = agent.final_status(snapshot.values)
            outcome = snapshot.values.get("outcome")
            self._store.update(session_id, status=status, step=None, outcome=outcome)
            self._store.add_event(session_id, {"type": "finished", "status": status, "outcome": outcome})
            log(logger, "session.finished", session_id=session_id, status=status, outcome=outcome)
        return self._view(session_id, agent.name, status)

    def _view(self, session_id: str, agent_name: str, status: str) -> SessionView:
        if status == "cancelled":
            return SessionView(session_id=session_id, agent=agent_name, status=status)
        agent = self._registry.get(agent_name)
        snapshot = self._registry.graph(agent_name).get_state(self._config(session_id))
        pending = snapshot.interrupts[0].value if snapshot.interrupts else None
        screen, completed = agent.render(snapshot.values, pending, self._deps)
        return SessionView(
            session_id=session_id, agent=agent_name, status=status, screen=screen, completed_steps=completed
        )
