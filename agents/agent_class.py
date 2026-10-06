"""The shared decision interface, independent of the hotel environment."""

from abc import ABC, abstractmethod


class Agent(ABC):
    """Receive detached perceptions and return an action, not a mutation.

    Create a new instance for each experiment. Diagnostics are cumulative work
    counters used by the runner; they are not observations of the hidden world.
    """

    def __init__(self):
        self.decision_reason = "No decision yet."
        self.diagnostics = {
            "candidate_checks": 0,
            "checks": 0,
            "fallbacks": 0,
            "observed_requests": 0,
            "decisions": 0,
            "last_decision_checks": 0,
            "max_decision_checks": 0,
            "batches": 0,
            "plans_checked": 0,
        }

    def _record_checks(self, checks):
        self.diagnostics["candidate_checks"] += checks
        self.diagnostics["checks"] += checks
        self.diagnostics["last_decision_checks"] = checks
        self.diagnostics["max_decision_checks"] = max(
            self.diagnostics["max_decision_checks"], checks
        )

    def order_requests(self, batch):
        """Default/baseline: preserve the incoming order of today's requests."""
        self.diagnostics["batches"] += 1
        self.batch_reason = "Incoming order"
        return [percept.client.request_id for percept in batch]

    @abstractmethod
    def decide(self, percept):
        """Choose a booking/relocation or refuse when no room is feasible."""
        raise NotImplementedError
