"""Action values carry IDs, never mutable hotel objects."""
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class BookRoomAction:
    room_number: int


@dataclass(frozen=True)
class RelocateRoomAction:
    room_number: int


@dataclass(frozen=True)
class RejectClientAction:
    pass


class ActionStatus(Enum):
    BOOKED = "booked"
    REJECTED = "rejected"
    FAILED = "failed"
    RELOCATED = "relocated"


@dataclass(frozen=True)
class ActionResult:
    status: ActionStatus
    reason: str = ""
    request_id: int | None = None
    room_number: int | None = None
