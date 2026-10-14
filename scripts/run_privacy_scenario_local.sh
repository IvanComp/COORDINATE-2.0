#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
if [[ -x .venv/bin/python ]]; then
    .venv/bin/python Privacy-Scenario/run_privacy_experiments.py "$@"
else
    python3 Privacy-Scenario/run_privacy_experiments.py "$@"
fi
