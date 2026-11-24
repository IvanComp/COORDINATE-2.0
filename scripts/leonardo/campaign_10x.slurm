#!/bin/bash
# One array task = one independent repetition (its own seed set and sandbox).
# Submitted by submit_10x.sh, which sets --array, account, partition, cpus, time.
#SBATCH --job-name=coord-10x
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --output=slurm_logs/10x-%A_%a.out
#SBATCH --error=slurm_logs/10x-%A_%a.err

set -euo pipefail

ROOT_DIR="${ROOT_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}"
cd "$ROOT_DIR"
source scripts/leonardo/config.sh

REP="${SLURM_ARRAY_TASK_ID:?must run as an array task}"
SANDBOX="$CAMPAIGN_ROOT/rep_$(printf '%02d' "$REP")"
WORKERS="${SLURM_CPUS_PER_TASK:-1}"
[[ -d "$SANDBOX/Paper Results" ]] || { echo "Sandbox missing: $SANDBOX (run prepare_campaign.sh)"; exit 2; }

module purge 2>/dev/null || true
for candidate in python/3.12.3 python/3.11.7 python/3.11 python; do
    module load "$candidate" 2>/dev/null && break
done
source .venv/bin/activate
export RTLOLA_BINARY_PATH="${RTLOLA_BINARY_PATH:-$ROOT_DIR/.venv/bin/rtlola-cli}"
# One simulation per core: keep numpy single-threaded.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "[10x] rep=$REP sandbox=$SANDBOX workers=$WORKERS host=$(hostname) job=${SLURM_JOB_ID:-}"
lscpu | grep -E "Model name|^CPU\(s\)" || true
python scripts/check_rtlola.py

IFS=',' read -ra rq_list <<< "$RQS"
status=0
for rq in "${rq_list[@]}"; do
    extra=()
    [[ "$rq" == "RQ3" ]] && extra+=(--no-reuse-rq1)
    [[ "$rq" == "RQ1" || "$rq" == "RQ4" ]] && extra+=(--machine-label "$MACHINE_LABEL")
    echo "[10x] ===== $rq rep $REP start $(date -Iseconds)"
    # shellcheck disable=SC2086
    if ! python scripts/leonardo/run_one_rep.py --sandbox "$SANDBOX" --rq "$rq" --rep "$REP" -- \
            --workers "$WORKERS" "${extra[@]}" $EXTRA_ARGS; then
        echo "[10x] $rq rep $REP FAILED"
        status=1
    fi
    echo "[10x] ===== $rq rep $REP end $(date -Iseconds)"
done
# Re-submitting the same array resumes: runners skip runs already in runs.csv.
exit $status
