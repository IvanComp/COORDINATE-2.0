#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON:-python}"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
RQ1_DIR="Paper Results/RQ1_realistic_completion"
RQ2_DIR="Paper Results/RQ2_realistic_completion"
RQ1_LOG="${RQ1_DIR}/rq1_realistic_completion_${RUN_STAMP}.log"
RQ2_LOG="${RQ2_DIR}/rq2_realistic_completion_${RUN_STAMP}.log"

mkdir -p "$RQ1_DIR" "$RQ2_DIR"

run_step() {
  local name="$1"
  local script="$2"
  local log_path="$3"
  local script_name
  script_name="$(basename "$script")"

  echo "[start] ${name}: ${log_path}"
  if (cd "Paper Results" && "$PYTHON_BIN" "$script_name" --repetitions 10) > "$log_path" 2>&1; then
    echo "[ok] ${name}: ${log_path}"
  else
    echo "[error] ${name}: ${log_path}"
    tail -n 80 "$log_path" || true
    exit 1
  fi
}

run_step "RQ1 realistic completion" "Paper Results/run_rq1_realistic_completion_experiments.py" "$RQ1_LOG"
run_step "RQ2 realistic completion" "Paper Results/run_rq2_realistic_completion_experiments.py" "$RQ2_LOG"

echo "[done] realistic-completion campaign completed"
echo "[data] ${RQ1_DIR}/runs.csv"
echo "[data] ${RQ2_DIR}/runs.csv"
echo "[data] ${RQ2_DIR}/adaptation_state_timeseries.csv.gz"
echo "[data] ${RQ2_DIR}/switch_timeline.csv"
