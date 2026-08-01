#!/usr/bin/env python3
"""
RQ4 runner: practical scalability limits of COORDINATE 2.0.

RQ4 focuses on execution time, memory usage, event throughput, and trace size as
simulation duration, fleet size, and workload increase. Each run is executed in
an isolated Python subprocess so peak RSS can be measured per simulation.

Default campaign per hardware profile:
    Extended one-factor-at-a-time sweeps of workload, fleet size, and topology
    size across the four coordination mechanisms.

Run examples:
    python "Paper Results/run_rq4_experiments.py" --dry-run
    nohup python "Paper Results/run_rq4_experiments.py" > "Paper Results/RQ4/rq4.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ4/runs.csv.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    BASE_CONFIG,
    COORD_TO_ARCH,
    PAPER_ROOT,
    PROJECT_ROOT,
    analyze_log,
    build_extended_daily_phases,
    cleanup_transient_artifacts,
    config_with_paths,
    completed_run_ids,
    ensure_rtlola_available,
    ensure_result_dirs,
    expiration_metadata,
    EXTENDED_ITEM_SPAWNING_TIMES,
    EXTENDED_NOMINAL_FAIL_PROB,
    EXTENDED_NOMINAL_MSG_LOSS,
    EXTENDED_NOMINAL_ROOMS,
    EXTENDED_NOMINAL_ROBOTS,
    EXTENDED_NOMINAL_SPAWN,
    EXTENDED_NOMINAL_TOPOLOGY,
    EXTENDED_ROBOT_COUNTS,
    EXTENDED_ROOM_COUNTS,
    extended_scenario_updates,
    file_size_mb,
    malicious_count,
    read_rows,
    replace_row,
    safe_float,
    resolve_worker_count,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ4"
RQ4_EXPERIMENT_PROFILE = "extended-wallclock-v2"
# RQ4 compares two hardware profiles and two mechanisms on the nominal
# configuration of the paper. No parameter is swept: the only factors are the
# execution platform and the coordination mechanism.
DEFAULT_SIM_DAYS = [90]
NOMINAL_SIM_DAYS = 90
DEFAULT_COORD_LABELS = ["CE", "DA"]
SUBPROCESS_MARKER = "__RQ4_RESULT__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ4 scalability experiments.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per configuration.")
    parser.add_argument(
        "--sim-days",
        default=None,
        help="Comma-separated simulation durations in days. Defaults to the full RQ4 duration set.",
    )
    parser.add_argument("--base-seed", type=int, default=20260604, help="Base random seed.")
    parser.add_argument("--fail-prob", type=float, default=EXTENDED_NOMINAL_FAIL_PROB, help="Baseline agent failure probability.")
    parser.add_argument("--msg-loss", type=float, default=EXTENDED_NOMINAL_MSG_LOSS, help="Baseline message loss probability.")
    parser.add_argument("--malicious-ratio", type=float, default=0.60, help="Malicious-agent ratio.")
    parser.add_argument(
        "--coord-labels",
        default=",".join(DEFAULT_COORD_LABELS),
        help="Comma-separated mechanisms to include.",
    )
    parser.add_argument(
        "--machine-label",
        default=None,
        help="Short label for the computer running this shard, e.g. mac or workstation.",
    )
    parser.add_argument("--shard-count", type=int, default=1, help="Number of machines/shards used for RQ4.")
    parser.add_argument("--shard-index", type=int, default=1, help="1-based index of the shard to run on this machine.")
    parser.add_argument("--quick", action="store_true", help="Small smoke campaign for checking the runner.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the run is already marked ok in runs.csv.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N run instances.")
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Independent simulations in parallel; 0 automatically uses available CPUs (up to 6).",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately if a run fails.")
    return parser.parse_args()


def sanitize_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return label or "machine"


def default_machine_label() -> str:
    """Label this host by hardware profile so the two profiles stay separable."""
    return "mac" if platform.system() == "Darwin" else "workstation"


def machine_label(args: argparse.Namespace) -> str:
    return sanitize_label(args.machine_label or default_machine_label())



def hardware_metadata(label: str) -> dict[str, Any]:
    return {
        "machine_label": label,
        "machine_node": platform.node(),
        "machine_system": platform.system(),
        "machine_release": platform.release(),
        "machine_platform": platform.platform(),
        "machine_processor": platform.processor(),
        "machine_cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
    }


def selected_coord_labels(args: argparse.Namespace) -> list[str]:
    labels = [label.strip().upper() for label in args.coord_labels.split(",") if label.strip()]
    unknown = [label for label in labels if label not in COORD_TO_ARCH]
    if unknown:
        raise ValueError(f"Unknown coordination labels: {', '.join(unknown)}")
    if not labels:
        raise ValueError("At least one coordination label is required.")
    return labels


def selected_sim_days(args: argparse.Namespace) -> list[int]:
    if args.sim_days is None:
        return DEFAULT_SIM_DAYS
    values = [value.strip() for value in args.sim_days.split(",") if value.strip()]
    if not values:
        raise ValueError("At least one simulation duration is required.")
    days = [int(value) for value in values]
    if any(day <= 0 for day in days):
        raise ValueError("Simulation durations must be positive integers.")
    return days


def validate_shard_args(args: argparse.Namespace) -> None:
    if args.shard_count < 1:
        raise ValueError("--shard-count must be >= 1")
    if args.shard_index < 1 or args.shard_index > args.shard_count:
        raise ValueError("--shard-index must be between 1 and --shard-count")


def build_campaign_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.quick:
        conditions = [("nominal", 1, EXTENDED_NOMINAL_SPAWN, EXTENDED_NOMINAL_ROBOTS, EXTENDED_NOMINAL_ROOMS)]
        coord_labels = selected_coord_labels(args)
        repetitions = 1 if args.repetitions == 10 else args.repetitions
    else:
        conditions = []
        seen: dict[tuple, int] = {}

        def add_condition(slice_name, sim_days=NOMINAL_SIM_DAYS, item_spawn=EXTENDED_NOMINAL_SPAWN,
                          n_robots=EXTENDED_NOMINAL_ROBOTS, n_rooms=EXTENDED_NOMINAL_ROOMS):
            key = (sim_days, item_spawn, n_robots, n_rooms)
            if key in seen:
                index = seen[key]
                conditions[index] = (conditions[index][0] + "," + slice_name, *key)
            else:
                seen[key] = len(conditions)
                conditions.append((slice_name, *key))

        # The nominal point is the value shared by the three extended sweeps, so
        # it carries their combined slice label and appears in every panel.
        for value in selected_sim_days(args):
            add_condition("workload,fleet,topology_size", sim_days=value)
        coord_labels = selected_coord_labels(args)
        repetitions = args.repetitions

    rows: list[dict[str, Any]] = []
    combo_idx = 0
    label = machine_label(args)
    for (analysis_slices, sim_days, item_spawn, n_robots, n_rooms), coord_label in product(
        conditions, coord_labels,
    ):
        combo_idx += 1
        for rep in range(1, repetitions + 1):
            rows.append({
                "combo_idx": combo_idx,
                "analysis_slices": analysis_slices,
                "rep": rep,
                "seed": args.base_seed + combo_idx * 1000 + rep,
                "machine_label": label,
                "coord_label": coord_label,
                "architecture": COORD_TO_ARCH[coord_label],
                "topology": f"{EXTENDED_NOMINAL_TOPOLOGY}{n_rooms}",
                "n_rooms": n_rooms,
                "sim_days": sim_days,
                "item_spawning_time": item_spawn,
                "n_robots": n_robots,
                "malicious_ratio": args.malicious_ratio,
                "n_malicious": malicious_count(n_robots, args.malicious_ratio),
                "fail_prob": args.fail_prob,
                "msg_loss_prob": args.msg_loss,
            })
    return rows


def shard_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    validate_shard_args(args)
    if args.shard_count == 1:
        return rows
    shard_offset = args.shard_index - 1
    return [
        row
        for idx, row in enumerate(rows)
        if idx % args.shard_count == shard_offset
    ]


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = shard_rows(build_campaign_rows(args), args)
    return rows[: args.limit] if args.limit else rows


def run_id(params: dict[str, Any]) -> str:
    return (
        f"{params['machine_label']}_c{params['combo_idx']:03d}_r{params['rep']:02d}_"
        f"{params['coord_label']}_{params['topology']}_days{params['sim_days']}_"
        f"spawn{params['item_spawning_time']}_bots{params['n_robots']}_{RQ4_EXPERIMENT_PROFILE}"
    )


def normalize_machine_label(value: Any) -> str:
    label = sanitize_label(str(value or ""))
    if label in {"linux", "workstation"}:
        return "workstation"
    if label in {"darwin", "macos", "mac"}:
        return "mac"
    return label or "workstation"


def legacy_machine_label_from_run_id(run_id_value: str) -> str:
    if run_id_value.startswith("mac_"):
        return "mac"
    if run_id_value.startswith("linux_") or run_id_value.startswith("workstation_"):
        return "workstation"
    return "workstation"


def resume_key_from_params(params: dict[str, Any]) -> tuple[Any, ...]:
    expiration = tuple(int(round(float(value))) for value in BASE_CONFIG["EXPIRATION_TIME"])
    return (
        normalize_machine_label(params.get("machine_label")),
        str(params.get("coord_label", "")),
        str(params.get("architecture", "")),
        str(params.get("topology", "")),
        int(params.get("n_rooms", 0)),
        int(params.get("rep", 0)),
        int(params.get("sim_days", 0)),
        int(params.get("item_spawning_time", 0)),
        int(params.get("n_robots", 0)),
        int(params.get("n_malicious", 0)),
        round(float(params.get("malicious_ratio", 0.0)), 6),
        round(float(params.get("fail_prob", 0.0)), 6),
        round(float(params.get("msg_loss_prob", 0.0)), 6),
        *expiration,
    )


def resume_key_from_row(row: dict[str, Any]) -> tuple[Any, ...]:
    run_id_value = str(row.get("run_id", ""))
    machine = row.get("machine_label") or legacy_machine_label_from_run_id(run_id_value)
    return (
        normalize_machine_label(machine),
        str(row.get("coord_label", "")),
        str(row.get("architecture", "")),
        str(row.get("topology", "")),
        int(float(row.get("n_rooms", 0) or 0)),
        int(float(row.get("rep", 0) or 0)),
        int(float(row.get("sim_days", 0) or 0)),
        int(float(row.get("item_spawning_time", 0) or 0)),
        int(float(row.get("n_robots", 0) or 0)),
        int(float(row.get("n_malicious", 0) or 0)),
        round(float(row.get("malicious_ratio", 0.0) or 0.0), 6),
        round(float(row.get("fail_prob", 0.0) or 0.0), 6),
        round(float(row.get("msg_loss_prob", 0.0) or 0.0), 6),
        int(float(row.get("expiration_time_low_s", 0) or 0)),
        int(float(row.get("expiration_time_medium_s", 0) or 0)),
        int(float(row.get("expiration_time_high_s", 0) or 0)),
    )


def completed_resume_keys(rows: list[dict[str, Any]]) -> set[tuple[Any, ...]]:
    keys: set[tuple[Any, ...]] = set()
    for row in rows:
        if row.get("status") != "ok":
            continue
        keys.add(resume_key_from_row(row))
    return keys


def replace_row_by_resume_key(rows: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    key = resume_key_from_row(row)
    run_id_value = row.get("run_id")
    return [
        existing
        for existing in rows
        if existing.get("run_id") != run_id_value and resume_key_from_row(existing) != key
    ] + [row]


def run_subprocess(cfg_path: Path) -> dict[str, Any]:
    code = f"""
import json
import resource
import sys
from pathlib import Path
from sim import simulator

cfg_path = Path(sys.argv[1])
logfile, wall_time, event_count = simulator.run(str(cfg_path))
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform == "darwin":
    max_rss_mb = rss / (1024 * 1024)
else:
    max_rss_mb = rss / 1024
print("{SUBPROCESS_MARKER}" + json.dumps({{
    "logfile": logfile,
    "wall_time_s": wall_time,
    "event_count": event_count,
    "max_rss_mb": max_rss_mb,
}}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, str(cfg_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-30:])
        raise RuntimeError(f"subprocess failed with code {proc.returncode}\n{tail}")

    result_lines = [line for line in proc.stdout.splitlines() if line.startswith(SUBPROCESS_MARKER)]
    if not result_lines:
        tail = "\n".join(proc.stdout.splitlines()[-30:])
        raise RuntimeError(f"subprocess completed but no result marker was found\n{tail}")
    return json.loads(result_lines[-1].removeprefix(SUBPROCESS_MARKER))


def execute_rq4_job(job: dict[str, Any]) -> dict[str, Any]:
    """Run one RSS-measured simulation; campaign CSVs are written by the parent."""
    try:
        logfile = Path(job["logfile"])
        if logfile.exists() and not job["force"]:
            logfile.unlink()
        subprocess_metrics = run_subprocess(Path(job["config_path"]))
        return {"status": "ok", "error": "", "subprocess_metrics": subprocess_metrics,
                "metrics": analyze_log(logfile, job["sim_time"])}
    except BaseException as exc:
        return {"status": "error", "error": str(exc) or exc.__class__.__name__,
                "subprocess_metrics": {"wall_time_s": math.nan, "event_count": math.nan,
                                       "max_rss_mb": math.nan}, "metrics": {}}


def run_campaign(args: argparse.Namespace) -> None:
    args.workers = resolve_worker_count(args.workers)
    label = machine_label(args)
    hardware = hardware_metadata(label)
    coord_labels = selected_coord_labels(args)
    if not args.dry_run and "DA" in coord_labels:
        rtlola_binary = ensure_rtlola_available()
        print(f"[preflight] RTLola binary: {rtlola_binary}")
    all_combos = build_campaign_rows(args)
    shard_combos = shard_rows(all_combos, args)
    combos = shard_combos[: args.limit] if args.limit else shard_combos
    design = {
        "research_question": "RQ4",
        "experiment_profile": RQ4_EXPERIMENT_PROFILE,
        "repetitions": args.repetitions,
        "total_runs": len(combos),
        "workers": args.workers,
        "full_campaign_runs": len(all_combos),
        "shard_runs_before_limit": len(shard_combos),
        "machine_label": label,
        "machine_metadata": hardware,
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "sim_days": [1] if args.quick else selected_sim_days(args),
        "item_spawning_times": [EXTENDED_NOMINAL_SPAWN] if args.quick else EXTENDED_ITEM_SPAWNING_TIMES,
        "n_robots": [EXTENDED_NOMINAL_ROBOTS] if args.quick else EXTENDED_ROBOT_COUNTS,
        "n_rooms": [EXTENDED_NOMINAL_ROOMS] if args.quick else EXTENDED_ROOM_COUNTS,
        "coordination_mechanisms": coord_labels,
        "malicious_ratio": args.malicious_ratio,
        "fail_prob": args.fail_prob,
        "msg_loss": args.msg_loss,
        "daily_operating_profile": "triangular severity and recovery",
        "expiration_time": expiration_metadata(extended_scenario_updates(
            topology_type=EXTENDED_NOMINAL_TOPOLOGY,
            n_rooms=EXTENDED_NOMINAL_ROOMS,
            n_robots=EXTENDED_NOMINAL_ROBOTS,
            n_malicious=malicious_count(EXTENDED_NOMINAL_ROBOTS, args.malicious_ratio),
            item_spawning_time=EXTENDED_NOMINAL_SPAWN,
            fail_prob=args.fail_prob,
            msg_loss_prob=args.msg_loss,
        )),
        "purpose": "Measure execution time, peak RSS, event throughput, and trace size.",
    }
    print("=" * 80)
    print("RQ4 SCALABILITY CAMPAIGN")
    print("=" * 80)
    print(design)
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    raw_logs_dir, configs_dir = ensure_result_dirs(RESULTS_ROOT)
    machine_raw_logs_dir = raw_logs_dir / label
    machine_configs_dir = configs_dir / label
    machine_raw_logs_dir.mkdir(parents=True, exist_ok=True)
    machine_configs_dir.mkdir(parents=True, exist_ok=True)

    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    completed = completed_run_ids(rows)
    completed_keys = completed_resume_keys(rows)
    started_at = time.time()

    jobs: list[dict[str, Any]] = []
    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        resume_key = resume_key_from_params(params)
        if (rid in completed or resume_key in completed_keys) and not args.force:
            print(f"[{idx}/{len(combos)}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = machine_raw_logs_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        logfile = run_dir / "simulation_log.csv"
        cfg_path = machine_configs_dir / f"{rid}.json"
        phases = build_extended_daily_phases(
            sim_days=params["sim_days"],
            base_fail_prob=params["fail_prob"],
            base_msg_loss=params["msg_loss_prob"],
            n_robots=params["n_robots"],
            n_malicious=params["n_malicious"],
            item_spawning_time=params["item_spawning_time"],
        )
        cfg = config_with_paths(
            results_root=RESULTS_ROOT,
            logfile=logfile,
            architecture=params["architecture"],
            seed=params["seed"],
            sim_days=params["sim_days"],
            updates={
                **extended_scenario_updates(
                    topology_type=EXTENDED_NOMINAL_TOPOLOGY,
                    n_rooms=params["n_rooms"],
                    n_robots=params["n_robots"],
                    n_malicious=params["n_malicious"],
                    item_spawning_time=params["item_spawning_time"],
                    fail_prob=params["fail_prob"],
                    msg_loss_prob=params["msg_loss_prob"],
                ),
                "MACHINE_LABEL": label,
                "MACHINE_METADATA": hardware,
            },
            phases=phases,
        )
        write_json(cfg_path, cfg)

        had_previous_error = any(error.get("run_id") == rid for error in errors)
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            logfile.unlink()

        jobs.append({"idx": idx, "run_id": rid, "params": params, "cfg": cfg,
                     "config_path": str(cfg_path), "logfile": str(logfile),
                     "sim_time": cfg["SIM_TIME"], "force": args.force})

    def persist_result(job: dict[str, Any], result: dict[str, Any], completed_count: int) -> None:
        nonlocal rows, errors, completed, completed_keys
        params = job["params"]
        cfg = job["cfg"]
        rid = job["run_id"]
        logfile = Path(job["logfile"])
        cfg_path = Path(job["config_path"])
        status = result["status"]
        error_message = result["error"]
        subprocess_metrics = result["subprocess_metrics"]
        metrics = result["metrics"]
        if status == "error":
            errors.append({**params, "run_id": rid, "config_path": str(cfg_path),
                           "logfile": str(logfile), "error": error_message})
            print(f"[{completed_count}/{len(jobs)}] {rid} ERROR: {error_message}", flush=True)
        else:
            print(f"[{completed_count}/{len(jobs)}] {rid} completed", flush=True)

        wall_time = safe_float(subprocess_metrics.get("wall_time_s"))
        event_count = safe_float(subprocess_metrics.get("event_count"))
        row = {
            "run_id": rid,
            "experiment_profile": RQ4_EXPERIMENT_PROFILE,
            "analysis_slices": params["analysis_slices"],
            "status": status,
            "error": error_message,
            "config_path": str(cfg_path),
            "logfile": str(logfile),
            "machine_label": label,
            "shard_count": args.shard_count,
            "shard_index": args.shard_index,
            **hardware,
            "coord_label": params["coord_label"],
            "architecture": params["architecture"],
            "rep": params["rep"],
            "seed": params["seed"],
            "sim_days": params["sim_days"],
            "topology": params["topology"],
            "n_rooms": params["n_rooms"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss_prob": params["msg_loss_prob"],
            **expiration_metadata(cfg),
            "wall_time_s": wall_time,
            "event_count": event_count,
            "events_per_wall_s": event_count / wall_time if wall_time and not math.isnan(wall_time) else math.nan,
            "max_rss_mb": subprocess_metrics.get("max_rss_mb"),
            "config_size_kb": cfg_path.stat().st_size / 1024 if cfg_path.exists() else 0.0,
            "total_output_size_mb": file_size_mb(logfile)
            + file_size_mb(logfile.with_name(logfile.stem + "_overhead.csv")),
            **metrics,
        }
        rows = replace_row_by_resume_key(rows, row)
        completed.add(rid)
        completed_keys.add(resume_key)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    print(f"Launching {len(jobs)} runs with {min(args.workers, len(jobs)) if jobs else 0} worker processes.", flush=True)
    if not jobs:
        print("No pending runs.", flush=True)
    elif args.workers == 1:
        for completed_count, job in enumerate(jobs, start=1):
            result = execute_rq4_job(job)
            persist_result(job, result, completed_count)
            if result["status"] == "error" and args.fail_fast:
                raise RuntimeError(result["error"])
    else:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as executor:
            future_to_job = {executor.submit(execute_rq4_job, job): job for job in jobs}
            for completed_count, future in enumerate(as_completed(future_to_job), start=1):
                job = future_to_job[future]
                result = future.result()
                persist_result(job, result, completed_count)
                if result["status"] == "error" and args.fail_fast:
                    for pending in future_to_job:
                        pending.cancel()
                    raise RuntimeError(result["error"])

    cleanup_transient_artifacts(RESULTS_ROOT)

    print("=" * 80)
    print(f"RQ4 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:   {RESULTS_ROOT / 'runs.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
