"""Actual world state and lifecycle; no room-selection policy lives here."""
from datetime import date, timedelta
import random

from agents.actions import ActionResult, ActionStatus
from config import CLIENT_NAMES, SimulationConfig
from models import (Allocation, BookingStatus, Client, Hotel, Room,
                    RoomStatus, RoomType, intervals_overlap)

LIVE_STATUSES = (BookingStatus.RESERVED, BookingStatus.ACTIVE)


class HotelEnvironment:
    def __init__(self, hotel, start_date, seed, scenario=None, config=None):
        # Same starting point as the original project: hotel, date and own RNG.
        self.hotel = hotel
        self.current_date = start_date
        self.random = random.Random(seed)
        self.scenario = scenario
        self.config = config or SimulationConfig(start_date=start_date)
        self.bookings = {}
        self.outcomes = {}
        self.broken_until = {}
        self.events = []
        self._begun_days = set()
        self._recorded_nights = set()
        self.next_request_id = 1
        self._cancellations = ()
        self._outages = ()
        if scenario is not None:
            self._cancellations = scenario.cancellations
            self._outages = scenario.outages

    @classmethod
    def from_scenario(cls, scenario):
        hotel = Hotel()
        for spec in scenario.rooms:
            hotel.add_room(Room(spec.number, spec.room_type))
        return cls(hotel, scenario.start_date, scenario.seed, scenario, scenario.config)

    def step(self):
        self.current_date += timedelta(days=1)

    def generate_rooms(self, num_rooms):
        rooms = []
        for room_num in range(num_rooms):
            room_type = self.random.choices(list(RoomType), weights=self.config.room_weights)[0]
            rooms.append(Room(room_num, room_type, RoomStatus.AVAILABLE))
        self.hotel.set_rooms(rooms)

    def generate_client(self):
        arrival = self.current_date + timedelta(days=self.random.randint(0, self.config.max_lead_days))
        departure = arrival + timedelta(days=self.random.randint(self.config.min_stay, self.config.max_stay))
        room_type = self.random.choices(list(RoomType), weights=self.config.demand_weights)[0]
        client = Client(self.random.choice(CLIENT_NAMES), room_type, arrival, departure,
                        request_id=self.next_request_id)
        self.next_request_id += 1
        return client

    def generate_clients(self):
        clients = []
        for _ in range(self.random.randint(self.config.min_requests, self.config.max_requests)):
            clients.append(self.generate_client())
        return clients

    def _log(self, event: str, **values):
        self.events.append({"date": self.current_date.isoformat(), "event": event, **values})

    def calendar(self, room_number: int, exclude_request: int | None = None):
        """Known, live allocations. Cancelled/completed stays release capacity."""
        entries = []
        for booking in self.bookings.values():
            if booking.status not in LIVE_STATUSES or booking.client.request_id == exclude_request:
                continue
            for segment in booking.allocations:
                if segment.room_number == room_number and segment.arrival_time < segment.departure_time:
                    entries.append((booking.client.request_id, segment))
        return tuple(entries)

    def can_book(self, client: Client, room_number: int, *, start: date | None = None,
                 exclude_request: int | None = None) -> bool:
        start = client.arrival_time if start is None else start
        room = self.hotel.get_room_by_number(room_number)
        if room is None or start < self.current_date or start >= client.departure_time:
            return False
        if room.room_type.capacity < client.guests:
            return False
        # Known repair dates can be used. Hidden future failures cannot.
        if room.state == RoomStatus.BROKEN:
            repair_day = self.broken_until.get(room.number)
            if repair_day is None or start < repair_day:
                return False
        for _, segment in self.calendar(room.number, exclude_request):
            if intervals_overlap(start, client.departure_time, segment.arrival_time, segment.departure_time):
                return False
        return True

    def _failure(self, client, reason: str, room_number=None):
        return ActionResult(ActionStatus.FAILED, reason, getattr(client, "request_id", None), room_number)

    def _new_request_error(self, client: Client) -> str | None:
        if client.request_id <= 0:
            return "A request must have a positive stable ID"
        if client.request_id in self.outcomes:
            return "Request already processed"
        if client.arrival_time < self.current_date:
            return "Arrival is in the past"
        return None

    def book_client(self, client: Client, room_number: int) -> ActionResult:
        error = self._new_request_error(client)
        if error:
            return self._failure(client, error, room_number)
        if not self.can_book(client, room_number):
            return self._failure(client, "Room is unknown, unsuitable, broken or already reserved", room_number)
        room = self.hotel.get_room_by_number(room_number)
        booking = self.hotel.book_room(client, room, self.broken_until.get(room_number))
        if booking is None:
            return self._failure(client, "Room could not be booked", room_number)
        self.bookings[client.request_id] = booking
        self.outcomes[client.request_id] = ActionStatus.BOOKED
        self._log("booked", request_id=client.request_id, room_number=room_number)
        return ActionResult(ActionStatus.BOOKED, "Room reserved", client.request_id, room_number)

    def reject_client(self, client: Client) -> ActionResult:
        error = self._new_request_error(client)
        if error:
            return self._failure(client, error)
        self.outcomes[client.request_id] = ActionStatus.REJECTED
        self._log("rejected", request_id=client.request_id)
        return ActionResult(ActionStatus.REJECTED, "Request rejected by agent", client.request_id)

    def mark_failed(self, client: Client):
        """Record an invalid initial action separately from a policy refusal."""
        if client.request_id not in self.outcomes:
            self.outcomes[client.request_id] = ActionStatus.FAILED
            self._log("invalid_action", request_id=client.request_id)

    def relocate_client(self, client: Client, room_number: int) -> ActionResult:
        booking = self.bookings.get(client.request_id)
        if booking is None or booking.status not in LIVE_STATUSES or booking.client != client:
            return self._failure(client, "No matching live reservation to relocate", room_number)
        start = max(self.current_date, client.arrival_time)
        if room_number == booking.room_number:
            return self._failure(client, "Relocation requires a different room", room_number)
        if not self.can_book(client, room_number, start=start, exclude_request=client.request_id):
            return self._failure(client, "Replacement room is unavailable", room_number)
        # Validate first, then change both allocations atomically. Move only the
        # remaining stay; preserve already delivered nights in the old room.
        old_room = booking.room_number
        booking.allocations[-1].departure_time = start
        booking.allocations.append(Allocation(room_number, start, client.departure_time))
        booking.room.bookings.remove(booking)
        booking.room = self.hotel.get_room_by_number(room_number)
        booking.arrival_time = start
        booking.room.bookings.append(booking)
        booking.room.bookings.sort(key=lambda item: item.arrival_time)
        booking.relocations += 1
        self._log("relocated", request_id=client.request_id, room_number=room_number, old_room=old_room)
        return ActionResult(ActionStatus.RELOCATED, "Remaining stay relocated", client.request_id, room_number)

    def disrupt_client(self, client: Client) -> ActionResult:
        booking = self.bookings.get(client.request_id)
        if booking is None or booking.status not in LIVE_STATUSES or booking.client != client:
            return self._failure(client, "No matching live reservation to disrupt")
        booking.allocations[-1].departure_time = max(self.current_date, client.arrival_time)
        booking.status = BookingStatus.DISRUPTED
        self.hotel.remove_client(client)
        self._log("disrupted", request_id=client.request_id, room_number=booking.room_number)
        return ActionResult(ActionStatus.REJECTED, "No replacement accommodation", client.request_id)

    def _check_out(self):
        for booking in self.bookings.values():
            if booking.status in LIVE_STATUSES and booking.client.departure_time <= self.current_date:
                booking.status = (BookingStatus.COMPLETED
                                  if booking.serviced_nights == booking.client.nights
                                  else BookingStatus.DISRUPTED)
                self.hotel.remove_client(booking.client)
                self._log(booking.status.value, request_id=booking.client.request_id)

    def begin_day(self, day: date) -> tuple[Client, ...]:
        if day < self.current_date or day in self._begun_days:
            raise ValueError("Days must be processed once in chronological order")
        self.current_date = day
        self._begun_days.add(day)
        self._check_out()
        for event in self._cancellations:
            if event.day != day:
                continue
            booking = self.bookings.get(event.request_id)
            if booking is not None and booking.status == BookingStatus.RESERVED:
                booking.status = BookingStatus.CANCELLED
                self.hotel.remove_client(booking.client)
            # Demand cancels even if one policy had rejected the request.
            self._log("cancellation", request_id=event.request_id)
        for room_number, repair_day in tuple(self.broken_until.items()):
            if repair_day <= day:
                self.hotel.get_room_by_number(room_number).state = RoomStatus.AVAILABLE
                del self.broken_until[room_number]
                self._log("repaired", room_number=room_number)
        for event in self._outages:
            if event.day != day:
                continue
            room = self.hotel.get_room_by_number(event.room_number)
            if room is None:
                raise ValueError("Outage references an unknown room")
            room.state = RoomStatus.BROKEN
            self.broken_until[room.number] = event.repair_day
            self._log("outage", room_number=room.number, repair_day=event.repair_day.isoformat())
        affected = []
        for booking in self.bookings.values():
            if booking.status not in LIVE_STATUSES:
                continue
            repair = self.broken_until.get(booking.room_number)
            if repair is not None and max(day, booking.client.arrival_time) < min(repair, booking.client.departure_time):
                affected.append(booking)
        affected.sort(key=lambda b: (b.status != BookingStatus.ACTIVE,
                                     b.client.arrival_time, b.client.request_id))
        return tuple(booking.client for booking in affected)

    def check_in(self):
        for booking in self.bookings.values():
            if booking.status == BookingStatus.RESERVED and booking.client.arrival_time == self.current_date:
                room = self.hotel.get_room_by_number(booking.room_number)
                if room.state == RoomStatus.BROKEN:
                    raise AssertionError("An unresolved outage reached check-in")
                booking.status = BookingStatus.ACTIVE
                self._log("checked_in", request_id=booking.client.request_id, room_number=room.number)

    def record_night(self) -> dict:
        if self.current_date in self._recorded_nights:
            raise ValueError("A night cannot be counted twice")
        if self.scenario is not None and self.current_date >= self.scenario.end_date:
            raise ValueError("Cannot count a night outside the observation horizon")
        self._recorded_nights.add(self.current_date)
        operational = [room for room in self.hotel.rooms if room.state == RoomStatus.AVAILABLE]
        occupied = set()
        guests = exact = 0
        for booking in self.bookings.values():
            if booking.status != BookingStatus.ACTIVE:
                continue
            client = booking.client
            if not client.arrival_time <= self.current_date < client.departure_time:
                raise AssertionError("Active stay outside its dates")
            room = self.hotel.get_room_by_number(booking.room_number)
            if room.state == RoomStatus.BROKEN or room.number in occupied:
                raise AssertionError("Broken room occupation or double booking")
            occupied.add(room.number)
            guests += client.guests
            booking.serviced_nights += 1
            if room.room_type == client.room_type:
                exact += 1
                booking.exact_match_nights += 1
        return {"date": self.current_date.isoformat(), "occupied_rooms": len(occupied),
                "operational_rooms": len(operational), "occupied_beds": guests,
                "operational_beds": sum(room.room_type.capacity for room in operational),
                "exact_match_nights": exact, "served_groups": len(occupied), "active_guests": guests}

    def finish(self):
        if self.scenario is None:
            raise ValueError("Finishing a simulation requires its observation horizon")
        self.current_date = self.scenario.end_date
        self._check_out()
        if any(booking.status in LIVE_STATUSES for booking in self.bookings.values()):
            raise AssertionError("Observation horizon ended before all stays were resolved")
        self.assert_invariants()

    def assert_invariants(self):
        assert len({room.number for room in self.hotel.rooms}) == len(self.hotel.rooms)
        for booking in self.bookings.values():
            assert booking in booking.room.bookings
            if booking.status in LIVE_STATUSES:
                assert booking.client in self.hotel.clients
            else:
                assert booking.client not in self.hotel.clients
            assert 0 <= booking.serviced_nights <= booking.client.nights
            assert 0 <= booking.exact_match_nights <= booking.serviced_nights
            for allocation in booking.allocations:
                room = self.hotel.get_room_by_number(allocation.room_number)
                assert room is not None and room.room_type.capacity >= booking.client.guests
                assert allocation.arrival_time <= allocation.departure_time
        for room in self.hotel.rooms:
            assert all(booking.room is room for booking in room.bookings)
            calendar = self.calendar(room.number)
            for index, (_, left) in enumerate(calendar):
                for _, right in calendar[index + 1:]:
                    assert not intervals_overlap(left.arrival_time, left.departure_time,
                                                 right.arrival_time, right.departure_time)
