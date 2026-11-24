#!/usr/bin/env python3
"""
RQ1 runner aligned with the original COORDINATE paper experiments.

Research question:
    Does Dynamic Adaptation improve MAS performance compared with fixed
    coordination mechanisms?

Experimental scenario:
    The paper's 25-room mesh, ring, and tree topologies with the same RQ1
    parameter sweeps. Each simulated day also includes the same six dynamic
    fault windows for every mechanism, including DA.

Default campaign:
    One-factor-at-a-time sweeps of every value listed in the paper input table,
    from the underlined ring-25 baseline, for all four mechanisms and ten
    repetitions.

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
import platform
import shutil
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from pathlib import Path


PAPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PAPER_ROOT.parent
RESULTS_ROOT = PAPER_ROOT / "RQ1"
RAW_LOGS_DIR = RESULTS_ROOT / "raw_logs"
CONFIGS_DIR = RESULTS_ROOT / "configs"
PHASE_METRICS_PATH = RESULTS_ROOT / "phase_metrics.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sim import simulator  # noqa: E402
from sim.contextual_bandit import FEATURE_NAMES  # noqa: E402
from sim.env_maps import topologyName_dict  # noqa: E402
from sim.rtlola_monitor import resolve_rtlola_binary  # noqa: E402


COORD_TO_ARCH = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
    "DA": "dynamic-adaptation",
}

BASE_CONFIG = {
    "RESULTS_DIR": str(RESULTS_ROOT),
    "SIM_TIME": 90 * 24 * 3600,
    "ARCHITECTURE": "centralized-impprox",
    "INITIAL_ARCHITECTURE": "centralized-impprox",
    "TOPOLOGY_NAME": "ring25",
    "N_ROOMS": 25,
    "SOURCE": 0,
    "TARGETS": -1,
    "ITEM_SPAWNING_TIME": 120,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.55, 0.25, 0.20],
    "EXPIRATION_TIME": [28800, 14400, 7200],
    "EXPIRATION_DISTR": ["deterministic", "deterministic", "deterministic"],
    "N_ROBOTS": 20,
    "N_MALICIOUS": 12,
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
    "FAIL_PROB": 0.09,
    "COMM_FAIL_PROB": 0.03,
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
    "COMM_TIME": 0.03,
    "COMM_DISTR": "exponential",
    "COMM_TRACE": "_",
    "COORDINATOR_SERVICE_TIME": 0.25,
    "COORDINATOR_FAKE_REQUEST_SERVICE_TIME": 0.25,
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
    "BANDIT_REWARD_VERSION": "weighted-cw50-v1",
    "BANDIT_OBJECTIVE_MODE": "weighted",
    "BANDIT_COMPLETION_WEIGHT": 0.50,
    "BANDIT_COMPLETION_TARGET": 0.65,
    "BANDIT_MIN_TERMINAL_OUTCOMES": 3,
    "BANDIT_CREATED_TASKS_REF": 40.0,
    "BANDIT_FAILURE_REF": 2.5,
    "BANDIT_SUSPICION_REF": 10.0,
    "BANDIT_RIDGE": 1.0,
    "BANDIT_UCB_ALPHA": 0.50,
    "BANDIT_INITIAL_SAMPLES_PER_ACTION": 1,
    "BANDIT_CONTEXT_MIN_SAMPLES_PER_ACTION": 1,
    "BANDIT_CONTEXT_BIN_THRESHOLD": 0.5,
    "BANDIT_INITIAL_SAMPLING_BYPASS_PERSISTENCE": True,
    "BANDIT_IMPROVEMENT_MARGIN": 0.03,
    "BANDIT_SWITCH_PENALTY": 0.03,
    "NETWORK_PROBE_SAMPLES_PER_CHECK": 5,
    "ADAPTATION_CHECK_INTERVAL": 60 * 60.0,
    "ADAPTATION_WINDOW": 60 * 60.0,
    "BANDIT_FEEDBACK_WINDOW": 60 * 60.0,
    "ADAPTATION_MIN_SWITCH_INTERVAL": 60 * 60.0,
    "ADAPTATION_PERSISTENCE_CHECKS": 1,
    "BANDIT_EXPLORATION_EPSILON": 0.02,
    "BANDIT_MIN_EXPLORATION_EPSILON": 0.0,
    "BANDIT_EXPLORATION_BYPASS_PERSISTENCE": False,
    # Match the original COORDINATE FD baseline: agents coordinate neither
    # through messages nor through a shared patrol schedule.
    "FD_PATROL_ENABLED": False,
    "FD_INSPECTION_INTERVAL": 2 * 60.0,
    "FD_MAX_PATROLLERS": 0,
    "FD_LOCAL_SEARCH_ENABLED": False,
    "FD_LOCAL_SEARCH_PROBABILITY": 0.0,
    "FD_LOCAL_SEARCH_HOPS": 3,
    "FD_LOCAL_SEARCH_AGENT_COUNT": 0,
    "FD_LOCAL_SEARCH_INTERVAL": 15 * 60.0,
    "FD_REQUEUE_ON_FAILURE": True,
    "SD_COORDINATION_HOPS": 1,
    "LATENCY_THRESHOLD_LOW": 10 * 60.0,
    "LATENCY_THRESHOLD_HIGH": 40 * 60.0,
    "RTLOLA_METRIC_TIMEOUT": 0.05,
}

PAPER_TOPOLOGY_TYPES = ["mesh", "ring", "tree"]
PAPER_ROOM_COUNTS = [4, 9, 16, 25, 36, 49]
PAPER_TOPOLOGIES = [f"{topology}25" for topology in PAPER_TOPOLOGY_TYPES]
PAPER_ITEM_SPAWNING_TIMES = [90, 120, 150, 180, 210, 240, 270, 300]
PAPER_ROBOT_COUNTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
PAPER_MALICIOUS_RATIOS = [value / 100 for value in [0, 20, 40, 60, 80, 100]]
PAPER_FAIL_PROBS = [value / 100 for value in range(1, 11)]
PAPER_MSG_LOSS_PROBS = [value / 100 for value in range(1, 11)]
PAPER_N_ROBOTS = 20
PAPER_N_MALICIOUS = 12
PAPER_BASE_FAIL_PROB = 0.09
PAPER_BASE_MSG_LOSS = 0.03
PAPER_BASE_ITEM_SPAWNING_TIME = 120
PAPER_BASE_TOPOLOGY = "ring25"
PAPER_BASE_N_ROOMS = 25
DEFAULT_COORD_LABELS = ["CE", "SD", "FD", "DA"]
RQ1_PROFILE_ID = "table-aligned-rq1-v1"
RQ1_METRIC_VERSION = "relative-latency-v1"
FD_POLICY_VERSION = "legacy-local-retry-v7"
RQ1_WORKLOAD_SLICE = "workload"
RQ1_TOPOLOGY_SLICE = "topology"
RQ1_SIZE_SLICE = "size"
RQ1_SCALE_SLICE = "scale"
RQ1_SECURITY_SLICE = "security"
RQ1_RELIABILITY_SLICE = "reliability"
RQ1_COMMUNICATION_SLICE = "communication"

# Six equally long phases form a daily triangular severity cycle. The profile
# rises linearly to a controlled peak and mirrors the same steps during recovery.
DAILY_SEVERITY_SEGMENTS = [
    ("severity_0", 0, 4, 0.00),
    ("severity_25", 4, 8, 0.25),
    ("severity_50", 8, 12, 0.50),
    ("severity_75", 12, 16, 0.75),
    ("severity_50_recovery", 16, 20, 0.50),
    ("severity_25_recovery", 20, 24, 0.25),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ1 paper experiments.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per configuration.")
    parser.add_argument("--sim-days", type=int, default=90, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260527, help="Base random seed.")
    parser.add_argument("--quick", action="store_true", help="Small smoke campaign for checking the runner.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the run is already marked ok in runs.csv.")
    parser.add_argument(
        "--coord-labels",
        default=",".join(DEFAULT_COORD_LABELS),
        help="Comma-separated mechanisms to include, e.g. DA or CE,SD,FD,DA.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N run instances.")
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Independent simulations in parallel; 0 automatically uses available CPUs (up to 6).",
    )
    parser.add_argument(
        "--machine-label",
        default=None,
        help="Short label for the host running this campaign, e.g. mac or leonardo. "
             "Recorded per run so timings measured on different machines stay separable.",
    )
    parser.add_argument(
        "--condition-indexes",
        default="",
        help="Comma-separated 1-based condition indexes to run, e.g. 12.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately if a run fails.")
    parser.add_argument(
        "--bandit-objective",
        choices=("completion-constrained", "completion-only", "latency-only", "weighted"),
        default=BASE_CONFIG["BANDIT_OBJECTIVE_MODE"],
        help="Performance objective used to train DA.",
    )
    parser.add_argument(
        "--bandit-completion-weight",
        type=float,
        default=BASE_CONFIG["BANDIT_COMPLETION_WEIGHT"],
        help="Completion weight in weighted mode (0.0 to 1.0).",
    )
    return parser.parse_args()


def selected_coord_labels(args: argparse.Namespace) -> list[str]:
    labels = [label.strip().upper() for label in args.coord_labels.split(",") if label.strip()]
    unknown = [label for label in labels if label not in COORD_TO_ARCH]
    if unknown:
        raise ValueError(f"Unknown coordination labels: {', '.join(unknown)}")
    if not labels:
        raise ValueError("At least one coordination label is required.")
    return labels


def configure_bandit_objective(args: argparse.Namespace) -> None:
    """Make the selected reward mode explicit in configs, IDs, and CSV metadata."""
    if not 0.0 <= args.bandit_completion_weight <= 1.0:
        raise ValueError("--bandit-completion-weight must be between 0.0 and 1.0.")
    mode = args.bandit_objective
    version = "completion-constrained-v1"
    if mode != "completion-constrained":
        version = f"{mode}-cw{int(round(args.bandit_completion_weight * 100)):02d}-v1"
    BASE_CONFIG.update({
        "BANDIT_OBJECTIVE_MODE": mode,
        "BANDIT_COMPLETION_WEIGHT": args.bandit_completion_weight,
        "BANDIT_REWARD_VERSION": version,
    })


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
    n_robots: int,
    n_malicious: int,
    item_spawning_time: float,
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

        daily_segments = []
        # The paper parameter is the daily baseline shown on the chart. The
        # fault windows apply a bounded, common modulation around it so all
        # mechanisms experience the same recurring runtime conditions.
        mode_settings = {
            "severity_0": {"fail": 1.00, "comm": 1.00, "spawn": 1.00, "malicious": 0.00},
            "severity_25": {"fail": 1.25, "comm": 1.25, "spawn": 0.90, "malicious": 0.05},
            "severity_50": {"fail": 1.50, "comm": 1.50, "spawn": 0.80, "malicious": 0.10},
            "severity_75": {"fail": 1.75, "comm": 1.75, "spawn": 0.70, "malicious": 0.15},
            "severity_50_recovery": {"fail": 1.50, "comm": 1.50, "spawn": 0.80, "malicious": 0.10},
            "severity_25_recovery": {"fail": 1.25, "comm": 1.25, "spawn": 0.90, "malicious": 0.05},
        }
        for label, start_hour, end_hour, severity in DAILY_SEVERITY_SEGMENTS:
            mode = mode_settings[label]
            daily_segments.append({
                "label": label,
                "severity_level": severity,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "N_MALICIOUS": malicious(n_malicious + mode["malicious"] * n_robots),
                "FAIL_PROB": prob(mode["fail"] * base_fail_prob),
                "COMM_FAIL_PROB": prob(mode["comm"] * base_msg_loss),
                "COORDINATOR_SERVICE_TIME": 0.25,
                "COORDINATOR_FAILURE_PROB": 0.0,
                "COORDINATOR_AVAILABLE": True,
                "ITEM_SPAWNING_TIME": spawn(mode["spawn"] * item_spawning_time),
            })

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
        conditions = [(
            PAPER_BASE_TOPOLOGY, PAPER_BASE_N_ROOMS, PAPER_BASE_ITEM_SPAWNING_TIME,
            PAPER_N_ROBOTS, PAPER_N_MALICIOUS, PAPER_BASE_FAIL_PROB, PAPER_BASE_MSG_LOSS,
            {RQ1_WORKLOAD_SLICE, RQ1_SECURITY_SLICE, RQ1_RELIABILITY_SLICE},
        )]
    else:
        condition_slices: dict[tuple[str, int, int, int, int, float, float], set[str]] = {}

        def add_condition(
            topology: str,
            n_rooms: int,
            item_spawn: int,
            n_robots: int,
            n_malicious: int,
            fail_prob: float,
            msg_loss: float,
            slice_name: str,
        ) -> None:
            key = (topology, n_rooms, item_spawn, n_robots, n_malicious, fail_prob, msg_loss)
            condition_slices.setdefault(key, set()).add(slice_name)

        for topology_type in PAPER_TOPOLOGY_TYPES:
            add_condition(
                f"{topology_type}{PAPER_BASE_N_ROOMS}", PAPER_BASE_N_ROOMS,
                PAPER_BASE_ITEM_SPAWNING_TIME, PAPER_N_ROBOTS, PAPER_N_MALICIOUS,
                PAPER_BASE_FAIL_PROB, PAPER_BASE_MSG_LOSS, RQ1_TOPOLOGY_SLICE,
            )
        for n_rooms in PAPER_ROOM_COUNTS:
            add_condition(
                f"ring{n_rooms}", n_rooms, PAPER_BASE_ITEM_SPAWNING_TIME,
                PAPER_N_ROBOTS, PAPER_N_MALICIOUS, PAPER_BASE_FAIL_PROB,
                PAPER_BASE_MSG_LOSS, RQ1_SIZE_SLICE,
            )
        # The paper presents workload, security, and reliability plots for
        # every topology. The remaining table factors are evaluated on the
        # same three topology families for a consistent paired comparison.
        for topology in PAPER_TOPOLOGIES:
            for item_spawn in PAPER_ITEM_SPAWNING_TIMES:
                add_condition(
                    topology, PAPER_BASE_N_ROOMS, item_spawn,
                    PAPER_N_ROBOTS, PAPER_N_MALICIOUS, PAPER_BASE_FAIL_PROB,
                    PAPER_BASE_MSG_LOSS, RQ1_WORKLOAD_SLICE,
                )
            for n_robots in PAPER_ROBOT_COUNTS:
                add_condition(
                    topology, PAPER_BASE_N_ROOMS, PAPER_BASE_ITEM_SPAWNING_TIME,
                    n_robots, int(round(n_robots * 0.60)), PAPER_BASE_FAIL_PROB,
                    PAPER_BASE_MSG_LOSS, RQ1_SCALE_SLICE,
                )
            for malicious_ratio in PAPER_MALICIOUS_RATIOS:
                add_condition(
                    topology, PAPER_BASE_N_ROOMS, PAPER_BASE_ITEM_SPAWNING_TIME,
                    PAPER_N_ROBOTS, int(round(PAPER_N_ROBOTS * malicious_ratio)),
                    PAPER_BASE_FAIL_PROB, PAPER_BASE_MSG_LOSS, RQ1_SECURITY_SLICE,
                )
            for fail_prob in PAPER_FAIL_PROBS:
                add_condition(
                    topology, PAPER_BASE_N_ROOMS, PAPER_BASE_ITEM_SPAWNING_TIME,
                    PAPER_N_ROBOTS, PAPER_N_MALICIOUS, fail_prob,
                    PAPER_BASE_MSG_LOSS, RQ1_RELIABILITY_SLICE,
                )
            for msg_loss in PAPER_MSG_LOSS_PROBS:
                add_condition(
                    topology, PAPER_BASE_N_ROOMS, PAPER_BASE_ITEM_SPAWNING_TIME,
                    PAPER_N_ROBOTS, PAPER_N_MALICIOUS, PAPER_BASE_FAIL_PROB,
                    msg_loss, RQ1_COMMUNICATION_SLICE,
                )
        conditions = [(*key, slices) for key, slices in sorted(condition_slices.items())]

    combos = []
    for condition_idx, (
        topology, n_rooms, item_spawn, n_robots, n_malicious, fail_prob, msg_loss, slices,
    ) in enumerate(conditions, start=1):
        for rep in range(1, args.repetitions + 1):
            # Fixed mechanisms and DA receive identical random seeds for a
            # paired comparison of the same scenario configuration.
            seed = args.base_seed + condition_idx * 1000 + rep
            for coord_label in coord_labels:
                combos.append({
                    "condition_idx": condition_idx,
                    "analysis_slices": ",".join(sorted(slices)),
                    "rep": rep,
                    "seed": seed,
                    "coord_label": coord_label,
                    "architecture": COORD_TO_ARCH[coord_label],
                    "topology": topology,
                    "n_rooms": n_rooms,
                    "item_spawning_time": item_spawn,
                    "n_robots": n_robots,
                    "malicious_ratio": n_malicious / n_robots,
                    "n_malicious": n_malicious,
                    "fail_prob": fail_prob,
                    "msg_loss": msg_loss,
                })

    if args.condition_indexes:
        selected_indexes = {
            int(value.strip()) for value in args.condition_indexes.split(",") if value.strip()
        }
        if any(index <= 0 for index in selected_indexes):
            raise ValueError("Condition indexes must be positive integers.")
        combos = [combo for combo in combos if combo["condition_idx"] in selected_indexes]
        if not combos:
            raise ValueError("No RQ1 configurations matched --condition-indexes.")
    return combos[: args.limit] if args.limit else combos


def run_id(params: dict) -> str:
    mal_pct = int(round(params["malicious_ratio"] * 100))
    fail_pct = int(round(params["fail_prob"] * 100))
    msg_pct = int(round(params["msg_loss"] * 100))
    policy_suffix = ""
    if params["coord_label"] == "DA":
        policy = str(BASE_CONFIG.get("ADAPTATION_POLICY", "contextual-bandit"))
        reward_version = str(BASE_CONFIG.get("BANDIT_REWARD_VERSION", "default"))
        reward_version = reward_version.replace("-", "").replace("_", "")
        policy_suffix = f"_{policy.replace('-', '')}_{reward_version}"
    return (
        f"c{params['condition_idx']:02d}_r{params['rep']:02d}_"
        f"{params['coord_label']}{policy_suffix}_{params['topology']}_spawn{params['item_spawning_time']}_"
        f"rooms{params['n_rooms']}_bots{params['n_robots']}_mal{mal_pct}_fail{fail_pct}_msg{msg_pct}_"
        f"{RQ1_PROFILE_ID}"
    )


def config_for(params: dict, args: argparse.Namespace, logfile: Path) -> dict:
    cfg = dict(BASE_CONFIG)
    cfg.update({
        "RESULTS_DIR": str(logfile.parent),
        "SIMTIME_LOGFILE": str(logfile.parent / "sim_time.csv"),
        "LOGFILE": str(logfile),
        "SIM_TIME": args.sim_days * 24 * 3600,
        "ARCHITECTURE": params["architecture"],
        "TOPOLOGY_NAME": params["topology"],
        "N_ROOMS": params["n_rooms"],
        "ITEM_SPAWNING_TIME": params["item_spawning_time"],
        "N_ROBOTS": params["n_robots"],
        "N_MALICIOUS": params["n_malicious"],
        "FAIL_PROB": params["fail_prob"],
        "COMM_FAIL_PROB": params["msg_loss"],
        "RANDOM_SEED": params["seed"],
    })
    cfg["PHASES"] = build_fault_windows(
        sim_days=args.sim_days,
        base_fail_prob=params["fail_prob"],
        base_msg_loss=params["msg_loss"],
        n_robots=params["n_robots"],
        n_malicious=params["n_malicious"],
        item_spawning_time=params["item_spawning_time"],
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


def phase_for_time(phases: list[dict], sim_time: float) -> dict:
    for phase in phases:
        if float(phase["start"]) <= sim_time < float(phase["end"]):
            return phase
    return phases[-1] if phases else {}


def analyze_phase_metrics(tasks, phases: list[dict]) -> list[dict]:
    groups: dict[tuple[str, float], dict] = {}
    for task in tasks.values():
        phase = phase_for_time(phases, task.created_at)
        key = (str(phase.get("label", "unknown")), float(phase.get("severity_level", math.nan)))
        group = groups.setdefault(
            key,
            {"created": 0, "delivered": 0, "expired": 0, "latencies": [], "relative_latencies": []},
        )
        group["created"] += 1
        if task.outcome == "deliver":
            group["delivered"] += 1
            latency = task.ended_at - task.created_at
            group["latencies"].append(latency)
            group["relative_latencies"].append(max(0.0, latency - task.minimum_delivery_time))
        elif task.outcome == "expire":
            group["expired"] += 1

    rows = []
    for (phase_label, severity_level), group in groups.items():
        total = group["created"]
        rows.append({
            "phase_label": phase_label,
            "severity_level": severity_level,
            "created": total,
            "delivered": group["delivered"],
            "expired": group["expired"],
            "pending": max(0, total - group["delivered"] - group["expired"]),
            "completion_rate": group["delivered"] / total if total else math.nan,
            "expiration_rate": group["expired"] / total if total else math.nan,
            "avg_latency_s": statistics.mean(group["latencies"]) if group["latencies"] else math.nan,
            "avg_relative_latency_s": (
                statistics.mean(group["relative_latencies"])
                if group["relative_latencies"] else math.nan
            ),
        })
    return rows


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


def completed_run_ids(rows: list[dict], sim_days: int) -> set[str]:
    completed = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if run_id and row.get("status") == "ok":
            try:
                if int(row.get("sim_days", "")) != sim_days:
                    continue
            except (TypeError, ValueError):
                continue
            if not row_matches_current_expiration(row):
                continue
            if str(row.get("log_expire", "")).lower() != "true":
                continue
            if str(row.get("analysis_metric_version", "")) != RQ1_METRIC_VERSION:
                continue
            if (
                str(row.get("coord_label", "")) in {"FD", "DA"}
                and str(row.get("fd_policy_version", "")) != FD_POLICY_VERSION
            ):
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


def execute_run_job(job: dict) -> dict:
    """Run one isolated simulation; the parent process persists campaign CSVs."""
    cfg_path = Path(job["config_path"])
    cfg = job["cfg"]
    try:
        result = simulator.run_with_stats(str(cfg_path), collect_tasks=True)
        return {
            "run_id": job["run_id"],
            "status": "ok",
            "error": "",
            "wall_time": result.wall_time,
            "event_count": result.event_count,
            "metrics": result.metrics,
            "phase_metrics": analyze_phase_metrics(result.tasks, cfg["PHASES"]),
        }
    except BaseException as exc:
        return {
            "run_id": job["run_id"],
            "status": "error",
            "error": str(exc) or exc.__class__.__name__,
            "wall_time": math.nan,
            "event_count": math.nan,
            "metrics": {},
            "phase_metrics": [],
        }


def run_campaign(args: argparse.Namespace) -> None:
    if args.workers < 0:
        raise ValueError("--workers must be zero (automatic) or a positive integer.")
    args.workers = max(1, min(6, os.cpu_count() or 1)) if args.workers == 0 else args.workers
    if not args.machine_label:
        args.machine_label = "mac" if platform.system() == "Darwin" else "workstation"
    configure_bandit_objective(args)
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
        "experiment_profile": RQ1_PROFILE_ID,
        "analysis_metric_version": RQ1_METRIC_VERSION,
        "fd_policy_version": FD_POLICY_VERSION,
        "fd_policy": {
            "patrol_enabled": BASE_CONFIG["FD_PATROL_ENABLED"],
            "inspection_interval_s": BASE_CONFIG["FD_INSPECTION_INTERVAL"],
            "max_patrollers": BASE_CONFIG["FD_MAX_PATROLLERS"],
            "local_search_enabled": BASE_CONFIG["FD_LOCAL_SEARCH_ENABLED"],
            "local_search_probability": BASE_CONFIG["FD_LOCAL_SEARCH_PROBABILITY"],
            "local_search_hops": BASE_CONFIG["FD_LOCAL_SEARCH_HOPS"],
            "local_search_agent_count": BASE_CONFIG["FD_LOCAL_SEARCH_AGENT_COUNT"],
            "local_search_interval_s": BASE_CONFIG["FD_LOCAL_SEARCH_INTERVAL"],
            "requeue_on_failure": BASE_CONFIG["FD_REQUEUE_ON_FAILURE"],
        },
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "total_runs": total_runs,
        "workers": args.workers,
        "coordination_mechanisms": coord_labels,
        "adaptation_policy": BASE_CONFIG["ADAPTATION_POLICY"],
        "bandit_reward_version": BASE_CONFIG.get("BANDIT_REWARD_VERSION", ""),
        "bandit_reward_parameters": {
            "objective_mode": BASE_CONFIG.get("BANDIT_OBJECTIVE_MODE"),
            "completion_weight": BASE_CONFIG.get("BANDIT_COMPLETION_WEIGHT"),
            "completion_target": BASE_CONFIG.get("BANDIT_COMPLETION_TARGET"),
            "minimum_terminal_outcomes": BASE_CONFIG.get("BANDIT_MIN_TERMINAL_OUTCOMES"),
            "feedback_window_s": BASE_CONFIG.get("BANDIT_FEEDBACK_WINDOW"),
            "latency_reference_s": BASE_CONFIG.get("LATENCY_THRESHOLD_HIGH"),
            "switch_penalty": BASE_CONFIG.get("BANDIT_SWITCH_PENALTY"),
            "ucb_alpha": BASE_CONFIG.get("BANDIT_UCB_ALPHA"),
            "initial_samples_per_action": BASE_CONFIG.get("BANDIT_INITIAL_SAMPLES_PER_ACTION"),
        },
        "bandit_context_parameters": {
            "features": list(FEATURE_NAMES),
            "arrival_reference_tasks_per_hour": BASE_CONFIG.get("BANDIT_CREATED_TASKS_REF"),
            "failure_reference_per_robot_hour": BASE_CONFIG.get("BANDIT_FAILURE_REF"),
            "suspicion_reference_signals_per_hour": BASE_CONFIG.get("BANDIT_SUSPICION_REF"),
            "network_probes_per_check": BASE_CONFIG.get("NETWORK_PROBE_SAMPLES_PER_CHECK"),
            "warmup_samples_per_action_context": BASE_CONFIG.get("BANDIT_CONTEXT_MIN_SAMPLES_PER_ACTION"),
            "context_bin_threshold": BASE_CONFIG.get("BANDIT_CONTEXT_BIN_THRESHOLD"),
        },
        "analysis_slices": {
            RQ1_TOPOLOGY_SLICE: {
                "topology_types": PAPER_TOPOLOGY_TYPES,
                "n_rooms": PAPER_BASE_N_ROOMS,
            },
            RQ1_SIZE_SLICE: {
                "topology_type": "ring",
                "n_rooms": PAPER_ROOM_COUNTS,
            },
            RQ1_WORKLOAD_SLICE: {
                "topologies": PAPER_TOPOLOGIES,
                "item_spawning_times": PAPER_ITEM_SPAWNING_TIMES,
                "n_robots": PAPER_N_ROBOTS,
                "n_malicious": PAPER_N_MALICIOUS,
                "fail_prob": PAPER_BASE_FAIL_PROB,
                "msg_loss": PAPER_BASE_MSG_LOSS,
            },
            RQ1_SCALE_SLICE: {
                "topologies": PAPER_TOPOLOGIES,
                "n_robots": PAPER_ROBOT_COUNTS,
                "malicious_ratio": 0.60,
            },
            RQ1_SECURITY_SLICE: {
                "topologies": PAPER_TOPOLOGIES,
                "item_spawning_time": PAPER_BASE_ITEM_SPAWNING_TIME,
                "malicious_ratios": PAPER_MALICIOUS_RATIOS,
                "fail_prob": PAPER_BASE_FAIL_PROB,
                "msg_loss": PAPER_BASE_MSG_LOSS,
            },
            RQ1_RELIABILITY_SLICE: {
                "topologies": PAPER_TOPOLOGIES,
                "item_spawning_time": PAPER_BASE_ITEM_SPAWNING_TIME,
                "n_malicious": PAPER_N_MALICIOUS,
                "fail_probs": PAPER_FAIL_PROBS,
                "msg_loss": PAPER_BASE_MSG_LOSS,
            },
            RQ1_COMMUNICATION_SLICE: {
                "topologies": PAPER_TOPOLOGIES,
                "item_spawning_time": PAPER_BASE_ITEM_SPAWNING_TIME,
                "n_malicious": PAPER_N_MALICIOUS,
                "fail_prob": PAPER_BASE_FAIL_PROB,
                "message_loss_probs": PAPER_MSG_LOSS_PROBS,
            },
        },
        "expiration_time": BASE_CONFIG["EXPIRATION_TIME"],
        "expiration_distribution": BASE_CONFIG["EXPIRATION_DISTR"],
        "importance_probabilities": BASE_CONFIG["IMPORTANCE_PROBABILITIES"],
        "daily_fault_windows": [
            f"{label}: {start:02d}h-{end:02d}h (severity={severity:.2f})"
            for label, start, end, severity in DAILY_SEVERITY_SEGMENTS
        ],
    "severity_scaling": {
        "operating_regimes": "daily severity rise and symmetric recovery",
        "malicious_agents": "baseline plus 0, 5, 10, or 15 percentage points",
        "agent_failure_probability": "baseline multiplied by 1.00, 1.25, 1.50, or 1.75",
        "task_interarrival_time": "baseline multiplied by 1.00, 0.90, 0.80, or 0.70",
        "message_loss_probability": "baseline multiplied by 1.00, 1.25, 1.50, or 1.75",
    },
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
    phase_metrics = [] if args.force else read_rows(PHASE_METRICS_PATH)
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
    completed = completed_run_ids(rows, args.sim_days)
    started_at = time.time()

    jobs = []
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
        jobs.append({
            "idx": idx,
            "run_id": rid,
            "params": params,
            "cfg": cfg,
            "config_path": str(cfg_path),
            "logfile": str(logfile),
            "force": args.force,
        })

    def persist_result(job: dict, result: dict, completed_count: int) -> None:
        nonlocal rows, errors, phase_metrics
        params = job["params"]
        cfg = job["cfg"]
        rid = job["run_id"]
        if result["status"] == "error":
            errors.append({
                **params,
                "run_id": rid,
                "config_path": job["config_path"],
                "logfile": job["logfile"],
                "error": result["error"],
            })
            print(f"[{completed_count}/{len(jobs)}] {rid} ERROR: {result['error']}", flush=True)
        else:
            print(f"[{completed_count}/{len(jobs)}] {rid} completed", flush=True)

        row = {
            "run_id": rid,
            "status": result["status"],
            "error": result["error"],
            "config_path": job["config_path"],
            "logfile": job["logfile"],
            "coord_label": params["coord_label"],
            "analysis_slices": params["analysis_slices"],
            "experiment_profile": RQ1_PROFILE_ID,
            "analysis_metric_version": RQ1_METRIC_VERSION,
            "fd_policy_version": FD_POLICY_VERSION,
            "fd_patrol_enabled": cfg["FD_PATROL_ENABLED"],
            "fd_inspection_interval_s": cfg["FD_INSPECTION_INTERVAL"],
            "fd_max_patrollers": cfg["FD_MAX_PATROLLERS"],
            "fd_local_search_enabled": cfg["FD_LOCAL_SEARCH_ENABLED"],
            "fd_local_search_probability": cfg["FD_LOCAL_SEARCH_PROBABILITY"],
            "fd_local_search_hops": cfg["FD_LOCAL_SEARCH_HOPS"],
            "fd_local_search_agent_count": cfg["FD_LOCAL_SEARCH_AGENT_COUNT"],
            "fd_local_search_interval_s": cfg["FD_LOCAL_SEARCH_INTERVAL"],
            "fd_requeue_on_failure": cfg["FD_REQUEUE_ON_FAILURE"],
            "architecture": params["architecture"],
            "topology": params["topology"],
            "n_rooms": params["n_rooms"],
            "adaptation_policy": cfg.get("ADAPTATION_POLICY", ""),
            "bandit_reward_version": cfg.get("BANDIT_REWARD_VERSION", ""),
            "bandit_objective_mode": cfg.get("BANDIT_OBJECTIVE_MODE", ""),
            "bandit_completion_weight": cfg.get("BANDIT_COMPLETION_WEIGHT", ""),
            "rep": params["rep"],
            "seed": params["seed"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss": params["msg_loss"],
            "expiration_time_low_s": cfg["EXPIRATION_TIME"][0],
            "expiration_time_medium_s": cfg["EXPIRATION_TIME"][1],
            "expiration_time_high_s": cfg["EXPIRATION_TIME"][2],
            "log_expire": cfg["LOG_EXPIRE"],
            "sim_days": args.sim_days,
            "wall_time_s": result["wall_time"],
            "event_count": result["event_count"],
            # Wall time and adaptation overhead depend on the host and on how
            # many simulations shared it, and RQ3 reads both from this file.
            # Recording them keeps timings from different machines separable.
            "machine_label": args.machine_label,
            "machine_cpu_count": os.cpu_count(),
            "workers": args.workers,
            **result["metrics"],
        }
        rows = replace_row(rows, row)
        phase_metrics = [metric for metric in phase_metrics if metric.get("run_id") != rid]
        phase_metrics.extend({
            "run_id": rid,
            "experiment_profile": RQ1_PROFILE_ID,
            "analysis_metric_version": RQ1_METRIC_VERSION,
            "fd_policy_version": FD_POLICY_VERSION,
            "fd_patrol_enabled": cfg["FD_PATROL_ENABLED"],
            "fd_inspection_interval_s": cfg["FD_INSPECTION_INTERVAL"],
            "fd_max_patrollers": cfg["FD_MAX_PATROLLERS"],
            "fd_local_search_enabled": cfg["FD_LOCAL_SEARCH_ENABLED"],
            "fd_local_search_probability": cfg["FD_LOCAL_SEARCH_PROBABILITY"],
            "fd_local_search_hops": cfg["FD_LOCAL_SEARCH_HOPS"],
            "fd_local_search_agent_count": cfg["FD_LOCAL_SEARCH_AGENT_COUNT"],
            "fd_local_search_interval_s": cfg["FD_LOCAL_SEARCH_INTERVAL"],
            "coord_label": params["coord_label"],
            "topology": params["topology"],
            "n_rooms": params["n_rooms"],
            "analysis_slices": params["analysis_slices"],
            "rep": params["rep"],
            "seed": params["seed"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "fail_prob": params["fail_prob"],
            "msg_loss": params["msg_loss"],
            **metric,
        } for metric in result["phase_metrics"])
        write_rows(RESULTS_ROOT / "runs.csv", rows)
        write_rows(PHASE_METRICS_PATH, phase_metrics)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    print(f"Launching {len(jobs)} runs with {min(args.workers, len(jobs))} worker processes.", flush=True)
    if not jobs:
        print("No pending runs.", flush=True)
    elif args.workers == 1:
        for completed_count, job in enumerate(jobs, start=1):
            print(f"[{completed_count}/{len(jobs)}] {job['run_id']} started", flush=True)
            result = execute_run_job(job)
            persist_result(job, result, completed_count)
            if result["status"] == "error" and args.fail_fast:
                raise RuntimeError(result["error"])
    else:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as executor:
            future_to_job = {executor.submit(execute_run_job, job): job for job in jobs}
            for completed_count, future in enumerate(as_completed(future_to_job), start=1):
                job = future_to_job[future]
                result = future.result()
                persist_result(job, result, completed_count)
                if result["status"] == "error" and args.fail_fast:
                    for pending in future_to_job:
                        pending.cancel()
                    raise RuntimeError(result["error"])

    cleanup_transient_artifacts()

    elapsed = time.time() - started_at
    print("=" * 80)
    print(f"RQ1 campaign completed in {elapsed:.2f}s wall-clock.")
    print(f"Run-level CSV:      {RESULTS_ROOT / 'runs.csv'}")
    print(f"Phase metrics CSV:  {PHASE_METRICS_PATH}")
    if errors:
        print(f"Errors CSV:         {RESULTS_ROOT / 'errors.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
