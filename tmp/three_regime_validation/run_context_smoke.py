"""Run one DA day and report the RTLola context received by the policy."""

import csv
import json
import subprocess
import sys

from run_comparison import OUTPUT, PAPER_RESULTS, ROOT, daily_phases, load_module


SEED = 20260821


def main() -> int:
    utils = load_module("paper_experiment_utils", PAPER_RESULTS / "paper_experiment_utils.py")
    run_dir = OUTPUT / "context_smoke"
    run_dir.mkdir(parents=True, exist_ok=True)
    logfile = run_dir / "simulation_log.csv"
    config = dict(utils.BASE_CONFIG)
    config.update({
        "ARCHITECTURE": "dynamic-adaptation",
        "INITIAL_ARCHITECTURE": "centralized-impprox",
        "SIM_TIME": 86400,
        "RANDOM_SEED": SEED,
        "RESULTS_DIR": str(run_dir),
        "LOGFILE": str(logfile),
        "SIMTIME_LOGFILE": str(run_dir / "sim_time.csv"),
        "PHASES": daily_phases(1),
        "RTLOLA_BINARY_PATH": "/Users/ivan/.cargo/bin/rtlola-cli",
        "FD_MAX_PATROLLERS": 2,
        "SD_COORDINATION_HOPS": 1,
    })
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    completed = subprocess.run(
        [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT,
    )
    if completed.returncode:
        return completed.returncode

    overhead_path = run_dir / "simulation_log_overhead.csv"
    fields = (
        "sim_time",
        "context_arrival_rate_norm",
        "context_failure_norm",
        "context_network_probe_loss_rate",
        "context_suspicion_norm",
    )
    with overhead_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    print(",".join(fields))
    for row in rows[-8:]:
        print(",".join(row.get(field, "") for field in fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
