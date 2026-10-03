from models import RoomStatus


class BaseLineAgent:
    def __init__(self, hotel):
        self.hotel = hotel

    def act(self, rooms, clients):
        for client in clients:
            for room in [room for room in rooms if room.room_type.capacity >= client.room_type.capacity and room.state == RoomStatus.AVAILABLE]:
                if self.hotel.book_room(client, room):
                    break