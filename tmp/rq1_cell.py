from pathlib import Path
import numpy as np
import pandas as pd

try:
    _IN_IPYTHON = get_ipython() is not None
except NameError:
    _IN_IPYTHON = False

if not _IN_IPYTHON:
    import matplotlib
    matplotlib.use('Agg')

import matplotlib.pyplot as plt

try:
    from IPython.display import display
except ImportError:
    def display(*args, **kwargs):
        return None

RESULTS_ROOT_OVERRIDE = None
SAVE_FIGURES = True
FIGURE_DIR_NAME = 'paper_figures'

plt.rcParams.update({
    'font.family': 'CMU Serif',
    'axes.labelsize': 9,
    'axes.titlesize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'axes.unicode_minus': False,
})

SINGLE_FIGSIZE = (3.0, 2.0)
WIDE_FIGSIZE = (6.4, 2.3)
TIMELINE_FIGSIZE = (6.8, 3.5)
COORD_ORDER = ['FD', 'SD', 'CE', 'DA']
COORD_COLORS = {'FD': '#666666', 'SD': '#999999', 'CE': '#b3b3b3', 'DA': '#ffffff'}
COORD_HATCHES = {'FD': '', 'SD': '', 'CE': '', 'DA': 'ooo'}
EDGE_COLOR = '#222222'
GRID_COLOR = '#bdbdbd'


def result_root_candidates():
    cwd = Path.cwd()
    candidates = []
    if RESULTS_ROOT_OVERRIDE is not None:
        candidates.append(Path(RESULTS_ROOT_OVERRIDE))
    candidates.extend([
        cwd,
        cwd / 'Paper Results',
        cwd.parent / 'Paper Results',
        Path.home() / 'Desktop' / 'COORDINATE-2.0' / 'Paper Results',
        Path.home() / 'Desktop' / 'Paper Results',
    ])
    unique = []
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        if candidate not in unique:
            unique.append(candidate)
    return unique


def find_results_root(required_any=(), required_all=()):
    checked = []
    for root in result_root_candidates():
        checked.append(root)
        if not root.exists():
            continue
        has_any = True if not required_any else any((root / path).exists() for path in required_any)
        has_all = all((root / path).exists() for path in required_all)
        if has_any and has_all:
            return root
    raise FileNotFoundError('Could not find result files. Checked: ' + ', '.join(str(path) for path in checked))


def style_axes(ax, grid_axis='y'):
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, linestyle=':', linewidth=0.5, color=GRID_COLOR)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def coord_color(label):
    return COORD_COLORS.get(str(label), '#b3b3b3')


def coord_hatch(label):
    return COORD_HATCHES.get(str(label), '')


def apply_hatches(bars, labels):
    for bar, label in zip(bars, labels):
        label = str(label)
        bar.set_facecolor(coord_color(label))
        bar.set_edgecolor(EDGE_COLOR)
        bar.set_linewidth(0.5)
        bar.set_hatch(coord_hatch(label))


def save_or_show(fig, root, filename=None):
    if SAVE_FIGURES and filename:
        out_dir = root / FIGURE_DIR_NAME
        out_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_dir / filename, bbox_inches='tight')
    if _IN_IPYTHON:
        plt.show()
    else:
        plt.close(fig)



TASK_EXPIRATION_COLUMNS = [
    'expiration_time_low_s',
    'expiration_time_medium_s',
    'expiration_time_high_s',
]


def filter_task_expiration_configured(frame, label, required=True):
    missing = [col for col in TASK_EXPIRATION_COLUMNS if col not in frame.columns]
    if missing:
        if required:
            raise ValueError(f'{label} is missing task-expiration columns: {missing}')
        return frame.copy()
    mask = pd.Series(True, index=frame.index)
    for col in TASK_EXPIRATION_COLUMNS:
        mask &= pd.to_numeric(frame[col], errors='coerce').fillna(0).gt(0)
    filtered = frame.loc[mask].copy()
    if filtered.empty:
        raise ValueError(f'{label} has no rows with task expiration configured.')
    return filtered

def first_existing_column(frame, candidates):
    for column in candidates:
        if column in frame.columns:
            return column
    return None


def numeric(frame, columns):
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors='coerce')
    return frame


def metric_summary(frame, metric, scale=1.0):
    grouped = frame.groupby('coord_label', observed=False)[metric]
    summary = grouped.agg(['mean', 'std', 'count']).reindex(COORD_ORDER).dropna(subset=['mean']).reset_index()
    summary['mean'] = summary['mean'] * scale
    summary['ci95'] = 1.96 * summary['std'].fillna(0.0) / np.sqrt(summary['count'].clip(lower=1)) * scale
    return summary


def plot_metric_with_ci(frame, metric, ylabel, filename, scale=1.0, title=None):
    summary = metric_summary(frame, metric, scale=scale)
    labels = summary['coord_label'].astype(str).tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=SINGLE_FIGSIZE)
    bars = ax.bar(x, summary['mean'].to_numpy(), width=0.72)
    apply_hatches(bars, labels)
    ax.errorbar(x, summary['mean'].to_numpy(), yerr=summary['ci95'].to_numpy(), fmt='none',
                ecolor=EDGE_COLOR, elinewidth=0.7, capsize=2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel('Mechanism')
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    style_axes(ax, grid_axis='y')
    fig.tight_layout()
    save_or_show(fig, ROOT, filename)
    return summary

ROOT = find_results_root(required_all=[Path('RQ1/runs.csv')])
rq1_path = ROOT / 'RQ1' / 'runs.csv'
runs = pd.read_csv(rq1_path)
if 'status' in runs.columns:
    runs = runs[runs['status'].fillna('ok').astype(str).str.lower() == 'ok'].copy()
else:
    runs = runs.copy()
runs = filter_task_expiration_configured(runs, 'RQ1 runs.csv')

metric_columns = [
    'avg_latency_s', 'median_latency_s', 'avg_relative_latency_s', 'relative_latency_s', 'completion_rate',
    'delivered', 'expired', 'deadline_misses', 'throughput_per_hour', 'created', 'pending',
    'switch_count', 'rep', 'event_count', 'wall_time_s',
]
runs = numeric(runs, metric_columns)
runs['completion_latency_efficiency'] = 100 * runs['completion_rate'] / (runs['median_latency_s'] / 60)
runs['coord_label'] = runs['coord_label'].astype(str)
coord_order = [label for label in COORD_ORDER if label in set(runs['coord_label'])]
runs['coord_label'] = pd.Categorical(runs['coord_label'], categories=coord_order, ordered=True)

latency_metric = first_existing_column(runs, ['avg_relative_latency_s', 'relative_latency_s', 'avg_latency_s'])
if latency_metric is None:
    raise ValueError('RQ1 runs.csv does not contain an average latency column.')
latency_label = 'Average relative latency (h)' if 'relative' in latency_metric else 'Average task latency (h)'
latency_summary = plot_metric_with_ci(
    runs,
    latency_metric,
    latency_label,
    'rq1_01_average_task_latency.pdf',
    scale=1 / 3600,
)

completion_summary = metric_summary(runs, 'completion_rate', scale=100)
delivered_summary = metric_summary(runs, 'delivered', scale=1.0)
labels = completion_summary['coord_label'].astype(str).tolist()
x = np.arange(len(labels))
fig, axes = plt.subplots(1, 2, figsize=WIDE_FIGSIZE)
bars = axes[0].bar(x, completion_summary['mean'].to_numpy(), width=0.72)
apply_hatches(bars, labels)
axes[0].errorbar(x, completion_summary['mean'].to_numpy(), yerr=completion_summary['ci95'].to_numpy(),
                 fmt='none', ecolor=EDGE_COLOR, elinewidth=0.7, capsize=2)
axes[0].set_xticks(x)
axes[0].set_xticklabels(labels)
axes[0].set_xlabel('Mechanism')
axes[0].set_ylabel('Completion rate (%)')
style_axes(axes[0], grid_axis='y')

bars = axes[1].bar(x, delivered_summary['mean'].to_numpy(), width=0.72)
apply_hatches(bars, labels)
axes[1].errorbar(x, delivered_summary['mean'].to_numpy(), yerr=delivered_summary['ci95'].to_numpy(),
                 fmt='none', ecolor=EDGE_COLOR, elinewidth=0.7, capsize=2)
axes[1].set_xticks(x)
axes[1].set_xticklabels(labels)
axes[1].set_xlabel('Mechanism')
axes[1].set_ylabel('Delivered tasks')
style_axes(axes[1], grid_axis='y')
fig.tight_layout()
save_or_show(fig, ROOT, 'rq1_02_completion_rate_delivered_tasks.pdf')

expired_metric = first_existing_column(runs, ['expired', 'deadline_misses', 'deadline_miss_count', 'missed_deadlines'])
if expired_metric is None:
    raise ValueError('RQ1 runs.csv does not contain expired/deadline-miss information.')
expired_summary = metric_summary(runs, expired_metric, scale=1.0)
labels = expired_summary['coord_label'].astype(str).tolist()
x = np.arange(len(labels))
fig, ax = plt.subplots(figsize=SINGLE_FIGSIZE)
bars = ax.bar(x, expired_summary['mean'].to_numpy(), width=0.72)
apply_hatches(bars, labels)
if expired_summary['mean'].fillna(0).sum() == 0:
    ax.set_ylim(0, 1)
    ax.text(
        0.5, 0.82, 'No expired tasks observed',
        transform=ax.transAxes, ha='center', va='center', fontsize=8,
    )
else:
    ax.errorbar(x, expired_summary['mean'].to_numpy(), yerr=expired_summary['ci95'].to_numpy(),
                fmt='none', ecolor=EDGE_COLOR, elinewidth=0.7, capsize=2)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_xlabel('Mechanism')
ax.set_ylabel('Expired tasks / deadline misses')
style_axes(ax, grid_axis='y')
fig.tight_layout()
save_or_show(fig, ROOT, 'rq1_03_expired_tasks_deadline_misses.pdf')

median_latency_summary = metric_summary(runs, 'median_latency_s', scale=1 / 60)
efficiency_label = 'Comp./median latency'
efficiency_summary = metric_summary(runs, 'completion_latency_efficiency', scale=1.0)

rq1_table = pd.DataFrame({
    'Mechanism': latency_summary['coord_label'].astype(str),
    latency_label: latency_summary['mean'].round(2),
    'Median latency (min)': median_latency_summary['mean'].round(2),
    'Completion rate (%)': completion_summary['mean'].round(2),
    'Delivered tasks': delivered_summary['mean'].round().astype(int),
    'Expired/deadline misses': expired_summary['mean'].round().astype(int),
    efficiency_label: efficiency_summary['mean'].round(2),
})
display(rq1_table)

FACET_GRID_FIGSIZE = (6.8, 5.0)
FACET_GRID_WIDE_FIGSIZE = (7.4, 5.0)


def _as_numeric_label(value):
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f'{number:g}'


def _metric_summary_for_panel(frame, metric, scale=1.0):
    if frame.empty:
        return pd.DataFrame(columns=['coord_label', 'mean', 'ci95', 'count'])
    grouped = frame.groupby('coord_label', observed=False)[metric]
    summary = grouped.agg(['mean', 'std', 'count']).reindex(COORD_ORDER).dropna(subset=['mean']).reset_index()
    summary['mean'] = summary['mean'] * scale
    summary['ci95'] = 1.96 * summary['std'].fillna(0.0) / np.sqrt(summary['count'].clip(lower=1)) * scale
    return summary


def plot_metric_facets(
    frame,
    *,
    metric,
    ylabel,
    filename,
    row_var,
    col_var,
    row_values,
    col_values,
    row_labeler,
    col_labeler,
    scale=1.0,
    figsize=FACET_GRID_FIGSIZE,
):
    fig, axes = plt.subplots(
        len(row_values), len(col_values),
        figsize=figsize,
        sharey=True,
        squeeze=False,
    )
    max_y = 0.0
    panel_summaries = {}
    for row_value in row_values:
        for col_value in col_values:
            panel = frame[(frame[row_var] == row_value) & (frame[col_var] == col_value)].copy()
            summary = _metric_summary_for_panel(panel, metric, scale=scale)
            panel_summaries[(row_value, col_value)] = summary
            if not summary.empty:
                max_y = max(max_y, (summary['mean'] + summary['ci95']).max())

    for row_idx, row_value in enumerate(row_values):
        for col_idx, col_value in enumerate(col_values):
            ax = axes[row_idx, col_idx]
            summary = panel_summaries[(row_value, col_value)]
            labels = summary['coord_label'].astype(str).tolist() if not summary.empty else []
            x = np.arange(len(labels))
            if labels:
                bars = ax.bar(x, summary['mean'].to_numpy(), width=0.72)
                apply_hatches(bars, labels)
                ax.errorbar(
                    x,
                    summary['mean'].to_numpy(),
                    yerr=summary['ci95'].to_numpy(),
                    fmt='none',
                    ecolor=EDGE_COLOR,
                    elinewidth=0.6,
                    capsize=1.8,
                )
            else:
                ax.text(0.5, 0.5, 'No data', transform=ax.transAxes, ha='center', va='center', fontsize=7)
            ax.set_xticks(x)
            if row_idx == len(row_values) - 1:
                ax.set_xticklabels(labels)
                ax.set_xlabel('Mechanism')
            else:
                ax.set_xticklabels([])
            if col_idx == 0:
                ax.set_ylabel(ylabel)
                ax.text(
                    -0.52, 0.5, row_labeler(row_value),
                    transform=ax.transAxes,
                    rotation=90,
                    ha='center', va='center',
                    fontsize=8,
                )
            if row_idx == 0:
                ax.set_title(col_labeler(col_value), fontsize=8)
            style_axes(ax, grid_axis='y')
            if max_y > 0:
                ax.set_ylim(0, max_y * 1.12)
    fig.subplots_adjust(left=0.13, right=0.99, top=0.92, bottom=0.10, wspace=0.14, hspace=0.18)
    save_or_show(fig, ROOT, filename)


workload_values = sorted(runs['item_spawning_time'].dropna().unique())
agent_values = sorted(runs['n_robots'].dropna().unique())
fault_values = sorted(runs['fail_prob'].dropna().unique())
malicious_values = sorted(runs['malicious_ratio'].dropna().unique())

workload_label = lambda value: f'$T_{{spawn}}={int(value)}$ s'
agent_count_label = lambda value: f'$N_{{agent}}={int(value)}$'
fault_label = lambda value: f'$p_{{fail}}={_as_numeric_label(value)}$'
malicious_label = lambda value: f'$r_{{mal}}={_as_numeric_label(float(value) * 100)}\\%$'

rq1_granular_metrics = [
    ('completion_rate', 'Completion rate (%)', 100.0, 'completion'),
    (latency_metric, latency_label, 1 / 3600, 'latency'),
    (expired_metric, 'Expired tasks / deadline misses', 1.0, 'expired'),
]

workload_agent_files = {
    'completion': 'rq1_06_completion_by_workload_agents.pdf',
    'latency': 'rq1_07_latency_by_workload_agents.pdf',
    'expired': 'rq1_08_expired_by_workload_agents.pdf',
}
fault_malicious_files = {
    'completion': 'rq1_10_completion_by_fault_malicious.pdf',
    'latency': 'rq1_11_latency_by_fault_malicious.pdf',
    'expired': 'rq1_12_expired_by_fault_malicious.pdf',
}

for metric, ylabel, scale, slug in rq1_granular_metrics:
    plot_metric_facets(
        runs,
        metric=metric,
        ylabel=ylabel,
        filename=workload_agent_files[slug],
        row_var='item_spawning_time',
        col_var='n_robots',
        row_values=workload_values,
        col_values=agent_values,
        row_labeler=workload_label,
        col_labeler=agent_count_label,
        scale=scale,
        figsize=FACET_GRID_FIGSIZE,
    )

for metric, ylabel, scale, slug in rq1_granular_metrics:
    plot_metric_facets(
        runs,
        metric=metric,
        ylabel=ylabel,
        filename=fault_malicious_files[slug],
        row_var='fail_prob',
        col_var='malicious_ratio',
        row_values=fault_values,
        col_values=malicious_values,
        row_labeler=fault_label,
        col_labeler=malicious_label,
        scale=scale,
        figsize=FACET_GRID_WIDE_FIGSIZE,
    )

LINE_PANEL_FIGSIZE = (6.8, 2.25)
LINE_PANEL_WIDE_FIGSIZE = (7.4, 2.25)
LINE_STYLE_BY_COORD = {
    'FD': {'color': '#222222', 'linestyle': '-', 'marker': 'o', 'markerfacecolor': '#222222'},
    'SD': {'color': '#555555', 'linestyle': '--', 'marker': 's', 'markerfacecolor': '#555555'},
    'CE': {'color': '#888888', 'linestyle': ':', 'marker': '^', 'markerfacecolor': '#888888'},
    'DA': {'color': '#222222', 'linestyle': '-.', 'marker': 'D', 'markerfacecolor': 'white'},
}
RQ1_NOMINAL = {
    'item_spawning_time': 120,
    'n_robots': 20,
    'fail_prob': 0.66,
    'malicious_ratio': 0.33,
}


def _series_matches_value(series, value):
    if pd.api.types.is_numeric_dtype(series):
        return np.isclose(pd.to_numeric(series, errors='coerce'), float(value))
    return series.astype(str) == str(value)


def _filter_rq1_nominal(frame, filters):
    filtered = frame.copy()
    for column, value in filters.items():
        if column not in filtered.columns:
            continue
        filtered = filtered.loc[_series_matches_value(filtered[column], value)].copy()
    return filtered


def _rq1_line_summary(frame, metric, x_var, panel_var, scale=1.0):
    summary = (
        frame.groupby([panel_var, x_var, 'coord_label'], observed=False)[metric]
        .agg(['mean', 'std', 'count'])
        .reset_index()
    )
    summary['mean'] = summary['mean'] * scale
    summary['ci95'] = 1.96 * summary['std'].fillna(0.0) / np.sqrt(summary['count'].clip(lower=1)) * scale
    return summary


def _line_axis_labels(values, formatter=None):
    if formatter is None:
        return [_as_numeric_label(value) for value in values]
    return [formatter(value) for value in values]


def plot_rq1_line_panels(
    frame,
    *,
    metric,
    ylabel,
    filename,
    x_var,
    panel_var,
    x_values,
    panel_values,
    x_label,
    panel_labeler,
    filters,
    scale=1.0,
    figsize=LINE_PANEL_FIGSIZE,
    x_formatter=None,
):
    plot_frame = _filter_rq1_nominal(frame, filters)
    summary = _rq1_line_summary(plot_frame, metric, x_var, panel_var, scale=scale)
    fig, axes = plt.subplots(1, len(panel_values), figsize=figsize, sharey=True, squeeze=False)
    axes = axes[0]
    y_max = 0.0
    y_min = 0.0
    line_handles = []

    for panel_value in panel_values:
        panel_summary = summary[np.isclose(pd.to_numeric(summary[panel_var], errors='coerce'), float(panel_value))]
        if not panel_summary.empty:
            y_max = max(y_max, (panel_summary['mean'] + panel_summary['ci95']).max())
            y_min = min(y_min, (panel_summary['mean'] - panel_summary['ci95']).min())

    for panel_idx, (ax, panel_value) in enumerate(zip(axes, panel_values)):
        for coord in COORD_ORDER:
            coord_panel = summary[
                np.isclose(pd.to_numeric(summary[panel_var], errors='coerce'), float(panel_value))
                & (summary['coord_label'].astype(str) == coord)
            ].copy()
            if coord_panel.empty:
                continue
            coord_panel = coord_panel.set_index(x_var).reindex(x_values)
            y = coord_panel['mean'].to_numpy(dtype=float)
            ci = coord_panel['ci95'].fillna(0.0).to_numpy(dtype=float)
            x = np.asarray(x_values, dtype=float)
            style = LINE_STYLE_BY_COORD.get(coord, LINE_STYLE_BY_COORD['FD'])
            line, = ax.plot(
                x,
                y,
                color=style['color'],
                linestyle=style['linestyle'],
                linewidth=0.9,
                marker=style['marker'],
                markersize=3.0,
                markerfacecolor=style['markerfacecolor'],
                markeredgecolor=EDGE_COLOR,
                markeredgewidth=0.4,
                label=coord,
            )
            ax.fill_between(
                x,
                y - ci,
                y + ci,
                color=style['color'],
                alpha=0.10,
                linewidth=0,
            )
            if panel_idx == 0:
                line_handles.append(line)
        ax.set_title(panel_labeler(panel_value), fontsize=8)
        ax.set_xlabel(x_label)
        ax.set_xticks(x_values)
        ax.set_xticklabels(_line_axis_labels(x_values, x_formatter))
        if panel_idx == 0:
            ax.set_ylabel(ylabel)
        style_axes(ax, grid_axis='y')
        if y_max > y_min:
            lower = 0 if y_min >= 0 else y_min * 1.08
            ax.set_ylim(lower, y_max * 1.08)
    fig.legend(handles=line_handles, loc='upper center', ncol=len(line_handles), frameon=False)
    fig.subplots_adjust(left=0.10, right=0.99, top=0.78, bottom=0.24, wspace=0.18)
    save_or_show(fig, ROOT, filename)


percent_label = lambda value: f'{_as_numeric_label(float(value) * 100)}'
prob_label = lambda value: _as_numeric_label(value)

plot_rq1_line_panels(
    runs,
    metric=latency_metric,
    ylabel=latency_label,
    filename='rq1_line_latency_vs_workload_by_agents.pdf',
    x_var='item_spawning_time',
    panel_var='n_robots',
    x_values=workload_values,
    panel_values=agent_values,
    x_label='$T_{spawn}$ (s)',
    panel_labeler=agent_count_label,
    filters={
        'fail_prob': RQ1_NOMINAL['fail_prob'],
        'malicious_ratio': RQ1_NOMINAL['malicious_ratio'],
    },
    scale=1 / 3600,
    figsize=LINE_PANEL_FIGSIZE,
)

plot_rq1_line_panels(
    runs,
    metric=latency_metric,
    ylabel=latency_label,
    filename='rq1_line_latency_vs_malicious_by_failure.pdf',
    x_var='malicious_ratio',
    panel_var='fail_prob',
    x_values=malicious_values,
    panel_values=fault_values,
    x_label='$r_{mal}$ (%)',
    panel_labeler=fault_label,
    filters={
        'item_spawning_time': RQ1_NOMINAL['item_spawning_time'],
        'n_robots': RQ1_NOMINAL['n_robots'],
    },
    scale=1 / 3600,
    figsize=LINE_PANEL_FIGSIZE,
    x_formatter=percent_label,
)

plot_rq1_line_panels(
    runs,
    metric=latency_metric,
    ylabel=latency_label,
    filename='rq1_line_latency_vs_failure_by_maliciousness.pdf',
    x_var='fail_prob',
    panel_var='malicious_ratio',
    x_values=fault_values,
    panel_values=malicious_values,
    x_label='$p_{fail}$',
    panel_labeler=malicious_label,
    filters={
        'item_spawning_time': RQ1_NOMINAL['item_spawning_time'],
        'n_robots': RQ1_NOMINAL['n_robots'],
    },
    scale=1 / 3600,
    figsize=LINE_PANEL_WIDE_FIGSIZE,
    x_formatter=prob_label,
)

plot_rq1_line_panels(
    runs,
    metric='completion_latency_efficiency',
    ylabel=efficiency_label,
    filename='rq1_14_efficiency_vs_workload_by_agents.pdf',
    x_var='item_spawning_time',
    panel_var='n_robots',
    x_values=workload_values,
    panel_values=agent_values,
    x_label='$T_{spawn}$ (s)',
    panel_labeler=agent_count_label,
    filters={},
    scale=1.0,
    figsize=LINE_PANEL_FIGSIZE,
)

plot_rq1_line_panels(
    runs,
    metric='completion_latency_efficiency',
    ylabel=efficiency_label,
    filename='rq1_15_efficiency_vs_malicious_by_failure.pdf',
    x_var='malicious_ratio',
    panel_var='fail_prob',
    x_values=malicious_values,
    panel_values=fault_values,
    x_label='$r_{mal}$ (%)',
    panel_labeler=fault_label,
    filters={},
    scale=1.0,
    figsize=LINE_PANEL_FIGSIZE,
    x_formatter=percent_label,
)
