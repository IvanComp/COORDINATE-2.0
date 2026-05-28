#!/usr/bin/env python3
"""
RQ2 runner: Dynamic Adaptation reaction to evolving operating conditions.

RQ2 is deliberately DA-only. The goal is not to re-run the full comparison from
RQ1, but to inspect when DA switches, which monitored state caused the switch,
and whether switches align with persistent fault windows.

Default campaign:
    4 dynamic profiles x 5 repetitions = 20 runs.

Run examples:
    python "Paper Results/run_rq2_experiments.py" --dry-run
    nohup python "Paper Results/run_rq2_experiments.py" > "Paper Results/RQ2/rq2.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ2/runs.csv and their raw log folders.
    Re-launching with more repetitions skips completed repetitions and runs only
    missing or previously failed ones. Use --force to intentionally re-run all.

Reuse behavior:
    The paper_daily_stress profile can reuse matching DA runs from RQ1 when
    available. Use --no-reuse-rq1 to force independent RQ2 runs.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from paper_experiment_utils import (
    COORD_TO_ARCH,
    PAPER_ROOT,
    analyze_log,
    config_with_paths,
    completed_run_ids,
    drop_rows_for_run,
    ensure_result_dirs,
    extract_switches,
    find_matching_rq1_row,
    malicious_count,
    nearest_overhead_sample,
    phase_for_time,
    read_rows,
    read_overhead_samples,
    replace_row,
    run_or_analyze,
    safe_float,
    summarise_rows,
    write_json,
    write_rows,
)


RESULTS_ROOT = PAPER_ROOT / "RQ2"
PROFILE_NAMES = [
    "paper_daily_stress",
    "communication_blackout",
    "malicious_surge",
    "load_fault_recovery",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ2 dynamic adaptation experiments.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per dynamic profile.")
    parser.add_argument("--sim-days", type=int, default=30, help="Number of simulated days.")
    parser.add_argument("--base-seed", type=int, default=20260602, help="Base random seed.")
    parser.add_argument(
        "--profiles",
        default=",".join(PROFILE_NAMES),
        help="Comma-separated profile names.",
    )
    parser.add_argument("--quick", action="store_true", help="Use one profile and one short repetition set.")
    parser.add_argument("--no-reuse-rq1", action="store_true", help="Do not import matching completed DA runs from RQ1.")
    parser.add_argument("--dry-run", action="store_true", help="Print the campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Re-run even if the raw log already exists.")
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
    n_robots = 20
    recovery = 1800.0

    if profile_name == "paper_daily_stress":
        base = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.66,
            msg_loss=0.10,
            recovery_time=recovery,
            item_spawning_time=120,
        )
        stress = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=min(1.0, 1.2 * 0.66),
            msg_loss=min(1.0, 1.2 * 0.10),
            recovery_time=1.2 * recovery,
            item_spawning_time=120,
        )
        description = "Paper baseline: one daily stress window from 12h to 24h."
        segments = [
            {"label": "normal", "start_hour": 0, "end_hour": 12, "params": base},
            {"label": "paper_stress", "start_hour": 12, "end_hour": 24, "params": stress},
        ]

    elif profile_name == "communication_blackout":
        normal = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.33,
            msg_loss=0.10,
            recovery_time=recovery,
            item_spawning_time=120,
        )
        blackout = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.66,
            msg_loss=0.45,
            recovery_time=1.5 * recovery,
            item_spawning_time=90,
        )
        recovery_phase = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.0,
            fail_prob=0.08,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=150,
        )
        description = "Communication-heavy stress period designed to make FD pressure observable."
        segments = [
            {"label": "normal", "start_hour": 0, "end_hour": 8, "params": normal},
            {"label": "comm_blackout", "start_hour": 8, "end_hour": 16, "params": blackout},
            {"label": "recovery", "start_hour": 16, "end_hour": 24, "params": recovery_phase},
        ]

    elif profile_name == "malicious_surge":
        normal = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.33,
            msg_loss=0.10,
            recovery_time=recovery,
            item_spawning_time=120,
        )
        surge = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.66,
            fail_prob=0.66,
            msg_loss=0.20,
            recovery_time=1.2 * recovery,
            item_spawning_time=90,
        )
        calm = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.08,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=150,
        )
        description = "Malicious-agent fraction increases during the daily stress interval."
        segments = [
            {"label": "normal", "start_hour": 0, "end_hour": 12, "params": normal},
            {"label": "malicious_surge", "start_hour": 12, "end_hour": 22, "params": surge},
            {"label": "calm", "start_hour": 22, "end_hour": 24, "params": calm},
        ]

    elif profile_name == "load_fault_recovery":
        calm = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.0,
            fail_prob=0.08,
            msg_loss=0.03,
            recovery_time=recovery,
            item_spawning_time=150,
        )
        stress = phase_params(
            n_robots=n_robots,
            malicious_ratio=0.33,
            fail_prob=0.80,
            msg_loss=0.35,
            recovery_time=1.5 * recovery,
            item_spawning_time=90,
        )
        description = "Low-risk period, intense combined stress, and explicit recovery period each day."
        segments = [
            {"label": "calm", "start_hour": 0, "end_hour": 8, "params": calm},
            {"label": "load_fault_stress", "start_hour": 8, "end_hour": 18, "params": stress},
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
        return ["load_fault_recovery"]
    profiles = [name.strip() for name in args.profiles.split(",") if name.strip()]
    unknown = [name for name in profiles if name not in PROFILE_NAMES]
    if unknown:
        raise ValueError(f"Unknown RQ2 profile(s): {', '.join(unknown)}")
    return profiles


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    profiles = selected_profiles(args)
    repetitions = 1 if args.quick and args.repetitions == 5 else args.repetitions
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


def phase_schedule_rows(
    *,
    run_meta: dict[str, Any],
    phases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, phase in enumerate(phases, start=1):
        rows.append({
            **run_meta,
            "phase_idx": idx,
            "phase_label": phase.get("label", "unknown"),
            "start": phase["start"],
            "end": phase["end"],
            "start_day": math.floor(float(phase["start"]) / (24 * 3600)) + 1,
            "start_hour": (float(phase["start"]) % (24 * 3600)) / 3600,
            "end_hour": (float(phase["end"]) % (24 * 3600)) / 3600,
            "N_MALICIOUS": phase.get("N_MALICIOUS"),
            "FAIL_PROB": phase.get("FAIL_PROB"),
            "COMM_FAIL_PROB": phase.get("COMM_FAIL_PROB"),
            "RECOVERY_TIME": phase.get("RECOVERY_TIME"),
            "ITEM_SPAWNING_TIME": phase.get("ITEM_SPAWNING_TIME"),
        })
    return rows


def state_distribution_rows(timeseries_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for row in timeseries_rows:
        key = (row["profile"], int(row["rep"]))
        state = row.get("performance_state") or "unknown"
        grouped[key][state] += 1
        totals[key] += 1

    rows: list[dict[str, Any]] = []
    for (profile, rep), counts in sorted(grouped.items()):
        total = totals[(profile, rep)]
        for state, count in sorted(counts.items()):
            rows.append({
                "profile": profile,
                "rep": rep,
                "performance_state": state,
                "checks": count,
                "fraction": count / total if total else 0.0,
            })
    return rows


def run_campaign(args: argparse.Namespace) -> None:
    raw_logs_dir, configs_dir = ensure_result_dirs(RESULTS_ROOT)
    combos = campaign(args)
    design = {
        "research_question": "RQ2",
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "profiles": selected_profiles(args),
        "total_runs": len(combos),
        "coordination_mechanisms": ["DA"],
        "reuse_rq1": not args.no_reuse_rq1,
        "purpose": "Relate DA switches to monitored states and dynamic fault windows.",
    }
    write_json(RESULTS_ROOT / "experiment_design.json", design)

    print("=" * 80)
    print("RQ2 DYNAMIC ADAPTATION REACTION CAMPAIGN")
    print("=" * 80)
    print(design)
    print("=" * 80)

    if args.dry_run:
        print("Dry run only. No simulations launched.")
        return

    rows = [] if args.force else read_rows(RESULTS_ROOT / "runs.csv")
    errors = [] if args.force else read_rows(RESULTS_ROOT / "errors.csv")
    all_timeseries = [] if args.force else read_rows(RESULTS_ROOT / "adaptation_state_timeseries.csv")
    all_switches = [] if args.force else read_rows(RESULTS_ROOT / "switch_timeline.csv")
    all_phases = [] if args.force else read_rows(RESULTS_ROOT / "phase_schedule.csv")
    completed = completed_run_ids(rows)
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
        errors = [error for error in errors if error.get("run_id") != rid]
        if had_previous_error and planned_logfile.exists() and not args.force:
            print("  previous error found; removing stale log and re-running", flush=True)
            planned_logfile.unlink()

        try:
            reuse_row = None
            if (
                params["profile"] == "paper_daily_stress"
                and not args.force
                and not args.no_reuse_rq1
            ):
                reuse_row = find_matching_rq1_row(
                    coord_label="DA",
                    rep=params["rep"],
                    item_spawning_time=120,
                    n_robots=20,
                    malicious_ratio=0.33,
                    fail_prob=0.66,
                    msg_loss_prob=0.10,
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
        }
        samples = read_overhead_samples(logfile) if logfile.exists() else []
        rows = [existing for existing in rows if existing.get("run_id") != rid]
        all_timeseries = drop_rows_for_run(all_timeseries, rid)
        all_switches = drop_rows_for_run(all_switches, rid)
        all_phases = drop_rows_for_run(all_phases, rid)

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
        all_phases.extend(phase_schedule_rows(run_meta=run_meta, phases=definition["phases"]))

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
        write_rows(RESULTS_ROOT / "adaptation_state_timeseries.csv", all_timeseries)
        write_rows(RESULTS_ROOT / "switch_timeline.csv", all_switches)
        write_rows(RESULTS_ROOT / "phase_schedule.csv", all_phases)
        if errors:
            write_rows(RESULTS_ROOT / "errors.csv", errors)

    summary = summarise_rows(
        rows,
        group_fields=["profile", "coord_label"],
        metric_fields=[
            "created",
            "delivered",
            "pending",
            "success_rate",
            "avg_latency_s",
            "p95_latency_s",
            "switch_count",
            "adapt_checks",
            "adapt_overhead_ms_mean",
        ],
    )
    write_rows(RESULTS_ROOT / "summary_by_profile.csv", summary)
    write_rows(RESULTS_ROOT / "state_distribution.csv", state_distribution_rows(all_timeseries))

    print("=" * 80)
    print(f"RQ2 campaign completed in {time.time() - started_at:.2f}s wall-clock.")
    print(f"Run-level CSV:       {RESULTS_ROOT / 'runs.csv'}")
    print(f"Timeseries CSV:      {RESULTS_ROOT / 'adaptation_state_timeseries.csv'}")
    print(f"Switch timeline CSV: {RESULTS_ROOT / 'switch_timeline.csv'}")
    print(f"Summary CSV:         {RESULTS_ROOT / 'summary_by_profile.csv'}")
    print("=" * 80)


if __name__ == "__main__":
    run_campaign(parse_args())
