from dataclasses import dataclass


@dataclass(frozen=True)
class BookRoomAction:
    room_number: int

class RejectClientAction:
    pass