#!/usr/bin/env python3
"""
RQ4 runner: practical scalability limits of COORDINATE 2.0.

RQ4 focuses on execution time, memory usage, event throughput, and trace size as
simulation duration, fleet size, and workload increase. Each run is executed in
an isolated Python subprocess so peak RSS can be measured per simulation.

Default campaign:
    3 durations x 3 workload levels x 3 fleet sizes x 2 mechanisms x
    5 repetitions = 270 runs.

Run examples:
    python "Paper Results/run_rq4_experiments.py" --dry-run
    nohup python "Paper Results/run_rq4_experiments.py" > "Paper Results/RQ4/rq4.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ4/runs.csv and their raw log folders.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    COORD_TO_ARCH,
    PAPER_ROOT,
    PROJECT_ROOT,
    analyze_log,
    build_paper_daily_phases,
    config_with_paths,
    completed_run_ids,
    ensure_result_dirs,
    file_size_mb,
    malicious_count,
    read_rows,
    replace_row,
    safe_float,
    summarise_rows,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ4"
DEFAULT_SIM_DAYS = [1, 7, 30]
DEFAULT_ITEM_SPAWNING_TIMES = [150, 120, 90]
DEFAULT_N_ROBOTS = [10, 20, 30]
DEFAULT_COORD_LABELS = ["CE", "DA"]
SUBPROCESS_MARKER = "__RQ4_RESULT__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ4 scalability experiments.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per configuration.")
    parser.add_argument("--base-seed", type=int, default=20260604, help="Base random seed.")
    parser.add_argument("--fail-prob", type=float, default=0.66, help="Baseline agent failure probability.")
    parser.add_argument("--msg-loss", type=float, default=0.10, help="Baseline message loss probability.")
    parser.add_argument("--malicious-ratio", type=float, default=0.33, help="Malicious-agent ratio.")
    parser.add_argument("--stress-multiplier", type=float, default=1.2, help="Paper stress-window multiplier.")
    parser.add_argument(
        "--coord-labels",
        default=",".join(DEFAULT_COORD_LABELS),
        help="Comma-separated mechanisms to include, usually CE,DA for scalability.",
    )
    parser.add_argument("--quick", action="store_true", help="Small smoke campaign for checking the runner.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the raw log already exists.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N run instances.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately if a run fails.")
    return parser.parse_args()


def selected_coord_labels(args: argparse.Namespace) -> list[str]:
    labels = [label.strip() for label in args.coord_labels.split(",") if label.strip()]
    unknown = [label for label in labels if label not in COORD_TO_ARCH]
    if unknown:
        raise ValueError(f"Unknown coordination labels: {', '.join(unknown)}")
    return labels


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.quick:
        sim_days_values = [1]
        item_spawning_times = [150]
        n_robots_values = [10]
        coord_labels = selected_coord_labels(args)
        repetitions = 1 if args.repetitions == 5 else args.repetitions
    else:
        sim_days_values = DEFAULT_SIM_DAYS
        item_spawning_times = DEFAULT_ITEM_SPAWNING_TIMES
        n_robots_values = DEFAULT_N_ROBOTS
        coord_labels = selected_coord_labels(args)
        repetitions = args.repetitions

    rows: list[dict[str, Any]] = []
    combo_idx = 0
    for sim_days, item_spawn, n_robots, coord_label in product(
        sim_days_values,
        item_spawning_times,
        n_robots_values,
        coord_labels,
    ):
        combo_idx += 1
        for rep in range(1, repetitions + 1):
            rows.append({
                "combo_idx": combo_idx,
                "rep": rep,
                "seed": args.base_seed + combo_idx * 1000 + rep,
                "coord_label": coord_label,
                "architecture": COORD_TO_ARCH[coord_label],
                "sim_days": sim_days,
                "item_spawning_time": item_spawn,
                "n_robots": n_robots,
                "malicious_ratio": args.malicious_ratio,
                "n_malicious": malicious_count(n_robots, args.malicious_ratio),
                "fail_prob": args.fail_prob,
                "msg_loss_prob": args.msg_loss,
            })
    return rows[: args.limit] if args.limit else rows


def run_id(params: dict[str, Any]) -> str:
    return (
        f"c{params['combo_idx']:03d}_r{params['rep']:02d}_"
        f"{params['coord_label']}_days{params['sim_days']}_"
        f"spawn{params['item_spawning_time']}_bots{params['n_robots']}"
    )


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


def run_campaign(args: argparse.Namespace) -> None:
    raw_logs_dir, configs_dir = ensure_result_dirs(RESULTS_ROOT)
    combos = campaign(args)
    design = {
        "research_question": "RQ4",
        "repetitions": args.repetitions,
        "total_runs": len(combos),
        "sim_days": [1] if args.quick else DEFAULT_SIM_DAYS,
        "item_spawning_times": [150] if args.quick else DEFAULT_ITEM_SPAWNING_TIMES,
        "n_robots": [10] if args.quick else DEFAULT_N_ROBOTS,
        "coordination_mechanisms": selected_coord_labels(args),
        "malicious_ratio": args.malicious_ratio,
        "fail_prob": args.fail_prob,
        "msg_loss": args.msg_loss,
        "daily_stress_window": [12, 24],
        "stress_multiplier": args.stress_multiplier,
        "purpose": "Measure execution time, peak RSS, event throughput, and trace size.",
    }
    write_json(RESULTS_ROOT / "experiment_design.json", design)

    print("=" * 80)
    print("RQ4 SCALABILITY CAMPAIGN")
    print("=" * 80)
    print(design)
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    completed = completed_run_ids(rows)
    started_at = time.time()

    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        if rid in completed and not args.force:
            print(f"[{idx}/{len(combos)}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = raw_logs_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        logfile = run_dir / "simulation_log.csv"
        cfg_path = configs_dir / f"{rid}.json"
        phases = build_paper_daily_phases(
            sim_days=params["sim_days"],
            base_fail_prob=params["fail_prob"],
            base_msg_loss=params["msg_loss_prob"],
            base_recovery_time=1800.0,
            n_malicious=params["n_malicious"],
            item_spawning_time=params["item_spawning_time"],
            stress_multiplier=args.stress_multiplier,
        )
        cfg = config_with_paths(
            results_root=RESULTS_ROOT,
            logfile=logfile,
            architecture=params["architecture"],
            seed=params["seed"],
            sim_days=params["sim_days"],
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
        subprocess_metrics = {
            "wall_time_s": math.nan,
            "event_count": math.nan,
            "max_rss_mb": math.nan,
        }
        metrics: dict[str, Any] = {}
        had_previous_error = any(error.get("run_id") == rid for error in errors)
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            logfile.unlink()

        try:
            if logfile.exists() and not args.force:
                print("  existing log found; analysing without re-running", flush=True)
            else:
                subprocess_metrics = run_subprocess(cfg_path)
            metrics = analyze_log(logfile, cfg["SIM_TIME"])
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            status = "error"
            error_message = str(exc) or exc.__class__.__name__
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

        wall_time = safe_float(subprocess_metrics.get("wall_time_s"))
        event_count = safe_float(subprocess_metrics.get("event_count"))
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
            "sim_days": params["sim_days"],
            "item_spawning_time": params["item_spawning_time"],
            "n_robots": params["n_robots"],
            "malicious_ratio": params["malicious_ratio"],
            "n_malicious": params["n_malicious"],
            "fail_prob": params["fail_prob"],
            "msg_loss_prob": params["msg_loss_prob"],
            "wall_time_s": wall_time,
            "event_count": event_count,
            "events_per_wall_s": event_count / wall_time if wall_time and not math.isnan(wall_time) else math.nan,
            "max_rss_mb": subprocess_metrics.get("max_rss_mb"),
            "config_size_kb": cfg_path.stat().st_size / 1024 if cfg_path.exists() else 0.0,
            "total_output_size_mb": file_size_mb(logfile)
            + file_size_mb(logfile.with_name(logfile.stem + "_overhead.csv")),
            **metrics,
        }
        rows = replace_row(rows, row)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    summary = summarise_rows(
        rows,
        group_fields=["coord_label", "architecture", "sim_days", "item_spawning_time", "n_robots"],
        metric_fields=[
            "wall_time_s",
            "event_count",
            "events_per_wall_s",
            "max_rss_mb",
            "trace_rows",
            "trace_size_mb",
            "overhead_trace_size_mb",
            "total_output_size_mb",
            "created",
            "delivered",
            "avg_latency_s",
            "p95_latency_s",
            "adapt_checks",
        ],
    )
    write_rows(RESULTS_ROOT / "scalability_summary.csv", summary)

    print("=" * 80)
    print(f"RQ4 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:   {RESULTS_ROOT / 'runs.csv'}")
    print(f"Summary CSV:     {RESULTS_ROOT / 'scalability_summary.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
