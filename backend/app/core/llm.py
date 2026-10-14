"""Provider-neutral LLM gateway.

Phase 1 runs without an LLM. When a provider is chosen, add an implementation of
LLMGateway and select it in container.py; nothing else changes.
"""

from typing import Optional, Protocol, Sequence


class AgentChoice(Protocol):
    name: str
    description: str


class LLMGateway(Protocol):
    def classify_intent(self, text: str, agents: Sequence[AgentChoice]) -> Optional[str]:
        """Return the name of the agent that best fits the text, or None."""
        ...


class NoLLM:
    """Used until a provider is connected: never classifies, so routing falls back to keywords."""

    def classify_intent(self, text, agents):
        return None
