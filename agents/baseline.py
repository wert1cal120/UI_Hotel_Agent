class BaseLineAgent():
    def __init__(self, hotel):
        self.hotel = hotel

    def act(self, rooms, clients):
        for client in clients:
            for room in [room for room in rooms if room.capacity >= client.capacity and room.state == "Available"]:
                if self.hotel.book_room(client, room):
                    break