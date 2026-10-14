"""What every agent provides to the platform.

An agent is a plug-in: a LangGraph state graph plus the logic that turns the
graph's state into screens. The orchestrator, API and MFE are shared by all agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from langgraph.graph import StateGraph

from app.core.config import Settings
from app.core.schemas import CompletedStep, Screen
from app.core.session_store import SessionStore
from app.tools.obcv import ObcvClient


@dataclass
class AgentDeps:
    settings: Settings
    store: SessionStore
    obcv: ObcvClient


class Agent(ABC):
    name: str
    title: str
    description: str
    # Words that route free text to this agent when no LLM is connected.
    keywords: tuple[str, ...] = ()

    @abstractmethod
    def build_graph(self, deps: AgentDeps) -> StateGraph:
        """Return the uncompiled graph; the platform compiles it with the checkpointer."""

    @abstractmethod
    def initial_state(self) -> dict[str, Any]: ...

    @abstractmethod
    def render(
        self, state: dict[str, Any], pending: Optional[dict[str, Any]], deps: AgentDeps
    ) -> tuple[Optional[Screen], list[CompletedStep]]:
        """Build the screen for the graph's current position.

        `pending` is the payload of the interrupt the graph is paused on, or None
        when the graph has finished.
        """

    @abstractmethod
    def final_status(self, state: dict[str, Any]) -> str:
        """Session status once the graph has finished: "completed" or "stopped"."""
