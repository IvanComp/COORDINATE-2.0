#!/usr/bin/env python3
"""
RQ2 runner: Dynamic Adaptation reaction to evolving operating conditions with
a more realistic task-completion regime.

RQ2 is deliberately DA-only. The goal is not to re-run the full comparison from
RQ1, but to inspect when DA switches, which monitored state caused the switch,
and whether switches align with persistent fault windows.

Default campaign:
    One repeated four-level daily operating cycle x 10 repetitions = 10 runs.

Run examples:
    python "Paper Results/run_rq2_experiments.py" --dry-run
    nohup python "Paper Results/run_rq2_experiments.py" > "Paper Results/RQ2/rq2.log" 2>&1 &

Resume behavior:
    Completed runs are detected from RQ2/runs.csv.
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
    BASE_CONFIG,
    COORD_TO_ARCH,
    FD_POLICY_VERSION,
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
from sim.contextual_bandit import FEATURE_NAMES


RESULTS_ROOT = PAPER_ROOT / "RQ2"
TIMESERIES_PATH = RESULTS_ROOT / "adaptation_state_timeseries.csv.gz"
PROFILE_NAMES = ["adaptive_operating_cycle"]
RQ2_EXPERIMENT_PROFILE = "table-aligned-operating-cycle-v1"
DAILY_OPERATING_SEGMENTS = [
    ("P1", 0, 6),
    ("P2", 6, 12),
    ("P3", 12, 18),
    ("P4", 18, 24),
]

COMPLETION_CONFIG_UPDATES = {
    "TOPOLOGY_NAME": "ring25",
    "N_ROOMS": 25,
    "IMPORTANCE_PROBABILITIES": [0.55, 0.25, 0.20],
    "EXPIRATION_TIME": [28800, 14400, 7200],
    "EXPIRATION_DISTR": ["deterministic", "deterministic", "deterministic"],
    "ADAPTATION_CHECK_INTERVAL": 60 * 60.0,
    "ADAPTATION_WINDOW": 60 * 60.0,
    "BANDIT_FEEDBACK_WINDOW": 60 * 60.0,
    "ADAPTATION_MIN_SWITCH_INTERVAL": 60 * 60.0,
    "ADAPTATION_PERSISTENCE_CHECKS": 1,
    "BANDIT_EXPLORATION_EPSILON": 0.02,
    "BANDIT_MIN_EXPLORATION_EPSILON": 0.0,
    "BANDIT_EXPLORATION_BYPASS_PERSISTENCE": False,
    "COORDINATOR_SERVICE_TIME": 0.25,
    "COORDINATOR_FAKE_REQUEST_SERVICE_TIME": 0.25,
    "FD_INSPECTION_INTERVAL": 2 * 60.0,
    "FD_MAX_PATROLLERS": 2,
    "SD_COORDINATION_HOPS": 1,
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


def completed_run_ids(rows: list[dict[str, Any]], sim_days: int) -> set[str]:
    expected = expiration_metadata()
    completed: set[str] = set()
    for row in rows:
        run_id = str(row.get("run_id", ""))
        if not run_id or row.get("status") != "ok":
            continue
        try:
            if int(row.get("sim_days", "")) != sim_days:
                continue
        except (TypeError, ValueError):
            continue
        if str(row.get("log_expire", "")).lower() != "true":
            continue
        if str(row.get("fd_policy_version", "")) != FD_POLICY_VERSION:
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
    parser = argparse.ArgumentParser(description="Run RQ2 dynamic adaptation experiments.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per dynamic profile.")
    parser.add_argument("--sim-days", type=int, default=90, help="Number of simulated days.")
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


def configure_bandit_objective(args: argparse.Namespace) -> None:
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
    coordinator_service_time: float = 0.0,
    coordinator_failure_prob: float = 0.0,
    coordinator_available: bool = True,
) -> dict[str, Any]:
    return {
        "N_MALICIOUS": malicious_count(n_robots, malicious_ratio),
        "FAIL_PROB": fail_prob,
        "COMM_FAIL_PROB": msg_loss,
        "RECOVERY_TIME": recovery_time,
        "ITEM_SPAWNING_TIME": item_spawning_time,
        "COORDINATOR_SERVICE_TIME": coordinator_service_time,
        "COORDINATOR_FAILURE_PROB": coordinator_failure_prob,
        "COORDINATOR_AVAILABLE": coordinator_available,
    }


def profile_definition(profile_name: str, sim_days: int) -> dict[str, Any]:
    if profile_name != "adaptive_operating_cycle":
        raise ValueError(f"Unknown RQ2 profile: {profile_name}")

    n_robots = 20
    recovery = 1800.0
    description = "Repeated four-level daily operating cycle P1--P4."
    segments = []
    # P1 is the underlined baseline in Table~\ref{tab:usecase-inputs}. P2--P4
    # apply the 25%, 50%, and 75% increments of the daily operating profile.
    # The malicious ratio cannot exceed 100%, hence P4 is capped at 20 agents.
    mode_settings = {
        "P1": {"malicious": 0.60, "fail": 0.0900, "comm": 0.0300, "spawn": 120.0},
        "P2": {"malicious": 0.75, "fail": 0.1125, "comm": 0.0375, "spawn": 90.0},
        "P3": {"malicious": 0.90, "fail": 0.1350, "comm": 0.0450, "spawn": 60.0},
        "P4": {"malicious": 1.00, "fail": 0.1575, "comm": 0.0525, "spawn": 30.0},
    }
    for label, start_hour, end_hour in DAILY_OPERATING_SEGMENTS:
        mode = mode_settings[label]
        segments.append({
            "label": label,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "params": phase_params(
                n_robots=n_robots,
                malicious_ratio=mode["malicious"],
                fail_prob=mode["fail"],
                msg_loss=mode["comm"],
                recovery_time=recovery,
                item_spawning_time=mode["spawn"],
                coordinator_service_time=0.25,
                coordinator_available=True,
            ),
        })

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
            "COORDINATOR_SERVICE_TIME": first_phase["COORDINATOR_SERVICE_TIME"],
            "COORDINATOR_FAILURE_PROB": first_phase["COORDINATOR_FAILURE_PROB"],
            "COORDINATOR_AVAILABLE": first_phase["COORDINATOR_AVAILABLE"],
            "RECOVERY_TIME": first_phase["RECOVERY_TIME"],
            "ITEM_SPAWNING_TIME": first_phase["ITEM_SPAWNING_TIME"],
        },
        "segments": segments,
        "phases": phases,
    }


def selected_profiles(args: argparse.Namespace) -> list[str]:
    if args.quick:
        return ["adaptive_operating_cycle"]
    profiles = [name.strip() for name in args.profiles.split(",") if name.strip()]
    unknown = [name for name in profiles if name not in PROFILE_NAMES]
    if unknown:
        raise ValueError(f"Unknown RQ2 profile(s): {', '.join(unknown)}")
    return profiles


def campaign(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    profiles = selected_profiles(args)
    repetitions = 1 if args.quick else args.repetitions
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
    policy = str(BASE_CONFIG.get("ADAPTATION_POLICY", "contextual-bandit")).replace("-", "")
    reward_version = str(BASE_CONFIG.get("BANDIT_REWARD_VERSION", "default"))
    reward_version = reward_version.replace("-", "").replace("_", "")
    return (
        f"{params['profile_idx']:02d}_{params['profile']}_r{params['rep']:02d}_"
        f"DA_{policy}_{reward_version}_{RQ2_EXPERIMENT_PROFILE}"
    )


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
            "completion_rate": sample.get("completion_rate"),
            "terminal_tasks_window": sample.get("terminal_tasks_window"),
            "bandit_reward": sample.get("bandit_reward"),
            "bandit_reward_mode": sample.get("bandit_reward_mode"),
            "pending_ratio": sample.get("pending_ratio"),
            "failure_rate": sample.get("failure_rate"),
            "message_loss_rate": sample.get("message_loss_rate"),
            "network_probe_loss_rate": sample.get("network_probe_loss_rate"),
            "suspicious_signals_window": sample.get("suspicious_signals_window"),
            "context_arrival_rate_norm": sample.get("context_arrival_rate_norm"),
            "context_failure_norm": sample.get("context_failure_norm"),
            "context_network_probe_loss_rate": sample.get("context_network_probe_loss_rate"),
            "context_suspicion_norm": sample.get("context_suspicion_norm"),
            "bandit_context_key": sample.get("bandit_context_key"),
        })
    return rows


def run_campaign(args: argparse.Namespace) -> None:
    configure_bandit_objective(args)
    if not args.dry_run:
        rtlola_binary = ensure_rtlola_available()
        print(f"[preflight] RTLola binary: {rtlola_binary}")
    combos = campaign(args)
    design = {
        "research_question": "RQ2",
        "experiment_profile": RQ2_EXPERIMENT_PROFILE,
        "sim_days": args.sim_days,
        "repetitions": args.repetitions,
        "profiles": selected_profiles(args),
        "total_runs": len(combos),
        "coordination_mechanisms": ["DA"],
        "adaptation_policy": BASE_CONFIG["ADAPTATION_POLICY"],
        "bandit_reward_version": BASE_CONFIG.get("BANDIT_REWARD_VERSION", ""),
        "fd_policy_version": FD_POLICY_VERSION,
        "fd_policy": {
            "inspection_interval_s": COMPLETION_CONFIG_UPDATES["FD_INSPECTION_INTERVAL"],
            "max_patrollers": COMPLETION_CONFIG_UPDATES["FD_MAX_PATROLLERS"],
        },
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
    expected_policy = str(BASE_CONFIG["ADAPTATION_POLICY"]).lower()
    rows = [
        row for row in rows
        if (
            str(row.get("adaptation_policy", "")).lower() == expected_policy
            and str(row.get("experiment_profile", "")) == RQ2_EXPERIMENT_PROFILE
            and str(row.get("fd_policy_version", "")) == FD_POLICY_VERSION
        )
    ]
    all_timeseries = [
        row for row in all_timeseries
        if (
            str(row.get("adaptation_policy", "")).lower() == expected_policy
            and str(row.get("experiment_profile", "")) == RQ2_EXPERIMENT_PROFILE
            and str(row.get("fd_policy_version", "")) == FD_POLICY_VERSION
        )
    ]
    all_switches = [
        row for row in all_switches
        if (
            str(row.get("adaptation_policy", "")).lower() == expected_policy
            and str(row.get("experiment_profile", "")) == RQ2_EXPERIMENT_PROFILE
            and str(row.get("fd_policy_version", "")) == FD_POLICY_VERSION
        )
    ]
    completed = completed_run_ids([
        row for row in rows
        if str(row.get("log_expire", "")).lower() == "true"
    ], args.sim_days)
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
            "experiment_profile": RQ2_EXPERIMENT_PROFILE,
            "profile": params["profile"],
            "rep": params["rep"],
            "seed": params["seed"],
            "coord_label": "DA",
            "architecture": COORD_TO_ARCH["DA"],
            "adaptation_policy": cfg.get("ADAPTATION_POLICY", ""),
            "bandit_reward_version": cfg.get("BANDIT_REWARD_VERSION", ""),
            "bandit_objective_mode": cfg.get("BANDIT_OBJECTIVE_MODE", ""),
            "bandit_completion_weight": cfg.get("BANDIT_COMPLETION_WEIGHT", ""),
            "fd_policy_version": FD_POLICY_VERSION,
            "fd_inspection_interval_s": cfg["FD_INSPECTION_INTERVAL"],
            "fd_max_patrollers": cfg["FD_MAX_PATROLLERS"],
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
