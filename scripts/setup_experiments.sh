#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_VENV="$ROOT_DIR/.venv"
TARGET_VENV="${VENV_DIR:-${VIRTUAL_ENV:-$DEFAULT_VENV}}"
if [[ "$TARGET_VENV" != /* ]]; then
    TARGET_VENV="$ROOT_DIR/$TARGET_VENV"
fi
TARGET_BIN="$TARGET_VENV/bin"

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

if [[ -x "$TARGET_BIN/python" ]]; then
    echo "[setup] Reusing existing virtual environment at $TARGET_VENV"
else
    echo "[setup] Creating virtual environment at $TARGET_VENV with $PYTHON_BIN"
    rm -rf "$TARGET_VENV"
    "$PYTHON_BIN" -m venv "$TARGET_VENV"
fi

if [[ "$TARGET_VENV" != "$DEFAULT_VENV" ]] && [[ ! -e "$DEFAULT_VENV" ]]; then
    ln -s "$TARGET_VENV" "$DEFAULT_VENV"
    echo "[setup] Linked $DEFAULT_VENV -> $TARGET_VENV"
fi

source "$TARGET_BIN/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ! bash scripts/install_rtlola_venv.sh; then
    echo "[setup] WARNING: RTLola could not be installed automatically."
    echo "[setup] The environment is still usable, but dynamic-adaptation runs may fail."
fi

echo "[setup] Ready."
echo "  Venv:   $TARGET_VENV"
echo "  Python: $("$TARGET_BIN/python" --version)"
if [[ -x "$TARGET_BIN/rtlola-cli" ]] && "$TARGET_BIN/rtlola-cli" --version >/dev/null 2>&1; then
    echo "  RTLola: $("$TARGET_BIN/rtlola-cli" --version)"
else
    echo "  RTLola: missing or unusable"
fi
