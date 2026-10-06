"""A simple single-agent entry point; command-line options live in cli.py."""

from agents.agent_types import AgentType
import config
from config import SimulationConfig
from scenario import create_scenario
from simulation import run_simulation


def main(agent=AgentType.BASELINE):
    # Like the original main(agent), but both policies use a saved scenario.
    settings = SimulationConfig(
        number_of_rooms=config.NUMBER_OF_ROOMS,
        intake_days=config.WORKING_DAYS,
    )
    scenario = create_scenario(settings, config.SEED)
    result = run_simulation(scenario, agent)
    for row in result.daily:
        print(f'Day {row["date"]}: {row["occupied_rooms"]} occupied rooms')
    print(result.metrics)
    return result


if __name__ == "__main__":
    from cli import main as run_command
    run_command()
