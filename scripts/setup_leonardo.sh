#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[setup] Project: $ROOT_DIR"

if command -v module >/dev/null 2>&1; then
    echo "[setup] Loading Python module if available"
    module purge || true
    module load python/3.11.7 || true
fi

PYTHON_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "$PYTHON_BIN" ]]; then
    echo "[setup] ERROR: Python not found. Load a Python >= 3.10 module first."
    exit 2
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"[setup] ERROR: Python >= 3.10 required, found {sys.version.split()[0]}")
print(f"[setup] Python: {sys.version.split()[0]}")
PY

echo "[setup] Creating .venv"
rm -rf .venv
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-docker.txt matplotlib notebook ipykernel

bash scripts/install_rtlola_venv.sh

echo "[setup] Final checks"
python --version
.venv/bin/rtlola-cli --version

echo
echo "[setup] Done. Submit a small test with:"
echo "  export REPETITIONS=1"
echo "  export RQS='RQ1'"
echo "  export EXTRA_ARGS='--limit 4'"
echo "  sbatch run_campaign.slurm"
