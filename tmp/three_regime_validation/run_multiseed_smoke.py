"""Run independent DA/static smoke comparisons for the operating-regime cycle."""

import csv
from pathlib import Path
import json
import subprocess
import sys

from run_comparison import ARCHITECTURES, OUTPUT, ROOT, PAPER_RESULTS, daily_phases, load_module


SIM_DAYS = 10
SEEDS = (20260811, 20260812, 20260813)


def main() -> int:
    utils = load_module("paper_experiment_utils", PAPER_RESULTS / "paper_experiment_utils.py")
    phases = daily_phases(SIM_DAYS)
    rows = []

    for seed in SEEDS:
        for label, architecture in ARCHITECTURES.items():
            run_dir = OUTPUT / "multiseed" / str(seed) / label
            run_dir.mkdir(parents=True, exist_ok=True)
            logfile = run_dir / "simulation_log.csv"
            config = dict(utils.BASE_CONFIG)
            config.update({
                "ARCHITECTURE": architecture,
                "INITIAL_ARCHITECTURE": "centralized-impprox",
                "SIM_TIME": SIM_DAYS * 86400,
                "RANDOM_SEED": seed,
                "RESULTS_DIR": str(run_dir),
                "LOGFILE": str(logfile),
                "SIMTIME_LOGFILE": str(run_dir / "sim_time.csv"),
                "PHASES": phases,
                "RTLOLA_BINARY_PATH": "/Users/ivan/.cargo/bin/rtlola-cli",
                "FD_MAX_PATROLLERS": 2,
                "SD_COORDINATION_HOPS": 1,
            })
            config_path = run_dir / "config.json"
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            print(f"=== seed={seed} {label}: {architecture} ===", flush=True)
            completed = subprocess.run(
                [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT,
            )
            if completed.returncode:
                return completed.returncode
            rows.append({"seed": seed, "mechanism": label, **utils.analyze_log(logfile, config["SIM_TIME"])})

    summary_path = OUTPUT / "multiseed_summary.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
