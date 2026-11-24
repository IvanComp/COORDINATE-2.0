#!/usr/bin/env python3
"""Merge the per-repetition sandboxes of a LEONARDO campaign.

For every RQ, all CSV files written by the runners in
<campaign-root>/rep_XX/Paper Results/<RQ>/ are concatenated into
<out>/<RQ>/<same file name>. runs.csv and errors.csv are de-duplicated on
run_id. A completeness report lists, for each configuration and mechanism,
which repetitions are missing or failed, so a re-submission can fill them.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ID_COLS = {"run_id"}
# Columns that identify a configuration (any present subset is used).
CONFIG_COLS = [
    "profile", "topology", "n_rooms", "item_spawning_time", "n_robots", "n_malicious",
    "malicious_ratio", "fail_prob", "msg_loss", "msg_loss_prob", "comp_time", "comm_time", "sim_days",
]


def read_any(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, compression="infer")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--rqs", default="RQ1,RQ2,RQ3,RQ4")
    p.add_argument("--expected-reps", type=int, default=None,
                   help="Expected repetitions per configuration (default: number of sandboxes).")
    args = p.parse_args()

    sandboxes = sorted(d for d in args.campaign_root.glob("rep_*") if d.is_dir())
    if not sandboxes:
        raise SystemExit(f"No rep_* sandboxes in {args.campaign_root}")
    expected = args.expected_reps or len(sandboxes)
    report: dict = {"campaign_root": str(args.campaign_root), "sandboxes": [s.name for s in sandboxes], "rqs": {}}

    for rq in [r.strip() for r in args.rqs.split(",") if r.strip()]:
        files: dict[str, list[pd.DataFrame]] = {}
        for sb in sandboxes:
            rq_dir = sb / "Paper Results" / rq
            if not rq_dir.is_dir():
                continue
            rep = int(re.sub(r"\D", "", sb.name))
            for f in sorted(list(rq_dir.glob("*.csv")) + list(rq_dir.glob("*.csv.gz"))):
                df = read_any(f)
                df.insert(0, "sandbox_rep", rep)
                files.setdefault(f.name, []).append(df)
        if not files:
            print(f"[merge] {rq}: no results found")
            continue
        out_dir = args.out / rq
        out_dir.mkdir(parents=True, exist_ok=True)
        rq_report: dict = {"files": {}}
        for name, frames in files.items():
            merged = pd.concat(frames, ignore_index=True, sort=False)
            if name in {"runs.csv", "errors.csv"} and "run_id" in merged.columns:
                merged = merged.drop_duplicates(subset="run_id", keep="last")
            merged.to_csv(out_dir / name, index=False, compression="infer")
            rq_report["files"][name] = int(len(merged))
            print(f"[merge] {rq}/{name}: {len(merged)} rows")

        runs_path = out_dir / "runs.csv"
        if runs_path.exists():
            runs = pd.read_csv(runs_path, low_memory=False)
            ok = runs[runs.get("status", "ok") == "ok"] if "status" in runs.columns else runs
            keys = [c for c in CONFIG_COLS if c in ok.columns] + (["coord_label"] if "coord_label" in ok.columns else [])
            if keys and "rep" in ok.columns:
                counts = ok.groupby(keys, dropna=False)["rep"].nunique().reset_index(name="reps_ok")
                incomplete = counts[counts["reps_ok"] < expected]
                incomplete.to_csv(out_dir / "incomplete_configs.csv", index=False)
                rq_report.update({
                    "runs_ok": int(len(ok)),
                    "runs_not_ok": int(len(runs) - len(ok)),
                    "configs_x_mechanisms": int(len(counts)),
                    "incomplete": int(len(incomplete)),
                    "expected_reps": expected,
                })
                print(f"[merge] {rq}: {len(ok)} ok runs, {len(incomplete)} config x mechanism cells "
                      f"with fewer than {expected} repetitions (see incomplete_configs.csv)")
        report["rqs"][rq] = rq_report

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.campaign_root / "campaign_manifest.txt"
    if manifest.exists():
        (args.out / "campaign_manifest.txt").write_text(manifest.read_text())
    (args.out / "merge_report.json").write_text(json.dumps(report, indent=2))
    print(f"[merge] report: {args.out / 'merge_report.json'}")


if __name__ == "__main__":
    main()
