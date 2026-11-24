#!/usr/bin/env bash
# Run ONCE on a LEONARDO login node (compute nodes have no internet).
# - creates/refreshes .venv with numpy, pandas, scipy
# - checks the Linux rtlola-cli (the one in the repo root is a macOS binary)
# - builds one sandbox per repetition under $CAMPAIGN_ROOT
# - prints the dry-run design of each RQ
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
source scripts/leonardo/config.sh

module purge 2>/dev/null || true
for candidate in python/3.12.3 python/3.11.7 python/3.11 python; do
    module load "$candidate" 2>/dev/null && break
done

if [[ ! -x .venv/bin/python ]]; then
    echo "[prepare] Creating .venv"
    bash scripts/setup_experiments.sh
fi
source .venv/bin/activate
python -m pip install --quiet -r requirements.txt
python -m pip install --quiet "scipy>=1.11"

if ! .venv/bin/rtlola-cli --version >/dev/null 2>&1; then
    echo "[prepare] rtlola-cli missing in .venv, trying install_rtlola_venv.sh"
    bash scripts/install_rtlola_venv.sh
fi
.venv/bin/rtlola-cli --version
export RTLOLA_BINARY_PATH="$ROOT_DIR/.venv/bin/rtlola-cli"
python scripts/check_rtlola.py

# Expand REPS ("1-10" or "1,3,5") into a list.
expand_reps() {
    local spec="$1" part
    IFS=',' read -ra parts <<< "$spec"
    for part in "${parts[@]}"; do
        if [[ "$part" == *-* ]]; then seq "${part%-*}" "${part#*-}"; else echo "$part"; fi
    done
}

mkdir -p "$CAMPAIGN_ROOT"
echo "[prepare] Campaign root: $CAMPAIGN_ROOT"
for rep in $(expand_reps "$REPS"); do
    sb="$CAMPAIGN_ROOT/rep_$(printf '%02d' "$rep")"
    mkdir -p "$sb/Paper Results"
    # Code is copied (not linked) so that Path(__file__).resolve() points at
    # the sandbox and every result file lands in the sandbox.
    cp "$ROOT_DIR/Paper Results/"*.py "$sb/Paper Results/"
    for item in sim spec2.rtlola scripts .venv requirements.txt; do
        ln -sfn "$ROOT_DIR/$item" "$sb/$item"
    done
    echo "[prepare] sandbox ready: $sb"
done

# Record the exact code version used for the campaign.
{
    echo "created: $(date -Iseconds)"
    echo "git_commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "git_dirty: $(git status --porcelain 2>/dev/null | wc -l) files"
    echo "reps: $REPS"
    echo "rqs: $RQS"
    echo "extra_args: $EXTRA_ARGS"
    python -c "import sys,numpy,pandas,scipy; print('python:',sys.version.split()[0],'numpy:',numpy.__version__,'pandas:',pandas.__version__,'scipy:',scipy.__version__)"
} > "$CAMPAIGN_ROOT/campaign_manifest.txt"
cat "$CAMPAIGN_ROOT/campaign_manifest.txt"

first="$CAMPAIGN_ROOT/rep_$(printf '%02d' "$(expand_reps "$REPS" | head -1)")"
IFS=',' read -ra rq_list <<< "$RQS"
for rq in "${rq_list[@]}"; do
    echo "[prepare] Dry run $rq (one repetition):"
    # shellcheck disable=SC2086
    python scripts/leonardo/run_one_rep.py --sandbox "$first" --rq "$rq" --rep 1 -- --dry-run $EXTRA_ARGS \
        | grep -E '"total_runs"|"repetitions"|"sim_days"' || true
done
echo "[prepare] Done. Next: bash scripts/leonardo/submit_10x.sh test   (then: full)"
