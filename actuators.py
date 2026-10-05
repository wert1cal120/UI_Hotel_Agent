from agents.actions import BookRoomAction, ActionResult, ActionStatus, RejectClientAction


class HotelActuator:
    def __init__(self, environment):
        self.environment = environment

    def execute(self, client, action):
        if isinstance(action, BookRoomAction):
            room = self.environment.hotel.get_room_by_number(action.room_number)
            if room:
                if self.environment.hotel.book_room(client, room):
                    return ActionResult(status=ActionStatus.BOOKED, reason="Room booked successfully")
                return ActionResult(status=ActionStatus.FAILED, reason="Room not booked")
        if isinstance(action, RejectClientAction):
            return ActionResult(status=ActionStatus.REJECTED, reason="Rejected by agent")