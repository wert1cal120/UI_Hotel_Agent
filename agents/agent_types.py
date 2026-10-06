"""Names and factories: never reuse one stateful agent between experiments."""

from enum import Enum

from agents.agent_class import Agent

from agents.baseline import BaselineAgent
from agents.intelligent import IntelligentAgent


class AgentType(Enum):
    BASELINE = "baseline"
    INTELLIGENT = "intelligent"

    def create(self, seed: int = 0) -> Agent:
        if self == AgentType.BASELINE:
            return BaselineAgent()
        return IntelligentAgent(seed=seed)


def create_agent(name: str | AgentType, seed: int = 0) -> Agent:
    """Create a fresh agent from a CLI name or an enum member."""
    agent_type = name if isinstance(name, AgentType) else AgentType(name)
    return agent_type.create(seed=seed)
