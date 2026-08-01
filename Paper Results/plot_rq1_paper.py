#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_plot_style import (  # noqa: E402
    ORDER,
    STYLE,
    add_legend,
    apply_rc,
    pending_text,
    save,
    style_axes,
)


PROFILE = "table-aligned-rq1-v1"
METRIC_VERSION = "relative-latency-v1"
FD_POLICY_VERSION = "legacy-local-retry-v7"
TOPOLOGIES = (("mesh25", "Mesh"), ("ring25", "Ring"), ("tree25", "Tree"))
SWEEPS = (
    ("workload", "item_spawning_time", [90, 120, 150, 180, 210, 240, 270, 300], r"$T_{spawn}$ [sec]"),
    ("security", "malicious_pct", [0, 20, 40, 60, 80, 100], r"$N_{mal}/N_{agent}$ [%]"),
    ("reliability", "fail_prob_pct", list(range(1, 11)), r"$F_{agent}$ [%]"),
    ("communication", "msg_loss_pct", list(range(1, 11)), r"$F_{msg}$ [%]"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("Paper Results"))
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_runs(path: Path) -> pd.DataFrame:
    runs = pd.read_csv(path)
    runs = runs[(runs["status"].astype(str) == "ok") & (runs["experiment_profile"].astype(str) == PROFILE)].copy()
    if "analysis_metric_version" not in runs or "fd_policy_version" not in runs:
        raise RuntimeError("RQ1 data predates the current relative-latency and FD-policy analysis.")
    runs = runs[runs["analysis_metric_version"].astype(str) == METRIC_VERSION].copy()
    # Every mechanism must come from the same FD policy generation, otherwise CE
    # and SD would mix runs from two different campaigns.
    runs = runs[runs["fd_policy_version"].astype(str).eq(FD_POLICY_VERSION)].copy()
    for column in ("item_spawning_time", "malicious_ratio", "fail_prob", "msg_loss", "avg_relative_latency_s", "completion_rate"):
        runs[column] = pd.to_numeric(runs[column], errors="coerce")
    runs["malicious_pct"] = (runs["malicious_ratio"] * 100.0).round(0)
    runs["fail_prob_pct"] = (runs["fail_prob"] * 100.0).round(0)
    runs["msg_loss_pct"] = (runs["msg_loss"] * 100.0).round(0)
    if runs.empty or runs["avg_relative_latency_s"].isna().all():
        raise RuntimeError("No current RQ1 data with relative-latency measurements is available.")
    return runs


def plot_metric(runs: pd.DataFrame, metric: str, ylabel: str, scale: float, filename: str, output_dir: Path) -> Path:
    fig, axes = plt.subplots(4, 3, figsize=(11.8, 11.1), constrained_layout=True)
    letters = iter("abcdefghijkl")
    legend_handles = []
    for row, (slice_name, x_column, x_values, x_label) in enumerate(SWEEPS):
        for col, (topology, topology_title) in enumerate(TOPOLOGIES):
            ax = axes[row, col]
            panel = runs[
                runs["topology"].astype(str).eq(topology)
                & runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)
            ]
            summary = panel.groupby(["coord_label", x_column], observed=False)[metric].agg(
                mean="mean", std="std", count="count"
            ).reset_index()
            for coord in ORDER:
                series = summary[summary["coord_label"].astype(str).eq(coord)].set_index(x_column).reindex(x_values)
                if series["mean"].notna().sum() == 0:
                    continue
                x = np.asarray(x_values, dtype=float)
                y = series["mean"].to_numpy(dtype=float) * scale
                ci = 1.96 * series["std"].fillna(0.0).to_numpy(dtype=float) / np.sqrt(series["count"].fillna(1.0).clip(lower=1)) * scale
                if metric == "completion_rate":
                    y = np.clip(y, 0, 100)
                    lower, upper = np.clip(y - ci, 0, 100), np.clip(y + ci, 0, 100)
                else:
                    lower, upper = y - ci, y + ci
                line, = ax.plot(x, y, label=coord, linewidth=1.0, markersize=3.5, **STYLE[coord])
                ax.fill_between(x, lower, upper, color=STYLE[coord]["color"], alpha=0.14, linewidth=0)
                if row == 0 and col == 0:
                    legend_handles.append(line)
            if panel.empty:
                pending_text(ax)
            if row == 0:
                ax.set_title(topology_title)
            ax.set_xlabel(x_label)
            ax.set_ylabel(ylabel if col == 0 else "")
            ax.set_xticks(x_values)
            ax.tick_params(axis="x", labelsize=7)
            style_axes(ax, metric)
            ax.text(0.5, -0.28, f"({next(letters)})", transform=ax.transAxes, ha="center", va="top")
    if legend_handles:
        legend_loc = "lower right" if metric == "completion_rate" else "upper right"
        add_legend(axes[0, 0], legend_handles, loc=legend_loc)
    return save(fig, output_dir, filename)


METRICS = (
    ("avg_relative_latency_s", "Relative latency [min]", 1 / 60.0, "rq1_relative_latency.pdf"),
    ("completion_rate", "Completion rate [%]", 100.0, "rq1_completion_rate.pdf"),
)


def generate(results_root: Path, output_dir: Path | None = None) -> list[Path]:
    """Write the two RQ1 figures and return their PDF paths.

    The notebook calls this directly so it renders exactly the paper figures.
    """
    root = Path(results_root).resolve()
    output_dir = Path(output_dir or root / "paper_figures_latest").resolve()
    apply_rc()
    runs = load_runs(root / "RQ1" / "runs.csv")
    return [
        plot_metric(runs, metric, ylabel, scale, filename, output_dir)
        for metric, ylabel, scale, filename in METRICS
    ]


def main() -> None:
    args = parse_args()
    generate(args.results_root, args.output_dir)


if __name__ == "__main__":
    main()

