"""Try a few clear daily queue orders; choose the best of those plans."""

from datetime import timedelta

from agents.actions import BookRoomAction, RejectClientAction, RelocateRoomAction
from agents.agent_class import Agent
from models import DecisionKind, intervals_overlap
from sensors import BookingInfo


class IntelligentAgent(Agent):
    # Not a prediction model and not an exhaustive search.
    # The same five rules are used for every seed and configuration.
    def __init__(self, seed=0):
        super().__init__()
        self.last_plan = {}
        self.batch_reason = "No batch yet"

    def _room_key(self, percept, room, planned):
        client = percept.client
        spare_beds = room.capacity - client.guests
        type_mismatch = room.room_type != client.room_type

        # Prefer a short existing free gap, keeping a long gap for later.
        left = percept.current_date
        if room.unavailable_until is not None:
            left = max(left, room.unavailable_until)
        right = client.departure_time + timedelta(days=30)
        bookings = room.bookings + tuple(planned.get(room.room_number, []))
        for booking in bookings:
            if booking.departure_time <= client.arrival_time:
                left = max(left, booking.departure_time)
            if booking.arrival_time >= client.departure_time:
                right = min(right, booking.arrival_time)
        gap = (client.arrival_time - left).days + (right - client.departure_time).days
        return spare_beds, type_mismatch, gap, room.room_number

    def _choose_room(self, percept, planned):
        best_room = None
        best_key = None
        checks = 0
        for room in percept.rooms:
            checks += 1
            if not room.available:
                continue
            conflict = False
            for booking in planned.get(room.room_number, []):
                if intervals_overlap(percept.client.arrival_time, percept.client.departure_time,
                                     booking.arrival_time, booking.departure_time):
                    conflict = True
                    break
            if conflict:
                continue
            key = self._room_key(percept, room, planned)
            if best_key is None or key < best_key:
                best_room = room
                best_key = key
        return best_room, checks

    def _try_order(self, order):
        # Temporary calendars only. This never writes to the real hotel.
        planned = {}
        accepted = 0
        exact_matches = 0
        wasted_bed_nights = 0
        checks = 0
        assignments = {}
        for percept in order:
            room, room_checks = self._choose_room(percept, planned)
            checks += room_checks
            if room is None:
                continue
            client = percept.client
            planned.setdefault(room.room_number, []).append(
                BookingInfo(client.request_id, client.arrival_time, client.departure_time))
            assignments[client.request_id] = room.room_number
            nights = (client.departure_time - client.arrival_time).days
            accepted += 1
            exact_matches += int(room.room_type == client.room_type)
            wasted_bed_nights += (room.capacity - client.guests) * nights
        # Compare group count first, type matches second, wasted capacity third.
        score = (accepted, exact_matches, -wasted_bed_nights)
        return score, assignments, checks

    def order_requests(self, batch):
        self.diagnostics["batches"] += 1
        orders = [
            ("incoming", list(batch)),
            ("short stays first", sorted(batch, key=lambda p:
                (p.client.departure_time - p.client.arrival_time).days)),
            ("fewest suitable rooms first", sorted(batch, key=lambda p:
                sum(room.available for room in p.rooms))),
            ("larger groups first", sorted(batch, key=lambda p: -p.client.guests)),
            ("earlier checkout first", sorted(batch, key=lambda p: p.client.departure_time)),
        ]
        best_order = []
        best_score = None
        seen_orders = set()
        checks = 0
        for name, order in orders:
            ids = tuple(percept.client.request_id for percept in order)
            if ids in seen_orders:
                continue
            seen_orders.add(ids)
            score, assignments, plan_checks = self._try_order(order)
            checks += plan_checks
            self.diagnostics["plans_checked"] += 1
            if best_score is None or score > best_score:
                best_score = score
                best_order = list(ids)
                self.last_plan = {"rule": name, "score": score, "assignments": assignments}
        self._record_checks(checks)
        self.batch_reason = (f'{self.last_plan["rule"]}: '
                             f'{best_score[0]} feasible requests in this batch')
        return best_order

    def decide(self, percept):
        self.diagnostics["decisions"] += 1
        if percept.kind == DecisionKind.BOOKING:
            self.diagnostics["observed_requests"] += 1
        room, checks = self._choose_room(percept, {})
        self._record_checks(checks)
        if room is None:
            self.decision_reason = "No room fits the complete stay"
            return RejectClientAction()
        self.decision_reason = f"Best capacity/calendar fit: room {room.room_number}"
        if percept.kind == DecisionKind.RELOCATION:
            return RelocateRoomAction(room.room_number)
        return BookRoomAction(room.room_number)
