from enum import Enum

class RoomStatus(Enum):
    AVAILABLE = "Available"
    BROKEN = "Broken"


class RoomType(Enum):
    SINGLE = (1, "Single")
    DOUBLE = (2, "Double")
    TRIPLE = (3, "Triple")
    QUAD = (4, "Quad")

    def __init__(self, capacity, label):
        self.capacity = capacity
        self.label = label


class Room:
    def __init__(self, number, room_type: RoomType, state: RoomStatus):
        self.number = number
        self.room_type = room_type
        self.state = state
        self.bookings = []


class Client:
    def __init__(self, name, room_type: RoomType, arrival_time, departure_time):
        self.name = name
        self.room_type = room_type
        self.arrival_time = arrival_time
        self.departure_time = departure_time

    def __str__(self):
        return (f"Client Name: {self.name},"
                f" Room Type: {self.room_type.label},"
                f" Arrival: {self.arrival_time.strftime('%m-%d')},"
                f" Departure: {self.departure_time.strftime('%m-%d')})")

class Booking:
    def __init__(self, client, room):
        if room.state == RoomStatus.BROKEN:
            raise ValueError("Room is broken and cannot be booked.")

        if client.room_type.capacity > room.room_type.capacity:
            raise ValueError("Client's room type exceeds room's room type.")

        for booking in room.bookings:
            #TODO: Check if it works correctly with overlapping bookings
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

    #TODO: MOVE OUT
    def print_bookings(self):
        for room in self.rooms:
            print(f"Room {room.number} (room type: {room.room_type.label})"
                  f" {room.state.value if room.state == RoomStatus.BROKEN else ""} bookings:")

            for booking in room.bookings:
                print(f"  Client: {booking.client.name}, Arrival: {booking.arrival_time.strftime('%m-%d')},"
                      f" Departure: {booking.departure_time.strftime('%m-%d')}")
            print()