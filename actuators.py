from agents.actions import BookRoomAction


class HotelActuator:
    def __init__(self, environment):
        self.environment = environment

    def execute(self, client, action):
        if isinstance(action, BookRoomAction):
            room = self.environment.hotel.get_room_by_number(action.room_number)
            if room:
                self.environment.hotel.book_room(client, room)