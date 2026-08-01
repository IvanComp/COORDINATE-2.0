#!/usr/bin/env python3

"""RQ3 figures: runtime cost of enabling Dynamic Adaptation.

The runtime cost is measured on the nominal campaign itself rather than on a
separate set of simulations, so the overhead reported here belongs to exactly
the runs whose performance RQ1 analyses. Those runs live in RQ1/runs.csv and
already carry both indicators: wall time for every mechanism, and per-check
adaptation overhead for DA.
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
NOMINAL_TOPOLOGY = "ring25"

SWEEPS = (
    ("workload", "item_spawning_time", [90, 120, 150, 180, 210, 240, 270, 300], r"$T_{spawn}$ [sec]"),
    ("security", "malicious_pct", [0, 20, 40, 60, 80, 100], r"$N_{mal}/N_{agent}$ [%]"),
    ("reliability", "fail_prob_pct", list(range(1, 11)), r"$F_{agent}$ [%]"),
    ("communication", "msg_loss_pct", list(range(1, 11)), r"$F_{msg}$ [%]"),
)

TABLE_SWEEPS = (
    ("workload", "item_spawning_time", None, r"$T_{spawn}$", " s"),
    ("security", "malicious_pct", None, r"$N_{mal}/N_{agent}$", "%"),
    ("reliability", "fail_prob_pct", None, r"$F_{agent}$", "%"),
    ("communication", "msg_loss_pct", None, r"$F_{msg}$", "%"),
)

# Panels are laid out two by two: the figure is meant to occupy a single paper
# column, and is sized so that its text scales down like the full-width RQ1
# figures do.
PANEL_ROWS, PANEL_COLS = 2, 2
FIGURE_SIZE = (5.9, 4.4)


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
    runs = runs[runs["fd_policy_version"].astype(str).eq(FD_POLICY_VERSION)].copy()
    # RQ3 reports the cost of the nominal configuration, so only the baseline
    # topology is kept; every other parameter is swept one at a time.
    runs = runs[runs["topology"].astype(str).eq(NOMINAL_TOPOLOGY)].copy()
    for column in ("item_spawning_time", "malicious_ratio", "fail_prob", "msg_loss",
                   "wall_time_s", "adapt_overhead_ms_mean", "adapt_checks", "rtlola_query_ms_mean"):
        if column in runs:
            runs[column] = pd.to_numeric(runs[column], errors="coerce")
    runs["malicious_pct"] = (runs["malicious_ratio"] * 100.0).round(0)
    runs["fail_prob_pct"] = (runs["fail_prob"] * 100.0).round(0)
    runs["msg_loss_pct"] = (runs["msg_loss"] * 100.0).round(0)
    if runs.empty:
        raise RuntimeError("No nominal RQ1 runs are available for the RQ3 overhead analysis.")
    return runs


def plot_metric(runs: pd.DataFrame, metric: str, ylabel: str, labels: tuple[str, ...],
                integer_ticks: bool, filename: str, output_dir: Path) -> Path:
    fig, axes = plt.subplots(PANEL_ROWS, PANEL_COLS, figsize=FIGURE_SIZE, constrained_layout=True)
    axes = axes.ravel()
    letters = iter("abcdefgh")
    legend_handles = []
    for index, (slice_name, x_column, x_values, x_label) in enumerate(SWEEPS):
        ax = axes[index]
        panel = runs[runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)]
        summary = panel.groupby(["coord_label", x_column], observed=False)[metric].agg(
            mean="mean", std="std", count="count"
        ).reset_index()
        has_data = False
        for coord in labels:
            series = summary[summary["coord_label"].astype(str).eq(coord)].set_index(x_column).reindex(x_values)
            if series["mean"].notna().sum() == 0:
                continue
            has_data = True
            x = np.asarray(x_values, dtype=float)
            y = series["mean"].to_numpy(dtype=float)
            ci = 1.96 * series["std"].fillna(0.0).to_numpy(dtype=float) / np.sqrt(series["count"].fillna(1.0).clip(lower=1))
            line, = ax.plot(x, y, label=coord, linewidth=1.0, markersize=3.5, **STYLE[coord])
            ax.fill_between(x, y - ci, y + ci, color=STYLE[coord]["color"], alpha=0.14, linewidth=0)
            if index == 0:
                legend_handles.append(line)
        if not has_data:
            pending_text(ax)
        ax.set_xlabel(x_label)
        ax.set_ylabel(ylabel if index % PANEL_COLS == 0 else "")
        ax.set_xticks(x_values)
        ax.tick_params(axis="x", labelsize=7)
        style_axes(ax, metric, integer_ticks=integer_ticks)
        ax.text(0.5, -0.34, f"({next(letters)})", transform=ax.transAxes, ha="center", va="top")
    if legend_handles and len(labels) > 1:
        add_legend(axes[0], legend_handles, loc="upper right")
    return save(fig, output_dir, filename)


def overhead_table(runs: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Per-check adaptation cost of DA, summarised over each swept parameter.

    Reporting the range observed along a sweep, rather than a single mean, shows
    both the level of the overhead and how little the operating conditions move
    it.
    """
    da = runs[runs["coord_label"].astype(str).eq("DA")]
    rows = []
    for slice_name, x_column, _, label, unit in TABLE_SWEEPS:
        panel = da[da["analysis_slices"].astype(str).str.contains(slice_name, regex=False)]
        if panel.empty:
            continue
        per_point = panel.groupby(x_column, observed=False)["adapt_overhead_ms_mean"].mean()
        total_s = panel["adapt_overhead_ms_mean"] * panel["adapt_checks"] / 1000.0
        rows.append({
            "Varied parameter": label,
            "Sweep range": f"{per_point.index.min():g}-{per_point.index.max():g}{unit}",
            "Overhead/check [ms]": f"{per_point.min():.3f}-{per_point.max():.3f}",
            "Monitor query [ms]": round(panel["rtlola_query_ms_mean"].mean(), 3),
            "Decision [ms]": round(panel["scoring_ms_mean"].mean(), 3),
            "Checks per run": int(round(panel["adapt_checks"].mean())),
            "Total overhead [s]": round(total_s.mean(), 2),
            "Share of wall time [%]": round(100.0 * (total_s / panel["wall_time_s"]).mean(), 2),
        })

    table = pd.DataFrame(rows).set_index("Varied parameter")
    table.to_csv(output_dir / "rq3_adaptation_overhead.csv")
    return table


def generate(results_root: Path, output_dir: Path | None = None) -> tuple[list[Path], pd.DataFrame]:
    """Write the RQ3 wall-time figure and the adaptation-overhead table."""
    root = Path(results_root).resolve()
    output_dir = Path(output_dir or root / "paper_figures_latest").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_rc()
    runs = load_runs(root / "RQ1" / "runs.csv")
    figures = [
        plot_metric(runs, "wall_time_s", "Simulation wall time [s]", ORDER, True,
                    "rq3_wall_time.pdf", output_dir),
    ]
    return figures, overhead_table(runs, output_dir)


def main() -> None:
    args = parse_args()
    generate(args.results_root, args.output_dir)


if __name__ == "__main__":
    main()
