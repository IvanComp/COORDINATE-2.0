#!/bin/bash
# RQ4 nominal campaign on a single exclusive CPU node.
#
# The node is requested exclusively because RQ4 measures wall time: sharing the
# node with another job would make the timings unreproducible.
#
# Submit with the account and partition of your CINECA project, for example:
#   sbatch --account=<your_account> --partition=dcgp_usr_prod scripts/rq4_leonardo.slurm

#SBATCH --job-name=coordinate-rq4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --exclusive
#SBATCH --time=01:00:00
#SBATCH --output=slurm_logs/rq4-%j.out
#SBATCH --error=slurm_logs/rq4-%j.err

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p slurm_logs

# The paper reports this node as the workstation-class profile, contrasted with
# the commodity-hardware profile. The job prints lscpu so the actual CPU model
# can be stated in the paper.
MACHINE_LABEL="${MACHINE_LABEL:-workstation}"

module purge 2>/dev/null || true
for candidate in python/3.12.3 python/3.11.7 python/3.11 python; do
    module load "$candidate" 2>/dev/null && break
done

# Running the campaign needs only numpy, so a virtual environment is optional:
# the module Python is enough when it already provides numpy.
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
    echo "[rq4] Using virtual environment: $PWD/.venv"
else
    echo "[rq4] No .venv found, using the module Python"
fi
python -c "import numpy; print('[rq4] numpy', numpy.__version__)"

# Compute nodes have no outbound network, so the monitor binary must already be
# on disk. The first readable candidate wins.
for candidate in "${RTLOLA_BINARY_PATH:-}" "$PWD/.venv/bin/rtlola-cli" "$PWD/bin/rtlola-cli"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
        export RTLOLA_BINARY_PATH="$candidate"
        break
    fi
done
echo "[rq4] RTLOLA_BINARY_PATH=${RTLOLA_BINARY_PATH:-<unset>}"

echo "[rq4] Host: $(hostname)"
echo "[rq4] Python: $(python --version 2>&1)"
lscpu | grep -E "Model name|^CPU\(s\)|Thread|Core\(s\)|Socket" || true

python scripts/check_rtlola.py

echo "[rq4] Campaign design:"
python "Paper Results/run_rq4_experiments.py" --dry-run

echo "[rq4] Running with machine label: $MACHINE_LABEL"
python "Paper Results/run_rq4_experiments.py" --machine-label "$MACHINE_LABEL"

echo "[rq4] Done. Results in Paper Results/RQ4/runs.csv"
