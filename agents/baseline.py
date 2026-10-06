"""The deliberately simple first-fit control agent."""

from agents.actions import BookRoomAction, RejectClientAction, RelocateRoomAction
from agents.agent_class import Agent
from models import DecisionKind

class BaselineAgent(Agent):
    """Take the first feasible room in the sensor's stable room order."""

    def decide(self, percept):
        self.diagnostics["decisions"] += 1
        if percept.kind == DecisionKind.BOOKING:
            self.diagnostics["observed_requests"] += 1
        checks = 0
        for room in percept.rooms:
            checks += 1
            if room.available:
                self._record_checks(checks)
                self.decision_reason = f"First feasible room: {room.room_number}."
                if percept.kind == DecisionKind.RELOCATION:
                    return RelocateRoomAction(room.room_number)
                return BookRoomAction(room.room_number)
        self._record_checks(checks)
        self.decision_reason = "No room can accommodate the complete requested interval."
        return RejectClientAction()
