from dataclasses import dataclass
from models import RoomStatus, Booking


@dataclass(frozen=True)
class RoomInfo:
    room_number: int
    room_type: int
    available: bool


class HotelSensor:
    def __init__(self, environment):
        self.environment = environment

    def observe(self, client):
        rooms = []
        for room in self.environment.hotel.rooms:
            try:
                if Booking.check_availability(client, room):
                    rooms.append(room)
            except ValueError:
                continue

        return [RoomInfo(room.number, room.room_type.value, room.state == RoomStatus.AVAILABLE) for room in rooms]
