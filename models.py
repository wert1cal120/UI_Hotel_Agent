class Room:
    def __init__(self, number, capacity, state):
        self.number = number
        self.capacity = capacity
        self.state = state
        self.bookings = []
        self.client = None


class Client:
    def __init__(self, name, capacity, arrival_time, departure_time):
        self.name = name
        self.capacity = capacity
        self.arrival_time = arrival_time
        self.departure_time = departure_time

class Booking:
    def __init__(self, client, room):
        if room.state == "Broken":
            raise ValueError("Room is broken and cannot be booked.")

        for booking in room.bookings:
            for date in range(client.arrival_time, client.departure_time):
                if date in range(booking.arrival_time, booking.departure_time):
                    raise ValueError("Room is already booked for the given time range.")

        self.client = client
        self.room = room
        self.arrival_time = client.arrival_time
        self.departure_time = client.departure_time
        room.bookings.append(self)
        room.bookings.sort(key=lambda b: b.arrival_time)

class Hotel:
    def __init__(self):
        self.rooms = []
        self.clients = []

    def add_room(self, room):
        self.rooms.append(room)

    def add_client(self, client):
        self.clients.append(client)

    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
        else:
            raise ValueError("Client not found in the hotel.")

    def book_room(self, client, room):
        try:
            booking = Booking(client, room)
            return booking
        except ValueError as e:
            print(e)
            return None

    def print_bookings(self):
        for room in self.rooms:
            print(f"Room {room.number} bookings:")
            for booking in room.bookings:
                print(f"  Client: {booking.client.name}, Arrival: {booking.arrival_time}, Departure: {booking.departure_time}")