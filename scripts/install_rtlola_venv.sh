#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_VENV="${RTLOLA_TARGET_VENV:-${VIRTUAL_ENV:-$ROOT_DIR/.venv}}"
TARGET_BIN="$TARGET_VENV/bin"

if [[ ! -f "$TARGET_BIN/activate" ]]; then
    echo "[rtlola] ERROR: virtual environment not found at $TARGET_VENV."
    echo "[rtlola] Create it first or set RTLOLA_TARGET_VENV=/path/to/venv."
    exit 2
fi

source "$TARGET_BIN/activate"

if [[ -x "$TARGET_BIN/rtlola-cli" ]] && "$TARGET_BIN/rtlola-cli" --version >/dev/null 2>&1; then
    echo "[rtlola] Using existing venv binary: $TARGET_BIN/rtlola-cli"
    "$TARGET_BIN/rtlola-cli" --version
    exit 0
fi

if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
    echo "[rtlola] Installing Rust in \$HOME via rustup"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o rustup.sh
    sh rustup.sh -y --profile minimal
    rm -f rustup.sh
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
fi

echo "[rtlola] Installing rtlola-cli 0.1.2 into $TARGET_BIN"
cargo install rtlola-cli --version 0.1.2 --root "$TARGET_VENV" --force

echo "[rtlola] Installed:"
"$TARGET_BIN/rtlola-cli" --version
