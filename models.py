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

    def __str__(self):
        return f"Client Name: {self.name}, Capacity: {self.capacity}, Arrival: {self.arrival_time.strftime('%m-%d')}, Departure: {self.departure_time.strftime('%m-%d')}"

class Booking:
    def __init__(self, client, room):
        if room.state == "Broken":
            raise ValueError("Room is broken and cannot be booked.")

        for booking in room.bookings:
            if client.arrival_time <= booking.departure_time and booking.arrival_time <= client.departure_time:
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

    def set_rooms(self, rooms):
        self.rooms = rooms

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
            self.add_client(client)
            return booking
        except ValueError as e:
            #print(e)
            return None

    def print_bookings(self):
        for room in self.rooms:
            print(f"Room {room.number} (capacity: {room.capacity}) {"*Broken*" if room.state == "Broken" else ""} bookings:")
            for booking in room.bookings:
                print(f"  Client: {booking.client.name}, Arrival: {booking.arrival_time.strftime('%m-%d')},"
                      f" Departure: {booking.departure_time.strftime('%m-%d')}")
            print()