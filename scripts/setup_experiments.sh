#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3.12 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3.12)"
    elif command -v python3.11 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3.11)"
    elif command -v python3.10 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3.10)"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
    echo "[setup] ERROR: Python >= 3.10 is required."
    exit 2
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"[setup] ERROR: Python >= 3.10 required, found {sys.version.split()[0]}")
print(f"[setup] Python: {sys.version.split()[0]}")
PY

echo "[setup] Creating .venv with $PYTHON_BIN"
rm -rf .venv
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-docker.txt matplotlib notebook ipykernel

if ! bash scripts/install_rtlola_venv.sh; then
    echo "[setup] WARNING: RTLola could not be installed automatically."
    echo "[setup] The environment is still usable, but dynamic-adaptation runs may fail."
fi

echo "[setup] Ready."
echo "  Python: $(.venv/bin/python --version)"
if [[ -x ".venv/bin/rtlola-cli" ]] && .venv/bin/rtlola-cli --version >/dev/null 2>&1; then
    echo "  RTLola: $(.venv/bin/rtlola-cli --version)"
else
    echo "  RTLola: missing or unusable"
fi
