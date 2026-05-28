#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "[rtlola] ERROR: .venv not found. Create the project venv first."
    exit 2
fi

source .venv/bin/activate

if [[ -x ".venv/bin/rtlola-cli" ]] && .venv/bin/rtlola-cli --version >/dev/null 2>&1; then
    echo "[rtlola] Using existing venv binary: $ROOT_DIR/.venv/bin/rtlola-cli"
    .venv/bin/rtlola-cli --version
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

echo "[rtlola] Installing rtlola-cli 0.1.2 into .venv/bin"
cargo install rtlola-cli --version 0.1.2 --root "$ROOT_DIR/.venv" --force

echo "[rtlola] Installed:"
"$ROOT_DIR/.venv/bin/rtlola-cli" --version
