from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class BookRoomAction:
    room_number: int

@dataclass(frozen=True)
class RejectClientAction:
    pass

class ActionStatus(Enum):
    BOOKED = "booked"
    REJECTED = "rejected"
    FAILED = "failed"

@dataclass(frozen=True)
class ActionResult:
    status: ActionStatus
    reason: str = ""