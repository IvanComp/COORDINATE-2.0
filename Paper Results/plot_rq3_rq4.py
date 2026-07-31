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
    COLORS,
    MARKERS,
    ORDER,
    STYLE,
    add_legend,
    apply_rc,
    pending_text,
    save,
    style_axes,
)


RQ3_PROFILE = "extended-overhead-v2"
RQ4_PROFILE = "extended-wallclock-v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=Path("Paper Results"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--rq",
        default="rq3,rq4",
        help="Comma-separated subset of figures to regenerate, e.g. rq3 or rq4.",
    )
    return parser.parse_args()


def load_runs(path: Path, profile: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    runs = pd.read_csv(path)
    if "status" in runs:
        runs = runs[runs["status"].astype(str).eq("ok")].copy()
    if "experiment_profile" in runs:
        runs = runs[runs["experiment_profile"].astype(str).eq(profile)].copy()
    else:
        return pd.DataFrame()
    for column in (
        "item_spawning_time", "n_robots", "n_rooms", "comp_time", "comm_time",
        "msg_loss_prob", "wall_time_s", "adapt_overhead_ms_mean",
        "avg_relative_latency_s", "completion_rate",
    ):
        if column in runs:
            runs[column] = pd.to_numeric(runs[column], errors="coerce")
    runs["coord_label"] = runs["coord_label"].astype(str).str.upper().str.strip()
    return runs[runs["coord_label"].isin(ORDER)].copy()


def int_labels(values: list[float]) -> list[str]:
    return [str(int(round(value))) for value in values]


def panel_figure(
    runs: pd.DataFrame,
    *,
    panels: list[tuple[str, str, list[float], str, float]],
    metric: str,
    ylabel: str,
    filename: str,
    output_dir: Path,
    only_da: bool = False,
) -> None:
    fig, axes = plt.subplots(1, len(panels), figsize=(9.2, 2.45), sharey=True, constrained_layout=True)
    legend_handles = []
    for index, (slice_name, x_column, x_values, x_label, x_scale) in enumerate(panels):
        ax = axes[index]
        if {"coord_label", "analysis_slices", x_column, metric}.issubset(runs.columns):
            panel = runs[runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)].copy()
        else:
            panel = pd.DataFrame(columns=["coord_label", x_column, metric])
        labels = ("DA",) if only_da else ORDER
        has_data = False
        for label in labels:
            series = panel[panel["coord_label"].eq(label)]
            if series.empty or metric not in series:
                continue
            summary = series.groupby(x_column, observed=False)[metric].mean().reindex(x_values)
            if summary.notna().sum() == 0:
                continue
            has_data = True
            x = np.asarray(x_values, dtype=float) * x_scale
            y = summary.to_numpy(dtype=float)
            if metric == "avg_relative_latency_s":
                y = y / 60.0
            elif metric == "completion_rate":
                y = y * 100.0
            line, = ax.plot(x, y, label=label, linewidth=1.1, markersize=3.8, **STYLE[label])
            if index == 0:
                legend_handles.append(line)
        if not has_data:
            pending_text(ax)
        x_ticks = [value * x_scale for value in x_values]
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(int_labels(x_ticks))
        ax.set_xlabel(x_label)
        ax.set_ylabel(ylabel if index == 0 else "")
        style_axes(ax, metric)
    if legend_handles:
        add_legend(axes[0], legend_handles, loc="upper left")
    save(fig, output_dir, filename)


# Hardware profiles keep the shared mechanism colour and marker; the hardware
# itself is encoded by the line style alone, so CE stays green and DA stays grey
# exactly as in RQ1, RQ2, and RQ3.
HW_ORDER = (
    ("workstation", "CE", "Workstation / CE", {"color": COLORS["CE"], "marker": MARKERS["CE"], "linestyle": "-"}),
    ("workstation", "DA", "Workstation / DA", {"color": COLORS["DA"], "marker": MARKERS["DA"], "linestyle": "-"}),
    ("mac",         "CE", "Commodity / CE",   {"color": COLORS["CE"], "marker": MARKERS["CE"], "linestyle": "--"}),
    ("mac",         "DA", "Commodity / DA",   {"color": COLORS["DA"], "marker": MARKERS["DA"], "linestyle": "--"}),
)



def panel_figure_rq4_hardware(
    runs: pd.DataFrame,
    *,
    panels: list[tuple[str, str, list[float], str, float]],
    metric: str,
    ylabel: str,
    filename: str,
    output_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, len(panels), figsize=(9.5, 2.7), sharey=True, constrained_layout=True)
    letters = iter("abc")
    legend_handles = []

    runs = runs.copy()
    if "machine_label" in runs.columns:
        runs["machine_norm"] = runs["machine_label"].astype(str).str.lower().map(
            lambda m: "mac" if m in ("mac", "commodity", "laptop") else ("workstation" if m in ("workstation", "linux") else m)
        )
    else:
        runs["machine_norm"] = "workstation"

    for index, (slice_name, x_column, x_values, x_label, x_scale) in enumerate(panels):
        ax = axes[index]
        if {"coord_label", "analysis_slices", x_column, metric}.issubset(runs.columns):
            panel = runs[runs["analysis_slices"].astype(str).str.contains(slice_name, regex=False)].copy()
        else:
            panel = pd.DataFrame()

        has_data = False
        for hw_key, coord, display_label, style in HW_ORDER:
            series = panel[
                panel["machine_norm"].eq(hw_key) & panel["coord_label"].eq(coord)
            ]
            if series.empty or metric not in series:
                continue
            summary = series.groupby(x_column, observed=False)[metric].agg(
                mean="mean", std="std", count="count"
            ).reindex(x_values)
            if summary["mean"].notna().sum() == 0:
                continue
            has_data = True
            x = np.asarray(x_values, dtype=float) * x_scale
            y = summary["mean"].to_numpy(dtype=float)
            ci = 1.96 * summary["std"].fillna(0.0).to_numpy(dtype=float) / np.sqrt(summary["count"].fillna(1.0).clip(lower=1))
            lower, upper = y - ci, y + ci
            line, = ax.plot(x, y, label=display_label, linewidth=1.1, markersize=3.8, **style)
            ax.fill_between(x, lower, upper, color=style["color"], alpha=0.12, linewidth=0)
            if index == 0:
                legend_handles.append(line)

        if not has_data:
            pending_text(ax)

        x_ticks = [value * x_scale for value in x_values]
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(int_labels(x_ticks))
        ax.set_xlabel(x_label)
        ax.set_ylabel(ylabel if index == 0 else "")
        style_axes(ax, metric)
        ax.text(0.5, -0.26, f"({next(letters)})", transform=ax.transAxes, ha="center", va="top")

    if legend_handles:
        add_legend(axes[0], legend_handles, loc="upper left", fontsize=8)

    save(fig, output_dir, filename)



def main() -> None:
    args = parse_args()
    root = args.results_root.resolve()
    output_dir = (args.output_dir or root / "paper_figures_latest").resolve()
    apply_rc()
    selected = {item.strip().lower() for item in str(args.rq).split(",") if item.strip()}
    unknown = selected - {"rq3", "rq4"}
    if unknown:
        raise SystemExit(f"--rq accepts only rq3 and rq4; got {', '.join(sorted(unknown))}")

    basic_panels = [
        ("workload", "item_spawning_time", [90, 120, 150, 180, 210, 240, 270, 300], r"$T_{arrival}$ [sec]", 1.0),
        ("fleet", "n_robots", [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], r"$N_{agent}$", 1.0),
        ("topology_size", "n_rooms", [4, 9, 16, 25, 36, 49], r"$N_{rooms}$", 1.0),
    ]

    if "rq3" in selected:
        rq3 = load_runs(root / "RQ3" / "runs.csv", RQ3_PROFILE)
        panel_figure(
            rq3, panels=basic_panels, metric="adapt_overhead_ms_mean", ylabel="Overhead/check [ms]",
            filename="rq3_monitoring_overhead_extended.pdf", output_dir=output_dir, only_da=True,
        )
        software_panels = [
            ("computation", "comp_time", [value / 10 for value in range(0, 11)], r"$T_{comp}$ [ms]", 1000.0),
            ("communication_time", "comm_time", [value / 10 for value in range(0, 11)], r"$T_{comm}$ [ms]", 1000.0),
            ("message_loss", "msg_loss_prob", [value / 10 for value in range(0, 11)], r"$F_{msg}$ [%]", 100.0),
        ]
        panel_figure(
            rq3, panels=software_panels, metric="avg_relative_latency_s", ylabel="Relative latency [min]",
            filename="rq3_latency_software_parameters.pdf", output_dir=output_dir,
        )
        panel_figure(
            rq3, panels=software_panels, metric="completion_rate", ylabel="Completion rate [%]",
            filename="rq3_completion_software_parameters.pdf", output_dir=output_dir,
        )

    if "rq4" in selected:
        rq4 = load_runs(root / "RQ4" / "runs.csv", RQ4_PROFILE)
        panel_figure_rq4_hardware(
            rq4, panels=basic_panels, metric="wall_time_s", ylabel="Wall-clock time [sec]",
            filename="rq4_wall_clock_extended.pdf", output_dir=output_dir,
        )


if __name__ == "__main__":
    main()

