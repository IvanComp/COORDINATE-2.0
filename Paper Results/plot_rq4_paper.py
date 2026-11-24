#!/usr/bin/env python3

"""RQ4 scalability figures for the extended campaign."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_plot_style import (  # noqa: E402
    COLORS, MARKER_EDGE_COLOR, SECONDARY_HATCH, STYLE,
    add_legend, apply_rc, pending_text, save, style_axes,
)
from run_rq4_experiments import NOMINAL_SIM_DAYS, RQ4_EXPERIMENT_PROFILE  # noqa: E402


LEGACY_PROFILE = "extended-wallclock-v2"
MECHANISMS = ("CE", "DA")
SERIES = (
    ("CE", "mac", "CE - Commodity"),
    ("DA", "mac", "DA - Commodity"),
    ("CE", "workstation", "CE - Workstation"),
    ("DA", "workstation", "DA - Workstation"),
)
SWEEPS = (
    ("workload", "item_spawning_time", [90, 120, 150, 180, 210, 240, 270, 300], r"$T_{spawn}$ [sec]"),
    ("fleet", "n_robots", [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], r"$N_{agent}$"),
    ("topology_size", "n_rooms", [4, 9, 16, 25, 36, 49], r"$N_{rooms}$"),
)
METRICS = (
    ("wall_time_s", "Simulation wall time [s]", "line"),
    ("event_count", "Events (#)", "line"),
    ("total_output_size_mb", "Trace size [MB]", "bar"),
)
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("Paper Results"))
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_runs(path: Path) -> pd.DataFrame:
    runs = pd.read_csv(path)
    runs = runs[
        runs["status"].fillna("ok").astype(str).eq("ok")
        & runs["coord_label"].astype(str).str.upper().isin(MECHANISMS)
        & pd.to_numeric(runs["sim_days"], errors="coerce").eq(NOMINAL_SIM_DAYS)
    ].copy()
    current = runs[runs["experiment_profile"].eq(RQ4_EXPERIMENT_PROFILE)]
    if current.empty:
        runs = runs[runs["experiment_profile"].eq(LEGACY_PROFILE)].copy()
    else:
        latest = current["implementation_sha256"].dropna().iloc[-1]
        runs = current[current["implementation_sha256"].eq(latest)].copy()
    for column in (
        "item_spawning_time", "n_robots", "n_rooms", "wall_time_s", "max_rss_mb",
        "event_count", "total_output_size_mb",
    ):
        runs[column] = pd.to_numeric(runs[column], errors="coerce")
    if runs.empty:
        raise RuntimeError("No current RQ4 runs are available for the extended scalability analysis.")
    runs["machine"] = runs["machine_label"].fillna("").astype(str).str.lower()
    return runs


def summary_for(panel: pd.DataFrame, metric: str, x_column: str, x_values: list[int]) -> pd.DataFrame:
    summary = panel.groupby(["coord_label", x_column], observed=False)[metric].agg(
        mean="mean", std="std", count="count"
    ).reset_index()
    rows = []
    for coord in MECHANISMS:
        series = summary[summary["coord_label"].eq(coord)].set_index(x_column).reindex(x_values)
        rows.append(pd.DataFrame({
            "coord_label": coord,
            x_column: x_values,
            "mean": series["mean"].to_numpy(),
            "std": series["std"].fillna(0.0).to_numpy(),
            "count": series["count"].fillna(1.0).clip(lower=1).to_numpy(),
        }))
    return pd.concat(rows, ignore_index=True)


def series_style(coord: str, machine: str) -> dict:
    style = dict(STYLE[coord])
    if machine == "workstation":
        style.update({"linestyle": ":", "markerfacecolor": "white"})
    return style


def legend_handles() -> list[Line2D]:
    return [
        Line2D([0], [0], label=label, linewidth=1.0, markersize=3.5, **series_style(coord, machine))
        for coord, machine, label in SERIES
    ]


def plot_line_panel(ax: plt.Axes, runs: pd.DataFrame, metric: str, slice_name: str,
                    x_column: str, x_values: list[int]) -> bool:
    has_data = False
    for coord, machine, _ in SERIES:
        panel = runs[
            runs["machine"].eq(machine)
            & runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)
        ]
        series = summary_for(panel, metric, x_column, x_values)
        series = series[series["coord_label"].eq(coord)]
        if series["mean"].notna().sum() == 0:
            continue
        has_data = True
        x = np.asarray(x_values, dtype=float)
        y = series["mean"].to_numpy(dtype=float)
        ci = 1.96 * series["std"].to_numpy(dtype=float) / np.sqrt(series["count"].to_numpy(dtype=float))
        ax.plot(x, y, linewidth=1.0, markersize=3.5, **series_style(coord, machine))
        ax.fill_between(x, y - ci, y + ci, color=COLORS[coord], alpha=0.14, linewidth=0)
    return has_data


def plot_bar_panel(ax: plt.Axes, runs: pd.DataFrame, metric: str, slice_name: str,
                   x_column: str, x_values: list[int]) -> bool:
    positions = np.arange(len(x_values), dtype=float)
    width = 0.19
    has_data = False
    for offset, (coord, machine, _) in enumerate(SERIES):
        panel = runs[
            runs["machine"].eq(machine)
            & runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)
        ]
        series = summary_for(panel, metric, x_column, x_values)
        series = series[series["coord_label"].eq(coord)]
        values = series["mean"].to_numpy(dtype=float)
        if not np.isfinite(values).any():
            continue
        has_data = True
        ci = 1.96 * series["std"].to_numpy(dtype=float) / np.sqrt(series["count"].to_numpy(dtype=float))
        ax.bar(
            positions + (offset - 1.5) * width, np.nan_to_num(values), width=width,
            yerr=np.nan_to_num(ci), capsize=2.0, error_kw={"linewidth": 0.6},
            color=COLORS[coord], edgecolor=MARKER_EDGE_COLOR, linewidth=0.4,
            hatch=SECONDARY_HATCH if machine == "workstation" else "",
        )
    ax.set_xticks(positions, [str(value) for value in x_values])
    return has_data


def plot_scalability(runs: pd.DataFrame, output_dir: Path) -> Path:
    fig, axes = plt.subplots(len(METRICS), len(SWEEPS), figsize=(11.8, 8.0), constrained_layout=True)
    letter = ord("a")
    for row, (metric, ylabel, kind) in enumerate(METRICS):
        for col, (slice_name, x_column, x_values, x_label) in enumerate(SWEEPS):
            ax = axes[row, col]
            has_data = (
                plot_line_panel(ax, runs, metric, slice_name, x_column, x_values)
                if kind == "line"
                else plot_bar_panel(ax, runs, metric, slice_name, x_column, x_values)
            )
            if not has_data:
                pending_text(ax)
            if kind == "line":
                ax.set_xticks(x_values)
            ax.set_xlabel(x_label)
            ax.set_ylabel(ylabel if col == 0 else "")
            ax.tick_params(axis="x", labelsize=7)
            style_axes(ax)
            ax.text(0.5, -0.28, f"({chr(letter)})", transform=ax.transAxes, ha="center", va="top")
            letter += 1
    add_legend(axes[0, 0], legend_handles(), loc="upper left")
    return save(fig, output_dir, "rq4_scalability.pdf")


def generate(results_root: Path, output_dir: Path | None = None) -> tuple[list[Path], None]:
    root = Path(results_root).resolve()
    output_dir = Path(output_dir or root / "paper_figures_latest").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_rc()
    return [plot_scalability(load_runs(root / "RQ4" / "runs.csv"), output_dir)], None


def main() -> None:
    args = parse_args()
    generate(args.results_root, args.output_dir)


if __name__ == "__main__":
    main()
