#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-test}"
REPETITIONS_ARG="${2:-2}"

if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
fi

if [[ ! -x scripts/setup_leonardo.sh ]]; then
    chmod +x scripts/setup_leonardo.sh
fi

if [[ ! -d .venv ]] || ! command -v rtlola-cli >/dev/null 2>&1; then
    bash scripts/setup_leonardo.sh
    if [[ -f "$HOME/.cargo/env" ]]; then
        # shellcheck disable=SC1091
        source "$HOME/.cargo/env"
    fi
fi

case "$MODE" in
    test)
        export REPETITIONS=1
        export RQS="RQ1"
        export EXTRA_ARGS="--limit 4"
        DEFAULT_TIME="00:30:00"
        ;;
    full)
        export REPETITIONS="$REPETITIONS_ARG"
        export RQS="RQ1,RQ2,RQ3,RQ4"
        unset EXTRA_ARGS || true
        DEFAULT_TIME="12:00:00"
        ;;
    *)
        echo "Usage:"
        echo "  bash scripts/submit_leonardo.sh test"
        echo "  bash scripts/submit_leonardo.sh full 2"
        exit 2
        ;;
esac

echo "[submit] Mode: $MODE"
echo "[submit] Repetitions: ${REPETITIONS:-}"
echo "[submit] RQs: ${RQS:-}"
echo "[submit] Extra args: ${EXTRA_ARGS:-<none>}"
echo "[submit] rtlola-cli: $(command -v rtlola-cli)"
rtlola-cli --version

SBATCH_ARGS=("--time=${SBATCH_TIME:-$DEFAULT_TIME}")

if [[ -n "${SBATCH_PARTITION:-}" ]]; then
    SBATCH_ARGS+=("--partition=$SBATCH_PARTITION")
fi

if [[ -n "${SBATCH_ACCOUNT:-}" ]]; then
    SBATCH_ARGS+=("--account=$SBATCH_ACCOUNT")
fi

echo "[submit] sbatch args: ${SBATCH_ARGS[*]}"
sbatch "${SBATCH_ARGS[@]}" run_campaign.slurm
