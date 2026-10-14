#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
mkdir -p slurm_logs
sbatch scripts/privacy_scenario_leonardo.slurm "$@"
