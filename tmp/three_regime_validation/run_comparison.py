"""Validate a mechanism-neutral daily operating-regime cycle."""

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS = ROOT / "Paper Results"
OUTPUT = Path(__file__).parent
SIM_DAYS = 7
SEED = 20260801
ARCHITECTURES = {
    "DA": "dynamic-adaptation",
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
}
DAILY_SEGMENTS = (
    # These regimes were selected from the static calibration scan, where each
    # mechanism is evaluated under the same configuration without DA.
    ("clean_central", 0, 6, 0, 0.02, 0.00, 60.0),
    ("malicious_peer", 6, 12, 6, 0.03, 0.00, 90.0),
    ("network_isolated", 12, 18, 0, 0.10, 0.80, 90.0),
    ("recovery", 18, 24, 0, 0.02, 0.00, 180.0),
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(PAPER_RESULTS))
    spec.loader.exec_module(module)
    return module


def daily_phases(sim_days=SIM_DAYS):
    phases = []
    for day in range(sim_days):
        start = day * 86400
        for label, start_hour, end_hour, malicious, failure, message_loss, spawn in DAILY_SEGMENTS:
            phases.append({
                "label": label,
                "start": start + start_hour * 3600,
                "end": start + end_hour * 3600,
                "N_MALICIOUS": malicious,
                "FAIL_PROB": failure,
                "COMM_FAIL_PROB": message_loss,
                "RECOVERY_TIME": 1800.0,
                "ITEM_SPAWNING_TIME": spawn,
                "COORDINATOR_SERVICE_TIME": 0.25,
                "COORDINATOR_FAKE_REQUEST_SERVICE_TIME": 0.25,
                "COORDINATOR_FAILURE_PROB": 0.0,
                "COORDINATOR_AVAILABLE": True,
            })
    return phases


def main() -> int:
    utils = load_module("paper_experiment_utils", PAPER_RESULTS / "paper_experiment_utils.py")
    phases = daily_phases()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []

    for label, architecture in ARCHITECTURES.items():
        run_dir = OUTPUT / label
        run_dir.mkdir(exist_ok=True)
        logfile = run_dir / "simulation_log.csv"
        config = dict(utils.BASE_CONFIG)
        config.update({
            "ARCHITECTURE": architecture,
            "INITIAL_ARCHITECTURE": "centralized-impprox",
            "SIM_TIME": SIM_DAYS * 86400,
            "RANDOM_SEED": SEED,
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
        print(f"=== {label}: {architecture} ===", flush=True)
        completed = subprocess.run(
            [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT,
        )
        if completed.returncode:
            return completed.returncode
        results.append({"mechanism": label, **utils.analyze_log(logfile, config["SIM_TIME"])})

    with (OUTPUT / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    (OUTPUT / "profile.json").write_text(json.dumps({"phases": phases}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
