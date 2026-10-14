#!/usr/bin/env bash
set -euo pipefail
scenario_dir="$(cd "$(dirname "$0")" && pwd)"
project_dir="$(cd "$scenario_dir/.." && pwd)"
cd "$project_dir"
python3 Privacy-Scenario/run_privacy_experiments.py "$@"
