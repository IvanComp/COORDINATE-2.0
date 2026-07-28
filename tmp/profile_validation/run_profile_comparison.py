"""Compare DA with static mechanisms on the calibrated RQ2 profile."""

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
SEED = 20260731
ARCHITECTURES = {
    "DA": "dynamic-adaptation",
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(PAPER_RESULTS))
    spec.loader.exec_module(module)
    return module


def main() -> int:
    utils = load_module("paper_experiment_utils", PAPER_RESULTS / "paper_experiment_utils.py")
    rq2 = load_module("run_rq2_experiments", PAPER_RESULTS / "run_rq2_experiments.py")
    definition = rq2.profile_definition("triangular_daily_cycle", SIM_DAYS)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []

    for label, architecture in ARCHITECTURES.items():
        run_dir = OUTPUT / label
        run_dir.mkdir(exist_ok=True)
        logfile = run_dir / "simulation_log.csv"
        config = dict(utils.BASE_CONFIG)
        config.update(definition["initial_updates"])
        config.update({
            "ARCHITECTURE": architecture,
            "INITIAL_ARCHITECTURE": "centralized-impprox",
            "SIM_TIME": SIM_DAYS * 24 * 3600,
            "RANDOM_SEED": SEED,
            "RESULTS_DIR": str(run_dir),
            "LOGFILE": str(logfile),
            "SIMTIME_LOGFILE": str(run_dir / "sim_time.csv"),
            "PHASES": definition["phases"],
            "RTLOLA_BINARY_PATH": "/Users/ivan/.cargo/bin/rtlola-cli",
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
    (OUTPUT / "profile.json").write_text(json.dumps(definition, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
