"""One hand-computed example, separate from the random experiment statistics."""

from datetime import date, timedelta

from config import SimulationConfig
from models import Client, RoomType
from scenario import RequestEvent, RoomSpec, Scenario


def batch_example():
    start = date(2026, 9, 1)
    config = SimulationConfig(name="batch-demo", number_of_rooms=1, intake_days=1,
                              min_requests=0, max_requests=0,
                              cancellation_probability=0, outage_probability=0)
    requests = (
        RequestEvent(start, Client("Long stay", RoomType.SINGLE, start,
                                  start + timedelta(days=6), request_id=1)),
        RequestEvent(start, Client("First short stay", RoomType.SINGLE, start,
                                  start + timedelta(days=3), request_id=2)),
        RequestEvent(start, Client("Second short stay", RoomType.SINGLE,
                                  start + timedelta(days=3), start + timedelta(days=6),
                                  request_id=3)),
    )
    return Scenario(config, 1111, start, start + timedelta(days=6),
                    (RoomSpec(0, RoomType.SINGLE),), requests, (), ())
