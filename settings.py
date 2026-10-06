"""Validated experiment settings and intentionally different difficulty presets."""

from dataclasses import asdict, dataclass, fields
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class SimulationConfig:
    name: str = "standard"
    start_date: date = date(2026, 9, 1)
    number_of_rooms: int = 12
    intake_days: int = 30
    min_requests: int = 1
    max_requests: int = 4
    max_lead_days: int = 7
    min_stay: int = 1
    max_stay: int = 7
    cancellation_probability: float = 0.10
    outage_probability: float = 0.01
    min_repair_days: int = 1
    max_repair_days: int = 3
    room_weights: tuple[float, ...] = (30, 40, 20, 10)
    demand_weights: tuple[float, ...] = (30, 40, 20, 10)

    def __post_init__(self):
        if not isinstance(self.start_date, date):
            raise ValueError("start_date must be a datetime.date")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a nonempty string")
        positive = ("number_of_rooms", "intake_days", "min_stay", "max_stay",
                    "min_repair_days", "max_repair_days")
        nonnegative = ("min_requests", "max_requests", "max_lead_days")
        for field_name in positive + nonnegative:
            value = getattr(self, field_name)
            minimum = 1 if field_name in positive else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{field_name} must be an integer >= {minimum}")
        for lower, upper in (("min_requests", "max_requests"),
                             ("min_stay", "max_stay"),
                             ("min_repair_days", "max_repair_days")):
            if getattr(self, lower) > getattr(self, upper):
                raise ValueError(f"{lower} must not exceed {upper}")
        for field_name in ("cancellation_probability", "outage_probability"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be a finite probability in [0, 1]")
        for field_name in ("room_weights", "demand_weights"):
            weights = tuple(getattr(self, field_name))
            if len(weights) != 4 or any(not isinstance(w, (int, float)) or
                                       not isfinite(w) or w < 0 for w in weights) or sum(weights) <= 0:
                raise ValueError(f"{field_name} needs four nonnegative weights with a positive sum")
            object.__setattr__(self, field_name, weights)

    def to_dict(self) -> dict:
        values = asdict(self)
        values["start_date"] = self.start_date.isoformat()
        values["room_weights"] = list(self.room_weights)
        values["demand_weights"] = list(self.demand_weights)
        return values

    @classmethod
    def from_dict(cls, values: dict) -> "SimulationConfig":
        if not isinstance(values, dict):
            raise ValueError("Configuration must contain a JSON object")
        unknown = set(values) - {field.name for field in fields(cls)}
        if unknown:
            names = ", ".join(sorted(str(name) for name in unknown))
            raise ValueError(f"Unknown configuration fields: {names}")
        values = dict(values)
        if isinstance(values.get("start_date"), str):
            values["start_date"] = date.fromisoformat(values["start_date"])
        return cls(**values)


PRESETS = {
    "relaxed": SimulationConfig(name="relaxed", number_of_rooms=16, max_requests=3,
                                outage_probability=0.005),
    "standard": SimulationConfig(),
    "stressed": SimulationConfig(name="stressed", number_of_rooms=8,
                                 min_requests=2, max_requests=5, outage_probability=0.02),
}
