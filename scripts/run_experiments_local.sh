#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]] || [[ ! -x ".venv/bin/rtlola-cli" ]]; then
    bash scripts/setup_experiments.sh
elif ! .venv/bin/rtlola-cli --version >/dev/null 2>&1; then
    bash scripts/install_rtlola_venv.sh
fi

.venv/bin/python scripts/check_rtlola.py

MODE="${1:-test}"
REPETITIONS="${2:-2}"

case "$MODE" in
    test)
        exec .venv/bin/python "Paper Results/run_full_paper_campaign.py" \
            --repetitions 1 \
            --rqs RQ1 \
            --limit 4
        ;;
    full)
        exec .venv/bin/python "Paper Results/run_full_paper_campaign.py" \
            --repetitions "$REPETITIONS"
        ;;
    *)
        echo "Usage:"
        echo "  bash scripts/run_experiments_local.sh test"
        echo "  bash scripts/run_experiments_local.sh full 10"
        exit 2
        ;;
esac
