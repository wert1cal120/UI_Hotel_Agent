from enum import Enum

from agents.baseline import BaselineAgent
from agents.intelligent import IntelligentAgent


class AgentType(Enum):
    BASELINE = BaselineAgent()
    INTELLIGENT = IntelligentAgent()