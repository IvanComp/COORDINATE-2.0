#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_PATH="$PROJECT_ROOT/Paper Results/RQ4/rq4_da_mac_90d.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$PROJECT_ROOT/Paper Results/RQ4"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting RQ4 DA 90-day completion campaign on mac"
  echo "Project: $PROJECT_ROOT"
  echo "Python: $PYTHON_BIN"
  echo "Log: $LOG_PATH"
  echo
} >> "$LOG_PATH"

cd "$PROJECT_ROOT"
"$PYTHON_BIN" -u "$PROJECT_ROOT/Paper Results/run_rq4_experiments.py" \
  --coord-labels DA \
  --machine-label mac \
  --sim-days 90 \
  --repetitions 10 >> "$LOG_PATH" 2>&1

STATUS=$?
echo >> "$LOG_PATH"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished with exit code $STATUS" >> "$LOG_PATH"
exit $STATUS
