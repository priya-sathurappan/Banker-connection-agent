"""Agent registry: every use case registers one agent here."""

from typing import Iterable, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.base import Agent, AgentDeps


class AgentRegistry:
    def __init__(self, agents: Iterable[Agent], deps: AgentDeps, checkpointer: BaseCheckpointSaver):
        self._agents: dict[str, Agent] = {}
        self._graphs: dict[str, CompiledStateGraph] = {}
        for agent in agents:
            self._agents[agent.name] = agent
            self._graphs[agent.name] = agent.build_graph(deps).compile(checkpointer=checkpointer, name=agent.name)

    def get(self, name: str) -> Optional[Agent]:
        return self._agents.get(name)

    def graph(self, name: str) -> CompiledStateGraph:
        return self._graphs[name]

    def all(self) -> list[Agent]:
        return list(self._agents.values())
