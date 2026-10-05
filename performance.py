from dataclasses import dataclass

from agents.actions import ActionStatus


@dataclass
class PerformanceMetrics:
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
        return {
            "total": total,
            "booked": self.booked,
            "rejected": self.rejected,
            "failed": self.failed,
            "booking_rate": (self.booked / total) * 100 if total > 0 else 0,
            "rejection_rate": (self.rejected / total) * 100 if total > 0 else 0,
            "failure_rate": (self.failed / total) * 100 if total > 0 else 0,
        }
