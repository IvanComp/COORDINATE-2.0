#!/usr/bin/env python3
"""
Shared helpers for the paper experiment runners.

The runners in this directory intentionally write plain CSV files so the paper
figures can be regenerated from simple, inspectable artifacts.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import shutil
import statistics
import sys
from pathlib import Path
from typing import Any, Optional


PAPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PAPER_ROOT.parent


def resolve_worker_count(requested: int, *, cap: int = 6) -> int:
    """Resolve ``--workers`` while avoiding excessive simulator contention.

    A value of zero selects a conservative number of independent simulation
    processes from the CPUs visible to the current machine.  An explicit value
    remains available for clusters and performance experiments.
    """
    if requested < 0:
        raise ValueError("--workers must be zero (automatic) or a positive integer.")
    if requested:
        return requested
    return max(1, min(cap, os.cpu_count() or 1))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sim import simulator  # noqa: E402
from sim.env_maps import topologyName_dict  # noqa: E402
from sim.rtlola_monitor import resolve_rtlola_binary  # noqa: E402


COORD_TO_ARCH = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
    "DA": "dynamic-adaptation",
}

ARCH_TO_COORD = {arch: label for label, arch in COORD_TO_ARCH.items()}
FD_POLICY_VERSION = "legacy-local-retry-v7"

EXTENDED_ROOM_COUNTS = [4, 9, 16, 25, 36, 49]
EXTENDED_ITEM_SPAWNING_TIMES = [90, 120, 150, 180, 210, 240, 270, 300]
EXTENDED_ROBOT_COUNTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
EXTENDED_NOMINAL_TOPOLOGY = "ring"
EXTENDED_NOMINAL_ROOMS = 25
EXTENDED_NOMINAL_SPAWN = 120
EXTENDED_NOMINAL_ROBOTS = 20
EXTENDED_NOMINAL_MALICIOUS = 12
EXTENDED_NOMINAL_FAIL_PROB = 0.09
EXTENDED_NOMINAL_MSG_LOSS = 0.03


BASE_CONFIG = {
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
    "EXPIRATION_TIME": [28800, 7200, 3600],
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
    "COORDINATOR_SERVICE_TIME": 0.25,
    "COORDINATOR_FAKE_REQUEST_SERVICE_TIME": 0.25,
    "COORDINATOR_FAILURE_PROB": 0.0,
    "COORDINATOR_AVAILABLE": True,
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
    "ADAPTATION_CHECK_INTERVAL": 10 * 60.0,
    "ADAPTATION_WINDOW": 60 * 60.0,
    "BANDIT_FEEDBACK_WINDOW": 60 * 60.0,
    "ADAPTATION_MIN_SWITCH_INTERVAL": 60 * 60.0,
    "LATENCY_THRESHOLD_LOW": 10 * 60.0,
    "LATENCY_THRESHOLD_HIGH": 40 * 60.0,
    "RTLOLA_METRIC_TIMEOUT": 0.05,
}


def extended_scenario_updates(
    *,
    topology_type: str,
    n_rooms: int,
    n_robots: int,
    n_malicious: int,
    item_spawning_time: float,
    fail_prob: float,
    msg_loss_prob: float,
    comp_time: float = 0.03,
    comm_time: float = 0.03,
) -> dict[str, Any]:
    """Return the common extended campaign configuration used by RQ3 and RQ4."""
    return {
        "TOPOLOGY_NAME": f"{topology_type}{n_rooms}",
        "N_ROOMS": n_rooms,
        "SOURCE": 0,
        "TARGETS": -1,
        "ITEM_SPAWNING_TIME": item_spawning_time,
        "IMPORTANCE_PROBABILITIES": [0.55, 0.25, 0.20],
        "EXPIRATION_TIME": [28800, 14400, 7200],
        "EXPIRATION_DISTR": ["deterministic", "deterministic", "deterministic"],
        "N_ROBOTS": n_robots,
        "N_MALICIOUS": n_malicious,
        "FAIL_PROB": fail_prob,
        "COMM_FAIL_PROB": msg_loss_prob,
        "COMP_TIME": comp_time,
        "COMM_TIME": comm_time,
        "ADAPTATION_CHECK_INTERVAL": 60 * 60.0,
        "ADAPTATION_WINDOW": 60 * 60.0,
        "BANDIT_FEEDBACK_WINDOW": 60 * 60.0,
        "ADAPTATION_MIN_SWITCH_INTERVAL": 60 * 60.0,
        "ADAPTATION_PERSISTENCE_CHECKS": 1,
        "BANDIT_EXPLORATION_EPSILON": 0.02,
        "BANDIT_MIN_EXPLORATION_EPSILON": 0.0,
        "BANDIT_EXPLORATION_BYPASS_PERSISTENCE": False,
        "FD_PATROL_ENABLED": False,
        "FD_MAX_PATROLLERS": 0,
        "FD_LOCAL_SEARCH_ENABLED": False,
        "FD_LOCAL_SEARCH_PROBABILITY": 0.0,
        "FD_LOCAL_SEARCH_HOPS": 3,
        "FD_LOCAL_SEARCH_AGENT_COUNT": 0,
        "FD_LOCAL_SEARCH_INTERVAL": 15 * 60.0,
        "FD_REQUEUE_ON_FAILURE": True,
    }


def build_extended_daily_phases(
    *,
    sim_days: int,
    base_fail_prob: float,
    base_msg_loss: float,
    n_robots: int,
    n_malicious: int,
    item_spawning_time: float,
) -> list[dict[str, Any]]:
    """Build the shared daily triangular severity profile for the extended campaign."""
    segments = [
        ("severity_0", 0, 4, 1.00, 1.00, 1.00, 0.00),
        ("severity_25", 4, 8, 1.25, 1.25, 0.90, 0.05),
        ("severity_50", 8, 12, 1.50, 1.50, 0.80, 0.10),
        ("severity_75", 12, 16, 1.75, 1.75, 0.70, 0.15),
        ("severity_50_recovery", 16, 20, 1.50, 1.50, 0.80, 0.10),
        ("severity_25_recovery", 20, 24, 1.25, 1.25, 0.90, 0.05),
    ]
    phases: list[dict[str, Any]] = []
    day_seconds = 24 * 3600
    for day in range(sim_days):
        day_start = day * day_seconds
        for label, start_hour, end_hour, fail_scale, msg_scale, spawn_scale, malicious_delta in segments:
            phases.append({
                "label": label,
                "start": day_start + start_hour * 3600,
                "end": day_start + end_hour * 3600,
                "N_MALICIOUS": max(0, min(n_robots, int(round(n_malicious + malicious_delta * n_robots)))),
                "FAIL_PROB": min(1.0, base_fail_prob * fail_scale),
                "COMM_FAIL_PROB": min(1.0, base_msg_loss * msg_scale),
                "ITEM_SPAWNING_TIME": max(30.0, item_spawning_time * spawn_scale),
                "COORDINATOR_SERVICE_TIME": 0.25,
                "COORDINATOR_FAILURE_PROB": 0.0,
                "COORDINATOR_AVAILABLE": True,
            })
    return phases


def ensure_rtlola_available() -> str:
    script_dir = PROJECT_ROOT / "sim"
    resolved = resolve_rtlola_binary(str(PROJECT_ROOT), str(script_dir))
    if not resolved:
        raise RuntimeError(
            "No usable RTLola binary found for dynamic adaptation. "
            f"python={sys.executable} "
            f"VIRTUAL_ENV={os.environ.get('VIRTUAL_ENV', '')} "
            "Run 'bash scripts/install_rtlola_venv.sh' inside the same environment "
            "or export RTLOLA_BINARY_PATH=/absolute/path/to/rtlola-cli."
        )
    return resolved


def ensure_result_dirs(results_root: Path) -> tuple[Path, Path]:
    raw_logs_dir = results_root / "raw_logs"
    configs_dir = results_root / "configs"
    for directory in [results_root, raw_logs_dir, configs_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    return raw_logs_dir, configs_dir


def cleanup_transient_artifacts(results_root: Path) -> None:
    for name in ("raw_logs", "configs"):
        path = results_root / name
        if path.exists():
            shutil.rmtree(path)
    design_path = results_root / "experiment_design.json"
    if design_path.exists():
        design_path.unlink()


def malicious_count(n_robots: int, malicious_ratio: float) -> int:
    return int(round(n_robots * malicious_ratio))


def build_paper_daily_phases(
    *,
    sim_days: int,
    base_fail_prob: float,
    base_msg_loss: float,
    base_recovery_time: float,
    n_malicious: int,
    item_spawning_time: float,
    stress_multiplier: float = 1.2,
    stress_start_hour: float = 12.0,
    stress_end_hour: float = 24.0,
    normal_label: str = "normal",
    stress_label: str = "daily_stress",
) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    day_seconds = 24 * 3600
    for day in range(sim_days):
        day_start = day * day_seconds
        day_end = day_start + day_seconds
        stress_start = min(max(day_start + stress_start_hour * 3600, day_start), day_end)
        stress_end = min(max(day_start + stress_end_hour * 3600, stress_start), day_end)

        normal = {
            "label": normal_label,
            "start": day_start,
            "end": stress_start,
            "N_MALICIOUS": n_malicious,
            "FAIL_PROB": base_fail_prob,
            "COMM_FAIL_PROB": base_msg_loss,
            "RECOVERY_TIME": base_recovery_time,
            "ITEM_SPAWNING_TIME": item_spawning_time,
        }
        stress = {
            "label": stress_label,
            "start": stress_start,
            "end": stress_end,
            "N_MALICIOUS": n_malicious,
            "FAIL_PROB": min(1.0, stress_multiplier * base_fail_prob),
            "COMM_FAIL_PROB": min(1.0, stress_multiplier * base_msg_loss),
            "RECOVERY_TIME": stress_multiplier * base_recovery_time,
            "ITEM_SPAWNING_TIME": item_spawning_time,
        }
        recovery = dict(normal)
        recovery.update({"start": stress_end, "end": day_end})
        phases.extend([normal, stress, recovery])

    return [phase for phase in phases if phase["end"] > phase["start"]]


def phase_for_time(phases: list[dict[str, Any]], sim_time: float) -> dict[str, Any]:
    for phase in phases:
        if float(phase["start"]) <= sim_time < float(phase["end"]):
            return phase
    return {}


def config_with_paths(
    *,
    results_root: Path,
    logfile: Path,
    architecture: str,
    seed: int,
    sim_days: int,
    updates: dict[str, Any],
    phases: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    cfg = dict(BASE_CONFIG)
    cfg.update({
        "RESULTS_DIR": str(logfile.parent),
        "SIMTIME_LOGFILE": str(logfile.parent / "sim_time.csv"),
        "LOGFILE": str(logfile),
        "SIM_TIME": sim_days * 24 * 3600,
        "ARCHITECTURE": architecture,
        "RANDOM_SEED": seed,
    })
    cfg.update(updates)
    if architecture == "dynamic-adaptation" and "RTLOLA_BINARY_PATH" not in cfg:
        cfg["RTLOLA_BINARY_PATH"] = ensure_rtlola_available()
    if phases is not None:
        cfg["PHASES"] = phases
    return cfg


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _csv_open(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode, newline="")
    return path.open(mode, newline="")


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with _csv_open(path, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        gz_path = path.with_name(path.name + ".gz")
        if not gz_path.exists():
            return []
        path = gz_path
    with _csv_open(path, "rt") as f:
        return list(csv.DictReader(f))


def expiration_metadata(cfg: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    source = cfg or BASE_CONFIG
    values = source["EXPIRATION_TIME"]
    return {
        "expiration_time_low_s": values[0],
        "expiration_time_medium_s": values[1],
        "expiration_time_high_s": values[2],
        "log_expire": bool(source.get("LOG_EXPIRE", False)),
    }


def row_logs_expiration(row: dict[str, Any]) -> bool:
    return str(row.get("log_expire", "")).lower() == "true"


def row_matches_current_expiration(row: dict[str, Any]) -> bool:
    if str(row.get("fd_policy_version", "")) != FD_POLICY_VERSION:
        return False
    expected = expiration_metadata()
    for key, expected_value in expected.items():
        try:
            actual_value = float(row.get(key, ""))
        except (TypeError, ValueError):
            return False
        if int(round(actual_value)) != int(round(float(expected_value))):
            return False
    return True


def completed_run_ids(rows: list[dict[str, Any]]) -> set[str]:
    completed: set[str] = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if not run_id or row.get("status") != "ok":
            continue
        if not row_matches_current_expiration(row):
            continue
        completed.add(run_id)
    return completed


def replace_row(rows: list[dict[str, Any]], row: dict[str, Any], key: str = "run_id") -> list[dict[str, Any]]:
    value = row.get(key)
    return [existing for existing in rows if existing.get(key) != value] + [row]


def drop_rows_for_run(rows: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("run_id") != run_id]


def float_matches(left: Any, right: Any, tolerance: float = 1e-9) -> bool:
    left_value = safe_float(left)
    right_value = safe_float(right)
    if math.isnan(left_value) or math.isnan(right_value):
        return False
    return abs(left_value - right_value) <= tolerance


def int_matches(left: Any, right: Any) -> bool:
    left_value = safe_float(left)
    right_value = safe_float(right)
    if math.isnan(left_value) or math.isnan(right_value):
        return False
    return int(round(left_value)) == int(round(right_value))


def find_matching_rq1_row(
    *,
    coord_label: str,
    rep: int,
    topology: str | None = None,
    n_rooms: int | None = None,
    item_spawning_time: float,
    n_robots: int,
    malicious_ratio: float,
    fail_prob: float,
    msg_loss_prob: float,
    comp_time: float = 0.03,
    comm_time: float = 0.03,
) -> Optional[dict[str, Any]]:
    rq1_runs = read_rows(PAPER_ROOT / "RQ1" / "runs.csv")
    for row in rq1_runs:
        logfile = Path(str(row.get("logfile", "")))
        if row.get("status") != "ok" or not logfile.exists():
            continue
        if not row_matches_current_expiration(row):
            continue
        if not row_logs_expiration(row):
            continue
        if row.get("coord_label") != coord_label:
            continue
        if topology is not None and str(row.get("topology", "")) != topology:
            continue
        if n_rooms is not None and not int_matches(row.get("n_rooms"), n_rooms):
            continue
        if not int_matches(row.get("rep"), rep):
            continue
        if not int_matches(row.get("item_spawning_time"), item_spawning_time):
            continue
        if not int_matches(row.get("n_robots"), n_robots):
            continue
        if not float_matches(row.get("malicious_ratio"), malicious_ratio, tolerance=0.005):
            continue
        if not float_matches(row.get("fail_prob"), fail_prob, tolerance=0.005):
            continue
        row_msg_loss = row.get("msg_loss_prob", row.get("msg_loss"))
        if not float_matches(row_msg_loss, msg_loss_prob, tolerance=0.005):
            continue
        if not float_matches(row.get("comp_time", 0.03), comp_time, tolerance=0.0005):
            continue
        if not float_matches(row.get("comm_time", 0.03), comm_time, tolerance=0.0005):
            continue
        return row
    return None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return ordered[idx]


def safe_float(value: Any) -> float:
    if value in (None, "", "nan", "None"):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024) if path.exists() else 0.0


def read_overhead_samples(logfile: Path) -> list[dict[str, Any]]:
    overhead_path = logfile.with_name(logfile.stem + "_overhead.csv")
    if not overhead_path.exists():
        return []
    with overhead_path.open(newline="") as f:
        return list(csv.DictReader(f))


def overhead_metrics(logfile: Path) -> dict[str, Any]:
    samples = read_overhead_samples(logfile)
    if not samples:
        return {
            "adapt_checks": 0,
            "adapt_switches_overhead": 0,
            "adapt_overhead_ms_total": 0.0,
            "adapt_overhead_ms_mean": math.nan,
            "adapt_overhead_ms_p95": math.nan,
            "rtlola_query_ms_mean": math.nan,
            "scoring_ms_mean": math.nan,
            "overhead_trace_size_mb": 0.0,
        }

    def values(name: str) -> list[float]:
        return [v for v in (safe_float(row.get(name)) for row in samples) if not math.isnan(v)]

    total_vals = values("total_overhead_ms")
    rtlola_vals = values("rtlola_query_ms")
    scoring_vals = values("scoring_ms")
    overhead_path = logfile.with_name(logfile.stem + "_overhead.csv")

    return {
        "adapt_checks": len(samples),
        "adapt_switches_overhead": sum(1 for row in samples if str(row.get("switched")) == "True"),
        "adapt_overhead_ms_total": sum(total_vals),
        "adapt_overhead_ms_mean": statistics.mean(total_vals) if total_vals else math.nan,
        "adapt_overhead_ms_p95": percentile(total_vals, 0.95),
        "rtlola_query_ms_mean": statistics.mean(rtlola_vals) if rtlola_vals else math.nan,
        "scoring_ms_mean": statistics.mean(scoring_vals) if scoring_vals else math.nan,
        "overhead_trace_size_mb": file_size_mb(overhead_path),
    }


def minimum_delivery_time(cfg: dict, destination: int) -> float:
    """Return the ideal source-to-destination delivery time used in the paper.

    Relative latency subtracts this floor from the observed latency, so a run on
    a large topology is not penalised for the distance its agents must cover.
    """
    topology = topologyName_dict[str(cfg["TOPOLOGY_NAME"])]
    source = int(cfg.get("SOURCE", 0))
    if destination == source:
        hops = 0
    else:
        queue = [(source, 0)]
        visited = {source}
        hops = None
        while queue:
            room, distance = queue.pop(0)
            for neighbor in topology[room]:
                if neighbor == destination:
                    hops = distance + 1
                    queue = []
                    break
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
    if hops is None:
        raise ValueError(f"Destination {destination} is unreachable in {cfg['TOPOLOGY_NAME']}.")
    return float(cfg["LOAD_TIME"]) + hops * float(cfg["MOVEMENT_TIME"]) + float(cfg["DROP_TIME"])


def analyze_log(logfile: Path, sim_time: float, cfg: Optional[dict] = None) -> dict[str, Any]:
    """Summarise one simulation trace.

    Pass ``cfg`` to also record ``avg_relative_latency_s``. Without it the column
    is still written as NaN so every RQ shares one result schema.
    """
    create_events: dict[int, tuple[float, int]] = {}
    delivery_latencies: list[float] = []
    relative_delivery_latencies: list[float] = []
    minimum_times: dict[int, float] = {}
    events: dict[str, int] = {}
    switches: list[tuple[float, str]] = []
    last_time = 0.0
    row_count = 0

    def minimum_time(destination: int) -> float:
        if destination not in minimum_times:
            minimum_times[destination] = minimum_delivery_time(cfg, destination)
        return minimum_times[destination]

    with logfile.open(newline="") as f:
        for row in csv.DictReader(f):
            row_count += 1
            event = row.get("event", "")
            item_id = int(row.get("itemId", -1) or -1)
            sim_t = safe_float(row.get("simTime"))
            if math.isnan(sim_t):
                sim_t = 0.0
            last_time = max(last_time, sim_t)
            events[event] = events.get(event, 0) + 1

            if event == "create" and item_id >= 0:
                create_events[item_id] = (sim_t, int(row.get("destination", -1) or -1))
            elif event == "deliver" and item_id in create_events:
                created_at, destination = create_events[item_id]
                latency = sim_t - created_at
                delivery_latencies.append(latency)
                if cfg is not None and destination >= 0:
                    relative_delivery_latencies.append(max(0.0, latency - minimum_time(destination)))
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
        "avg_relative_latency_s": (
            statistics.mean(relative_delivery_latencies) if relative_delivery_latencies else math.nan
        ),
        "median_latency_s": statistics.median(delivery_latencies) if delivery_latencies else math.nan,
        "p95_latency_s": percentile(delivery_latencies, 0.95),
        "max_latency_s": max(delivery_latencies) if delivery_latencies else math.nan,
        "switch_count": len(switches),
        "fd_switch_count": sum(1 for _, arch in switches if arch == "decentralized"),
        "sd_switch_count": sum(1 for _, arch in switches if arch == "semi-decentralized"),
        "ce_switch_count": sum(1 for _, arch in switches if arch == "centralized-impprox"),
        "first_switch_time": switches[0][0] if switches else math.nan,
        "last_sim_time": last_time,
        "trace_rows": row_count,
        "trace_size_mb": file_size_mb(logfile),
    }
    metrics.update(overhead_metrics(logfile))
    return metrics


def extract_switches(logfile: Path) -> list[dict[str, Any]]:
    switches: list[dict[str, Any]] = []
    if not logfile.exists():
        return switches
    with logfile.open(newline="") as f:
        for row in csv.DictReader(f):
            event = row.get("event", "")
            if not event.startswith("switch_architecture_"):
                continue
            sim_time = safe_float(row.get("simTime"))
            arch = event.replace("switch_architecture_", "")
            switches.append({
                "sim_time": sim_time,
                "selected_architecture": arch,
                "selected_coord_label": ARCH_TO_COORD.get(arch, arch),
            })
    return switches


def nearest_overhead_sample(samples: list[dict[str, Any]], sim_time: float) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_distance = math.inf
    for sample in samples:
        sample_time = safe_float(sample.get("sim_time"))
        if math.isnan(sample_time):
            continue
        distance = abs(sample_time - sim_time)
        if distance < best_distance:
            best = sample
            best_distance = distance
    return best


def summarise_rows(
    rows: list[dict[str, Any]],
    *,
    group_fields: list[str],
    metric_fields: list[str],
    status_field: str = "status",
) -> list[dict[str, Any]]:
    ok_rows = [row for row in rows if row.get(status_field) in (None, "", "ok")]
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in ok_rows:
        key = tuple(row.get(field) for field in group_fields)
        grouped.setdefault(key, []).append(row)

    summary: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        record = dict(zip(group_fields, key))
        record["runs"] = len(group)
        for metric in metric_fields:
            values = [safe_float(row.get(metric)) for row in group]
            values = [value for value in values if not math.isnan(value)]
            record[f"{metric}_mean"] = statistics.mean(values) if values else math.nan
            record[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
            record[f"{metric}_p95"] = percentile(values, 0.95) if values else math.nan
        summary.append(record)
    return summary


def run_or_analyze(
    *,
    cfg_path: Path,
    logfile: Path,
    sim_time: float,
    force: bool,
) -> tuple[dict[str, Any], float, float]:
    wall_time = math.nan
    event_count = math.nan
    if logfile.exists() and not force:
        print("  existing log found; analysing without re-running", flush=True)
    else:
        _, wall_time, event_count = simulator.run(str(cfg_path))
    metrics = analyze_log(logfile, sim_time)
    return metrics, wall_time, event_count
