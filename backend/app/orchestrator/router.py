"""Intent router: picks the agent for a free-text request.

Uses the LLM gateway when one is connected, and keyword matching otherwise.
Button clicks never come here: they name their agent directly.
"""

import re
from typing import Optional

from app.agents.base import Agent
from app.core.llm import LLMGateway


class IntentRouter:
    def __init__(self, llm: LLMGateway):
        self._llm = llm

    def route(self, text: str, agents: list[Agent]) -> Optional[Agent]:
        by_name = {a.name: a for a in agents}
        choice = self._llm.classify_intent(text, agents)
        if choice in by_name:
            return by_name[choice]

        words = set(re.findall(r"[a-z]+", text.lower()))
        scored = [(len(words.intersection(a.keywords)), a) for a in agents]
        best_score, best = max(scored, key=lambda pair: pair[0], default=(0, None))
        return best if best_score > 0 else None
