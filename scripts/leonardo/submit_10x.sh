#!/usr/bin/env bash
# Submit the 10-repetition campaign as a SLURM job array + a merge job.
#   bash scripts/leonardo/submit_10x.sh test   # 2 reps, 2 simulated days, 8 runs per RQ
#   bash scripts/leonardo/submit_10x.sh full   # 10 reps, full campaign
# Re-running "full" after a timeout resumes from what each sandbox already has.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
MODE="${1:-test}"

case "$MODE" in
    test)
        export REPS="${REPS:-1-2}"
        export CAMPAIGN_NAME="${CAMPAIGN_NAME:-coordinate_10x_test}"
        export MERGED_DIR_NAME="${MERGED_DIR_NAME:-leonardo_10x_test}"
        export EXTRA_ARGS="${EXTRA_ARGS:---sim-days 2 --limit 8}"
        export CPUS_PER_REP="${CPUS_PER_REP:-8}"
        export TIME_PER_REP="${TIME_PER_REP:-00:30:00}"
        ;;
    full) ;;
    *) echo "Usage: $0 test|full"; exit 2 ;;
esac
source scripts/leonardo/config.sh

# Sandboxes are cheap to (re)build and keep the code in sync with this checkout.
bash scripts/leonardo/prepare_campaign.sh >/dev/null
mkdir -p slurm_logs

common=(--account="$SBATCH_ACCOUNT" --partition="$SBATCH_PARTITION" --qos="$SBATCH_QOS")
# Exported variables (REPS, RQS, EXTRA_ARGS, CAMPAIGN_*) reach the job.
export ROOT_DIR REPS RQS EXTRA_ARGS CAMPAIGN_NAME CAMPAIGN_ROOT MERGED_DIR_NAME MACHINE_LABEL

array_id=$(sbatch --parsable "${common[@]}" --export=ALL \
    --array="$REPS" --cpus-per-task="$CPUS_PER_REP" --mem="$MEM_PER_REP" --time="$TIME_PER_REP" \
    scripts/leonardo/campaign_10x.slurm)
merge_id=$(sbatch --parsable "${common[@]}" --export=ALL \
    --dependency="afterany:${array_id}" scripts/leonardo/merge_10x.slurm)

echo "[submit] mode=$MODE reps=$REPS rqs=$RQS cpus/rep=$CPUS_PER_REP time/rep=$TIME_PER_REP"
echo "[submit] campaign root: $CAMPAIGN_ROOT"
echo "[submit] array job: $array_id   merge job: $merge_id"
echo "[submit] monitor:  squeue -u \$USER ;  tail -f slurm_logs/10x-${array_id}_1.out"
