"""Read-only perceptions: copies of known data, not live model objects."""
from dataclasses import dataclass
from datetime import date

from models import Client, DecisionKind, RoomType


@dataclass(frozen=True)
class BookingInfo:
    request_id: int
    arrival_time: date
    departure_time: date


@dataclass(frozen=True)
class ClientInfo:
    request_id: int
    name: str
    room_type: RoomType
    guests: int
    arrival_time: date
    departure_time: date


@dataclass(frozen=True)
class RoomInfo:
    room_number: int
    room_type: RoomType
    capacity: int
    available: bool
    bookings: tuple[BookingInfo, ...] = ()
    unavailable_until: date | None = None


@dataclass(frozen=True)
class Percept:
    current_date: date
    client: ClientInfo
    rooms: tuple[RoomInfo, ...]
    kind: DecisionKind = DecisionKind.BOOKING


class HotelSensor:
    def __init__(self, environment):
        self._environment = environment

    def observe_batch(self, clients):
        # Both agents see the same complete queue for this day, not future days.
        return tuple(self.observe(client) for client in clients)

    def observe(self, client: Client, kind: DecisionKind = DecisionKind.BOOKING) -> Percept:
        environment = self._environment
        relocation = kind == DecisionKind.RELOCATION
        start = max(environment.current_date, client.arrival_time) if relocation else client.arrival_time
        excluded = client.request_id if relocation else None
        snapshot = ClientInfo(client.request_id, client.name, client.room_type,
                              client.guests, start, client.departure_time)
        rooms = []
        for room in environment.hotel.rooms:
            calendar = []
            for request_id, segment in environment.calendar(room.number, excluded):
                calendar.append(BookingInfo(request_id, segment.arrival_time, segment.departure_time))
            calendar.sort(key=lambda booking: (booking.arrival_time, booking.request_id))
            available = environment.can_book(client, room.number, start=start, exclude_request=excluded)
            if relocation:
                current = environment.bookings.get(client.request_id)
                available = available and current is not None and room.number != current.room_number
            rooms.append(RoomInfo(room.number, room.room_type, room.room_type.capacity,
                                  available, tuple(calendar), environment.broken_until.get(room.number)))
        return Percept(environment.current_date, snapshot, tuple(rooms), kind)
