#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_VENV="${RTLOLA_TARGET_VENV:-${VIRTUAL_ENV:-$ROOT_DIR/.venv}}"
if [[ "$TARGET_VENV" != /* ]]; then
    TARGET_VENV="$ROOT_DIR/$TARGET_VENV"
fi
TARGET_BIN="$TARGET_VENV/bin"

platform_names() {
    local system machine os_names arch_names
    system="$(uname -s | tr '[:upper:]' '[:lower:]')"
    machine="$(uname -m | tr '[:upper:]' '[:lower:]')"

    case "$system" in
        darwin) os_names=("macos" "darwin") ;;
        linux) os_names=("linux") ;;
        mingw*|msys*|cygwin*) os_names=("windows" "win") ;;
        *) os_names=("$system") ;;
    esac

    case "$machine" in
        x86_64|amd64) arch_names=("x86_64" "amd64") ;;
        aarch64|arm64) arch_names=("aarch64" "arm64") ;;
        *) arch_names=("$machine") ;;
    esac

    for os_name in "${os_names[@]}"; do
        for arch_name in "${arch_names[@]}"; do
            printf '%s\n' "rtlola-cli-${os_name}-${arch_name}"
            printf '%s\n' "rtlola-cli-${os_name}_${arch_name}"
        done
        printf '%s\n' "rtlola-cli-${os_name}"
    done
    printf '%s\n' "rtlola-cli"
}

candidate_paths() {
    local name
    while IFS= read -r name; do
        printf '%s\n' "$ROOT_DIR/$name"
        printf '%s\n' "$ROOT_DIR/bin/$name"
        printf '%s\n' "$ROOT_DIR/tools/$name"
        printf '%s\n' "$ROOT_DIR/sim/$name"
    done < <(platform_names)
}

install_bundled_binary() {
    local candidate
    while IFS= read -r candidate; do
        [[ -f "$candidate" ]] || continue
        chmod +x "$candidate" 2>/dev/null || true
        if "$candidate" --version >/dev/null 2>&1; then
            cp "$candidate" "$TARGET_BIN/rtlola-cli"
            chmod +x "$TARGET_BIN/rtlola-cli"
            echo "[rtlola] Using bundled native binary: $candidate"
            "$TARGET_BIN/rtlola-cli" --version
            return 0
        fi
    done < <(candidate_paths)
    return 1
}

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

if install_bundled_binary; then
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
