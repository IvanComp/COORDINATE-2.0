"""Map static-mechanism trade-offs before defining DA fault windows."""

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).parent
BASE_CONFIG = ROOT / "tmp" / "da_policy_smoke" / "config.json"
ARCHITECTURES = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
}
PROFILES = {
    "nominal": {"N_MALICIOUS": 0, "FAIL_PROB": 0.01, "COMM_FAIL_PROB": 0.00, "ITEM_SPAWNING_TIME": 120.0},
    "moderate_local": {"N_MALICIOUS": 6, "FAIL_PROB": 0.03, "COMM_FAIL_PROB": 0.02, "ITEM_SPAWNING_TIME": 105.0},
    "security_pressure": {"N_MALICIOUS": 12, "FAIL_PROB": 0.04, "COMM_FAIL_PROB": 0.05, "ITEM_SPAWNING_TIME": 90.0},
    "network_faults": {"N_MALICIOUS": 6, "FAIL_PROB": 0.06, "COMM_FAIL_PROB": 0.35, "ITEM_SPAWNING_TIME": 90.0},
    "critical": {"N_MALICIOUS": 18, "FAIL_PROB": 0.08, "COMM_FAIL_PROB": 0.50, "ITEM_SPAWNING_TIME": 75.0},
    "ce_rescue": {"N_MALICIOUS": 0, "FAIL_PROB": 0.05, "COMM_FAIL_PROB": 0.00, "ITEM_SPAWNING_TIME": 180.0},
    "sd_rescue": {"N_MALICIOUS": 6, "FAIL_PROB": 0.05, "COMM_FAIL_PROB": 0.00, "ITEM_SPAWNING_TIME": 120.0},
    "fd_resilient": {"N_MALICIOUS": 15, "FAIL_PROB": 0.08, "COMM_FAIL_PROB": 0.20, "ITEM_SPAWNING_TIME": 90.0},
}


def load_analyzer():
    module_path = ROOT / "Paper Results" / "paper_experiment_utils.py"
    spec = importlib.util.spec_from_file_location("paper_experiment_utils", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="", help="Comma-separated profile names to run.")
    args = parser.parse_args()
    selected = [name for name in args.profiles.split(",") if name] or list(PROFILES)
    unknown = [name for name in selected if name not in PROFILES]
    if unknown:
        raise ValueError(f"Unknown profile(s): {', '.join(unknown)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    base = json.loads(BASE_CONFIG.read_text())
    analyzer = load_analyzer()
    rows = []

    for profile_index, profile in enumerate(selected, start=1):
        updates = PROFILES[profile]
        for label, architecture in ARCHITECTURES.items():
            run_dir = OUTPUT / profile / label
            run_dir.mkdir(parents=True, exist_ok=True)
            config = dict(base)
            config.update({
                **updates,
                "ARCHITECTURE": architecture,
                "RESULTS_DIR": str(run_dir),
                "LOGFILE": str(run_dir / "simulation_log.csv"),
                "SIMTIME_LOGFILE": str(run_dir / "sim_time.csv"),
                "SIM_TIME": 3 * 24 * 3600,
                "RANDOM_SEED": 20260730 + profile_index,
                "PHASES": [],
                "COORDINATOR_SERVICE_TIME": 0.25,
                "COORDINATOR_FAKE_REQUEST_SERVICE_TIME": 0.25,
                "COORDINATOR_FAILURE_PROB": 0.0,
                "COORDINATOR_AVAILABLE": True,
                "SD_COORDINATION_HOPS": 1,
            })
            config_path = run_dir / "config.json"
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            print(f"=== {profile} / {label} ===", flush=True)
            completed = subprocess.run(
                [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT,
            )
            if completed.returncode:
                return completed.returncode
            metrics = analyzer.analyze_log(run_dir / "simulation_log.csv", config["SIM_TIME"])
            rows.append({
                "profile": profile,
                "mechanism": label,
                **updates,
                **metrics,
            })

    suffix = "_".join(selected) if args.profiles else "all"
    summary = OUTPUT / f"static_summary_{suffix}.csv"
    with summary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
