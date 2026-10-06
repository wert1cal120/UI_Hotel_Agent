"""Paired comparisons, saved raw runs, descriptive statistics and figures."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import re

from config import PRESETS, SEED
from scenario import create_scenario
from simulation import json_default, run_simulation


PLOT_METRICS = {
    "fulfillment_rate": "Fully accommodated groups (%)",
    "exact_type_match_rate": "Preferred room match (%)",
    "occupancy": "Operational room occupancy (%)",
}
PAIRED_METRICS = ("completed_groups", "fulfillment_rate", "completed_guests",
                  "guest_night_fulfillment_rate", "exact_type_match_rate", "occupancy",
                  "disrupted_groups", "relocations", "decision_checks", "runtime_s")


def _pandas():
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("Reporting needs pandas; run: python -m pip install -r requirements.txt") from error
    return pd


def _pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError("Charts need matplotlib; run: python -m pip install -r requirements.txt") from error
    return plt


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=json_default) + "\n",
                    encoding="utf-8")


def save_scenario(scenario, output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "scenario.json"
    _write_json(path, {"scenario_hash": scenario.fingerprint, **scenario.to_dict()})
    return path


def _safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def _software_manifest():
    dependencies = {}
    for package in ("pandas", "matplotlib"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "not installed"
    root = Path(__file__).resolve().parent
    sources = list(root.glob("*.py")) + list((root / "agents").glob("*.py"))
    return {"python": platform.python_version(), "platform": platform.platform(),
            "libraries": dependencies,
            "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(sources)}}


def summarize_runs(rows: list[dict]):
    pd = _pandas()
    runs = pd.DataFrame(rows)
    metadata = {"config", "agent", "seed", "scenario_hash"}
    metrics = [column for column in runs.columns if column not in metadata]
    summary = runs.groupby(["config", "agent"], sort=False)[metrics].agg(["mean", "std"])
    summary.columns = [f"{metric}_{statistic}" for metric, statistic in summary.columns]
    summary = summary.fillna(0.0).reset_index()
    return runs, summary


def paired_comparisons(runs):
    """Difference is intelligent minus baseline; pairs share a scenario hash."""
    pd = _pandas()
    baseline = runs[runs.agent == "baseline"].set_index(["config", "seed", "scenario_hash"])
    intelligent = runs[runs.agent == "intelligent"].set_index(["config", "seed", "scenario_hash"])
    if not baseline.index.is_unique or not intelligent.index.is_unique or \
            set(baseline.index) != set(intelligent.index):
        raise ValueError("Every scenario needs exactly one independent run of each agent")
    rows = []
    for key in baseline.index:
        row = {"config": key[0], "seed": key[1], "scenario_hash": key[2]}
        for metric in PAIRED_METRICS:
            row[f"{metric}_delta"] = intelligent.loc[key, metric] - baseline.loc[key, metric]
        row["winner"] = ("intelligent" if row["completed_groups_delta"] > 0 else
                         "baseline" if row["completed_groups_delta"] < 0 else "tie")
        rows.append(row)
    paired = pd.DataFrame(rows)
    summaries = []
    for name, group in paired.groupby("config", sort=False):
        row = {"config": name, "pairs": len(group),
               "intelligent_wins": int((group.winner == "intelligent").sum()),
               "baseline_wins": int((group.winner == "baseline").sum()),
               "ties": int((group.winner == "tie").sum())}
        for metric in PAIRED_METRICS:
            values = group[f"{metric}_delta"]
            row[f"{metric}_delta_mean"] = values.mean()
            row[f"{metric}_delta_std"] = values.std(ddof=1) if len(values) > 1 else 0.0
        summaries.append(row)
    return paired, pd.DataFrame(summaries)


def save_comparison(results, output_dir, plots=True):
    """Reporting belongs here, not in command-line argument handling."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in results:
        rows.append({"config": result.config_name, "seed": result.seed, "agent": result.agent,
                     "scenario_hash": result.scenario_hash, **result.metrics})
    runs, summary = summarize_runs(rows)
    paired, paired_summary = paired_comparisons(runs)
    for filename, frame in (("runs.csv", runs), ("summary.csv", summary),
                            ("paired.csv", paired), ("paired_summary.csv", paired_summary)):
        frame.to_csv(directory / filename, index=False)
    if plots:
        plot_summary(summary, paired, directory)


def plot_summary(summary, paired, output_dir: str | Path):
    plt = _pyplot()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    names = list(dict.fromkeys(summary.config))
    colors = {"baseline": "#64748b", "intelligent": "#0f766e"}
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    for axis, (metric, label) in zip(axes, PLOT_METRICS.items()):
        for offset, agent in ((-0.19, "baseline"), (0.19, "intelligent")):
            group = summary[summary.agent == agent].set_index("config")
            positions = [index + offset for index in range(len(names))]
            means = [group.loc[name, f"{metric}_mean"] for name in names]
            deviations = [group.loc[name, f"{metric}_std"] for name in names]
            axis.bar(positions, means, yerr=deviations, width=0.36, capsize=4,
                     color=colors[agent], label=agent)
        axis.set_xticks(range(len(names)), names)
        axis.set_ylabel(label)
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", alpha=0.18)
    axes[0].legend()
    figure.suptitle("Paired scenarios: means with sample standard deviation")
    figure.savefig(directory / "comparison.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    for index, name in enumerate(names):
        values = paired[paired.config == name].completed_groups_delta.to_list()
        offsets = [index + (position % 5 - 2) * 0.035 for position in range(len(values))]
        axis.scatter(offsets, values, color="#0f766e", alpha=0.6, s=30)
        axis.plot([index - 0.22, index + 0.22], [sum(values) / len(values)] * 2,
                  color="#111827", linewidth=2)
    axis.axhline(0, color="#64748b", linestyle="--", linewidth=1)
    axis.set_xticks(range(len(names)), names)
    axis.set_ylabel("Completed groups: intelligent minus baseline")
    axis.set_title("Every seed pair; black line = mean difference")
    axis.grid(axis="y", alpha=0.18)
    figure.savefig(directory / "paired_deltas.png", dpi=180)
    plt.close(figure)


def plot_daily(results, output_dir: str | Path):
    plt = _pyplot()
    figure, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, constrained_layout=True)
    for result in results:
        days = [index + 1 for index in range(len(result.daily))]
        axes[0].plot(days, [row["occupied_rooms"] for row in result.daily], label=result.agent)
        axes[1].plot(days, [100 * row["occupied_rooms"] / row["operational_rooms"]
                           if row["operational_rooms"] else 0 for row in result.daily], label=result.agent)
    if results:
        days = list(range(1, len(results[0].daily) + 1))
        axes[0].plot(days, [row["operational_rooms"] for row in results[0].daily],
                     color="#64748b", linestyle="--", label="operational rooms")
    axes[0].set_ylabel("Occupied rooms")
    axes[1].set_ylabel("Occupancy (%)")
    axes[1].set_xlabel("Simulation day (includes drain horizon)")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.legend()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    figure.savefig(directory / "daily.png", dpi=180)
    plt.close(figure)


def run_experiments(configs=None, repetitions: int = 20, base_seed: int = SEED,
                    output_dir: str | Path = "results/experiments", progress=None,
                    plots: bool = True):
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    configs = tuple(PRESETS.values() if configs is None else configs)
    if not configs or len({_safe_name(config.name) for config in configs}) != len(configs):
        raise ValueError("Configurations must have distinct nonempty output names")
    pd = _pandas()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows, pairs = [], []
    for config in configs:
        for seed in range(base_seed, base_seed + repetitions):
            scenario = create_scenario(config, seed)
            scenario_dir = directory / "scenarios" / f"{_safe_name(config.name)}_{seed}"
            save_scenario(scenario, scenario_dir)
            pairs.append({"config": config.name, "seed": seed, "scenario_hash": scenario.fingerprint,
                          "scenario_file": str((scenario_dir / "scenario.json").relative_to(directory))})
            for agent_name in ("baseline", "intelligent"):
                result = run_simulation(scenario, agent_name)
                result.save(directory / "runs" / _safe_name(config.name) / str(seed) / agent_name)
                rows.append({"config": config.name, "seed": seed, "agent": agent_name,
                             "scenario_hash": scenario.fingerprint, **result.metrics})
            if progress:
                progress(config.name, seed, len(rows))
    runs, summary = summarize_runs(rows)
    paired, paired_summary = paired_comparisons(runs)
    for filename, frame in (("runs.csv", runs), ("summary.csv", summary),
                             ("paired.csv", paired), ("paired_summary.csv", paired_summary)):
        frame.to_csv(directory / filename, index=False)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "repetitions": repetitions, "base_seed": base_seed,
                "agent_names": ["baseline", "intelligent"],
                "run_count": len(rows), "pair_count": len(pairs),
                "assignment_minimum_met": len(configs) >= 3 and repetitions >= 20,
                "standard_deviation": "sample, ddof=1; zero for single-run smoke tests",
                "paired_delta": "intelligent minus baseline",
                "configs": [config.to_dict() for config in configs], "scenarios": pairs,
                **_software_manifest()}
    _write_json(directory / "manifest.json", manifest)
    if plots:
        plot_summary(summary, paired, directory)
    return {"runs": runs, "summary": summary, "paired": paired,
            "paired_summary": paired_summary, "manifest": manifest, "output_dir": directory}
