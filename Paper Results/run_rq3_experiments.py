#!/usr/bin/env python3
"""
RQ3 runner: runtime overhead of stream-based monitoring and adaptation.

The default campaign keeps the scenario representative while staying smaller
than the full RQ1 grid. It compares DA with the three fixed mechanisms under
the paper's daily stress-window setup and records both simulation wall time and
per-check adaptation overhead.

Default campaign:
    3 workload levels x 3 fleet sizes x 4 mechanisms x
    5 repetitions = 180 runs.

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
import math
import time
from itertools import product
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    COORD_TO_ARCH,
    PAPER_ROOT,
    build_paper_daily_phases,
    cleanup_transient_artifacts,
    config_with_paths,
    completed_run_ids,
    drop_rows_for_run,
    ensure_result_dirs,
    find_matching_rq1_row,
    analyze_log,
    malicious_count,
    read_rows,
    read_overhead_samples,
    replace_row,
    run_or_analyze,
    safe_float,
    summarise_rows,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ3"
DEFAULT_ITEM_SPAWNING_TIMES = [90, 120, 150]
DEFAULT_N_ROBOTS = [10, 20, 30]
DEFAULT_COORD_LABELS = ["CE", "SD", "FD", "DA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ3 overhead experiments.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per configuration.")
    parser.add_argument("--sim-days", type=int, default=30, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260603, help="Base random seed.")
    parser.add_argument("--fail-prob", type=float, default=0.66, help="Baseline agent failure probability.")
    parser.add_argument("--msg-loss", type=float, default=0.10, help="Baseline message loss probability.")
    parser.add_argument("--malicious-ratio", type=float, default=0.33, help="Malicious-agent ratio.")
    parser.add_argument("--stress-multiplier", type=float, default=1.2, help="Paper stress-window multiplier.")
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
        item_spawning_times = [120]
        n_robots_values = [20]
        repetitions = 1 if args.repetitions == 5 else args.repetitions
    else:
        item_spawning_times = DEFAULT_ITEM_SPAWNING_TIMES
        n_robots_values = DEFAULT_N_ROBOTS
        repetitions = args.repetitions

    rows: list[dict[str, Any]] = []
    combo_idx = 0
    for item_spawn, n_robots, coord_label in product(item_spawning_times, n_robots_values, coord_labels):
        combo_idx += 1
        for rep in range(1, repetitions + 1):
            rows.append({
                "combo_idx": combo_idx,
                "rep": rep,
                "seed": args.base_seed + combo_idx * 1000 + rep,
                "coord_label": coord_label,
                "architecture": COORD_TO_ARCH[coord_label],
                "item_spawning_time": item_spawn,
                "n_robots": n_robots,
                "malicious_ratio": args.malicious_ratio,
                "n_malicious": malicious_count(n_robots, args.malicious_ratio),
                "fail_prob": args.fail_prob,
                "msg_loss_prob": args.msg_loss,
            })
    return rows[: args.limit] if args.limit else rows


def run_id(params: dict[str, Any]) -> str:
    mal_pct = int(round(params["malicious_ratio"] * 100))
    fail_pct = int(round(params["fail_prob"] * 100))
    return (
        f"c{params['combo_idx']:03d}_r{params['rep']:02d}_"
        f"{params['coord_label']}_spawn{params['item_spawning_time']}_"
        f"bots{params['n_robots']}_mal{mal_pct}_fail{fail_pct}"
    )


def overhead_sample_rows(
    *,
    run_meta: dict[str, Any],
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        sim_time = safe_float(sample.get("sim_time"))
        rows.append({
            **run_meta,
            **sample,
            "sim_time": sim_time,
            "sim_day": math.floor(sim_time / (24 * 3600)) + 1 if not math.isnan(sim_time) else math.nan,
            "sim_hour": (sim_time % (24 * 3600)) / 3600 if not math.isnan(sim_time) else math.nan,
        })
    return rows


def run_campaign(args: argparse.Namespace) -> None:
    combos = campaign(args)
    design = {
        "research_question": "RQ3",
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "total_runs": len(combos),
        "coordination_mechanisms": selected_coord_labels(args),
        "item_spawning_times": [120] if args.quick else DEFAULT_ITEM_SPAWNING_TIMES,
        "n_robots": [20] if args.quick else DEFAULT_N_ROBOTS,
        "malicious_ratio": args.malicious_ratio,
        "fail_prob": args.fail_prob,
        "msg_loss": args.msg_loss,
        "daily_stress_window": [12, 24],
        "stress_multiplier": args.stress_multiplier,
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
    overhead_rows = [] if args.force else read_rows(RESULTS_ROOT / "overhead_samples.csv")
    completed = completed_run_ids(rows)
    started_at = time.time()

    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        if rid in completed and not args.force:
            print(f"[{idx}/{len(combos)}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = raw_logs_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        planned_logfile = run_dir / "simulation_log.csv"
        logfile = planned_logfile
        cfg_path = configs_dir / f"{rid}.json"
        phases = build_paper_daily_phases(
            sim_days=args.sim_days,
            base_fail_prob=params["fail_prob"],
            base_msg_loss=params["msg_loss_prob"],
            base_recovery_time=1800.0,
            n_malicious=params["n_malicious"],
            item_spawning_time=params["item_spawning_time"],
            stress_multiplier=args.stress_multiplier,
        )
        cfg = config_with_paths(
            results_root=RESULTS_ROOT,
            logfile=planned_logfile,
            architecture=params["architecture"],
            seed=params["seed"],
            sim_days=args.sim_days,
            updates={
                "N_ROBOTS": params["n_robots"],
                "N_MALICIOUS": params["n_malicious"],
                "FAIL_PROB": params["fail_prob"],
                "COMM_FAIL_PROB": params["msg_loss_prob"],
                "ITEM_SPAWNING_TIME": params["item_spawning_time"],
            },
            phases=phases,
        )
        write_json(cfg_path, cfg)

        print(f"[{idx}/{len(combos)}] {rid}", flush=True)
        status = "ok"
        error_message = ""
        metrics: dict[str, Any] = {}
        wall_time = math.nan
        event_count = math.nan
        source_rq = "RQ3"
        source_run_id = rid
        source_logfile = str(planned_logfile)
        had_previous_error = any(error.get("run_id") == rid for error in errors)
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and planned_logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            planned_logfile.unlink()

        try:
            reuse_row = None
            if not args.force and not args.no_reuse_rq1:
                reuse_row = find_matching_rq1_row(
                    coord_label=params["coord_label"],
                    rep=params["rep"],
                    item_spawning_time=params["item_spawning_time"],
                    n_robots=params["n_robots"],
                    malicious_ratio=params["malicious_ratio"],
                    fail_prob=params["fail_prob"],
                    msg_loss_prob=params["msg_loss_prob"],
                )

            if reuse_row:
                logfile = Path(str(reuse_row["logfile"]))
                source_rq = "RQ1"
                source_run_id = str(reuse_row.get("run_id", ""))
                source_logfile = str(logfile)
                wall_time = safe_float(reuse_row.get("wall_time_s"))
                event_count = safe_float(reuse_row.get("event_count"))
                metrics = analyze_log(logfile, cfg["SIM_TIME"])
                print(f"  reused from RQ1: {source_run_id}", flush=True)
            else:
                metrics, wall_time, event_count = run_or_analyze(
                    cfg_path=cfg_path,
                    logfile=planned_logfile,
                    sim_time=cfg["SIM_TIME"],
                    force=args.force,
            )
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            status = "error"
            error_message = str(exc) or exc.__class__.__name__
            errors.append({
                **params,
                "run_id": rid,
                "config_path": str(cfg_path),
                "logfile": str(planned_logfile),
                "error": error_message,
            })
            print(f"  ERROR: {error_message}", flush=True)
            if args.fail_fast:
                raise

        run_meta = {
            "run_id": rid,
            "coord_label": params["coord_label"],
            "architecture": params["architecture"],
            "rep": params["rep"],
            "seed": params["seed"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "source_rq": source_rq,
            "source_run_id": source_run_id,
            "source_logfile": source_logfile,
        }
        rows = [existing for existing in rows if existing.get("run_id") != rid]
        overhead_rows = drop_rows_for_run(overhead_rows, rid)

        if params["coord_label"] == "DA" and logfile.exists():
            overhead_rows.extend(overhead_sample_rows(
                run_meta=run_meta,
                samples=read_overhead_samples(logfile),
            ))

        row = {
            **run_meta,
            "status": status,
            "error": error_message,
            "config_path": str(cfg_path),
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
        write_rows(RESULTS_ROOT / "overhead_samples.csv", overhead_rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    metric_fields = [
        "wall_time_s",
        "event_count",
        "events_per_wall_s",
        "adapt_checks",
        "adapt_overhead_ms_total",
        "adapt_overhead_ms_mean",
        "adapt_overhead_ms_p95",
        "rtlola_query_ms_mean",
        "scoring_ms_mean",
        "adapt_overhead_wall_pct",
        "trace_size_mb",
        "overhead_trace_size_mb",
    ]
    overhead_summary = summarise_rows(
        rows,
        group_fields=["coord_label", "architecture", "item_spawning_time", "n_robots"],
        metric_fields=metric_fields,
    )
    wall_time_summary = summarise_rows(
        rows,
        group_fields=["coord_label", "architecture"],
        metric_fields=metric_fields,
    )
    write_rows(RESULTS_ROOT / "overhead_summary.csv", overhead_summary)
    write_rows(RESULTS_ROOT / "wall_time_summary.csv", wall_time_summary)
    cleanup_transient_artifacts(RESULTS_ROOT)

    print("=" * 80)
    print(f"RQ3 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:        {RESULTS_ROOT / 'runs.csv'}")
    print(f"Overhead samples CSV: {RESULTS_ROOT / 'overhead_samples.csv'}")
    print(f"Summary CSV:          {RESULTS_ROOT / 'overhead_summary.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
