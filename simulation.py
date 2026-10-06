"""Run one policy against a private environment and save an auditable trace."""

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date
from enum import Enum
from copy import deepcopy
from pathlib import Path
import csv
import json
from time import perf_counter

from scenario import Scenario
from actuators import HotelActuator
from agents.actions import ActionStatus
from agents.agent_types import AgentType
from environment import HotelEnvironment
from models import DecisionKind
from performance import evaluate
from sensors import HotelSensor


def json_default(value):
    if isinstance(value, (date, Path)):
        return str(value)
    if isinstance(value, Enum):
        return value.value if isinstance(value.value, str) else value.name
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


@dataclass
class SimulationResult:
    agent: str
    config_name: str
    seed: int
    scenario_hash: str
    metrics: dict
    daily: list[dict]
    events: list[dict]
    actions: list[dict]
    batches: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: str | Path) -> Path:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=json_default) + "\n",
            encoding="utf-8")
        schemas = {
            "daily.csv": ("date", "occupied_rooms", "operational_rooms", "occupied_beds",
                          "operational_beds", "exact_match_nights", "served_groups", "active_guests"),
            "actions.csv": ("date", "request_id", "kind", "action", "room_number", "status",
                            "reason", "decision_reason"),
            "events.csv": ("date", "event", "request_id", "room_number", "old_room", "repair_day"),
            "batches.csv": ("date", "incoming_order", "chosen_order", "strategy", "plans_checked"),
        }
        for filename, rows in (("daily.csv", self.daily), ("actions.csv", self.actions),
                               ("events.csv", self.events), ("batches.csv", self.batches)):
            write_csv(directory / filename, rows, schemas[filename])
        write_csv(directory / "metrics.csv", [self.metrics])
        return directory


def write_csv(path: Path, rows: list[dict], schema=()):
    """Keep mixed event payloads valid CSV without discarding optional columns."""
    fieldnames = list(dict.fromkeys(tuple(schema) + tuple(key for row in rows for key in row)))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            encoded = {key: (json.dumps(value, default=json_default, ensure_ascii=False)
                             if isinstance(value, (dict, list, tuple)) else
                             json_default(value) if isinstance(value, (date, Enum, Path)) else value)
                       for key, value in row.items()}
            writer.writerow(encoded)


def execute_request(environment, sensor, actuator, agent, client, kind):
    percept = sensor.observe(client, kind=kind)
    started = perf_counter()
    action = agent.decide(percept)
    elapsed = perf_counter() - started
    result = actuator.execute(client, action, kind=kind)
    log = {"date": environment.current_date.isoformat(),
           "request_id": client.request_id, "kind": kind.value,
           "action": action.__class__.__name__,
           "room_number": result.room_number, "status": result.status.value,
           "reason": result.reason, "decision_reason": agent.decision_reason}
    return result, log, elapsed


def run_simulation(scenario: Scenario, agent="intelligent") -> SimulationResult:
    """No full scenario reference is passed to the policy or its constructor."""

    if isinstance(agent, str):
        agent_name = agent
        agent = AgentType(agent).create(seed=scenario.seed)
    elif isinstance(agent, AgentType):
        agent_name = agent.value
        agent = agent.create(seed=scenario.seed)
    else:
        agent_name = getattr(agent, "name", agent.__class__.__name__)
    started = perf_counter()
    environment = HotelEnvironment.from_scenario(scenario)
    sensor, actuator = HotelSensor(environment), HotelActuator(environment)
    requests_by_day = {}
    for event in scenario.requests:
        # Ordinary Client objects belong to this run, never to another world.
        requests_by_day.setdefault(event.day, []).append(deepcopy(event.client))
    actions, daily, batches = [], [], []
    decision_time_s = 0.0

    while environment.current_date < scenario.end_date:
        for client in environment.begin_day(environment.current_date):
            result, log, elapsed = execute_request(environment, sensor, actuator,
                                                   agent, client, DecisionKind.RELOCATION)
            actions.append(log)
            decision_time_s += elapsed
            if result.status == ActionStatus.FAILED:
                # Invalid relocation does not mutate the reservation. The runner
                # explicitly ends unsupported service instead of occupying a broken room.
                environment.disrupt_client(client)
        clients = requests_by_day.get(environment.current_date, [])
        if clients:
            batch = sensor.observe_batch(clients)
            before = agent.diagnostics.get("plans_checked", 0)
            planning_started = perf_counter()
            order = agent.order_requests(batch)
            decision_time_s += perf_counter() - planning_started
            incoming = [client.request_id for client in clients]
            if len(order) != len(incoming) or set(order) != set(incoming):
                raise ValueError("Agent must order every request in today's batch exactly once")
            batches.append({"date": environment.current_date.isoformat(),
                            "incoming_order": incoming, "chosen_order": order,
                            "strategy": agent.batch_reason,
                            "plans_checked": agent.diagnostics["plans_checked"] - before})
            clients_by_id = {client.request_id: client for client in clients}
            clients = [clients_by_id[request_id] for request_id in order]
        for client in clients:
            result, log, elapsed = execute_request(environment, sensor, actuator,
                                                   agent, client, DecisionKind.BOOKING)
            actions.append(log)
            decision_time_s += elapsed
            if result.status == ActionStatus.FAILED:
                environment.mark_failed(client)
        environment.check_in()
        daily.append(environment.record_night())
        environment.assert_invariants()
        environment.step()
    environment.finish()
    environment.assert_invariants()
    runtime_s = perf_counter() - started
    diagnostics = getattr(agent, "diagnostics", {})
    metrics = evaluate(scenario, environment, daily, decisions=len(actions),
                       failed_actions=sum(row["status"] == ActionStatus.FAILED.value for row in actions),
                       decision_checks=int(diagnostics.get("candidate_checks", 0)),
                       runtime_s=runtime_s, decision_time_s=decision_time_s)
    metrics["decision_fallbacks"] = int(diagnostics.get("fallbacks", 0))
    metrics["max_decision_checks"] = int(diagnostics.get("max_decision_checks", 0))
    metrics["batch_count"] = len(batches)
    metrics["plans_checked"] = int(diagnostics.get("plans_checked", 0))
    return SimulationResult(agent_name, scenario.config.name, scenario.seed, scenario.fingerprint,
                            metrics, daily, list(environment.events), actions, batches)
