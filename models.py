"""Hotel data. Dates use [arrival, departure): checkout day is not occupied."""

from datetime import date
from enum import Enum


class RoomStatus(Enum):
    AVAILABLE = "Available"
    BROKEN = "Broken"


class RoomType(Enum):
    SINGLE = (1, "Single")
    DOUBLE = (2, "Double")
    TRIPLE = (3, "Triple")
    QUAD = (4, "Quad")

    @property
    def capacity(self):
        return self.value[0]

    @property
    def label(self):
        return self.value[1]


class DecisionKind(Enum):
    BOOKING = "booking"
    RELOCATION = "relocation"


class BookingStatus(Enum):
    RESERVED = "reserved"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISRUPTED = "disrupted"


class Room:
    def __init__(self, number, room_type: RoomType, state=RoomStatus.AVAILABLE):
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError("Room number must be a non-negative integer")
        if not isinstance(room_type, RoomType) or not isinstance(state, RoomStatus):
            raise ValueError("Invalid room type or state")
        self.number = number
        self.room_type = room_type
        self.state = state
        self.bookings = []


class Client:
    # One Client is one group request. guests is the number of people in it.
    def __init__(self, name, room_type: RoomType, arrival_time, departure_time,
                 request_id=0, guests=None):
        if not isinstance(room_type, RoomType):
            raise ValueError("Unknown preferred room type")
        if not isinstance(arrival_time, date) or not isinstance(departure_time, date):
            raise ValueError("Arrival and departure must be dates")
        if departure_time <= arrival_time:
            raise ValueError("Departure must be after arrival")
        if guests is None:
            guests = room_type.capacity
        if isinstance(guests, bool) or not isinstance(guests, int) or not 1 <= guests <= room_type.capacity:
            raise ValueError("Guest count must fit the preferred room type")
        if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id < 0:
            raise ValueError("Request ID must be a non-negative integer")
        self.name = name
        self.room_type = room_type
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        self.request_id = request_id
        self.guests = guests

    @property
    def nights(self):
        return (self.departure_time - self.arrival_time).days

    def __str__(self):
        return (f"Client #{self.request_id}: {self.name}, Room Type: {self.room_type.label}, "
                f"Guests: {self.guests}, Arrival: {self.arrival_time:%m-%d}, "
                f"Departure: {self.departure_time:%m-%d}")


class Allocation:
    # Keep old room/date segments when an already checked-in guest must move.
    def __init__(self, room_number, arrival_time, departure_time):
        self.room_number = room_number
        self.arrival_time = arrival_time
        self.departure_time = departure_time


class Booking:
    def __init__(self, client, room, repair_day=None):
        self.check_availability(client, room, repair_day)
        self.client = client
        self.room = room
        self.arrival_time = client.arrival_time
        self.departure_time = client.departure_time
        self.status = BookingStatus.RESERVED
        self.allocations = [Allocation(room.number, self.arrival_time, self.departure_time)]
        self.serviced_nights = 0
        self.exact_match_nights = 0
        self.relocations = 0
        room.bookings.append(self)
        room.bookings.sort(key=lambda booking: booking.arrival_time)

    @property
    def room_number(self):
        return self.room.number

    @staticmethod
    def is_broken(room, arrival_time=None, repair_day=None):
        if room.state != RoomStatus.BROKEN:
            return False
        return repair_day is None or arrival_time is None or arrival_time < repair_day

    @staticmethod
    def is_room_type_appropriate(client, room):
        return client.guests <= room.room_type.capacity

    @staticmethod
    def is_bookings_overlaps(client, room):
        for booking in room.bookings:
            if booking.status not in (BookingStatus.RESERVED, BookingStatus.ACTIVE):
                continue
            if intervals_overlap(client.arrival_time, client.departure_time,
                                 booking.arrival_time, booking.departure_time):
                return True
        return False

    @staticmethod
    def check_availability(client, room, repair_day=None):
        if Booking.is_broken(room, client.arrival_time, repair_day):
            raise ValueError("Room is broken and cannot be booked")
        if not Booking.is_room_type_appropriate(client, room):
            raise ValueError("Room cannot accommodate this group")
        if Booking.is_bookings_overlaps(client, room):
            raise ValueError("Room is already booked for these dates")
        return True


class Hotel:
    def __init__(self, rooms=()):
        self.rooms = []
        self.clients = []
        self.set_rooms(rooms)

    def add_room(self, room):
        if self.get_room_by_number(room.number) is not None:
            raise ValueError("Duplicate room number")
        self.rooms.append(room)

    def set_rooms(self, rooms):
        rooms = list(rooms)
        numbers = [room.number for room in rooms]
        if len(set(numbers)) != len(numbers):
            raise ValueError("Room numbers must be unique")
        self.rooms = rooms

    def get_room_by_number(self, number):
        for room in self.rooms:
            if room.number == number:
                return room
        return None

    def add_client(self, client):
        self.clients.append(client)

    def remove_client(self, client):
        if client not in self.clients:
            raise ValueError("Client not found in the hotel")
        self.clients.remove(client)

    def book_room(self, client, room, repair_day=None):
        try:
            booking = Booking(client, room, repair_day)
        except ValueError:
            return None
        self.add_client(client)
        return booking

    def print_bookings(self):
        for room in self.rooms:
            print(f"Room {room.number} ({room.room_type.label}, {room.state.value}):")
            for booking in room.bookings:
                print(f"  {booking.client.name}: {booking.arrival_time:%m-%d} - "
                      f"{booking.departure_time:%m-%d}, {booking.status.value}")


def intervals_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a
