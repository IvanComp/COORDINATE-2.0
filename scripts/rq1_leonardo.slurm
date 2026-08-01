#!/bin/bash
# RQ1: complete the campaign up to ten repetitions per configuration.
#
# This is the workload that justifies a cluster: about 1700 runs are missing,
# roughly 63 core-hours, so the wall-clock time is divided by the number of
# cores granted to the job.
#
# The runner parallelises across independent simulations, so --cpus-per-task is
# the knob that matters. Raise it to whatever the partition allows and the job
# scales down accordingly:
#     8 cores  -> about  8 h
#    16 cores  -> about  4 h
#    32 cores  -> about  2 h
#
# Check what the partition grants before raising it:
#    scontrol show partition <partition> | tr ' ' '\n' | grep -i maxcpus
#    sacctmgr show qos format=Name%20,MaxTRESPerJob%30
#
# Submit with:
#    sbatch scripts/rq1_leonardo.slurm
#    sbatch --account=<account> --partition=<partition> scripts/rq1_leonardo.slurm

#SBATCH --job-name=coordinate-rq1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=slurm_logs/rq1-%j.out
#SBATCH --error=slurm_logs/rq1-%j.err

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p slurm_logs

# Timings recorded here must stay distinguishable from the ones measured on the
# laptop, because RQ3 reads wall time and adaptation overhead from RQ1 results.
MACHINE_LABEL="${MACHINE_LABEL:-leonardo}"

# os.cpu_count() reports every core of the node, not the cores Slurm granted.
WORKERS="${SLURM_CPUS_PER_TASK:-1}"

module purge 2>/dev/null || true
for candidate in python/3.12.3 python/3.11.7 python/3.11 python; do
    module load "$candidate" 2>/dev/null && break
done

if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
    echo "[rq1] Using virtual environment: $PWD/.venv"
else
    echo "[rq1] No .venv found, using the module Python"
fi
python -c "import numpy; print('[rq1] numpy', numpy.__version__)"

for candidate in "${RTLOLA_BINARY_PATH:-}" "$PWD/.venv/bin/rtlola-cli" "$PWD/bin/rtlola-cli"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
        export RTLOLA_BINARY_PATH="$candidate"
        break
    fi
done
echo "[rq1] RTLOLA_BINARY_PATH=${RTLOLA_BINARY_PATH:-<unset>}"

echo "[rq1] Host: $(hostname)"
lscpu | grep -E "Model name|^CPU\(s\)|Thread|Core\(s\)|Socket" || true

python scripts/check_rtlola.py

echo "[rq1] Running with machine label: $MACHINE_LABEL and $WORKERS worker(s)"
python "Paper Results/run_rq1_experiments.py" \
    --repetitions 10 \
    --workers "$WORKERS" \
    --machine-label "$MACHINE_LABEL"

echo "[rq1] Done. Results in Paper Results/RQ1/runs.csv"
