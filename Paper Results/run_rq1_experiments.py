#!/usr/bin/env python3
"""
RQ1 overnight runner for the Dynamic Adaptation paper experiments.

Research question:
    Does Dynamic Adaptation improve MAS performance compared with fixed
    coordination mechanisms?

Motivating scenario:
    Ghent hospital logistics with recurring daily stress windows. Each simulated
    day starts with regular operating conditions and moves into a stressed
    interval in the second half of the day, where failure probability,
    communication loss, and recovery time are increased. The stress schedule is
    identical for every coordination mechanism and repetition, so RQ1 compares
    DA against CE, SD, and FD under the same dynamic conditions.

Default campaign:
    3 workload levels x 3 fleet sizes x 4 malicious-agent ratios x
    3 base fault levels x 1 message-loss level x 1 mechanism (DA) x
    5 repetitions = 540 runs.

    The fixed-mechanism baselines can still be requested explicitly with
    --coord-labels CE,SD,FD,DA.

Run from the project root or from this directory, for example:
    python "Paper Results/run_rq1_experiments.py"
    nohup python "Paper Results/run_rq1_experiments.py" > "Paper Results/RQ1/rq1.log" 2>&1 &

Useful dry checks:
    python "Paper Results/run_rq1_experiments.py" --dry-run
    python "Paper Results/run_rq1_experiments.py" --quick --repetitions 1

Resume behavior:
    Completed runs are detected from RQ1/runs.csv.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import statistics
import sys
import time
from itertools import product
from pathlib import Path


PAPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PAPER_ROOT.parent
RESULTS_ROOT = PAPER_ROOT / "RQ1"
RAW_LOGS_DIR = RESULTS_ROOT / "raw_logs"
CONFIGS_DIR = RESULTS_ROOT / "configs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sim import simulator  # noqa: E402


COORD_TO_ARCH = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
    "DA": "dynamic-adaptation",
}

BASE_CONFIG = {
    "RESULTS_DIR": str(RESULTS_ROOT),
    "SIM_TIME": 30 * 24 * 3600,
    "ARCHITECTURE": "centralized-impprox",
    "INITIAL_ARCHITECTURE": "centralized-impprox",
    "TOPOLOGY_NAME": "GUH73",
    "N_ROOMS": 73,
    "SOURCE": 0,
    "TARGETS": -1,
    "ITEM_SPAWNING_TIME": 120,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.50, 0.10, 0.40],
    "EXPIRATION_TIME": [-1, -1, -1],
    "EXPIRATION_DISTR": ["exponential", "exponential", "exponential"],
    "N_ROBOTS": 20,
    "N_MALICIOUS": 0,
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
    "FAIL_PROB": 0.33,
    "COMM_FAIL_PROB": 0.10,
    "LOAD_TIME": 1.0,
    "LOAD_DISTR": "exponential",
    "LOAD_TRACE": "_",
    "MOVEMENT_TIME": 5.0,
    "MOVEMENT_DISTR": "exponential",
    "MOVEMENT_TRACE": "_",
    "DROP_TIME": 1.0,
    "DROP_DISTR": "exponential",
    "DROP_TRACE": "_",
    "COMP_TIME": 0.03,
    "COMP_DISTR": "exponential",
    "COMP_TRACE": "_",
    "COMM_TIME": 0.5,
    "COMM_DISTR": "exponential",
    "COMM_TRACE": "_",
    "RECOVERY_TIME": 1800.0,
    "RECOVERY_DISTR": "exponential",
    "RECOVERY_TRACE": "_",
    "LOG_ITEM": True,
    "LOG_DELIVERY": True,
    "LOG_LOAD": False,
    "LOG_DROP": False,
    "LOG_EXPIRE": False,
    "LOG_MOVE": False,
    "LOG_FAIL": True,
    "LOG_RECOVERY": True,
    "LOG_HELP": False,
    "LOG_FAKE": False,
    "LOG_RESCUE": False,
    "ADAPTATION_POLICY": "hybrid-score",
    "ADAPTATION_CHECK_INTERVAL": 10 * 60.0,
    "LATENCY_THRESHOLD_LOW": 10 * 60.0,
    "LATENCY_THRESHOLD_HIGH": 40 * 60.0,
    "RTLOLA_METRIC_TIMEOUT": 0.05,
}

DEFAULT_ITEM_SPAWNING_TIMES = [90, 120, 150]
DEFAULT_N_ROBOTS = [10, 20, 30]
DEFAULT_MALICIOUS_RATIOS = [0.0, 0.33, 0.66, 1.0]
DEFAULT_FAIL_PROBS = [0.33, 0.66, 1.0]
DEFAULT_MSG_LOSS_PROBS = [0.10]
DEFAULT_COORD_LABELS = ["DA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ1 paper experiments.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per configuration.")
    parser.add_argument("--sim-days", type=int, default=30, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260527, help="Base random seed.")
    parser.add_argument("--stress-multiplier", type=float, default=1.2, help="Fault multiplier in stress windows.")
    parser.add_argument("--stress-start-hour", type=float, default=12.0, help="Daily stress-window start hour.")
    parser.add_argument("--stress-end-hour", type=float, default=24.0, help="Daily stress-window end hour.")
    parser.add_argument("--quick", action="store_true", help="Small smoke campaign for checking the runner.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the run is already marked ok in runs.csv.")
    parser.add_argument(
        "--coord-labels",
        default=",".join(DEFAULT_COORD_LABELS),
        help="Comma-separated mechanisms to include, e.g. DA or CE,SD,FD,DA.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N run instances.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately if a run fails.")
    return parser.parse_args()


def selected_coord_labels(args: argparse.Namespace) -> list[str]:
    labels = [label.strip().upper() for label in args.coord_labels.split(",") if label.strip()]
    unknown = [label for label in labels if label not in COORD_TO_ARCH]
    if unknown:
        raise ValueError(f"Unknown coordination labels: {', '.join(unknown)}")
    if not labels:
        raise ValueError("At least one coordination label is required.")
    return labels


def ensure_dirs() -> None:
    for directory in [RESULTS_ROOT, RAW_LOGS_DIR, CONFIGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def cleanup_transient_artifacts() -> None:
    for path in (RAW_LOGS_DIR, CONFIGS_DIR):
        if path.exists():
            shutil.rmtree(path)
    design_path = RESULTS_ROOT / "experiment_design.json"
    if design_path.exists():
        design_path.unlink()


def build_fault_windows(
    *,
    sim_days: int,
    base_fail_prob: float,
    base_msg_loss: float,
    base_recovery_time: float,
    n_malicious: int,
    item_spawning_time: float,
    stress_multiplier: float,
    stress_start_hour: float,
    stress_end_hour: float,
) -> list[dict]:
    phases = []
    day_seconds = 24 * 3600
    for day in range(sim_days):
        day_start = day * day_seconds
        day_end = day_start + day_seconds
        stress_start = min(max(day_start + stress_start_hour * 3600, day_start), day_end)
        stress_end = min(max(day_start + stress_end_hour * 3600, stress_start), day_end)

        phases.append({
            "start": day_start,
            "end": stress_start,
            "N_MALICIOUS": n_malicious,
            "FAIL_PROB": base_fail_prob,
            "COMM_FAIL_PROB": base_msg_loss,
            "RECOVERY_TIME": base_recovery_time,
            "ITEM_SPAWNING_TIME": item_spawning_time,
        })
        phases.append({
            "start": stress_start,
            "end": min(stress_end, day_end),
            "N_MALICIOUS": n_malicious,
            "FAIL_PROB": min(1.0, stress_multiplier * base_fail_prob),
            "COMM_FAIL_PROB": min(1.0, stress_multiplier * base_msg_loss),
            "RECOVERY_TIME": stress_multiplier * base_recovery_time,
            "ITEM_SPAWNING_TIME": item_spawning_time,
        })
        phases.append({
            "start": stress_end,
            "end": day_end,
            "N_MALICIOUS": n_malicious,
            "FAIL_PROB": base_fail_prob,
            "COMM_FAIL_PROB": base_msg_loss,
            "RECOVERY_TIME": base_recovery_time,
            "ITEM_SPAWNING_TIME": item_spawning_time,
        })

    return [phase for phase in phases if phase["end"] > phase["start"]]


def campaign_grid(args: argparse.Namespace) -> list[dict]:
    coord_labels = selected_coord_labels(args)
    if args.quick:
        item_spawning_times = [120]
        n_robots_values = [20]
        malicious_ratios = [0.33]
        fail_probs = [0.33]
        msg_loss_probs = [0.10]
    else:
        item_spawning_times = DEFAULT_ITEM_SPAWNING_TIMES
        n_robots_values = DEFAULT_N_ROBOTS
        malicious_ratios = DEFAULT_MALICIOUS_RATIOS
        fail_probs = DEFAULT_FAIL_PROBS
        msg_loss_probs = DEFAULT_MSG_LOSS_PROBS

    combos = []
    combo_idx = 0
    for item_spawn, n_robots, mal_ratio, fail_prob, msg_loss, coord_label in product(
        item_spawning_times,
        n_robots_values,
        malicious_ratios,
        fail_probs,
        msg_loss_probs,
        coord_labels,
    ):
        combo_idx += 1
        n_malicious = int(round(mal_ratio * n_robots))
        for rep in range(1, args.repetitions + 1):
            seed = args.base_seed + combo_idx * 1000 + rep
            combos.append({
                "combo_idx": combo_idx,
                "rep": rep,
                "seed": seed,
                "coord_label": coord_label,
                "architecture": COORD_TO_ARCH[coord_label],
                "item_spawning_time": item_spawn,
                "n_robots": n_robots,
                "malicious_ratio": mal_ratio,
                "n_malicious": n_malicious,
                "fail_prob": fail_prob,
                "msg_loss_prob": msg_loss,
            })

    return combos[: args.limit] if args.limit else combos


def run_id(params: dict) -> str:
    mal_pct = int(round(params["malicious_ratio"] * 100))
    fail_pct = int(round(params["fail_prob"] * 100))
    msg_pct = int(round(params["msg_loss_prob"] * 100))
    return (
        f"c{params['combo_idx']:04d}_r{params['rep']:02d}_"
        f"{params['coord_label']}_spawn{params['item_spawning_time']}_"
        f"bots{params['n_robots']}_mal{mal_pct}_fail{fail_pct}_msg{msg_pct}"
    )


def config_for(params: dict, args: argparse.Namespace, logfile: Path) -> dict:
    cfg = dict(BASE_CONFIG)
    cfg.update({
        "RESULTS_DIR": str(logfile.parent),
        "SIMTIME_LOGFILE": str(RESULTS_ROOT / "sim_time.csv"),
        "LOGFILE": str(logfile),
        "SIM_TIME": args.sim_days * 24 * 3600,
        "ARCHITECTURE": params["architecture"],
        "ITEM_SPAWNING_TIME": params["item_spawning_time"],
        "N_ROBOTS": params["n_robots"],
        "N_MALICIOUS": params["n_malicious"],
        "FAIL_PROB": params["fail_prob"],
        "COMM_FAIL_PROB": params["msg_loss_prob"],
        "RANDOM_SEED": params["seed"],
    })
    cfg["PHASES"] = build_fault_windows(
        sim_days=args.sim_days,
        base_fail_prob=params["fail_prob"],
        base_msg_loss=params["msg_loss_prob"],
        base_recovery_time=cfg["RECOVERY_TIME"],
        n_malicious=params["n_malicious"],
        item_spawning_time=params["item_spawning_time"],
        stress_multiplier=args.stress_multiplier,
        stress_start_hour=args.stress_start_hour,
        stress_end_hour=args.stress_end_hour,
    )
    return cfg


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return ordered[idx]


def read_overhead(logfile: Path) -> dict:
    overhead_path = logfile.with_name(logfile.stem + "_overhead.csv")
    if not overhead_path.exists():
        return {
            "adapt_checks": 0,
            "adapt_switches_overhead": 0,
            "adapt_overhead_ms_mean": math.nan,
            "rtlola_query_ms_mean": math.nan,
            "scoring_ms_mean": math.nan,
        }

    with overhead_path.open(newline="") as f:
        samples = list(csv.DictReader(f))
    if not samples:
        return {
            "adapt_checks": 0,
            "adapt_switches_overhead": 0,
            "adapt_overhead_ms_mean": math.nan,
            "rtlola_query_ms_mean": math.nan,
            "scoring_ms_mean": math.nan,
        }

    def mean_field(name: str) -> float:
        vals = [float(row[name]) for row in samples if row.get(name) not in (None, "")]
        return statistics.mean(vals) if vals else math.nan

    return {
        "adapt_checks": len(samples),
        "adapt_switches_overhead": sum(1 for row in samples if row.get("switched") == "True"),
        "adapt_overhead_ms_mean": mean_field("total_overhead_ms"),
        "rtlola_query_ms_mean": mean_field("rtlola_query_ms"),
        "scoring_ms_mean": mean_field("scoring_ms"),
    }


def analyze_log(logfile: Path, sim_time: float) -> dict:
    create_times = {}
    delivery_latencies = []
    events = {}
    switches = []
    last_time = 0.0

    with logfile.open(newline="") as f:
        for row in csv.DictReader(f):
            event = row.get("event", "")
            item_id = int(row.get("itemId", -1) or -1)
            sim_t = float(row.get("simTime", 0.0) or 0.0)
            last_time = max(last_time, sim_t)
            events[event] = events.get(event, 0) + 1

            if event == "create" and item_id >= 0:
                create_times[item_id] = sim_t
            elif event == "deliver" and item_id in create_times:
                delivery_latencies.append(sim_t - create_times[item_id])
            elif event.startswith("switch_architecture_"):
                switches.append((sim_t, event.replace("switch_architecture_", "")))

    created = events.get("create", 0)
    delivered = events.get("deliver", 0)
    expired = events.get("expire", 0)
    pending = max(0, created - delivered - expired)
    completed_or_expired = delivered + expired

    metrics = {
        "created": created,
        "delivered": delivered,
        "expired": expired,
        "pending": pending,
        "failed": events.get("fail", 0),
        "recovered": events.get("recover", 0) + events.get("recovery", 0),
        "success_rate": delivered / created if created else 0.0,
        "completion_rate": completed_or_expired / created if created else 0.0,
        "throughput_per_hour": delivered / (sim_time / 3600.0) if sim_time else 0.0,
        "avg_latency_s": statistics.mean(delivery_latencies) if delivery_latencies else math.nan,
        "median_latency_s": statistics.median(delivery_latencies) if delivery_latencies else math.nan,
        "p95_latency_s": percentile(delivery_latencies, 0.95),
        "max_latency_s": max(delivery_latencies) if delivery_latencies else math.nan,
        "switch_count": len(switches),
        "fd_switch_count": sum(1 for _, arch in switches if arch == "decentralized"),
        "sd_switch_count": sum(1 for _, arch in switches if arch == "semi-decentralized"),
        "ce_switch_count": sum(1 for _, arch in switches if arch == "centralized-impprox"),
        "first_switch_time": switches[0][0] if switches else math.nan,
        "last_sim_time": last_time,
    }
    metrics.update(read_overhead(logfile))
    return metrics


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def completed_run_ids(rows: list[dict]) -> set[str]:
    completed = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if run_id and row.get("status") == "ok":
            completed.add(run_id)
    return completed


def replace_row(rows: list[dict], row: dict) -> list[dict]:
    run_id = row.get("run_id")
    return [existing for existing in rows if existing.get("run_id") != run_id] + [row]


def summarise_runs(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    group_fields = [
        "coord_label",
        "architecture",
        "item_spawning_time",
        "n_robots",
        "malicious_ratio",
        "n_malicious",
        "fail_prob",
        "msg_loss_prob",
    ]
    metric_fields = [
        "created",
        "delivered",
        "pending",
        "success_rate",
        "completion_rate",
        "throughput_per_hour",
        "avg_latency_s",
        "median_latency_s",
        "p95_latency_s",
        "max_latency_s",
        "switch_count",
        "adapt_overhead_ms_mean",
        "rtlola_query_ms_mean",
        "scoring_ms_mean",
    ]

    grouped = {}
    for row in ok_rows:
        key = tuple(row[field] for field in group_fields)
        grouped.setdefault(key, []).append(row)

    summary = []
    for key, group in sorted(grouped.items()):
        record = dict(zip(group_fields, key))
        record["runs"] = len(group)
        for metric in metric_fields:
            values = [
                float(row[metric])
                for row in group
                if row.get(metric) not in (None, "", "nan") and not math.isnan(float(row[metric]))
            ]
            record[f"{metric}_mean"] = statistics.mean(values) if values else math.nan
            record[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        summary.append(record)

    mechanism_summary = []
    for coord_label in sorted({row["coord_label"] for row in ok_rows}):
        group = [row for row in ok_rows if row["coord_label"] == coord_label]
        record = {"coord_label": coord_label, "architecture": COORD_TO_ARCH[coord_label], "runs": len(group)}
        for metric in metric_fields:
            values = [
                float(row[metric])
                for row in group
                if row.get(metric) not in (None, "", "nan") and not math.isnan(float(row[metric]))
            ]
            record[f"{metric}_mean"] = statistics.mean(values) if values else math.nan
            record[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        mechanism_summary.append(record)

    return summary, mechanism_summary


def run_campaign(args: argparse.Namespace) -> None:
    combos = campaign_grid(args)
    total_runs = len(combos)
    design = {
        "research_question": "RQ1",
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "total_runs": total_runs,
        "coordination_mechanisms": selected_coord_labels(args),
        "item_spawning_times": [120] if args.quick else DEFAULT_ITEM_SPAWNING_TIMES,
        "n_robots": [20] if args.quick else DEFAULT_N_ROBOTS,
        "malicious_ratios": [0.33] if args.quick else DEFAULT_MALICIOUS_RATIOS,
        "fail_probs": [0.33] if args.quick else DEFAULT_FAIL_PROBS,
        "msg_loss_probs": DEFAULT_MSG_LOSS_PROBS,
        "daily_stress_window": [args.stress_start_hour, args.stress_end_hour],
        "stress_multiplier": args.stress_multiplier,
    }
    print("=" * 80)
    print("RQ1 DYNAMIC ADAPTATION EXPERIMENTAL CAMPAIGN")
    print("=" * 80)
    print(json.dumps(design, indent=2))
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    ensure_dirs()
    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    completed = completed_run_ids(rows)
    started_at = time.time()

    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        if rid in completed and not args.force:
            print(f"[{idx}/{total_runs}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = RAW_LOGS_DIR / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        logfile = run_dir / "simulation_log.csv"
        cfg_path = CONFIGS_DIR / f"{rid}.json"
        cfg = config_for(params, args, logfile)
        cfg_path.write_text(json.dumps(cfg, indent=2))

        print(f"[{idx}/{total_runs}] {rid}", flush=True)
        status = "ok"
        error_message = ""
        wall_time = math.nan
        event_count = math.nan
        had_previous_error = any(error.get("run_id") == rid for error in errors)
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            logfile.unlink()

        try:
            if logfile.exists() and not args.force:
                print("  existing log found; analysing without re-running", flush=True)
            else:
                _, wall_time, event_count = simulator.run(str(cfg_path))

            metrics = analyze_log(logfile, cfg["SIM_TIME"])
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            status = "error"
            error_message = str(exc) or exc.__class__.__name__
            metrics = {}
            errors.append({
                **params,
                "run_id": rid,
                "config_path": str(cfg_path),
                "logfile": str(logfile),
                "error": error_message,
            })
            print(f"  ERROR: {error_message}", flush=True)
            if args.fail_fast:
                raise

        row = {
            "run_id": rid,
            "status": status,
            "error": error_message,
            "config_path": str(cfg_path),
            "logfile": str(logfile),
            "coord_label": params["coord_label"],
            "architecture": params["architecture"],
            "rep": params["rep"],
            "seed": params["seed"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss_prob": params["msg_loss_prob"],
            "sim_days": args.sim_days,
            "stress_multiplier": args.stress_multiplier,
            "stress_start_hour": args.stress_start_hour,
            "stress_end_hour": args.stress_end_hour,
            "wall_time_s": wall_time,
            "event_count": event_count,
            **metrics,
        }
        rows = replace_row(rows, row)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    summary, mechanism_summary = summarise_runs(rows)
    write_rows(RESULTS_ROOT / "summary.csv", summary)
    write_rows(RESULTS_ROOT / "summary_by_mechanism.csv", mechanism_summary)
    cleanup_transient_artifacts()

    elapsed = time.time() - started_at
    print("=" * 80)
    print(f"RQ1 campaign completed in {elapsed:.2f}s wall-clock.")
    print(f"Run-level CSV:      {RESULTS_ROOT / 'runs.csv'}")
    print(f"Summary CSV:        {RESULTS_ROOT / 'summary.csv'}")
    print(f"Mechanism summary:  {RESULTS_ROOT / 'summary_by_mechanism.csv'}")
    if errors:
        print(f"Errors CSV:         {RESULTS_ROOT / 'errors.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
