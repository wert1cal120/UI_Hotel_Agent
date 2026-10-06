"""Console entry point: one simulation, paired comparison, or full experiments."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import config as defaults

from settings import PRESETS, SimulationConfig
from experiments import plot_daily, run_experiments, save_comparison, save_scenario
from scenario import create_scenario
from simulation import run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Intelligent hotel management agent")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("compare", "simulate"):
        command = commands.add_parser(name)
        command.add_argument("--config", choices=tuple(PRESETS), default="standard")
        command.add_argument("--seed", type=int, default=defaults.SEED)
        command.add_argument("--rooms", type=int)
        command.add_argument("--days", type=int, help="Days accepting new requests")
        command.add_argument("--config-file", type=Path, help="Extra settings in JSON")
        command.add_argument("--output", type=Path)
        command.add_argument("--no-plots", action="store_true")
        if name == "simulate":
            command.add_argument("--agent", choices=("baseline", "intelligent"), default="intelligent")
    demo = commands.add_parser("demo", help="One room: one long request versus two short requests")
    demo.add_argument("--output", type=Path, default=Path("results/demo"))
    demo.add_argument("--no-plots", action="store_true")
    experiments = commands.add_parser("experiments", help="Run paired multi-seed experiments")
    experiments.add_argument("--repetitions", type=int, default=20)
    experiments.add_argument("--seed", type=int, default=defaults.SEED, help="First seed in the series")
    experiments.add_argument("--output", type=Path, default=Path("results/experiments"))
    experiments.add_argument("--no-plots", action="store_true")
    report = commands.add_parser("report", help="Generate Slovak Markdown/PDF from verified experiments")
    report.add_argument("--results", type=Path, default=Path("results/experiments"))
    report.add_argument("--output", type=Path, default=Path("output/pdf/documentation.pdf"))
    return parser


def preset_config(name):
    config = replace(PRESETS[name], intake_days=defaults.WORKING_DAYS)
    if name == "standard":
        config = replace(config, number_of_rooms=defaults.NUMBER_OF_ROOMS)
    return config


def config_from_args(args) -> SimulationConfig:
    config = preset_config(args.config)
    if args.config_file:
        overrides = json.loads(args.config_file.read_text(encoding="utf-8"))
        if not isinstance(overrides, dict):
            raise ValueError("Configuration JSON must contain an object")
        config = SimulationConfig.from_dict({**config.to_dict(), **overrides})
    if args.rooms is not None:
        config = replace(config, number_of_rooms=args.rooms)
    if args.days is not None:
        config = replace(config, intake_days=args.days)
    return config


def print_results(results):
    print("\nOutcome-based results (rates are percentages):")
    metrics = ("completed_groups", "completed_guests", "fulfillment_rate", "accepted",
               "rejected", "cancelled_requests", "disrupted_groups", "exact_type_match_rate",
               "occupancy", "relocations", "failed_actions", "batch_count", "plans_checked",
               "decision_checks", "runtime_s")
    print(f"{'Metric':30}" + "".join(f"{result.agent:>16}" for result in results))
    for metric in metrics:
        values = [result.metrics[metric] for result in results]
        formatted = [f"{value:.3f}" if isinstance(value, float) else str(value) for value in values]
        print(f"{metric:30}" + "".join(f"{value:>16}" for value in formatted))


def main(argv=None):
    parser = build_parser()
    arguments = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(arguments or ["compare"])
    try:
        if args.command == "report":
            from report import generate_report
            output = generate_report(args.results, args.output)
            print(f"Saved documentation to {output}")
            return output
        if args.command == "experiments":
            def progress(config_name, seed, runs):
                print(f"{config_name:10} seed={seed} completed_runs={runs}", flush=True)

            output = run_experiments([preset_config(name) for name in PRESETS],
                                     args.repetitions, args.seed, args.output,
                                     progress=progress, plots=not args.no_plots)
            columns = ["config", "agent", "completed_groups_mean", "completed_groups_std",
                       "fulfillment_rate_mean", "fulfillment_rate_std", "runtime_s_mean"]
            print("\nMeans and sample standard deviations:")
            print(output["summary"][columns].round(3).to_string(index=False))
            print("\nPaired winners by completed groups:")
            print(output["paired_summary"][["config", "pairs", "intelligent_wins",
                                            "baseline_wins", "ties"]].to_string(index=False))
            if not output["manifest"]["assignment_minimum_met"]:
                print("Smoke test only: assignment requires >=3 configurations and >=20 repetitions.")
            print(f"\nSaved {output['manifest']['run_count']} runs to {args.output.resolve()}")
            return output

        if args.command == "demo":
            from examples import batch_example
            scenario = batch_example()
        else:
            scenario = create_scenario(config_from_args(args), args.seed)
        config = scenario.config
        directory = args.output or Path("results") / ("simulation" if args.command == "simulate" else "compare")
        save_scenario(scenario, directory)
        names = [args.agent] if args.command == "simulate" else ["baseline", "intelligent"]
        results = [run_simulation(scenario, name) for name in names]
        for result in results:
            result.save(directory / result.agent)
        if args.command in ("compare", "demo"):
            save_comparison(results, directory, plots=not args.no_plots)
        if not args.no_plots:
            plot_daily(results, directory)
        print(f"Configuration={config.name}; seed={scenario.seed}; scenario={scenario.fingerprint[:12]}")
        print_results(results)
        if args.command == "demo":
            print("\nHand-computed demonstration, not a random experiment:")
            for result in results:
                batch = result.batches[0]
                print(f"{result.agent}: order {batch['chosen_order']}; {batch['strategy']}")
                for action in result.actions:
                    print(f"  Request #{action['request_id']}: {action['status']}, room={action['room_number']}")
        print(f"\nSaved full trace and results to {directory.resolve()}")
        return results
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
