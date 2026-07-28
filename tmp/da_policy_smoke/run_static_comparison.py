"""Run CE, SD and FD with the exact smoke-test scenario used by DA."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG = Path(__file__).with_name("config.json")
ARCHITECTURES = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
}


def main() -> int:
    base = json.loads(BASE_CONFIG.read_text())
    for label, architecture in ARCHITECTURES.items():
        output_dir = BASE_CONFIG.parent / label
        output_dir.mkdir(exist_ok=True)
        config = dict(base)
        config.update(
            {
                "RESULTS_DIR": str(output_dir),
                "SIMTIME_LOGFILE": str(output_dir / "sim_time.csv"),
                "LOGFILE": str(output_dir / "simulation_log.csv"),
                "ARCHITECTURE": architecture,
            }
        )
        config_path = output_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        print(f"\n=== {label}: {architecture} ===", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "sim.simulator", str(config_path)], cwd=ROOT
        )
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
