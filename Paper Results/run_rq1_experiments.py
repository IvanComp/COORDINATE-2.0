#!/usr/bin/env python3
"""
RQ1 overnight runner for the Dynamic Adaptation paper experiments with a
more realistic task-completion regime.

Research question:
    Does Dynamic Adaptation improve MAS performance compared with fixed
    coordination mechanisms?

Motivating scenario:
    Ghent hospital logistics with recurring multi-regime dynamic fault windows.
    Each simulated day alternates nominal operation, load/failure windows,
    communication degradation, malicious-agent surges, and recovery. The
    schedule is identical for every coordination mechanism and repetition, so
    RQ1 compares DA against CE, SD, and FD under the same dynamic conditions.

Default campaign:
    3 workload levels x 3 numbers of agents x 4 malicious-agent ratios x
    3 base fault levels x 1 message-loss level x 4 mechanisms x
    10 repetitions = 4320 runs.

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
from sim.rtlola_monitor import resolve_rtlola_binary  # noqa: E402


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
    "ITEM_SPAWNING_TIME": 210,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.55, 0.25, 0.20],
    "EXPIRATION_TIME": [28800, 14400, 7200],
    "EXPIRATION_DISTR": ["deterministic", "deterministic", "deterministic"],
    "N_ROBOTS": 40,
    "N_MALICIOUS": 0,
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
    "FAIL_PROB": 0.20,
    "COMM_FAIL_PROB": 0.05,
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
    "LOG_EXPIRE": True,
    "LOG_MOVE": False,
    "LOG_FAIL": True,
    "LOG_RECOVERY": True,
    "LOG_HELP": False,
    "LOG_FAKE": False,
    "LOG_RESCUE": False,
    "ADAPTATION_POLICY": "contextual-bandit",
    "BANDIT_REWARD_VERSION": "completion_v2",
    "BANDIT_WEIGHT_LATENCY": 0.20,
    "BANDIT_WEIGHT_PENDING": 0.30,
    "BANDIT_WEIGHT_FAILURE": 0.05,
    "BANDIT_WEIGHT_MESSAGE_LOSS": 0.10,
    "BANDIT_WEIGHT_DEADLINE_MISS": 0.30,
    "BANDIT_WEIGHT_THROUGHPUT_SHORTFALL": 0.25,
    "BANDIT_WEIGHT_IDLE_WHEN_PENDING": 0.05,
    "BANDIT_WEIGHT_THROUGHPUT": 0.20,
    "BANDIT_BACKLOG_OVERRIDE_REQUIRES_FAULT": True,
    "ADAPTATION_CHECK_INTERVAL": 10 * 60.0,
    "LATENCY_THRESHOLD_LOW": 10 * 60.0,
    "LATENCY_THRESHOLD_HIGH": 40 * 60.0,
    "RTLOLA_METRIC_TIMEOUT": 0.05,
}

DEFAULT_ITEM_SPAWNING_TIMES = [180, 210, 240]
DEFAULT_N_ROBOTS = [30, 40, 50]
DEFAULT_MALICIOUS_RATIOS = [0.0, 0.33, 0.66, 1.0]
DEFAULT_FAIL_PROBS = [0.10, 0.20, 0.33]
DEFAULT_MSG_LOSS_PROBS = [0.05]
DEFAULT_COORD_LABELS = ["CE", "SD", "FD", "DA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ1 paper experiments.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per configuration.")
    parser.add_argument("--sim-days", type=int, default=30, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260527, help="Base random seed.")
    parser.add_argument("--fault-window-multiplier", type=float, default=1.15, help="Fault multiplier in dynamic fault windows.")
    parser.add_argument("--fault-window-start-hour", type=float, default=12.0, help="Legacy single-window start hour.")
    parser.add_argument("--fault-window-end-hour", type=float, default=24.0, help="Legacy single-window end hour.")
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
    n_robots: int,
    n_malicious: int,
    item_spawning_time: float,
    fault_window_multiplier: float,
    fault_window_start_hour: float,
    fault_window_end_hour: float,
) -> list[dict]:
    phases = []
    day_seconds = 24 * 3600

    def prob(value: float) -> float:
        return max(0.0, min(1.0, value))

    def malicious(value: float) -> int:
        return max(0, min(n_robots, int(round(value))))

    def spawn(value: float) -> float:
        return max(30.0, float(value))

    for day in range(sim_days):
        day_start = day * day_seconds
        day_end = day_start + day_seconds

        daily_segments = [
            {
                "label": "nominal",
                "start_hour": 0,
                "end_hour": 6,
                "N_MALICIOUS": malicious(0.25 * n_malicious),
                "FAIL_PROB": prob(0.50 * base_fail_prob),
                "COMM_FAIL_PROB": prob(0.50 * base_msg_loss),
                "RECOVERY_TIME": base_recovery_time,
                "ITEM_SPAWNING_TIME": spawn(1.50 * item_spawning_time),
            },
            {
                "label": "load_failure_surge",
                "start_hour": 6,
                "end_hour": 10,
                "N_MALICIOUS": n_malicious,
                "FAIL_PROB": prob(fault_window_multiplier * base_fail_prob),
                "COMM_FAIL_PROB": base_msg_loss,
                "RECOVERY_TIME": fault_window_multiplier * base_recovery_time,
                "ITEM_SPAWNING_TIME": spawn(0.75 * item_spawning_time),
            },
            {
                "label": "baseline",
                "start_hour": 10,
                "end_hour": 14,
                "N_MALICIOUS": n_malicious,
                "FAIL_PROB": base_fail_prob,
                "COMM_FAIL_PROB": base_msg_loss,
                "RECOVERY_TIME": base_recovery_time,
                "ITEM_SPAWNING_TIME": item_spawning_time,
            },
            {
                "label": "malicious_surge",
                "start_hour": 14,
                "end_hour": 18,
                "N_MALICIOUS": malicious(n_malicious + 0.33 * n_robots),
                "FAIL_PROB": prob(fault_window_multiplier * base_fail_prob),
                "COMM_FAIL_PROB": prob(2.0 * base_msg_loss),
                "RECOVERY_TIME": fault_window_multiplier * base_recovery_time,
                "ITEM_SPAWNING_TIME": spawn(0.90 * item_spawning_time),
            },
            {
                "label": "recovery",
                "start_hour": 18,
                "end_hour": 24,
                "N_MALICIOUS": malicious(0.25 * n_malicious),
                "FAIL_PROB": prob(max(0.03, 0.25 * base_fail_prob)),
                "COMM_FAIL_PROB": prob(max(0.02, 0.30 * base_msg_loss)),
                "RECOVERY_TIME": base_recovery_time,
                "ITEM_SPAWNING_TIME": spawn(1.50 * item_spawning_time),
            },
        ]

        for segment in daily_segments:
            start = min(max(day_start + segment["start_hour"] * 3600, day_start), day_end)
            end = min(max(day_start + segment["end_hour"] * 3600, start), day_end)
            phase = dict(segment)
            phase.update({"start": start, "end": end})
            phase.pop("start_hour")
            phase.pop("end_hour")
            phases.append(phase)

    return [phase for phase in phases if phase["end"] > phase["start"]]


def campaign_grid(args: argparse.Namespace) -> list[dict]:
    coord_labels = selected_coord_labels(args)
    if args.quick:
        item_spawning_times = [210]
        n_robots_values = [40]
        malicious_ratios = [0.33]
        fail_probs = [0.20]
        msg_loss_probs = [0.05]
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
    policy_suffix = ""
    if params["coord_label"] == "DA":
        policy = str(BASE_CONFIG.get("ADAPTATION_POLICY", "contextual-bandit"))
        reward_version = str(BASE_CONFIG.get("BANDIT_REWARD_VERSION", "default"))
        reward_version = reward_version.replace("-", "").replace("_", "")
        policy_suffix = f"_{policy.replace('-', '')}_{reward_version}"
    return (
        f"c{params['combo_idx']:04d}_r{params['rep']:02d}_"
        f"{params['coord_label']}{policy_suffix}_spawn{params['item_spawning_time']}_"
        f"bots{params['n_robots']}_mal{mal_pct}_fail{fail_pct}_msg{msg_pct}"
    )


def config_for(params: dict, args: argparse.Namespace, logfile: Path) -> dict:
    cfg = dict(BASE_CONFIG)
    cfg.update({
        "RESULTS_DIR": str(logfile.parent),
        "SIMTIME_LOGFILE": str(logfile.parent / "sim_time.csv"),
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
        n_robots=params["n_robots"],
        n_malicious=params["n_malicious"],
        item_spawning_time=params["item_spawning_time"],
        fault_window_multiplier=args.fault_window_multiplier,
        fault_window_start_hour=args.fault_window_start_hour,
        fault_window_end_hour=args.fault_window_end_hour,
    )
    if params["architecture"] == "dynamic-adaptation":
        resolved = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / "sim"))
        if not resolved:
            raise RuntimeError(
                "No usable RTLola binary found for dynamic adaptation. "
                f"python={sys.executable}. "
                "Run 'bash scripts/install_rtlola_venv.sh' in the same environment "
                "or export RTLOLA_BINARY_PATH=/absolute/path/to/rtlola-cli."
            )
        cfg["RTLOLA_BINARY_PATH"] = resolved
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

    metrics = {
        "created": created,
        "delivered": delivered,
        "expired": expired,
        "pending": pending,
        "failed": events.get("fail", 0),
        "recovered": events.get("recover", 0) + events.get("recovery", 0),
        "success_rate": delivered / created if created else 0.0,
        "completion_rate": delivered / created if created else 0.0,
        "expiration_rate": expired / created if created else 0.0,
        "terminal_rate": (delivered + expired) / created if created else 0.0,
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
            if not row_matches_current_expiration(row):
                continue
            if str(row.get("log_expire", "")).lower() != "true":
                continue
            completed.add(run_id)
    return completed


def expiration_metadata(cfg=None) -> dict:
    values = (cfg or BASE_CONFIG)["EXPIRATION_TIME"]
    return {
        "expiration_time_low_s": values[0],
        "expiration_time_medium_s": values[1],
        "expiration_time_high_s": values[2],
    }


def row_matches_current_expiration(row: dict) -> bool:
    expected = expiration_metadata()
    for key, expected_value in expected.items():
        try:
            actual_value = float(row.get(key, ""))
        except (TypeError, ValueError):
            return False
        if int(round(actual_value)) != int(round(float(expected_value))):
            return False
    return True


def replace_row(rows: list[dict], row: dict) -> list[dict]:
    run_id = row.get("run_id")
    return [existing for existing in rows if existing.get("run_id") != run_id] + [row]


def run_campaign(args: argparse.Namespace) -> None:
    combos = campaign_grid(args)
    total_runs = len(combos)
    coord_labels = selected_coord_labels(args)
    if not args.dry_run and "DA" in coord_labels:
        resolved = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / "sim"))
        if not resolved:
            raise RuntimeError(
                "No usable RTLola binary found for dynamic adaptation. "
                f"python={sys.executable}. "
                "Run 'bash scripts/install_rtlola_venv.sh' in the same environment "
                "or export RTLOLA_BINARY_PATH=/absolute/path/to/rtlola-cli."
            )
        print(f"[preflight] RTLola binary: {resolved}")
    design = {
        "research_question": "RQ1",
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "total_runs": total_runs,
        "coordination_mechanisms": coord_labels,
        "adaptation_policy": BASE_CONFIG["ADAPTATION_POLICY"],
        "bandit_reward_version": BASE_CONFIG.get("BANDIT_REWARD_VERSION", ""),
        "bandit_reward_weights": {
            "latency": BASE_CONFIG.get("BANDIT_WEIGHT_LATENCY"),
            "pending": BASE_CONFIG.get("BANDIT_WEIGHT_PENDING"),
            "deadline_miss": BASE_CONFIG.get("BANDIT_WEIGHT_DEADLINE_MISS"),
            "throughput_shortfall": BASE_CONFIG.get("BANDIT_WEIGHT_THROUGHPUT_SHORTFALL"),
            "throughput": BASE_CONFIG.get("BANDIT_WEIGHT_THROUGHPUT"),
        },
        "item_spawning_times": [210] if args.quick else DEFAULT_ITEM_SPAWNING_TIMES,
        "n_robots": [40] if args.quick else DEFAULT_N_ROBOTS,
        "malicious_ratios": [0.33] if args.quick else DEFAULT_MALICIOUS_RATIOS,
        "fail_probs": [0.20] if args.quick else DEFAULT_FAIL_PROBS,
        "msg_loss_probs": DEFAULT_MSG_LOSS_PROBS,
        "expiration_time": BASE_CONFIG["EXPIRATION_TIME"],
        "expiration_distribution": BASE_CONFIG["EXPIRATION_DISTR"],
        "importance_probabilities": BASE_CONFIG["IMPORTANCE_PROBABILITIES"],
        "daily_fault_windows": [
            "nominal: 00h-06h",
            "load_failure_surge: 06h-10h",
            "baseline: 10h-14h",
            "malicious_surge: 14h-18h",
            "recovery: 18h-24h",
        ],
        "fault_window_multiplier": args.fault_window_multiplier,
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
    expected_policy = str(BASE_CONFIG["ADAPTATION_POLICY"]).lower()
    expected_reward_version = str(BASE_CONFIG.get("BANDIT_REWARD_VERSION", "")).lower()
    rows = [
        row for row in rows
        if str(row.get("coord_label", "")) != "DA"
        or (
            str(row.get("adaptation_policy", "")).lower() == expected_policy
            and str(row.get("bandit_reward_version", "")).lower() == expected_reward_version
        )
    ]
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
        had_stale_expire_log = any(
            row.get("run_id") == rid
            and row.get("status") == "ok"
            and str(row.get("log_expire", "")).lower() != "true"
            for row in rows
        )
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            logfile.unlink()
        if had_stale_expire_log and logfile.exists() and not args.force:
            print("  old log lacks expire events; removing stale log and re-running", flush=True)
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
            "adaptation_policy": cfg.get("ADAPTATION_POLICY", ""),
            "bandit_reward_version": cfg.get("BANDIT_REWARD_VERSION", ""),
            "rep": params["rep"],
            "seed": params["seed"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss_prob": params["msg_loss_prob"],
            "expiration_time_low_s": cfg["EXPIRATION_TIME"][0],
            "expiration_time_medium_s": cfg["EXPIRATION_TIME"][1],
            "expiration_time_high_s": cfg["EXPIRATION_TIME"][2],
            "log_expire": cfg["LOG_EXPIRE"],
            "sim_days": args.sim_days,
            "fault_window_multiplier": args.fault_window_multiplier,
            "fault_window_start_hour": args.fault_window_start_hour,
            "fault_window_end_hour": args.fault_window_end_hour,
            "wall_time_s": wall_time,
            "event_count": event_count,
            **metrics,
        }
        rows = replace_row(rows, row)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    cleanup_transient_artifacts()

    elapsed = time.time() - started_at
    print("=" * 80)
    print(f"RQ1 campaign completed in {elapsed:.2f}s wall-clock.")
    print(f"Run-level CSV:      {RESULTS_ROOT / 'runs.csv'}")
    if errors:
        print(f"Errors CSV:         {RESULTS_ROOT / 'errors.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
