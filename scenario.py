"""Agent-independent, reproducible arrivals, cancellations and room outages.

The complete scenario belongs to the experiment runner, never to an agent.
Only events that have already happened enter sensor observations.
"""

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
import random

from config import SimulationConfig
from environment import HotelEnvironment
from models import Client, Hotel, RoomType


@dataclass(frozen=True)
class RoomSpec:
    number: int
    room_type: RoomType


@dataclass(frozen=True)
class RequestEvent:
    day: date
    client: Client


@dataclass(frozen=True)
class CancellationEvent:
    day: date
    request_id: int


@dataclass(frozen=True)
class OutageEvent:
    day: date
    room_number: int
    repair_day: date


@dataclass(frozen=True)
class Scenario:
    config: SimulationConfig
    seed: int
    start_date: date
    end_date: date
    rooms: tuple[RoomSpec, ...]
    requests: tuple[RequestEvent, ...]
    cancellations: tuple[CancellationEvent, ...]
    outages: tuple[OutageEvent, ...]

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(), "seed": self.seed,
            "start_date": self.start_date.isoformat(), "end_date": self.end_date.isoformat(),
            "rooms": [{"number": room.number, "room_type": room.room_type.name,
                       "capacity": room.room_type.capacity} for room in self.rooms],
            "requests": [{"day": event.day.isoformat(), "request_id": event.client.request_id,
                          "name": event.client.name, "room_type": event.client.room_type.name,
                          "guests": event.client.guests,
                          "arrival_time": event.client.arrival_time.isoformat(),
                          "departure_time": event.client.departure_time.isoformat()}
                         for event in self.requests],
            "cancellations": [{"day": event.day.isoformat(), "request_id": event.request_id}
                              for event in self.cancellations],
            "outages": [{"day": event.day.isoformat(), "room_number": event.room_number,
                         "repair_day": event.repair_day.isoformat()} for event in self.outages],
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def create_scenario(config: SimulationConfig, seed: int) -> Scenario:
    """Generate everything before either policy acts, including cancelled demand.

    Cancellations are possible only when there is a full day between receipt
    and arrival. Outages use a separate RNG and cannot overlap on one room.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    environment = HotelEnvironment(Hotel(), config.start_date, seed, config=config)
    environment.generate_rooms(config.number_of_rooms)
    rooms = tuple(RoomSpec(room.number, room.room_type) for room in environment.hotel.rooms)
    requests, cancellations = [], []
    cancellation_rng = random.Random(seed + 1)
    for offset in range(config.intake_days):
        receipt_day = environment.current_date
        for client in environment.generate_clients():
            requests.append(RequestEvent(receipt_day, client))
            lead = (client.arrival_time - receipt_day).days
            if lead >= 2 and cancellation_rng.random() < config.cancellation_probability:
                cancel_day = receipt_day + timedelta(days=cancellation_rng.randint(1, lead - 1))
                cancellations.append(CancellationEvent(cancel_day, client.request_id))
        environment.step()
    intake_end = config.start_date + timedelta(days=config.intake_days)
    end_date = max([intake_end] + [event.client.departure_time for event in requests])
    outage_rng = random.Random(seed + 2)
    outages = []
    for room in rooms:
        day = config.start_date
        while day < end_date:
            if outage_rng.random() < config.outage_probability:
                repair_day = day + timedelta(days=outage_rng.randint(config.min_repair_days,
                                                                    config.max_repair_days))
                outages.append(OutageEvent(day, room.number, repair_day))
                day = repair_day
            else:
                day += timedelta(days=1)
    return Scenario(config, seed, config.start_date, end_date, rooms, tuple(requests),
                    tuple(sorted(cancellations, key=lambda event: (event.day, event.request_id))),
                    tuple(sorted(outages, key=lambda event: (event.day, event.room_number))))
