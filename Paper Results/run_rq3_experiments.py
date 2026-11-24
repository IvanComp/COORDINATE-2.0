#!/usr/bin/env python3
"""
RQ3 runner: runtime overhead of stream-based monitoring and adaptation.

The default campaign keeps the scenario representative while staying smaller
than the full RQ1 grid. It compares DA with the three fixed mechanisms under
the paper's daily stress-window setup and records both simulation wall time and
per-check adaptation overhead.

Default campaign:
    Extended one-factor-at-a-time workload, fleet-size, topology-size, and
    software-cost sweeps across the four coordination mechanisms.

Run examples:
    python "Paper Results/run_rq3_experiments.py" --dry-run
    nohup python "Paper Results/run_rq3_experiments.py" > "Paper Results/RQ3/rq3.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ3/runs.csv.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.

Reuse behavior:
    By default, matching RQ1 runs are reused when available, because RQ3's
    default grid is a subset of RQ1. Use --no-reuse-rq1 to force independent RQ3
    runs without using RQ1 artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    BASE_CONFIG,
    COORD_TO_ARCH,
    PAPER_ROOT,
    build_extended_daily_phases,
    cleanup_transient_artifacts,
    config_with_paths,
    ensure_rtlola_available,
    ensure_result_dirs,
    expiration_metadata,
    EXTENDED_ITEM_SPAWNING_TIMES,
    EXTENDED_NOMINAL_FAIL_PROB,
    EXTENDED_NOMINAL_MALICIOUS,
    EXTENDED_NOMINAL_MSG_LOSS,
    EXTENDED_NOMINAL_ROBOTS,
    EXTENDED_NOMINAL_ROOMS,
    EXTENDED_NOMINAL_SPAWN,
    EXTENDED_NOMINAL_TOPOLOGY,
    EXTENDED_ROBOT_COUNTS,
    EXTENDED_ROOM_COUNTS,
    extended_scenario_updates,
    FD_POLICY_VERSION,
    find_matching_rq1_row,
    float_matches,
    analyze_log,
    malicious_count,
    read_rows,
    replace_row,
    resolve_worker_count,
    row_matches_expiration,
    run_or_analyze,
    safe_float,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ3"
RQ3_EXPERIMENT_PROFILE = "extended-overhead-v3"
# RQ3 measures the runtime cost of the same nominal configuration analysed in
# RQ1, so it sweeps exactly the RQ1 factors one at a time from the ring-25
# baseline. Reusing the RQ1 grid also lets --reuse-rq1 import every run.
DEFAULT_ITEM_SPAWNING_TIMES = [90, 120, 150, 180, 210, 240, 270, 300]
DEFAULT_MALICIOUS_RATIOS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
DEFAULT_FAIL_PROBS = [value / 100 for value in range(1, 11)]
DEFAULT_MSG_LOSS_PROBS = [value / 100 for value in range(1, 11)]
DEFAULT_COORD_LABELS = ["CE", "SD", "FD", "DA"]
NOMINAL_COMP_TIME = 0.03
NOMINAL_COMM_TIME = 0.03


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ3 overhead experiments.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per configuration.")
    parser.add_argument("--sim-days", type=int, default=90, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260603, help="Base random seed.")
    parser.add_argument("--fail-prob", type=float, default=EXTENDED_NOMINAL_FAIL_PROB, help="Baseline agent failure probability.")
    parser.add_argument("--msg-loss", type=float, default=EXTENDED_NOMINAL_MSG_LOSS, help="Baseline message loss probability.")
    parser.add_argument("--malicious-ratio", type=float, default=0.60, help="Malicious-agent ratio.")
    parser.add_argument("--no-reuse-rq1", action="store_true", help="Do not import matching completed runs from RQ1.")
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


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    coord_labels = selected_coord_labels(args)
    if args.quick:
        conditions = [("nominal", EXTENDED_NOMINAL_SPAWN, args.malicious_ratio, args.fail_prob, args.msg_loss)]
        repetitions = 1 if args.repetitions == 10 else args.repetitions
    else:
        conditions = []
        seen: dict[tuple, int] = {}

        def add_condition(slice_name, item_spawn=EXTENDED_NOMINAL_SPAWN,
                          malicious_ratio=args.malicious_ratio, fail_prob=args.fail_prob,
                          msg_loss=args.msg_loss):
            key = (item_spawn, malicious_ratio, fail_prob, msg_loss)
            if key in seen:
                index = seen[key]
                conditions[index] = (conditions[index][0] + "," + slice_name, *key)
            else:
                seen[key] = len(conditions)
                conditions.append((slice_name, *key))

        for value in DEFAULT_ITEM_SPAWNING_TIMES:
            add_condition("workload", item_spawn=value)
        for value in DEFAULT_MALICIOUS_RATIOS:
            add_condition("security", malicious_ratio=value)
        for value in DEFAULT_FAIL_PROBS:
            add_condition("reliability", fail_prob=value)
        for value in DEFAULT_MSG_LOSS_PROBS:
            add_condition("communication", msg_loss=value)
        repetitions = args.repetitions

    rows: list[dict[str, Any]] = []
    combo_idx = 0
    n_robots = EXTENDED_NOMINAL_ROBOTS
    n_rooms = EXTENDED_NOMINAL_ROOMS
    for analysis_slices, item_spawn, malicious_ratio, fail_prob, msg_loss in conditions:
        n_malicious = malicious_count(n_robots, malicious_ratio)
        for coord_label in coord_labels:
            combo_idx += 1
            for rep in range(1, repetitions + 1):
                rows.append({
                    "combo_idx": combo_idx,
                    "analysis_slices": analysis_slices,
                    "rep": rep,
                    "seed": args.base_seed + combo_idx * 1000 + rep,
                    "coord_label": coord_label,
                    "architecture": COORD_TO_ARCH[coord_label],
                    "topology": f"{EXTENDED_NOMINAL_TOPOLOGY}{n_rooms}",
                    "n_rooms": n_rooms,
                    "item_spawning_time": item_spawn,
                    "n_robots": n_robots,
                    "malicious_ratio": malicious_ratio,
                    "n_malicious": n_malicious,
                    "fail_prob": fail_prob,
                    "msg_loss_prob": msg_loss,
                    "comp_time": NOMINAL_COMP_TIME,
                    "comm_time": NOMINAL_COMM_TIME,
                })
    return rows[: args.limit] if args.limit else rows


def run_id(params: dict[str, Any]) -> str:
    mal_pct = int(round(params["malicious_ratio"] * 100))
    fail_pct = int(round(params["fail_prob"] * 100))
    return (
        f"c{params['combo_idx']:03d}_r{params['rep']:02d}_"
        f"{params['coord_label']}_{params['topology']}_spawn{params['item_spawning_time']}_"
        f"bots{params['n_robots']}_mal{mal_pct}_fail{fail_pct}_"
        f"comp{int(round(params['comp_time'] * 1000)):04d}_comm{int(round(params['comm_time'] * 1000)):04d}_"
        f"msg{int(round(params['msg_loss_prob'] * 100)):03d}_{RQ3_EXPERIMENT_PROFILE}"
    )


def matches_completed_rq3(row, params, sim_days, expected_expiration):
    if row.get("status") != "ok" or row.get("experiment_profile") != RQ3_EXPERIMENT_PROFILE:
        return False
    if (row.get("fd_policy_version") or FD_POLICY_VERSION) != FD_POLICY_VERSION:
        return False
    if row.get("topology") != params["topology"] or row.get("architecture") != params["architecture"]:
        return False
    numeric = {
        "sim_days": sim_days,
        **{key: params[key] for key in (
            "seed", "n_rooms", "n_robots", "n_malicious", "item_spawning_time",
            "malicious_ratio", "fail_prob", "msg_loss_prob", "comp_time", "comm_time",
        )},
    }
    return (
        row_matches_expiration(row, expected_expiration)
        and all(float_matches(row.get(key), value) for key, value in numeric.items())
    )


def execute_rq3_job(job: dict[str, Any]) -> dict[str, Any]:
    """Run or reuse one configuration without concurrently writing CSV files."""
    try:
        params = job["params"]
        cfg = job["cfg"]
        planned_logfile = Path(job["logfile"])
        source_rq = "RQ3"
        source_run_id = job["run_id"]
        source_logfile = str(planned_logfile)
        reuse_row = None
        if not job["force"] and not job["no_reuse_rq1"]:
            reuse_row = find_matching_rq1_row(
                cfg=cfg,
                coord_label=params["coord_label"], rep=params["rep"], topology=params["topology"],
                n_rooms=params["n_rooms"], item_spawning_time=params["item_spawning_time"],
                n_robots=params["n_robots"], malicious_ratio=params["malicious_ratio"],
                fail_prob=params["fail_prob"], msg_loss_prob=params["msg_loss_prob"],
                comp_time=params["comp_time"], comm_time=params["comm_time"],
            )
        if reuse_row:
            logfile = Path(str(reuse_row["logfile"]))
            source_rq = "RQ1"
            source_run_id = str(reuse_row.get("run_id", ""))
            source_logfile = str(logfile)
            wall_time = safe_float(reuse_row.get("wall_time_s"))
            event_count = safe_float(reuse_row.get("event_count"))
            metrics = analyze_log(logfile, cfg["SIM_TIME"])
        else:
            logfile = planned_logfile
            metrics, wall_time, event_count = run_or_analyze(
                cfg_path=Path(job["config_path"]), logfile=logfile,
                force=job["force"] or job.get("configuration_changed", False),
            )
        return {"status": "ok", "error": "", "metrics": metrics, "wall_time": wall_time,
                "event_count": event_count, "logfile": str(logfile), "source_rq": source_rq,
                "source_run_id": source_run_id, "source_logfile": source_logfile}
    except BaseException as exc:
        return {"status": "error", "error": str(exc) or exc.__class__.__name__, "metrics": {},
                "wall_time": math.nan, "event_count": math.nan, "logfile": job["logfile"],
                "source_rq": "RQ3", "source_run_id": job["run_id"],
                "source_logfile": job["logfile"]}


def run_campaign(args: argparse.Namespace) -> None:
    args.workers = resolve_worker_count(args.workers)
    coord_labels = selected_coord_labels(args)
    if not args.dry_run and "DA" in coord_labels:
        rtlola_binary = ensure_rtlola_available()
        print(f"[preflight] RTLola binary: {rtlola_binary}")
    combos = campaign(args)
    design = {
        "research_question": "RQ3",
        "experiment_profile": RQ3_EXPERIMENT_PROFILE,
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "total_runs": len(combos),
        "workers": args.workers,
        "coordination_mechanisms": coord_labels,
        "item_spawning_times": [EXTENDED_NOMINAL_SPAWN] if args.quick else DEFAULT_ITEM_SPAWNING_TIMES,
        "malicious_ratios": [args.malicious_ratio] if args.quick else DEFAULT_MALICIOUS_RATIOS,
        "fail_probabilities": [args.fail_prob] if args.quick else DEFAULT_FAIL_PROBS,
        "message_loss_probabilities": [args.msg_loss] if args.quick else DEFAULT_MSG_LOSS_PROBS,
        "n_robots": [EXTENDED_NOMINAL_ROBOTS],
        "n_rooms": [EXTENDED_NOMINAL_ROOMS],
        "malicious_ratio": args.malicious_ratio,
        "fail_prob": args.fail_prob,
        "msg_loss": args.msg_loss,
        "daily_operating_profile": "triangular severity and recovery",
        "expiration_time": expiration_metadata({
            **BASE_CONFIG,
            **extended_scenario_updates(
                topology_type=EXTENDED_NOMINAL_TOPOLOGY,
                n_rooms=EXTENDED_NOMINAL_ROOMS,
                n_robots=EXTENDED_NOMINAL_ROBOTS,
                n_malicious=EXTENDED_NOMINAL_MALICIOUS,
                item_spawning_time=EXTENDED_NOMINAL_SPAWN,
                fail_prob=args.fail_prob,
                msg_loss_prob=args.msg_loss,
            ),
        }),
        "reuse_rq1": not args.no_reuse_rq1,
        "purpose": "Measure wall-clock and per-check monitoring/adaptation overhead.",
    }
    print("=" * 80)
    print("RQ3 MONITORING AND ADAPTATION OVERHEAD CAMPAIGN")
    print("=" * 80)
    print(design)
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    raw_logs_dir, configs_dir = ensure_result_dirs(RESULTS_ROOT)
    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    previous_runs = {row["run_id"]: row for row in rows if row.get("run_id")}
    started_at = time.time()

    jobs: list[dict[str, Any]] = []
    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        updates = extended_scenario_updates(
            topology_type=EXTENDED_NOMINAL_TOPOLOGY,
            n_rooms=params["n_rooms"],
            n_robots=params["n_robots"],
            n_malicious=params["n_malicious"],
            item_spawning_time=params["item_spawning_time"],
            fail_prob=params["fail_prob"],
            msg_loss_prob=params["msg_loss_prob"],
            comp_time=params["comp_time"],
            comm_time=params["comm_time"],
        )
        expected_expiration = expiration_metadata({**BASE_CONFIG, **updates})
        previous_run = previous_runs.get(rid, {})
        if not args.force and matches_completed_rq3(previous_run, params, args.sim_days, expected_expiration):
            print(f"[{idx}/{len(combos)}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = raw_logs_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        planned_logfile = run_dir / "simulation_log.csv"
        logfile = planned_logfile
        cfg_path = configs_dir / f"{rid}.json"
        phases = build_extended_daily_phases(
            sim_days=args.sim_days,
            base_fail_prob=params["fail_prob"],
            base_msg_loss=params["msg_loss_prob"],
            n_robots=params["n_robots"],
            n_malicious=params["n_malicious"],
            item_spawning_time=params["item_spawning_time"],
        )
        cfg = config_with_paths(
            results_root=RESULTS_ROOT,
            logfile=planned_logfile,
            architecture=params["architecture"],
            seed=params["seed"],
            sim_days=args.sim_days,
            updates=updates,
            phases=phases,
        )
        configuration_changed = False
        if planned_logfile.exists():
            try:
                configuration_changed = json.loads(cfg_path.read_text(encoding="utf-8")) != cfg
            except (OSError, ValueError):
                configuration_changed = True
        write_json(cfg_path, cfg)

        had_previous_error = any(error.get("run_id") == rid for error in errors)
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and planned_logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            planned_logfile.unlink()

        jobs.append({"idx": idx, "run_id": rid, "params": params, "cfg": cfg,
                     "config_path": str(cfg_path), "logfile": str(planned_logfile),
                     "force": args.force, "no_reuse_rq1": args.no_reuse_rq1,
                     "configuration_changed": configuration_changed})

    def persist_result(job: dict[str, Any], result: dict[str, Any], completed_count: int) -> None:
        nonlocal rows, errors
        params = job["params"]
        cfg = job["cfg"]
        rid = job["run_id"]
        status = result["status"]
        error_message = result["error"]
        metrics = result["metrics"]
        wall_time = result["wall_time"]
        event_count = result["event_count"]
        logfile = Path(result["logfile"])
        planned_logfile = Path(job["logfile"])
        source_rq = result["source_rq"]
        source_run_id = result["source_run_id"]
        source_logfile = result["source_logfile"]
        if status == "error":
            errors.append({**params, "run_id": rid, "config_path": job["config_path"],
                           "logfile": job["logfile"], "error": error_message})
            print(f"[{completed_count}/{len(jobs)}] {rid} ERROR: {error_message}", flush=True)
        else:
            suffix = f" reused from {source_run_id}" if source_rq == "RQ1" else " completed"
            print(f"[{completed_count}/{len(jobs)}] {rid}{suffix}", flush=True)

        run_meta = {
            "run_id": rid,
            "experiment_profile": RQ3_EXPERIMENT_PROFILE,
            "fd_policy_version": FD_POLICY_VERSION,
            "analysis_slices": params["analysis_slices"],
            "coord_label": params["coord_label"],
            "architecture": params["architecture"],
            "rep": params["rep"],
            "seed": params["seed"],
            "topology": params["topology"],
            "n_rooms": params["n_rooms"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "comp_time": params["comp_time"],
            "comm_time": params["comm_time"],
            "source_rq": source_rq,
            "source_run_id": source_run_id,
            "source_logfile": source_logfile,
            **expiration_metadata(cfg),
        }
        rows = [existing for existing in rows if existing.get("run_id") != rid]
        row = {
            **run_meta,
            "status": status,
            "error": error_message,
            "config_path": job["config_path"],
            "logfile": str(logfile),
            "planned_logfile": str(planned_logfile),
            "source_rq": source_rq,
            "source_run_id": source_run_id,
            "source_logfile": source_logfile,
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss_prob": params["msg_loss_prob"],
            "sim_days": args.sim_days,
            "wall_time_s": wall_time,
            "event_count": event_count,
            "events_per_wall_s": event_count / wall_time if wall_time and not math.isnan(wall_time) else math.nan,
            "adapt_overhead_wall_pct": (
                metrics.get("adapt_overhead_ms_total", 0.0) / 1000.0 / wall_time * 100.0
                if wall_time and not math.isnan(wall_time)
                else math.nan
            ),
            **metrics,
        }
        rows = replace_row(rows, row)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    print(f"Launching {len(jobs)} runs with {min(args.workers, len(jobs)) if jobs else 0} worker processes.", flush=True)
    if not jobs:
        print("No pending runs.", flush=True)
    elif args.workers == 1:
        for completed_count, job in enumerate(jobs, start=1):
            result = execute_rq3_job(job)
            persist_result(job, result, completed_count)
            if result["status"] == "error" and args.fail_fast:
                raise RuntimeError(result["error"])
    else:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as executor:
            future_to_job = {executor.submit(execute_rq3_job, job): job for job in jobs}
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
    print(f"RQ3 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:        {RESULTS_ROOT / 'runs.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
