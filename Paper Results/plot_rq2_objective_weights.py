#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


PROFILE = "table-aligned-operating-cycle-v1"
FD_POLICY = "limited-patrol-v2"
SECONDS_PER_DAY = 24 * 3600
OBJECTIVES = (
    (0.50, "balanced_50_50"),
    (1.00, "completion_100"),
    (0.00, "latency_100"),
)
PHASE_DISPLAY = {
    "P1": "P1",
    "P2": "P2",
    "P3": "P3",
    "P4": "P4",
}
PHASE_COLORS = {
    "P1": "#e0e0e0",
    "P2": "#a6a6a6",
    "P3": "#737373",
    "P4": "#f2f2f2",
}
SWITCH_COLORS = {"CE": "#1f77b4", "SD": "#ff7f0e", "FD": "#2ca02c"}
SWITCH_MARKERS = {"CE": "o", "SD": "s", "FD": "^"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("Paper Results/RQ2"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Paper Results/paper_figures_latest/rq2_objective_weights"),
    )
    return parser.parse_args()


def label(architecture: object) -> str:
    value = str(architecture).lower()
    if "semi" in value:
        return "SD"
    if "decentral" in value:
        return "FD"
    return "CE"


def style_axes(ax: plt.Axes) -> None:
    ax.set_axisbelow(True)
    ax.grid(axis="y", linestyle=":", linewidth=0.5, color="#bdbdbd")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save(fig: plt.Figure, output_dir: Path, filename: str) -> None:
    fig.savefig(output_dir / filename, bbox_inches="tight")
    fig.savefig(output_dir / "previews" / filename.replace(".pdf", ".png"), dpi=160, bbox_inches="tight")
    plt.close(fig)


def truth(values: pd.Series) -> pd.Series:
    return values.astype(str).str.lower().eq("true")


def phase_blocks(trace: pd.DataFrame) -> pd.DataFrame:
    phases = trace[["sim_time", "phase_label"]].dropna().copy()
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
                       color=color, alpha=0.45, linewidth=0)


def plot_timeline(trace_all: pd.DataFrame, phases: pd.DataFrame, slug: str, output_dir: Path, days: int, number: str) -> None:
    start_day = best_window_start(trace_all, days)
    start = (start_day - 1) * SECONDS_PER_DAY
    end = start + days * SECONDS_PER_DAY
    trace = trace_all[trace_all["sim_time"].between(start, end)].copy()
    phase_trace = phases[(phases["end"] >= start) & (phases["start"] <= end)].copy()
    trace["day"] = trace["sim_time"] / SECONDS_PER_DAY + 1
    trace["latency_min"] = trace["latency"].rolling(5, min_periods=1).mean() / 60
    trace["completion_smooth"] = 100 * trace["completion_rate"].rolling(5, min_periods=1).mean()

    fig, (ax_windows, ax_perf) = plt.subplots(
        2, 1, figsize=(6.4, 3.1), sharex=True,
        gridspec_kw={"height_ratios": [0.35, 1.0], "hspace": 0.08},
    )
    for phase in phase_trace.itertuples():
        color = PHASE_COLORS.get(str(phase.phase_label))
        if color:
            ax_windows.axvspan(max(phase.start, start) / SECONDS_PER_DAY + 1,
                               min(phase.end, end) / SECONDS_PER_DAY + 1, color=color, alpha=0.85, linewidth=0)
    ax_windows.set_ylim(0, 1)
    ax_windows.set_yticks([])
    ax_windows.set_ylabel("Dynamic\nphases")
    ax_windows.spines["top"].set_visible(False)
    ax_windows.spines["right"].set_visible(False)
    ax_windows.spines["left"].set_visible(False)

    ax_perf.plot(trace["day"], trace["latency_min"], color="#222222", linewidth=1.0, label="Latency")
    ax_perf.set_ylabel("Latency (min)")
    style_axes(ax_perf)
    ax_completion = ax_perf.twinx()
    ax_completion.plot(trace["day"], trace["completion_smooth"], color="#777777", linewidth=1.0, linestyle="--", label="Completion rate")
    ax_completion.set_ylim(0, 100)
    ax_completion.set_ylabel("Completion rate (%)")
    ax_completion.spines["top"].set_visible(False)

    switches = trace[truth(trace["switched"])]
    seen = set()
    for row in switches.itertuples():
        selected = label(row.selected_architecture)
        ax_perf.axvline(row.day, color=SWITCH_COLORS[selected], linestyle=":", linewidth=0.8, alpha=0.85)
        ax_windows.scatter([row.day], [0.5], s=20, marker=SWITCH_MARKERS[selected], facecolor=SWITCH_COLORS[selected],
                           edgecolor="#222222", linewidth=0.4, zorder=3)
        seen.add(selected)
    handles = [
        Line2D([0], [0], color="#222222", lw=1.0, label="Latency"),
        Line2D([0], [0], color="#777777", lw=1.0, linestyle="--", label="Completion rate"),
    ] + [
        Line2D([0], [0], color=SWITCH_COLORS[item], marker=SWITCH_MARKERS[item], linestyle=":", lw=0.8,
               markersize=4, label=f"Switch to {item}") for item in ("CE", "SD", "FD") if item in seen
    ]
    ax_perf.legend(handles=handles, loc="upper left", ncol=2, frameon=False)
    ax_perf.set_xlabel("Simulation day")
    ax_perf.set_xlim(start_day, start_day + days)
    step = 1 if days <= 7 else 3 if days <= 31 else 15
    ax_perf.set_xticks(np.arange(start_day, start_day + days + 0.1, step))
    fig.subplots_adjust(left=0.10, right=0.88, top=0.96, bottom=0.16, hspace=0.08)
    save(fig, output_dir, f"rq2_{slug}_{number}_timeline_{days}d.pdf")


def plot_objective(timeline: pd.DataFrame, slug: str, output_dir: Path) -> None:
    counts = timeline.assign(_switched=truth(timeline["switched"])).groupby("run_id")["_switched"].sum()
    trace_all = timeline[timeline["run_id"].eq(counts.sort_values(ascending=False).index[0])].sort_values("sim_time").copy()
    phases = phase_blocks(trace_all)
    start_day = best_window_start(trace_all, 7)
    start = (start_day - 1) * SECONDS_PER_DAY
    end = start + 7 * SECONDS_PER_DAY
    trend = trace_all[trace_all["sim_time"].between(start, end)].copy()
    trend["day"] = trend["sim_time"] / SECONDS_PER_DAY + 1

    fig, ax = plt.subplots(figsize=(6.4, 2.55))
    shade(ax, phases, start, end)
    for name, column, color, linestyle in (
        ("Failure pressure", "context_failure_norm", "#222222", "-"),
        ("Network probe loss", "context_network_probe_loss_rate", "#555555", "--"),
        ("Suspicious activity", "context_suspicion_norm", "#888888", ":"),
    ):
        ax.plot(trend["day"], trend[column].rolling(5, min_periods=1).mean(), label=name, color=color, linestyle=linestyle, linewidth=1.0)
    ax.set_xlim(start_day, start_day + 7)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Simulation day")
    ax.set_ylabel("Monitored context (normalised)")
    ax.set_xticks(np.arange(start_day, start_day + 8))
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.02))
    style_axes(ax)
    fig.legend(handles=[Patch(facecolor=PHASE_COLORS[key], edgecolor="none", alpha=0.7, label=PHASE_DISPLAY[key]) for key in PHASE_DISPLAY],
               ncol=4, frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    save(fig, output_dir, f"rq2_{slug}_01_switch_context_by_phase.pdf")

    mechanism_codes = {"FD": 0, "SD": 1, "CE": 2}
    selected = trend["selected_architecture"].map(label)
    switches = trend[truth(trend["switched"])]
    fig, ax = plt.subplots(figsize=(6.4, 2.35))
    shade(ax, phases, start, end)
    ax.step(trend["day"], selected.map(mechanism_codes), where="post", color="#222222", linewidth=1.0)
    for mechanism in ("CE", "SD", "FD"):
        points = switches[switches["selected_architecture"].map(label).eq(mechanism)]
        ax.scatter(points["day"], [mechanism_codes[mechanism]] * len(points), s=16, color=SWITCH_COLORS[mechanism],
                   marker=SWITCH_MARKERS[mechanism], edgecolor="#222222", linewidth=0.35, label=f"Switch to {mechanism}", zorder=3)
    ax.set_xlim(start_day, start_day + 7)
    ax.set_xticks(np.arange(start_day, start_day + 8))
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["FD", "SD", "CE"])
    ax.set_xlabel("Simulation day")
    ax.set_ylabel("Active mechanism")
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.02))
    style_axes(ax)
    fig.legend(handles=[Patch(facecolor=PHASE_COLORS[key], edgecolor="none", alpha=0.7, label=PHASE_DISPLAY[key]) for key in PHASE_DISPLAY],
               ncol=4, frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    save(fig, output_dir, f"rq2_{slug}_02_mechanism_time_by_phase.pdf")
    plot_timeline(trace_all, phases, slug, output_dir, 15, "03")
    full_days = max(1, int(np.ceil(trace_all["sim_time"].max() / SECONDS_PER_DAY)))
    plot_timeline(trace_all, phases, slug, output_dir, full_days, "04")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "previews").mkdir(exist_ok=True)
    for path in list(args.output_dir.glob("rq2_*.pdf")) + list((args.output_dir / "previews").glob("rq2_*.png")):
        path.unlink()
    plt.rcParams.update({"font.family": "CMU Serif", "axes.labelsize": 9, "axes.titlesize": 9,
                         "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8, "axes.unicode_minus": False})
    runs = pd.read_csv(args.data_dir / "runs.csv")
    timeline = pd.read_csv(args.data_dir / "adaptation_state_timeseries.csv.gz", low_memory=False)
    runs = runs[(runs["experiment_profile"].eq(PROFILE)) & (runs["fd_policy_version"].eq(FD_POLICY)) &
                (runs["status"].fillna("ok").astype(str).str.lower().eq("ok"))].copy()
    for column in ("sim_time", "latency", "completion_rate", "bandit_completion_weight"):
        if column in timeline:
            timeline[column] = pd.to_numeric(timeline[column], errors="coerce")
    generated = 0
    for weight, slug in OBJECTIVES:
        selected = runs[np.isclose(pd.to_numeric(runs["bandit_completion_weight"], errors="coerce"), weight)]
        if selected.empty:
            continue
        trace = timeline[timeline["run_id"].astype(str).isin(set(selected["run_id"].astype(str)))].copy()
        plot_objective(trace, slug, args.output_dir)
        generated += 4
    if not generated:
        raise RuntimeError("No successful RQ2 runs were found for the current experiment profile.")


if __name__ == "__main__":
    main()
