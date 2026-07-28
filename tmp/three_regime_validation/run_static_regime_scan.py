"""Find naturally favourable operating regimes for the three static mechanisms."""

import csv
import json
import subprocess
import sys

from run_comparison import ARCHITECTURES, OUTPUT, PAPER_RESULTS, ROOT, load_module


SIM_DAYS = 2
SEED = 20260831
REGIMES = {
    "clean_light": {"ITEM_SPAWNING_TIME": 180.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.02, "COMM_FAIL_PROB": 0.00},
    "clean_heavy": {"ITEM_SPAWNING_TIME": 60.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.02, "COMM_FAIL_PROB": 0.00},
    "failure_moderate": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.07, "COMM_FAIL_PROB": 0.00},
    "failure_high": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.12, "COMM_FAIL_PROB": 0.00},
    "malicious_moderate": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 6, "FAIL_PROB": 0.03, "COMM_FAIL_PROB": 0.00},
    "malicious_high": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 12, "FAIL_PROB": 0.03, "COMM_FAIL_PROB": 0.00},
    "network_moderate": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.04, "COMM_FAIL_PROB": 0.30},
    "network_high": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.04, "COMM_FAIL_PROB": 0.60},
    "network_failure": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.07, "COMM_FAIL_PROB": 0.60},
    "network_failure_high": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 0, "FAIL_PROB": 0.10, "COMM_FAIL_PROB": 0.80},
    "network_malicious": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 6, "FAIL_PROB": 0.05, "COMM_FAIL_PROB": 0.60},
    "network_malicious_high": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 12, "FAIL_PROB": 0.05, "COMM_FAIL_PROB": 0.80},
    "mixed": {"ITEM_SPAWNING_TIME": 90.0, "N_MALICIOUS": 6, "FAIL_PROB": 0.08, "COMM_FAIL_PROB": 0.30},
}


def main() -> int:
    utils = load_module("paper_experiment_utils", PAPER_RESULTS / "paper_experiment_utils.py")
    root = OUTPUT / "static_regime_scan"
    rows = []
    for regime, overrides in REGIMES.items():
        for mechanism, architecture in ARCHITECTURES.items():
            if mechanism == "DA":
                continue
            run_dir = root / regime / mechanism
            run_dir.mkdir(parents=True, exist_ok=True)
            logfile = run_dir / "simulation_log.csv"
            config = dict(utils.BASE_CONFIG)
            config.update(overrides)
            config.update({
                "ARCHITECTURE": architecture,
                "SIM_TIME": SIM_DAYS * 86400,
                "RANDOM_SEED": SEED,
                "RESULTS_DIR": str(run_dir),
                "LOGFILE": str(logfile),
                "SIMTIME_LOGFILE": str(run_dir / "sim_time.csv"),
                "FD_MAX_PATROLLERS": 2,
                "SD_COORDINATION_HOPS": 1,
            })
            config_path = run_dir / "config.json"
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            print(f"=== {regime} {mechanism} ===", flush=True)
            completed = subprocess.run(
                [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT,
            )
            if completed.returncode:
                return completed.returncode
            rows.append({"regime": regime, "mechanism": mechanism, **utils.analyze_log(logfile, config["SIM_TIME"])})

    summary_path = root / "summary.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
