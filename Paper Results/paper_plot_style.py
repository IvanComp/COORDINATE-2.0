#!/usr/bin/env python3
"""Single source of truth for the paper figure style.

Every RQ figure script imports the palette, markers, axis styling, and save
helpers from here so that the same coordination mechanism is always drawn the
same way across RQ1, RQ2, RQ3, and RQ4.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator


PAPER_ROOT = Path(__file__).resolve().parent
DEFAULT_FIGURES_DIR = PAPER_ROOT / "paper_figures_latest"

# Coordination mechanisms, in the order they appear in every legend.
ORDER = ("FD", "SD", "CE", "DA")

STYLE = {
    "FD": {"color": "#0000ff", "marker": "o", "linestyle": "-"},
    "SD": {"color": "#f5a000", "marker": "^", "linestyle": "-"},
    "CE": {"color": "#008000", "marker": "s", "linestyle": "-"},
    "DA": {"color": "#333333", "marker": "D", "linestyle": "--"},
}

COLORS = {label: spec["color"] for label, spec in STYLE.items()}
MARKERS = {label: spec["marker"] for label, spec in STYLE.items()}
LINESTYLES = {label: spec["linestyle"] for label, spec in STYLE.items()}

GRID_COLOR = "#d9d9d9"
LEGEND_EDGE_COLOR = "#dddddd"
PENDING_COLOR = "#666666"
# Outline drawn around scatter markers and bars, so a light fill stays visible.
MARKER_EDGE_COLOR = "#222222"
# Texture that distinguishes a second variant of the same series, currently the
# hardware profile in RQ4, without spending another colour on it.
SECONDARY_HATCH = "////"

# Neutral greys for the fault-window bands. They stay outside the mechanism
# palette so a shaded window is never confused with a mechanism. The shade
# tracks severity: FW1 leaves the background untouched because it applies no
# extra fault pressure, and each later window is darker.
PHASE_DISPLAY = {"I1": "FW1", "I2": "FW2", "I3": "FW3", "I4": "FW4"}
PHASE_COLORS = {"I1": "#ffffff", "I2": "#dcdcdc", "I3": "#b0b0b0", "I4": "#808080"}
PHASE_EDGE_COLOR = "#9e9e9e"

# Non-mechanism series (RQ2 timelines) also share one convention.
METRIC_STYLE = {
    "latency": {"color": "#222222", "linestyle": "-"},
    "completion_rate": {"color": "#777777", "linestyle": "--"},
}

# These are exactly the RQ1 rcParams. Tick labels deliberately inherit
# font.size instead of being set explicitly: overriding them changes every tick
# in every figure, so the values stay as the published RQ1 figures had them.
RC_PARAMS = {
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "axes.unicode_minus": False,
}


def apply_rc() -> None:
    """Apply the shared rcParams. Call once at the start of a figure script."""
    plt.rcParams.update(RC_PARAMS)


def mechanism_label(architecture: object) -> str:
    """Map a full architecture name onto its short mechanism label."""
    value = str(architecture).lower()
    if "semi" in value:
        return "SD"
    if "decentral" in value:
        return "FD"
    if "dynamic" in value or "adapt" in value:
        return "DA"
    return "CE"


def style_axes(ax: plt.Axes, metric: str | None = None, grid_axis: str = "y",
               integer_ticks: bool = True) -> None:
    """Apply the shared axis look, plus the metric-specific y-range if known.

    Pass ``integer_ticks=False`` for quantities whose useful range is below a
    few units, such as per-check overhead in milliseconds, where integer ticks
    would collapse the axis.
    """
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID_COLOR, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if metric == "completion_rate":
        ax.set_ylim(0, 105)
        ax.set_yticks(range(0, 101, 20))
    else:
        ax.yaxis.set_major_locator(MaxNLocator(integer=integer_ticks, nbins=6))


def legend_handles(labels=ORDER, linewidth: float = 1.0, markersize: float = 3.5) -> list[Line2D]:
    """Build legend proxies so panels without data still get a full legend."""
    return [
        Line2D([0], [0], label=label, linewidth=linewidth, markersize=markersize, **STYLE[label])
        for label in labels
        if label in STYLE
    ]


def add_legend(ax: plt.Axes, handles, loc: str = "upper left", **kwargs):
    """Attach a legend using the shared frame styling."""
    if not handles:
        return None
    kwargs.setdefault("frameon", True)
    kwargs.setdefault("edgecolor", LEGEND_EDGE_COLOR)
    return ax.legend(handles=handles, loc=loc, **kwargs)


def pending_text(ax: plt.Axes, message: str = "Data pending") -> None:
    """Mark an empty panel instead of leaving it silently blank."""
    ax.text(0.5, 0.5, message, transform=ax.transAxes,
            ha="center", va="center", color=PENDING_COLOR)


def save(fig: plt.Figure, output_dir: Path, filename: str, dpi: int = 180) -> Path:
    """Write the PDF used by the paper plus the PNG preview used by the notebook."""
    output_dir = Path(output_dir)
    previews = output_dir / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    previews.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / filename
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(previews / filename.replace(".pdf", ".png"), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return pdf_path
