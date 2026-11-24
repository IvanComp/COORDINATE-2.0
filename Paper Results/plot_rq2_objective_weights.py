#!/usr/bin/env python3

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
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_plot_style import (  # noqa: E402
    COLORS,
    MARKERS,
    METRIC_STYLE,
    PHASE_COLORS,
    PHASE_DISPLAY,
    MARKER_EDGE_COLOR,
    PHASE_EDGE_COLOR,
    apply_rc,
    mechanism_label,
    save,
    style_axes,
)
from run_rq2_experiments import RQ2_EXPERIMENT_PROFILE


FD_POLICY = "legacy-local-retry-v7"
SECONDS_PER_DAY = 24 * 3600

# One row per objective weighting in each of the two figures.
OBJECTIVES = (
    (0.50, "balanced_50_50", r"$r_{j+1} = w_1 = 0.50 + w_2 = 0.50$"),
    (1.00, "completion_100", r"$r_{j+1} = w_1 = 1.00 + w_2 = 0.00$"),
    (0.00, "latency_100", r"$r_{j+1} = w_1 = 0.00 + w_2 = 1.00$"),
)

PHASE_ALIASES = {f"P{index}": f"I{index}" for index in range(1, 5)}
# Switch markers reuse the shared mechanism palette so a "Switch to CE" dot is
# the same green as the CE line in RQ1, RQ3, and RQ4.
SWITCH_COLORS = {label: COLORS[label] for label in ("CE", "SD", "FD")}
SWITCH_MARKERS = {label: MARKERS[label] for label in ("CE", "SD", "FD")}
LATENCY_STYLE = METRIC_STYLE["latency"]
COMPLETION_STYLE = METRIC_STYLE["completion_rate"]
MECHANISM_CODES = {"FD": 0, "SD": 1, "CE": 2}
# Figure width matches RQ1 so that identical point sizes render at the same
# relative text size across every research question.
FIGURE_WIDTH = 11.8

label = mechanism_label


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("Paper Results/RQ2"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Paper Results/paper_figures_latest/rq2_objective_weights"),
    )
    return parser.parse_args()


def truth(values: pd.Series) -> pd.Series:
    return values.astype(str).str.lower().eq("true")


def phase_blocks(trace: pd.DataFrame) -> pd.DataFrame:
    phases = trace[["sim_time", "phase_label"]].dropna().copy()
    phases["phase_label"] = phases["phase_label"].astype(str).map(lambda value: PHASE_ALIASES.get(value, value))
    phases["block"] = phases["phase_label"].ne(phases["phase_label"].shift()).cumsum()
    phases = phases.groupby("block", as_index=False).agg(start=("sim_time", "min"), phase_label=("phase_label", "first"))
    phases["end"] = phases["start"].shift(-1).fillna(trace["sim_time"].max())
    return phases


def best_window_start(trace: pd.DataFrame, days: int) -> int:
    switch_times = trace.loc[truth(trace["switched"]), "sim_time"]
    max_day = max(days, int(np.ceil(trace["sim_time"].max() / SECONDS_PER_DAY)))
    candidates = range(1, max_day - days + 2)
    return max(candidates, key=lambda day: ((switch_times >= (day - 1) * SECONDS_PER_DAY) & (switch_times <= (day - 1 + days) * SECONDS_PER_DAY)).sum())


def shade(ax: plt.Axes, phases: pd.DataFrame, start: float, end: float) -> None:
    for phase in phases.itertuples():
        color = PHASE_COLORS.get(str(phase.phase_label))
        if color:
            ax.axvspan(max(phase.start, start) / SECONDS_PER_DAY + 1, min(phase.end, end) / SECONDS_PER_DAY + 1,
                       color=color, alpha=0.70, linewidth=0)


def prepare(timeline: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pick the run with the most switches and derive its operating phases."""
    counts = timeline.assign(_switched=truth(timeline["switched"])).groupby("run_id")["_switched"].sum()
    trace_all = timeline[timeline["run_id"].eq(counts.sort_values(ascending=False).index[0])].sort_values("sim_time").copy()
    return trace_all, phase_blocks(trace_all)


def draw_mechanism(ax: plt.Axes, trace_all: pd.DataFrame, phases: pd.DataFrame, days: int,
                   show_label: bool) -> set[str]:
    start_day = best_window_start(trace_all, days)
    start = (start_day - 1) * SECONDS_PER_DAY
    end = start + days * SECONDS_PER_DAY
    trend = trace_all[trace_all["sim_time"].between(start, end)].copy()
    trend["day"] = trend["sim_time"] / SECONDS_PER_DAY + 1

    shade(ax, phases, start, end)
    ax.step(trend["day"], trend["selected_architecture"].map(label).map(MECHANISM_CODES),
            where="post", color=LATENCY_STYLE["color"], linewidth=1.0)

    switches = trend[truth(trend["switched"])]
    seen: set[str] = set()
    for mechanism in ("CE", "SD", "FD"):
        points = switches[switches["selected_architecture"].map(label).eq(mechanism)]
        if points.empty:
            continue
        seen.add(mechanism)
        ax.scatter(points["day"], [MECHANISM_CODES[mechanism]] * len(points), s=16,
                   color=SWITCH_COLORS[mechanism], marker=SWITCH_MARKERS[mechanism],
                   edgecolor=MARKER_EDGE_COLOR, linewidth=0.35, zorder=3)

    style_axes(ax)
    ax.set_xlim(start_day, start_day + days)
    step = 1 if days <= 7 else 3 if days <= 31 else 15
    ax.set_xticks(np.arange(start_day, start_day + days + 0.1, step))
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["FD", "SD", "CE"])
    if show_label:
        ax.set_ylabel("Active mechanism")
    return seen


def draw_timeline(ax_windows: plt.Axes, ax_perf: plt.Axes, trace_all: pd.DataFrame,
                  phases: pd.DataFrame, days: int, show_labels: bool) -> set[str]:
    start_day = best_window_start(trace_all, days)
    start = (start_day - 1) * SECONDS_PER_DAY
    end = start + days * SECONDS_PER_DAY
    trace = trace_all[trace_all["sim_time"].between(start, end)].copy()
    phase_trace = phases[(phases["end"] >= start) & (phases["start"] <= end)]
    trace["day"] = trace["sim_time"] / SECONDS_PER_DAY + 1
    trace["latency_min"] = trace["latency"].rolling(5, min_periods=1).mean() / 60
    trace["completion_smooth"] = 100 * trace["completion_rate"].rolling(5, min_periods=1).mean()

    for phase in phase_trace.itertuples():
        color = PHASE_COLORS.get(str(phase.phase_label))
        if color:
            ax_windows.axvspan(max(phase.start, start) / SECONDS_PER_DAY + 1,
                               min(phase.end, end) / SECONDS_PER_DAY + 1,
                               color=color, alpha=0.85, linewidth=0)
    ax_windows.set_ylim(0, 1)
    ax_windows.set_yticks([])
    for side in ("top", "right", "left"):
        ax_windows.spines[side].set_visible(False)

    ax_perf.plot(trace["day"], trace["latency_min"], linewidth=1.0, **LATENCY_STYLE)
    if show_labels:
        ax_perf.set_ylabel("Latency (min)")
    style_axes(ax_perf)
    # Drop the topmost tick so its label cannot collide with the phase band above.
    ax_perf.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5, prune="upper"))
    ax_completion = ax_perf.twinx()
    ax_completion.plot(trace["day"], trace["completion_smooth"], linewidth=1.0, **COMPLETION_STYLE)
    ax_completion.set_ylim(0, 105)
    ax_completion.set_yticks(range(0, 101, 20))
    if show_labels:
        ax_completion.set_ylabel("Completion rate (%)")
    ax_completion.spines["top"].set_visible(False)

    seen: set[str] = set()
    for row in trace[truth(trace["switched"])].itertuples():
        selected = label(row.selected_architecture)
        ax_perf.axvline(row.day, color=SWITCH_COLORS[selected], linestyle=":", linewidth=0.8, alpha=0.85)
        ax_windows.scatter([row.day], [0.5], s=20, marker=SWITCH_MARKERS[selected],
                           facecolor=SWITCH_COLORS[selected], edgecolor=MARKER_EDGE_COLOR, linewidth=0.4, zorder=3)
        seen.add(selected)

    ax_perf.set_xlim(start_day, start_day + days)
    step = 1 if days <= 7 else 3 if days <= 31 else 15
    ax_perf.set_xticks(np.arange(start_day, start_day + days + 0.1, step))
    return seen


def phase_handles() -> list[Patch]:
    """One legend entry per fault window, from the untinted FW1 to the darkest."""
    return [
        Patch(facecolor=PHASE_COLORS[key], edgecolor=PHASE_EDGE_COLOR,
              linewidth=0.4, label=PHASE_DISPLAY[key])
        for key in PHASE_DISPLAY
    ]


def figure_legend(fig, handles: list) -> None:
    fig.legend(handles=handles, ncol=len(handles), frameon=False,
               loc="upper center", bbox_to_anchor=(0.5, 1.0))


def switch_handles(seen: set[str], linestyle: str) -> list[Line2D]:
    return [Line2D([0], [0], color=SWITCH_COLORS[mechanism], marker=SWITCH_MARKERS[mechanism],
                   linestyle=linestyle, lw=0.8, markersize=4, markeredgecolor=MARKER_EDGE_COLOR,
                   markeredgewidth=0.35, label=f"Switch to {mechanism}")
            for mechanism in ("CE", "SD", "FD") if mechanism in seen]


def plot_mechanism_figure(datasets: list[dict], output_dir: Path, days: int) -> Path:
    """One figure stacking the active-mechanism timeline of every objective."""
    fig, axes = plt.subplots(len(datasets), 1, figsize=(FIGURE_WIDTH, 1.75 * len(datasets)))
    axes = np.atleast_1d(axes)
    seen: set[str] = set()
    middle = len(datasets) // 2
    for index, (ax, data) in enumerate(zip(axes, datasets)):
        seen |= draw_mechanism(ax, data["trace"], data["phases"], days, index == middle)
        ax.set_title(data["title"])
    axes[-1].set_xlabel("Simulation day")

    figure_legend(fig, switch_handles(seen, "none") + phase_handles())
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return save(fig, output_dir, "rq2_mechanism_time_by_phase.pdf")


def plot_timeline_figure(datasets: list[dict], output_dir: Path, days: int) -> Path:
    """One figure stacking the full-duration timeline of every objective."""
    fig = plt.figure(figsize=(FIGURE_WIDTH, 2.20 * len(datasets)))
    outer = fig.add_gridspec(len(datasets), 1, hspace=0.55)
    seen: set[str] = set()
    middle = len(datasets) // 2
    for index, data in enumerate(datasets):
        inner = outer[index].subgridspec(2, 1, height_ratios=[0.30, 1.0], hspace=0.10)
        ax_windows = fig.add_subplot(inner[0])
        ax_perf = fig.add_subplot(inner[1], sharex=ax_windows)
        seen |= draw_timeline(ax_windows, ax_perf, data["trace"], data["phases"], days, index == middle)
        ax_windows.set_title(data["title"])
        if index == len(datasets) - 1:
            ax_perf.set_xlabel("Simulation day")
        plt.setp(ax_windows.get_xticklabels(), visible=False)

    handles = [
        Line2D([0], [0], lw=1.0, label="Latency", **LATENCY_STYLE),
        Line2D([0], [0], lw=1.0, label="Completion rate", **COMPLETION_STYLE),
    ] + switch_handles(seen, ":") + phase_handles()
    figure_legend(fig, handles)
    fig.subplots_adjust(left=0.06, right=0.94, top=0.91, bottom=0.08)
    return save(fig, output_dir, f"rq2_timeline_{days}d.pdf")


def switch_statistics(datasets: list[dict], output_dir: Path) -> pd.DataFrame:
    """Share of DA switches per dynamic fault window and target mechanism.

    Percentages are taken over all switches of one objective, so every block of
    three mechanism rows sums to 100.
    """
    rows = []
    for data in datasets:
        trace = data["runs"]
        switches = trace[truth(trace["switched"])]
        phases = switches["phase_label"].astype(str).map(lambda value: PHASE_ALIASES.get(value, value))
        selected = switches["selected_architecture"].map(label)
        total = len(switches)
        for mechanism in ("CE", "SD", "FD"):
            row = {"Objective": data["title"], "Mechanism": mechanism}
            for key in PHASE_DISPLAY:
                matches = phases.eq(key) & selected.eq(mechanism)
                row[PHASE_DISPLAY[key]] = round(100.0 * matches.sum() / total, 1) if total else float("nan")
            rows.append(row)

    table = pd.DataFrame(rows).set_index(["Objective", "Mechanism"])
    table.to_csv(output_dir / "rq2_switch_statistics.csv")
    return table


def load_datasets(data_dir: Path) -> list[dict]:
    runs = pd.read_csv(data_dir / "runs.csv")
    timeline = pd.read_csv(data_dir / "adaptation_state_timeseries.csv.gz", low_memory=False)
    runs = runs[
        runs["experiment_profile"].eq(RQ2_EXPERIMENT_PROFILE)
        & runs["fd_policy_version"].eq(FD_POLICY)
        & runs["status"].fillna("ok").astype(str).str.lower().eq("ok")
    ].copy()
    for column in ("sim_time", "latency", "completion_rate", "bandit_completion_weight"):
        if column in timeline:
            timeline[column] = pd.to_numeric(timeline[column], errors="coerce")

    datasets = []
    for weight, slug, title in OBJECTIVES:
        selected = runs[np.isclose(pd.to_numeric(runs["bandit_completion_weight"], errors="coerce"), weight)]
        if selected.empty:
            continue
        trace = timeline[timeline["run_id"].astype(str).isin(set(selected["run_id"].astype(str)))].copy()
        representative, phases = prepare(trace)
        # The figures show one representative run; the table aggregates them all.
        datasets.append({
            "slug": slug,
            "title": title,
            "trace": representative,
            "phases": phases,
            "runs": trace,
        })
    if not datasets:
        raise RuntimeError("No successful RQ2 runs were found for the current experiment profile.")
    return datasets


def generate(data_dir: Path, output_dir: Path | None = None) -> tuple[list[Path], pd.DataFrame]:
    """Write the two RQ2 figures plus the switch-statistics table."""
    data_dir = Path(data_dir).resolve()
    output_dir = Path(
        output_dir or data_dir.parent / "paper_figures_latest" / "rq2_objective_weights"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "previews").mkdir(exist_ok=True)
    for path in list(output_dir.glob("rq2_*.pdf")) + list((output_dir / "previews").glob("rq2_*.png")):
        path.unlink()

    apply_rc()
    datasets = load_datasets(data_dir)
    days = max(1, int(np.ceil(max(data["trace"]["sim_time"].max() for data in datasets) / SECONDS_PER_DAY)))
    figures = [
        plot_mechanism_figure(datasets, output_dir, days),
        plot_timeline_figure(datasets, output_dir, days),
    ]
    return figures, switch_statistics(datasets, output_dir)


def main() -> None:
    args = parse_args()
    generate(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
