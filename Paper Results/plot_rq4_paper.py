#!/usr/bin/env python3

"""RQ4 figures: scalability of the tool across hardware profiles.

The analysis keeps the nominal configuration and grows the simulated horizon,
comparing CE against DA on a workstation and on commodity hardware. Bars encode
the mechanism with the shared palette and the hardware profile with a hatch, so
the mechanism colour stays consistent with RQ1, RQ2, and RQ3.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_plot_style import (  # noqa: E402
    COLORS,
    add_legend,
    apply_rc,
    pending_text,
    save,
    style_axes,
)


# The nominal configuration of the paper: no parameter is swept, the only
# factors are the execution platform and the coordination mechanism.
NOMINAL_SPAWN = 120
NOMINAL_ROBOTS = 20
NOMINAL_ROOMS = 25
NOMINAL_SIM_DAYS = 90
NOMINAL_EXPIRATION_MEDIUM = 14400
MECHANISMS = ("CE", "DA")

HARDWARE = (
    ("workstation", "Workstation", ""),
    ("mac", "Commodity", "////"),
)

TABLE_METRICS = (
    ("max_rss_mb", "Peak memory (MB)", 2),
    ("event_count", "Events (#)", 0),
    ("total_output_size_mb", "Trace size (MB)", 2),
)

BAR_EDGE_COLOR = "#222222"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("Paper Results"))
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def normalise_machine(value: object) -> str:
    label = str(value).strip().lower()
    if label in {"mac", "commodity", "laptop"}:
        return "mac"
    if label in {"", "nan", "none", "workstation", "linux", "ws"}:
        return "workstation"
    return label


def load_runs(path: Path) -> pd.DataFrame:
    runs = pd.read_csv(path)
    runs = runs[runs["status"].fillna("ok").astype(str).eq("ok")].copy()
    for column in ("sim_days", "item_spawning_time", "n_robots", "n_rooms",
                   "expiration_time_medium_s", "wall_time_s",
                   "max_rss_mb", "event_count", "total_output_size_mb"):
        if column in runs:
            runs[column] = pd.to_numeric(runs[column], errors="coerce")
    runs["machine"] = runs["machine_label"].map(normalise_machine) if "machine_label" in runs else "workstation"
    runs["coord_label"] = runs["coord_label"].astype(str).str.upper().str.strip()
    # Older runs used shorter task deadlines; selecting the nominal expiration
    # keeps this analysis on the same scenario as RQ1, RQ2, and RQ3.
    runs = runs[
        runs["coord_label"].isin(MECHANISMS)
        & runs["sim_days"].eq(NOMINAL_SIM_DAYS)
        & runs["item_spawning_time"].eq(NOMINAL_SPAWN)
        & runs["n_robots"].eq(NOMINAL_ROBOTS)
        & runs["n_rooms"].eq(NOMINAL_ROOMS)
        & runs["expiration_time_medium_s"].eq(NOMINAL_EXPIRATION_MEDIUM)
    ].copy()
    if runs.empty:
        raise RuntimeError("No nominal RQ4 runs are available for the scalability analysis.")
    return runs


def plot_wall_time(runs: pd.DataFrame, output_dir: Path) -> Path:
    """Wall time of CE and DA on both hardware profiles, at the nominal setup."""
    fig, ax = plt.subplots(figsize=(3.4, 2.4), constrained_layout=True)
    positions = np.arange(len(HARDWARE), dtype=float)
    width = 0.34
    for offset, mech in enumerate(MECHANISMS):
        values, errors = [], []
        for hw, _, _ in HARDWARE:
            panel = runs[runs["machine"].eq(hw) & runs["coord_label"].eq(mech)]["wall_time_s"]
            values.append(panel.mean() if len(panel) else np.nan)
            errors.append(1.96 * panel.std(ddof=1) / np.sqrt(len(panel)) if len(panel) > 1 else 0.0)
        ax.bar(
            positions + (offset - 0.5) * width, np.nan_to_num(values), width=width,
            yerr=errors, capsize=2.5, error_kw={"linewidth": 0.6},
            color=COLORS[mech], edgecolor=BAR_EDGE_COLOR, linewidth=0.4, label=mech,
        )
    if runs.empty:
        pending_text(ax)
    ax.set_xticks(positions)
    ax.set_xticklabels([hw_label for _, hw_label, _ in HARDWARE])
    ax.set_ylabel("Simulation wall time [s]")
    style_axes(ax, integer_ticks=False)
    add_legend(ax, ax.containers, loc="upper left")
    return save(fig, output_dir, "rq4_wall_time.pdf")


def scalability_table(runs: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Peak memory, event count, and trace size at the nominal configuration."""
    rows = []
    for hw, hw_label, _ in HARDWARE:
        for mech in MECHANISMS:
            panel = runs[runs["machine"].eq(hw) & runs["coord_label"].eq(mech)]
            row = {"Hardware": hw_label, "Mechanism": mech, "Runs": len(panel)}
            for column, name, digits in TABLE_METRICS:
                value = panel[column].mean() if len(panel) else float("nan")
                row[name] = round(value, digits) if digits else (
                    int(round(value)) if pd.notna(value) else pd.NA
                )
            rows.append(row)

    table = pd.DataFrame(rows).set_index(["Hardware", "Mechanism"])
    table.to_csv(output_dir / "rq4_scalability.csv")
    return table


def generate(results_root: Path, output_dir: Path | None = None) -> tuple[list[Path], pd.DataFrame]:
    """Write the RQ4 scalability figure and the per-day cost table."""
    root = Path(results_root).resolve()
    output_dir = Path(output_dir or root / "paper_figures_latest").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_rc()
    runs = load_runs(root / "RQ4" / "runs.csv")
    return [plot_wall_time(runs, output_dir)], scalability_table(runs, output_dir)


def main() -> None:
    args = parse_args()
    generate(args.results_root, args.output_dir)


if __name__ == "__main__":
    main()
