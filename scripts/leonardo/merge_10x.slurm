#!/bin/bash
# Runs after the array (afterany): merges the sandboxes and runs the statistics.
#SBATCH --job-name=coord-10x-merge
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=slurm_logs/10x-merge-%j.out
#SBATCH --error=slurm_logs/10x-merge-%j.err
set -euo pipefail
ROOT_DIR="${ROOT_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}"
cd "$ROOT_DIR"
source scripts/leonardo/config.sh
module purge 2>/dev/null || true
for candidate in python/3.12.3 python/3.11.7 python/3.11 python; do
    module load "$candidate" 2>/dev/null && break
done
source .venv/bin/activate
OUT="$ROOT_DIR/Paper Results/$MERGED_DIR_NAME"
python scripts/leonardo/merge_reps.py --campaign-root "$CAMPAIGN_ROOT" --out "$OUT" --rqs "$RQS"
if [[ -f "$OUT/RQ1/runs.csv" ]]; then
    python "Paper Results/stats_analysis.py" --rq RQ1 --runs "$OUT/RQ1/runs.csv" --out "$OUT/stats/RQ1"
fi
if [[ -f "$OUT/RQ3/runs.csv" ]]; then
    python "Paper Results/stats_analysis.py" --rq RQ3 --runs "$OUT/RQ3/runs.csv" --out "$OUT/stats/RQ3"
fi
if [[ -f "$OUT/RQ2/runs.csv" ]]; then
    python "Paper Results/stats_analysis.py" --rq RQ2 --runs "$OUT/RQ2/runs.csv" --out "$OUT/stats/RQ2"
fi
echo "[merge] Done: $OUT"
