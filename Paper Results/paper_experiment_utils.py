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
import shutil
import statistics
import sys
from pathlib import Path
from typing import Any, Optional


PAPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PAPER_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sim import simulator  # noqa: E402


COORD_TO_ARCH = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
    "DA": "dynamic-adaptation",
}

ARCH_TO_COORD = {arch: label for label, arch in COORD_TO_ARCH.items()}


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
        "SIMTIME_LOGFILE": str(results_root / "sim_time.csv"),
        "LOGFILE": str(logfile),
        "SIM_TIME": sim_days * 24 * 3600,
        "ARCHITECTURE": architecture,
        "RANDOM_SEED": seed,
    })
    cfg.update(updates)
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


def completed_run_ids(rows: list[dict[str, Any]]) -> set[str]:
    completed: set[str] = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if not run_id or row.get("status") != "ok":
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
    item_spawning_time: float,
    n_robots: int,
    malicious_ratio: float,
    fail_prob: float,
    msg_loss_prob: float,
) -> Optional[dict[str, Any]]:
    rq1_runs = read_rows(PAPER_ROOT / "RQ1" / "runs.csv")
    for row in rq1_runs:
        logfile = Path(str(row.get("logfile", "")))
        if row.get("status") != "ok" or not logfile.exists():
            continue
        if row.get("coord_label") != coord_label:
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
        if not float_matches(row.get("msg_loss_prob"), msg_loss_prob, tolerance=0.005):
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


def analyze_log(logfile: Path, sim_time: float) -> dict[str, Any]:
    create_times: dict[int, float] = {}
    delivery_latencies: list[float] = []
    events: dict[str, int] = {}
    switches: list[tuple[float, str]] = []
    last_time = 0.0
    row_count = 0

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
