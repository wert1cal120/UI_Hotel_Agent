"""Evaluate supplied accommodation, not a policy's choice of particular actions."""

from dataclasses import dataclass

from agents.actions import ActionStatus
from models import BookingStatus


def percentage(numerator: float, denominator: float) -> float:
    """An empty cohort has rate zero, not an exception or invented perfect score."""
    return 100.0 * numerator / denominator if denominator else 0.0


def evaluate(scenario, environment, daily: list[dict], *, decisions: int,
             failed_actions: int, decision_checks: int, runtime_s: float,
             decision_time_s: float) -> dict:
    """Measure both worlds against identical exogenous, non-cancelled demand.

    A cancellation belongs to a request even if an agent previously rejected
    it. Consequently it is removed from both agents' fulfillment denominator.
    Accepted reservations alone never count as successfully served stays.
    """
    cancelled_ids = {event.request_id for event in scenario.cancellations}
    eligible = [event.client for event in scenario.requests
                if event.client.request_id not in cancelled_ids]
    eligible_bookings = [booking for request_id, booking in environment.bookings.items()
                         if request_id not in cancelled_ids]
    completed = [booking for booking in eligible_bookings
                 if booking.status == BookingStatus.COMPLETED and
                 booking.serviced_nights == (booking.client.departure_time -
                                             booking.client.arrival_time).days]
    delivered_room_nights = sum(booking.serviced_nights for booking in eligible_bookings)
    delivered_guest_nights = sum(booking.serviced_nights * booking.client.guests
                                for booking in eligible_bookings)
    requested_guest_nights = sum((client.departure_time - client.arrival_time).days * client.guests
                                for client in eligible)
    exact_nights = sum(booking.exact_match_nights for booking in eligible_bookings)
    occupied_room_nights = sum(row["occupied_rooms"] for row in daily)
    operational_room_nights = sum(row["operational_rooms"] for row in daily)
    occupied_bed_nights = sum(row["occupied_beds"] for row in daily)
    operational_bed_nights = sum(row["operational_beds"] for row in daily)
    outcomes = list(environment.outcomes.values())
    return {
        "total_requests": len(scenario.requests), "eligible_requests": len(eligible),
        "accepted": sum(status == ActionStatus.BOOKED for status in outcomes),
        "rejected": sum(status == ActionStatus.REJECTED for status in outcomes),
        "failed": sum(status == ActionStatus.FAILED for status in outcomes),
        "cancelled_requests": len(cancelled_ids),
        "completed_groups": len(completed),
        "completed_guests": sum(booking.client.guests for booking in completed),
        "fulfillment_rate": percentage(len(completed), len(eligible)),
        "disrupted_groups": sum(booking.status == BookingStatus.DISRUPTED
                                for booking in eligible_bookings),
        "requested_guest_nights": requested_guest_nights,
        "delivered_guest_nights": delivered_guest_nights,
        "guest_night_fulfillment_rate": percentage(delivered_guest_nights, requested_guest_nights),
        "delivered_room_nights": delivered_room_nights,
        "exact_type_match_rate": percentage(exact_nights, delivered_room_nights),
        "occupied_room_nights": occupied_room_nights,
        "operational_room_nights": operational_room_nights,
        "occupancy": percentage(occupied_room_nights, operational_room_nights),
        "bed_utilization": percentage(occupied_bed_nights, operational_bed_nights),
        "relocations": sum(booking.relocations for booking in environment.bookings.values()),
        "failed_actions": failed_actions, "steps": len(daily), "decisions": decisions,
        "decision_checks": decision_checks, "decision_time_s": decision_time_s,
        "runtime_s": runtime_s,
    }


@dataclass
class PerformanceMetrics:
    """Legacy action counter; final experiments use outcome-based evaluate()."""

    booked: int = 0
    rejected: int = 0
    failed: int = 0

    def record(self, action_result):
        if action_result.status == ActionStatus.BOOKED:
            self.booked += 1
        elif action_result.status == ActionStatus.REJECTED:
            self.rejected += 1
        elif action_result.status == ActionStatus.FAILED:
            self.failed += 1

    def summary(self):
        total = self.booked + self.rejected + self.failed
        return {"total": total, "booked": self.booked, "rejected": self.rejected,
                "failed": self.failed, "booking_rate": percentage(self.booked, total),
                "rejection_rate": percentage(self.rejected, total),
                "failure_rate": percentage(self.failed, total)}
