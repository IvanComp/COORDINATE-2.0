#!/usr/bin/env bash
#SBATCH --job-name=coordinate-privacy
#SBATCH --output=slurm_logs/privacy-%j.out
#SBATCH --error=slurm_logs/privacy-%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
set -euo pipefail
project_dir="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$project_dir"
source .venv/bin/activate
python Privacy-Scenario/run_privacy_experiments.py "$@"
