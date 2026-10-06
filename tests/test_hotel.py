"""Basic checks for the main hotel features."""

import unittest
from datetime import date, timedelta

from examples import batch_example
from models import Client, Hotel, Room, RoomType
from scenario import CancellationEvent, OutageEvent, RequestEvent, RoomSpec, Scenario, create_scenario
from settings import SimulationConfig
from simulation import run_simulation


START = date(2026, 9, 1)


def day(number):
    return START + timedelta(days=number)


def make_scenario(requests, rooms=(RoomType.SINGLE,), cancellations=(), outages=()):
    # These small examples all fit into six days.
    config = SimulationConfig(name="test", number_of_rooms=len(rooms), intake_days=1,
                              min_requests=0, max_requests=0,
                              cancellation_probability=0, outage_probability=0)
    room_list = []
    for number, room_type in enumerate(rooms):
        room_list.append(RoomSpec(number, room_type))
    return Scenario(config, 7, START, day(6), tuple(room_list), tuple(requests),
                    tuple(cancellations), tuple(outages))


class HotelTests(unittest.TestCase):
    def test_booking(self):
        room = Room(0, RoomType.SINGLE)
        hotel = Hotel([room])
        client = Client("Anna", RoomType.SINGLE, day(0), day(3))
        self.assertIsNotNone(hotel.book_room(client, room))

    def test_booking_dates(self):
        room = Room(0, RoomType.SINGLE)
        hotel = Hotel([room])
        hotel.book_room(Client("Anna", RoomType.SINGLE, day(0), day(3)), room)
        overlap = Client("Peter", RoomType.SINGLE, day(1), day(2))
        next_guest = Client("Eva", RoomType.SINGLE, day(3), day(6))
        self.assertIsNone(hotel.book_room(overlap, room))
        self.assertIsNotNone(hotel.book_room(next_guest, room))

    def test_room_capacity(self):
        room = Room(0, RoomType.SINGLE)
        hotel = Hotel([room])
        client = Client("Peter", RoomType.DOUBLE, day(0), day(3))
        self.assertIsNone(hotel.book_room(client, room))

    def test_cancellation(self):
        first = Client("Anna", RoomType.SINGLE, day(3), day(5), request_id=1)
        second = Client("Peter", RoomType.SINGLE, day(3), day(5), request_id=2)
        scenario = make_scenario(
            [RequestEvent(day(0), first), RequestEvent(day(2), second)],
            cancellations=[CancellationEvent(day(1), 1)])
        result = run_simulation(scenario, "baseline")
        self.assertEqual(result.metrics["accepted"], 2)
        self.assertEqual(result.metrics["cancelled_requests"], 1)
        self.assertEqual(result.metrics["fulfillment_rate"], 100)

    def test_relocation(self):
        client = Client("Anna", RoomType.SINGLE, day(0), day(3), request_id=1)
        scenario = make_scenario(
            [RequestEvent(day(0), client)], rooms=[RoomType.SINGLE, RoomType.SINGLE],
            outages=[OutageEvent(day(1), 0, day(3))])
        result = run_simulation(scenario, "baseline")
        self.assertEqual(result.metrics["relocations"], 1)
        self.assertEqual(result.metrics["delivered_room_nights"], 3)
        self.assertEqual(result.metrics["fulfillment_rate"], 100)

    def test_seed(self):
        config = SimulationConfig(intake_days=2)
        first = create_scenario(config, 1111)
        second = create_scenario(config, 1111)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_daily_batch(self):
        scenario = batch_example()
        baseline = run_simulation(scenario, "baseline")
        intelligent = run_simulation(scenario, "intelligent")
        self.assertEqual(baseline.metrics["accepted"], 1)
        self.assertEqual(intelligent.metrics["accepted"], 2)


if __name__ == "__main__":
    unittest.main()
