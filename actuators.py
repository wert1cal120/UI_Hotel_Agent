"""Validate action values and delegate world mutations to the environment."""
from agents.actions import (ActionResult, ActionStatus, BookRoomAction,
                            RejectClientAction, RelocateRoomAction)
from models import Client, DecisionKind


class HotelActuator:
    def __init__(self, environment):
        self._environment = environment

    def execute(self, client: Client, action, kind: DecisionKind = DecisionKind.BOOKING) -> ActionResult:
        request_id = getattr(client, "request_id", None)
        if not isinstance(client, Client) or not isinstance(kind, DecisionKind):
            return ActionResult(ActionStatus.FAILED, "Invalid request or decision kind", request_id)
        if isinstance(action, RejectClientAction):
            return (self._environment.reject_client(client) if kind == DecisionKind.BOOKING
                    else self._environment.disrupt_client(client))
        if isinstance(action, (BookRoomAction, RelocateRoomAction)):
            room_number = action.room_number
            if isinstance(room_number, bool) or not isinstance(room_number, int):
                return ActionResult(ActionStatus.FAILED, "Room number must be an integer", request_id)
            if isinstance(action, BookRoomAction) and kind == DecisionKind.BOOKING:
                return self._environment.book_client(client, room_number)
            if isinstance(action, RelocateRoomAction) and kind == DecisionKind.RELOCATION:
                return self._environment.relocate_client(client, room_number)
        return ActionResult(ActionStatus.FAILED, "Unsupported action for this decision", request_id)
