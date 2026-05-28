#!/bin/bash
#SBATCH --job-name=coordinate-rqs
#SBATCH --output=slurm_logs/coordinate_%j.out
#SBATCH --error=slurm_logs/coordinate_%j.err
#SBATCH --time=48:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G

# If LEONARDO requires explicit accounting/partition values, uncomment and
# adapt the following lines before submitting:
##SBATCH --account=<your_account>
##SBATCH --partition=<your_partition>

set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

mkdir -p slurm_logs

echo "Job id: ${SLURM_JOB_ID:-local}"
echo "Node list: ${SLURM_JOB_NODELIST:-local}"
echo "Project dir: $PROJECT_DIR"
echo "Started at: $(date -Is)"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "ERROR: .venv not found in $PROJECT_DIR"
    echo "Create it first with a recent Python, for example:"
    echo "  module purge"
    echo "  module load python/3.11.7"
    echo "  python3.11 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  python -m pip install --upgrade pip"
    echo "  python -m pip install -r requirements-docker.txt matplotlib notebook ipykernel"
    exit 2
fi

source .venv/bin/activate

python --version
python - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"ERROR: Python >= 3.10 required, found {sys.version.split()[0]}")
PY

if ! command -v rtlola-cli >/dev/null 2>&1 && [[ ! -x "./rtlola-cli" ]]; then
    echo "WARNING: rtlola-cli was not found in PATH or as ./rtlola-cli."
    echo "Dynamic-adaptation runs may fail unless RTLola is installed."
fi

REPETITIONS="${REPETITIONS:-2}"
RQS="${RQS:-RQ1,RQ2,RQ3,RQ4}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

read -r -a EXTRA_ARGS_ARRAY <<< "$EXTRA_ARGS"

echo "Repetitions: $REPETITIONS"
echo "RQs: $RQS"
echo "Extra args: ${EXTRA_ARGS:-<none>}"

python "Paper Results/run_full_paper_campaign.py" \
    --repetitions "$REPETITIONS" \
    --rqs "$RQS" \
    "${EXTRA_ARGS_ARRAY[@]}"

echo "Finished at: $(date -Is)"
