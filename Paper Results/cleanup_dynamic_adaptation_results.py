#!/usr/bin/env python3
"""
Remove existing Dynamic Adaptation artifacts from the paper result folders.

The fixed-mechanism raw logs and CSV rows are left intact. This is useful after
CE/SD/FD have completed and DA needs to be re-run cleanly across the RQs.

Run from the project root:
    python "Paper Results/cleanup_dynamic_adaptation_results.py"
    python "Paper Results/cleanup_dynamic_adaptation_results.py" --apply
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Iterable


PAPER_ROOT = Path(__file__).resolve().parent

CSV_FILES = {
    "RQ1": [
        "runs.csv",
        "sim_time.csv",
        "summary.csv",
        "summary_by_mechanism.csv",
        "errors.csv",
    ],
    "RQ2": [
        "runs.csv",
        "sim_time.csv",
        "adaptation_state_timeseries.csv",
        "switch_timeline.csv",
        "phase_schedule.csv",
        "summary_by_profile.csv",
        "state_distribution.csv",
        "errors.csv",
    ],
    "RQ3": [
        "runs.csv",
        "overhead_samples.csv",
        "overhead_summary.csv",
        "wall_time_summary.csv",
        "errors.csv",
    ],
    "RQ4": [
        "runs.csv",
        "sim_time.csv",
        "scalability_summary.csv",
        "errors.csv",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean DA artifacts from Paper Results.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete files and rewrite CSVs. Without this, only print the planned cleanup.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print every removed path.")
    return parser.parse_args()


def is_da_name(path: Path) -> bool:
    name = path.name
    return "_DA" in name or name.endswith("DA")


def is_da_row(row: dict[str, str], *, rq: str) -> bool:
    if rq == "RQ2":
        return True
    run_id = row.get("run_id", "")
    return (
        row.get("coord_label") == "DA"
        or row.get("arch") == "dynamic-adaptation"
        or row.get("architecture") == "dynamic-adaptation"
        or "_DA" in run_id
        or "_DA" in row.get("config_path", "")
        or "_DA" in row.get("logfile", "")
        or "_DA" in row.get("source_run_id", "")
    )


def iter_da_paths(rq_root: Path) -> Iterable[Path]:
    raw_logs = rq_root / "raw_logs"
    configs = rq_root / "configs"
    if raw_logs.exists():
        yield from (path for path in raw_logs.rglob("*") if path.is_dir() and is_da_name(path))
    if configs.exists():
        yield from (path for path in configs.rglob("*") if path.is_file() and is_da_name(path))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_csv(path: Path, *, rq: str, apply: bool) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    fieldnames, rows = read_csv(path)
    if not rows:
        return 0, 0

    kept = [row for row in rows if not is_da_row(row, rq=rq)]
    removed = len(rows) - len(kept)
    if apply and removed:
        if kept:
            write_csv(path, fieldnames, kept)
        else:
            path.unlink()
    return removed, len(kept)


def main() -> int:
    args = parse_args()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Dynamic Adaptation cleanup ({mode})")
    print(f"Root: {PAPER_ROOT}")

    total_paths = 0
    total_rows = 0

    for rq, csv_names in CSV_FILES.items():
        rq_root = PAPER_ROOT / rq
        print(f"\n{rq}")

        da_paths = sorted(iter_da_paths(rq_root))
        if args.verbose:
            for path in da_paths:
                print(f"  remove path: {path.relative_to(PAPER_ROOT)}")
        elif da_paths:
            preview = ", ".join(str(path.relative_to(PAPER_ROOT)) for path in da_paths[:3])
            suffix = "..." if len(da_paths) > 3 else ""
            print(f"  example paths: {preview}{suffix}")

        for path in da_paths:
            if args.apply:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        total_paths += len(da_paths)
        print(f"  DA paths: {len(da_paths)}")

        rq_rows = 0
        for csv_name in csv_names:
            removed, kept = clean_csv(rq_root / csv_name, rq=rq, apply=args.apply)
            if removed:
                print(f"  {csv_name}: removed {removed} row(s), kept {kept}")
            rq_rows += removed
        total_rows += rq_rows
        print(f"  DA CSV rows: {rq_rows}")

    print("\nSummary")
    print(f"  DA paths removed/planned: {total_paths}")
    print(f"  DA CSV rows removed/planned: {total_rows}")
    if not args.apply:
        print("  Re-run with --apply to perform the cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
