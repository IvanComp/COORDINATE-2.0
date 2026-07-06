#!/usr/bin/env python3
"""
RQ2 runner: Dynamic Adaptation reaction to evolving operating conditions with
a more realistic task-completion regime.

RQ2 is deliberately DA-only. The goal is not to re-run the full comparison from
RQ1, but to inspect when DA switches, which monitored state caused the switch,
and whether switches align with persistent fault windows.

Default campaign:
    4 dynamic profiles x 10 repetitions = 40 runs.

Run examples:
    python "Paper Results/run_rq2_realistic_completion_experiments.py" --dry-run
    nohup python "Paper Results/run_rq2_realistic_completion_experiments.py" > "Paper Results/RQ2_realistic_completion/rq2.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ2_realistic_completion/runs.csv.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.

Reuse behavior:
    These runs are independent from the original RQ1 campaign because they use
    different workload, fault, and deadline settings.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    COORD_TO_ARCH,
    PAPER_ROOT,
    analyze_log,
    config_with_paths,
    cleanup_transient_artifacts,
    completed_run_ids,
    drop_rows_for_run,
    ensure_rtlola_available,
    ensure_result_dirs,
    extract_switches,
    malicious_count,
    nearest_overhead_sample,
    phase_for_time,
    read_rows,
    read_overhead_samples,
    replace_row,
    run_or_analyze,
    safe_float,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ2_realistic_completion"
TIMESERIES_PATH = RESULTS_ROOT / "adaptation_state_timeseries.csv.gz"
PROFILE_NAMES = [
    "daily_fault_windows",
    "communication_degradation",
    "malicious_surge",
    "load_failure_recovery",
]

COMPLETION_CONFIG_UPDATES = {
    "IMPORTANCE_PROBABILITIES": [0.55, 0.25, 0.20],
    "EXPIRATION_TIME": [28800, 14400, 7200],
    "EXPIRATION_DISTR": ["deterministic", "deterministic", "deterministic"],
}


def expiration_metadata(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    source = cfg or COMPLETION_CONFIG_UPDATES
    values = source["EXPIRATION_TIME"]
    return {
        "expiration_time_low_s": values[0],
        "expiration_time_medium_s": values[1],
        "expiration_time_high_s": values[2],
        "log_expire": bool(source.get("LOG_EXPIRE", True)),
    }


def completed_run_ids(rows: list[dict[str, Any]]) -> set[str]:
    expected = expiration_metadata()
    completed: set[str] = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if not run_id or row.get("status") != "ok":
            continue
        if str(row.get("log_expire", "")).lower() != "true":
            continue
        matches = True
        for key, expected_value in expected.items():
            if key == "log_expire":
                continue
            try:
                actual_value = float(row.get(key, ""))
            except (TypeError, ValueError):
                matches = False
                break
            if int(round(actual_value)) != int(round(float(expected_value))):
                matches = False
                break
        if matches:
            completed.add(run_id)
    return completed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ2 dynamic adaptation experiments with realistic completion settings.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per dynamic profile.")
    parser.add_argument("--sim-days", type=int, default=30, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260602, help="Base random seed.")
    parser.add_argument(
        "--profiles",
        default=",".join(PROFILE_NAMES),
        help="Comma-separated profile names.",
    )
    parser.add_argument("--quick", action="store_true", help="Use one profile and one short repetition set.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the run is already marked ok in runs.csv.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N run instances.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately if a run fails.")
    return parser.parse_args()


def day_segments_to_phases(
    *,
    sim_days: int,
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    day_seconds = 24 * 3600
    for day in range(sim_days):
        day_start = day * day_seconds
        for segment in segments:
            start = day_start + float(segment["start_hour"]) * 3600
            end = day_start + float(segment["end_hour"]) * 3600
            params = dict(segment["params"])
            params.update({
                "label": segment["label"],
                "start": start,
                "end": end,
            })
            phases.append(params)
    return [phase for phase in phases if phase["end"] > phase["start"]]


def phase_params(
    *,
    n_robots: int,
    malicious_ratio: float,
    fail_prob: float,
    msg_loss: float,
    recovery_time: float,
    item_spawning_time: float,
) -> dict[str, Any]:
    return {
        "N_MALICIOUS": malicious_count(n_robots, malicious_ratio),
        "FAIL_PROB": fail_prob,
        "COMM_FAIL_PROB": msg_loss,
        "RECOVERY_TIME": recovery_time,
        "ITEM_SPAWNING_TIME": item_spawning_time,
    }


def profile_definition(profile_name: str, sim_days: int) -> dict[str, Any]:
    n_robots = 35
    recovery = 1500.0

    if profile_name == "daily_fault_windows":
        nominal = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.10,
            fail_prob=0.08,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=240,
        )
        load_failure = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.25,
            msg_loss=0.06,
            recovery_time=1.15 * recovery,
            item_spawning_time=150,
        )
        communication = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.15,
            msg_loss=0.06,
            recovery_time=recovery,
            item_spawning_time=210,
        )
        malicious = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.66,
            fail_prob=0.30,
            msg_loss=0.10,
            recovery_time=1.15 * recovery,
            item_spawning_time=150,
        )
        recovery_phase = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.0,
            fail_prob=0.05,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=240,
        )
        description = "Multi-regime daily profile alternating nominal, load/failure, communication degradation, malicious-agent surge, and recovery phases."
        segments = [
            {"label": "nominal", "start_hour": 0, "end_hour": 6, "params": nominal},
            {"label": "load_failure_window", "start_hour": 6, "end_hour": 10, "params": load_failure},
            {"label": "baseline", "start_hour": 10, "end_hour": 14, "params": communication},
            {"label": "malicious_surge", "start_hour": 14, "end_hour": 18, "params": malicious},
            {"label": "recovery", "start_hour": 18, "end_hour": 24, "params": recovery_phase},
        ]

    elif profile_name == "communication_degradation":
        normal = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.10,
            fail_prob=0.15,
            msg_loss=0.06,
            recovery_time=recovery,
            item_spawning_time=210,
        )
        degraded = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.30,
            msg_loss=0.20,
            recovery_time=1.15 * recovery,
            item_spawning_time=150,
        )
        recovery_phase = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.0,
            fail_prob=0.05,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=240,
        )
        description = "Communication degradation period designed to make FD pressure observable."
        segments = [
            {"label": "normal", "start_hour": 0, "end_hour": 8, "params": normal},
            {"label": "communication_degradation", "start_hour": 8, "end_hour": 16, "params": degraded},
            {"label": "recovery", "start_hour": 16, "end_hour": 24, "params": recovery_phase},
        ]

    elif profile_name == "malicious_surge":
        normal = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.10,
            fail_prob=0.15,
            msg_loss=0.06,
            recovery_time=recovery,
            item_spawning_time=210,
        )
        surge = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.66,
            fail_prob=0.35,
            msg_loss=0.12,
            recovery_time=1.15 * recovery,
            item_spawning_time=150,
        )
        calm = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.10,
            fail_prob=0.05,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=240,
        )
        description = "Malicious-agent fraction increases during the daily surge interval."
        segments = [
            {"label": "normal", "start_hour": 0, "end_hour": 12, "params": normal},
            {"label": "malicious_surge", "start_hour": 12, "end_hour": 22, "params": surge},
            {"label": "calm", "start_hour": 22, "end_hour": 24, "params": calm},
        ]

    elif profile_name == "load_failure_recovery":
        calm = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.0,
            fail_prob=0.05,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=240,
        )
        load_failure = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.35,
            msg_loss=0.18,
            recovery_time=1.25 * recovery,
            item_spawning_time=150,
        )
        description = "Low-fault period, combined load/failure window, and explicit recovery period each day."
        segments = [
            {"label": "calm", "start_hour": 0, "end_hour": 8, "params": calm},
            {"label": "load_failure_window", "start_hour": 8, "end_hour": 18, "params": load_failure},
            {"label": "recovery", "start_hour": 18, "end_hour": 24, "params": calm},
        ]

    else:
        raise ValueError(f"Unknown RQ2 profile: {profile_name}")

    phases = day_segments_to_phases(sim_days=sim_days, segments=segments)
    first_phase = phases[0]
    return {
        "profile": profile_name,
        "description": description,
        "n_robots": n_robots,
        "initial_updates": {
            **COMPLETION_CONFIG_UPDATES,
            "N_ROBOTS": n_robots,
            "N_MALICIOUS": first_phase["N_MALICIOUS"],
            "FAIL_PROB": first_phase["FAIL_PROB"],
            "COMM_FAIL_PROB": first_phase["COMM_FAIL_PROB"],
            "RECOVERY_TIME": first_phase["RECOVERY_TIME"],
            "ITEM_SPAWNING_TIME": first_phase["ITEM_SPAWNING_TIME"],
        },
        "segments": segments,
        "phases": phases,
    }


def selected_profiles(args: argparse.Namespace) -> list[str]:
    if args.quick:
        return ["load_failure_recovery"]
    profiles = [name.strip() for name in args.profiles.split(",") if name.strip()]
    unknown = [name for name in profiles if name not in PROFILE_NAMES]
    if unknown:
        raise ValueError(f"Unknown RQ2 profile(s): {', '.join(unknown)}")
    return profiles


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    profiles = selected_profiles(args)
    repetitions = 1 if args.quick and args.repetitions == 10 else args.repetitions
    for profile_idx, profile in enumerate(profiles, start=1):
        definition = profile_definition(profile, args.sim_days)
        for rep in range(1, repetitions + 1):
            rows.append({
                "profile_idx": profile_idx,
                "profile": profile,
                "rep": rep,
                "seed": args.base_seed + profile_idx * 1000 + rep,
                "definition": definition,
            })
    return rows[: args.limit] if args.limit else rows


def run_id(params: dict[str, Any]) -> str:
    return f"{params['profile_idx']:02d}_{params['profile']}_r{params['rep']:02d}_DA"


def annotate_overhead_rows(
    *,
    run_meta: dict[str, Any],
    samples: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        sim_time = safe_float(sample.get("sim_time"))
        phase = phase_for_time(phases, sim_time)
        rows.append({
            **run_meta,
            **sample,
            "sim_time": sim_time,
            "sim_day": math.floor(sim_time / (24 * 3600)) + 1 if not math.isnan(sim_time) else math.nan,
            "sim_hour": (sim_time % (24 * 3600)) / 3600 if not math.isnan(sim_time) else math.nan,
            "phase_label": phase.get("label", "unknown"),
            "phase_fail_prob": phase.get("FAIL_PROB"),
            "phase_msg_loss": phase.get("COMM_FAIL_PROB"),
            "phase_n_malicious": phase.get("N_MALICIOUS"),
            "phase_item_spawning_time": phase.get("ITEM_SPAWNING_TIME"),
        })
    return rows


def switch_rows(
    *,
    run_meta: dict[str, Any],
    logfile: Path,
    samples: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, switch in enumerate(extract_switches(logfile), start=1):
        sim_time = safe_float(switch["sim_time"])
        phase = phase_for_time(phases, sim_time)
        sample = nearest_overhead_sample(samples, sim_time)
        rows.append({
            **run_meta,
            "switch_idx": idx,
            "sim_time": sim_time,
            "sim_day": math.floor(sim_time / (24 * 3600)) + 1 if not math.isnan(sim_time) else math.nan,
            "sim_hour": (sim_time % (24 * 3600)) / 3600 if not math.isnan(sim_time) else math.nan,
            "phase_label": phase.get("label", "unknown"),
            "selected_architecture": switch["selected_architecture"],
            "selected_coord_label": switch["selected_coord_label"],
            "performance_score": sample.get("performance_score"),
            "performance_state": sample.get("performance_state"),
            "fd_pressure": sample.get("fd_pressure"),
            "recovery_mode": sample.get("recovery_mode"),
            "switch_reason": sample.get("switch_reason"),
            "latency": sample.get("latency"),
            "pending_ratio": sample.get("pending_ratio"),
            "failure_rate": sample.get("failure_rate"),
            "message_loss_rate": sample.get("message_loss_rate"),
        })
    return rows


def run_campaign(args: argparse.Namespace) -> None:
    if not args.dry_run:
        rtlola_binary = ensure_rtlola_available()
        print(f"[preflight] RTLola binary: {rtlola_binary}")
    combos = campaign(args)
    design = {
        "research_question": "RQ2",
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "profiles": selected_profiles(args),
        "total_runs": len(combos),
        "coordination_mechanisms": ["DA"],
        "expiration_time": expiration_metadata(),
        "reuse_rq1": False,
        "purpose": "Relate DA switches to monitored states and dynamic fault windows.",
    }
    print("=" * 80)
    print("RQ2 DYNAMIC ADAPTATION REACTION CAMPAIGN")
    print("=" * 80)
    print(design)
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    raw_logs_dir, configs_dir = ensure_result_dirs(RESULTS_ROOT)
    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    all_timeseries = [] if args.force else read_rows(TIMESERIES_PATH)
    all_switches = [] if args.force else read_rows(RESULTS_ROOT / "switch_timeline.csv")
    completed = completed_run_ids([
        row for row in rows
        if str(row.get("log_expire", "")).lower() == "true"
    ])
    started_at = time.time()

    for idx, params in enumerate(combos, start=1):
        rid = run_id(params)
        definition = params["definition"]
        if rid in completed and not args.force:
            print(f"[{idx}/{len(combos)}] {rid} already completed; skipping", flush=True)
            continue

        run_dir = raw_logs_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        planned_logfile = run_dir / "simulation_log.csv"
        logfile = planned_logfile
        cfg_path = configs_dir / f"{rid}.json"
        cfg = config_with_paths(
            results_root=RESULTS_ROOT,
            logfile=planned_logfile,
            architecture=COORD_TO_ARCH["DA"],
            seed=params["seed"],
            sim_days=args.sim_days,
            updates=definition["initial_updates"],
            phases=definition["phases"],
        )
        write_json(cfg_path, cfg)

        print(f"[{idx}/{len(combos)}] {rid}", flush=True)
        status = "ok"
        error_message = ""
        metrics: dict[str, Any] = {}
        wall_time = math.nan
        event_count = math.nan
        source_rq = "RQ2"
        source_run_id = rid
        source_logfile = str(planned_logfile)
        had_previous_error = any(error.get("run_id") == rid for error in errors)
        had_stale_expire_log = any(
            row.get("run_id") == rid
            and row.get("status") == "ok"
            and str(row.get("log_expire", "")).lower() != "true"
            for row in rows
        )
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and planned_logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            planned_logfile.unlink()
        if had_stale_expire_log and planned_logfile.exists() and not args.force:
            print("  old log lacks expire events; removing stale log and re-running", flush=True)
            planned_logfile.unlink()

        try:
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
                "run_id": rid,
                "profile": params["profile"],
                "rep": params["rep"],
                "config_path": str(cfg_path),
                "logfile": str(planned_logfile),
                "error": error_message,
            })
            print(f"  ERROR: {error_message}", flush=True)
            if args.fail_fast:
                raise

        run_meta = {
            "run_id": rid,
            "profile": params["profile"],
            "rep": params["rep"],
            "seed": params["seed"],
            "coord_label": "DA",
            "architecture": COORD_TO_ARCH["DA"],
            "source_rq": source_rq,
            "source_run_id": source_run_id,
            "source_logfile": source_logfile,
            **expiration_metadata(cfg),
        }
        samples = read_overhead_samples(logfile) if logfile.exists() else []
        rows = [existing for existing in rows if existing.get("run_id") != rid]
        all_timeseries = drop_rows_for_run(all_timeseries, rid)
        all_switches = drop_rows_for_run(all_switches, rid)

        all_timeseries.extend(annotate_overhead_rows(
            run_meta=run_meta,
            samples=samples,
            phases=definition["phases"],
        ))
        all_switches.extend(switch_rows(
            run_meta=run_meta,
            logfile=logfile,
            samples=samples,
            phases=definition["phases"],
        ))

        row = {
            **run_meta,
            "status": status,
            "error": error_message,
            "description": definition["description"],
            "config_path": str(cfg_path),
            "logfile": str(logfile),
            "planned_logfile": str(planned_logfile),
            "source_rq": source_rq,
            "source_run_id": source_run_id,
            "source_logfile": source_logfile,
            "sim_days": args.sim_days,
            "wall_time_s": wall_time,
            "event_count": event_count,
            **metrics,
        }
        rows = replace_row(rows, row)

        write_rows(RESULTS_ROOT / "runs.csv", rows)
        write_rows(TIMESERIES_PATH, all_timeseries)
        write_rows(RESULTS_ROOT / "switch_timeline.csv", all_switches)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    cleanup_transient_artifacts(RESULTS_ROOT)

    print("=" * 80)
    print(f"RQ2 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:       {RESULTS_ROOT / 'runs.csv'}")
    print(f"Timeseries CSV:      {TIMESERIES_PATH}")
    print(f"Switch timeline CSV: {RESULTS_ROOT / 'switch_timeline.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
