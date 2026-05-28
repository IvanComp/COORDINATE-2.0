#!/usr/bin/env python3
"""
Run the full paper experimental campaign.

The script runs the RQ scripts sequentially and relies on each runner's resume
logic. It is intended for overnight runs on workstations or batch allocations
such as LEONARDO.

Examples:
    python "Paper Results/run_full_paper_campaign.py" --dry-run
    python "Paper Results/run_full_paper_campaign.py" --repetitions 10
    nohup python "Paper Results/run_full_paper_campaign.py" --repetitions 10 > "Paper Results/full_campaign.out" 2>&1 &

By default, RQ2 and RQ3 reuse matching completed RQ1 artifacts when available.
Use --no-reuse-rq1 to force independent runs for those RQs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from paper_experiment_utils import PAPER_ROOT, completed_run_ids, read_rows, write_rows


RQ_SCRIPTS = {
    "RQ1": PAPER_ROOT / "run_rq1_experiments.py",
    "RQ2": PAPER_ROOT / "run_rq2_experiments.py",
    "RQ3": PAPER_ROOT / "run_rq3_experiments.py",
    "RQ4": PAPER_ROOT / "run_rq4_experiments.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all paper experiment campaigns.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per configuration.")
    parser.add_argument(
        "--rqs",
        default="RQ1,RQ2,RQ3,RQ4",
        help="Comma-separated list of RQs to run, e.g. RQ1,RQ3.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable to use.")
    parser.add_argument("--quick", action="store_true", help="Forward --quick to each RQ script.")
    parser.add_argument("--dry-run", action="store_true", help="Print campaign design without running simulations.")
    parser.add_argument("--force", action="store_true", help="Force every RQ script to re-run all configured runs.")
    parser.add_argument("--fail-fast", action="store_true", help="Forward --fail-fast to each RQ script.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue with later RQs if one RQ script fails. This is the default.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop the campaign when an RQ script fails.")
    parser.add_argument("--no-reuse-rq1", action="store_true", help="Disable RQ1 artifact reuse in RQ2/RQ3.")
    parser.add_argument("--limit", type=int, default=None, help="Forward --limit to each RQ script.")
    parser.add_argument(
        "--log-file",
        default=str(PAPER_ROOT / "full_campaign.log"),
        help="Master log file path.",
    )
    return parser.parse_args()


def selected_rqs(raw: str) -> list[str]:
    rqs = [rq.strip().upper() for rq in raw.split(",") if rq.strip()]
    unknown = [rq for rq in rqs if rq not in RQ_SCRIPTS]
    if unknown:
        raise ValueError(f"Unknown RQ(s): {', '.join(unknown)}")
    return rqs


def read_design_total(rq: str) -> Optional[int]:
    design_path = PAPER_ROOT / rq / "experiment_design.json"
    if not design_path.exists():
        return None
    try:
        design = json.loads(design_path.read_text())
    except json.JSONDecodeError:
        return None
    total = design.get("total_runs")
    return int(total) if total is not None else None


def rq_status(rq: str) -> dict[str, Any]:
    rows = read_rows(PAPER_ROOT / rq / "runs.csv")
    completed = completed_run_ids(rows)
    errors = [row for row in rows if row.get("status") == "error"]
    total = read_design_total(rq)
    remaining = total - len(completed) if total is not None else None
    return {
        "rq": rq,
        "expected_runs": total,
        "rows": len(rows),
        "completed": len(completed),
        "errors": len(errors),
        "remaining": remaining,
    }


def command_for_rq(rq: str, args: argparse.Namespace) -> list[str]:
    cmd = [args.python, str(RQ_SCRIPTS[rq]), "--repetitions", str(args.repetitions)]
    if args.quick:
        cmd.append("--quick")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.force:
        cmd.append("--force")
    if args.fail_fast:
        cmd.append("--fail-fast")
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.no_reuse_rq1 and rq in {"RQ2", "RQ3"}:
        cmd.append("--no-reuse-rq1")
    return cmd


def print_status(prefix: str, status: dict[str, Any]) -> None:
    expected = status["expected_runs"] if status["expected_runs"] is not None else "?"
    remaining = status["remaining"] if status["remaining"] is not None else "?"
    print(
        f"{prefix} {status['rq']} status: "
        f"completed={status['completed']}/{expected}, "
        f"errors={status['errors']}, remaining={remaining}",
        flush=True,
    )


def run_step(rq: str, cmd: list[str], log_file: Path) -> int:
    print(f"\n{'=' * 80}", flush=True)
    print(f"Starting {rq}: {' '.join(cmd)}", flush=True)
    print(f"{'=' * 80}", flush=True)

    with log_file.open("a") as log:
        log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] START {rq}: {' '.join(cmd)}\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            prefixed = f"[{rq}] {line}"
            print(prefixed, end="", flush=True)
            log.write(prefixed)
            log.flush()
        return_code = proc.wait()
        log.write(f"[{datetime.now().isoformat(timespec='seconds')}] END {rq}: return_code={return_code}\n")
        log.flush()
    return return_code


def run_campaign(args: argparse.Namespace) -> int:
    rqs = selected_rqs(args.rqs)
    log_file = Path(args.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    status_rows: list[dict[str, Any]] = []

    print("Full paper campaign")
    print(f"RQs: {', '.join(rqs)}")
    print(f"Repetitions: {args.repetitions}")
    print(f"Master log: {log_file}")
    print(f"RQ1 reuse enabled for RQ2/RQ3: {not args.no_reuse_rq1}")
    print("Resume is enabled by default in every RQ script.")

    for rq in rqs:
        before = rq_status(rq)
        print_status("Before", before)
        start = time.time()
        cmd = command_for_rq(rq, args)
        return_code = run_step(rq, cmd, log_file)
        duration = time.time() - start
        after = rq_status(rq)
        print_status("After ", after)

        status_rows.append({
            "rq": rq,
            "command": " ".join(cmd),
            "return_code": return_code,
            "duration_s": duration,
            "expected_runs": after["expected_runs"],
            "completed": after["completed"],
            "errors": after["errors"],
            "remaining": after["remaining"],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        write_rows(PAPER_ROOT / "campaign_status.csv", status_rows)

        if return_code != 0 and args.stop_on_error:
            print(f"Stopping because {rq} failed with return code {return_code}.", flush=True)
            return return_code

    print("\nFull paper campaign finished.")
    print(f"Status CSV: {PAPER_ROOT / 'campaign_status.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_campaign(parse_args()))
