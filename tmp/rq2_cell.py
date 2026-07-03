from pathlib import Path
from itertools import product

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
from matplotlib.lines import Line2D

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
WIDE_FIGSIZE = (6.4, 2.2)
MULTIPANEL_FIGSIZE = (6.4, 4.2)
COORD_ORDER = ['FD', 'SD', 'CE', 'DA']
COORD_COLORS = {'FD': '#666666', 'SD': '#999999', 'CE': '#b3b3b3', 'DA': '#ffffff'}
COORD_HATCHES = {'FD': '', 'SD': '', 'CE': '', 'DA': 'ooo'}
EDGE_COLOR = '#222222'
GRID_COLOR = '#bdbdbd'
LINE_COLORS = ['#222222', '#555555', '#888888', '#b3b3b3', '#d0d0d0']
LINE_STYLES = ['-', '--', ':', '-.']
MARKERS = ['o', 's', '^', 'D', 'v']
SECONDS_PER_DAY = 24 * 3600
TIMELINE_FIGSIZE = (6.4, 3.1)
SWITCH_COLORS = {'CE': '#1f77b4', 'SD': '#ff7f0e', 'FD': '#2ca02c'}
SWITCH_MARKERS = {'CE': 'o', 'SD': 's', 'FD': '^'}


def architecture_to_label(value):
    text = str(value).lower()
    if 'semi' in text:
        return 'SD'
    if 'decentral' in text:
        return 'FD'
    if 'central' in text:
        return 'CE'
    return str(value)



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


def plot_coord_bars(ax, labels, values, width=0.72):
    labels = [str(label) for label in labels]
    x = np.arange(len(labels))
    bars = ax.bar(x, values, width=width)
    apply_hatches(bars, labels)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    style_axes(ax, grid_axis='y')
    return bars


def style_pandas_bar_containers(ax, labels):
    for container, label in zip(ax.containers, labels):
        for patch in container.patches:
            patch.set_facecolor(coord_color(label))
            patch.set_edgecolor(EDGE_COLOR)
            patch.set_linewidth(0.5)
            patch.set_hatch(coord_hatch(label))
    style_axes(ax, grid_axis='y')


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

ROOT = find_results_root(required_all=[Path('RQ2/runs.csv'), Path('RQ2/switch_timeline.csv')])
rq2 = ROOT / 'RQ2'
runs = pd.read_csv(rq2 / 'runs.csv')
switches = pd.read_csv(rq2 / 'switch_timeline.csv')

if 'status' in runs.columns:
    runs = runs[runs['status'].fillna('ok').astype(str).str.lower() == 'ok'].copy()
else:
    runs = runs.copy()
runs = filter_task_expiration_configured(runs, 'RQ2 runs.csv')
switches = filter_task_expiration_configured(switches, 'RQ2 switch_timeline.csv', required=False)
if 'run_id' in switches.columns and 'run_id' in runs.columns:
    switches = switches[switches['run_id'].astype(str).isin(set(runs['run_id'].astype(str)))].copy()

def numeric(frame, columns):
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors='coerce')
    return frame


for frame in [runs, switches]:
    numeric(frame, [
        'rep', 'switch_count', 'fd_switch_count', 'sd_switch_count', 'ce_switch_count',
        'first_switch_time', 'performance_score', 'latency', 'pending_ratio',
        'failure_rate', 'message_loss_rate', 'switch_idx', 'sim_time', 'sim_day', 'sim_hour',
    ])

profile_order = ['paper_daily_stress', 'communication_blackout', 'malicious_surge', 'load_fault_recovery']
profile_labels = {
    'paper_daily_stress': 'Daily fault windows',
    'communication_blackout': 'Communication degradation',
    'malicious_surge': 'Malicious-agent surge',
    'load_fault_recovery': 'Load/failure recovery',
}
phase_groups = {
    'normal': 'Nominal',
    'calm': 'Nominal',
    'paper_stress': 'Fault window',
    'comm_blackout': 'Fault window',
    'malicious_surge': 'Fault window',
    'load_fault_stress': 'Fault window',
    'recovery': 'Recovery',
}
mechanism_order = ['FD', 'SD', 'CE']
phase_order = ['Nominal', 'Fault window', 'Recovery']
phase_colors = {'Nominal': '#b3b3b3', 'Fault window': '#4d4d4d', 'Recovery': '#808080'}
phase_hatches = {'Nominal': '', 'Fault window': '', 'Recovery': '///'}

runs = runs[runs['profile'].isin(profile_order)].copy()
switches = switches[switches['profile'].isin(profile_order)].copy()
runs['profile'] = pd.Categorical(runs['profile'], categories=profile_order, ordered=True)
switches['profile'] = pd.Categorical(switches['profile'], categories=profile_order, ordered=True)

run_counts = runs.groupby('profile', observed=False)['run_id'].nunique().reindex(profile_order).replace(0, np.nan)
mech_counts = switches.pivot_table(
    index='profile', columns='selected_coord_label', values='switch_idx', aggfunc='count', fill_value=0, observed=False,
).reindex(index=profile_order, columns=mechanism_order, fill_value=0)
mech_per_run = mech_counts.div(run_counts, axis=0)

switches['phase_group'] = switches['phase_label'].map(phase_groups).fillna('Other')
phase_counts = switches.pivot_table(
    index='profile', columns='phase_group', values='switch_idx', aggfunc='count', fill_value=0, observed=False,
).reindex(index=profile_order, columns=phase_order, fill_value=0)
phase_per_run = phase_counts.div(run_counts, axis=0)

profile_summary = runs.groupby('profile', observed=False).agg(
    switches_per_run=('switch_count', 'mean'),
    first_switch_h=('first_switch_time', lambda values: values.mean() / 3600),
).reindex(profile_order)
score_at_switch = switches.groupby('profile', observed=False)['performance_score'].mean().reindex(profile_order)

rq2_table = pd.DataFrame({
    'Profile': [profile_labels[p] for p in profile_order],
    'Switches/run': profile_summary['switches_per_run'].round(1).to_numpy(),
    'First switch (h)': profile_summary['first_switch_h'].round(2).to_numpy(),
    'Score at switch': score_at_switch.round(2).to_numpy(),
    'FD switches/run': mech_per_run['FD'].round(1).to_numpy(),
    'SD switches/run': mech_per_run['SD'].round(1).to_numpy(),
    'CE switches/run': mech_per_run['CE'].round(1).to_numpy(),
})

fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.55))
x = np.arange(len(profile_order))
labels = [profile_labels[p] for p in profile_order]

bottom = np.zeros(len(profile_order))
for mechanism in mechanism_order:
    values = mech_per_run[mechanism].fillna(0).to_numpy()
    bars = axes[0].bar(x, values, bottom=bottom, width=0.72, label=mechanism)
    apply_hatches(bars, [mechanism] * len(values))
    bottom += values
axes[0].set_xticks(x)
axes[0].set_xticklabels(labels, rotation=25, ha='right')
axes[0].set_ylabel('Switches/run')
style_axes(axes[0], grid_axis='y')
axes[0].legend(frameon=False, fontsize=7, ncol=3)

bottom = np.zeros(len(profile_order))
for phase in phase_order:
    values = phase_per_run[phase].fillna(0).to_numpy()
    bars = axes[1].bar(x, values, bottom=bottom, width=0.72, label=phase)
    for bar in bars:
        bar.set_facecolor(phase_colors[phase])
        bar.set_edgecolor(EDGE_COLOR)
        bar.set_linewidth(0.5)
        bar.set_hatch(phase_hatches[phase])
    bottom += values
axes[1].set_xticks(x)
axes[1].set_xticklabels(labels, rotation=25, ha='right')
axes[1].set_ylabel('Switches/run')
style_axes(axes[1], grid_axis='y')
axes[1].legend(frameon=False, fontsize=7, ncol=3)

fig.tight_layout()
save_or_show(fig, ROOT, 'rq2_dynamic_reaction.pdf')

phase_detail_groups = {
    'normal': 'Nominal',
    'nominal': 'Nominal',
    'baseline': 'Nominal',
    'calm': 'Nominal',
    'comm_blackout': 'Communication degradation',
    'load_fault_stress': 'Load/failure window',
    'load_failure_surge': 'Load/failure window',
    'malicious_surge': 'Malicious-agent surge',
    'recovery': 'Recovery',
}
phase_detail_order = ['Nominal', 'Communication degradation', 'Load/failure window', 'Malicious-agent surge', 'Recovery']
switches['phase_detail'] = switches['phase_label'].map(phase_detail_groups).fillna(switches['phase_label'].astype(str))
phase_selection = pd.crosstab(switches['phase_detail'], switches['selected_coord_label']).reindex(
    index=phase_detail_order, columns=mechanism_order, fill_value=0,
)
phase_selection_pct = phase_selection.div(phase_selection.sum(axis=1).replace(0, np.nan), axis=0) * 100

fig, ax = plt.subplots(figsize=(6.4, 2.35))
x = np.arange(len(phase_detail_order))
bottom = np.zeros(len(phase_detail_order))
for mechanism in mechanism_order:
    values = phase_selection_pct[mechanism].fillna(0).to_numpy()
    bars = ax.bar(x, values, bottom=bottom, width=0.72, label=mechanism)
    apply_hatches(bars, [mechanism] * len(values))
    bottom += values
ax.set_xticks(x)
ax.set_xticklabels(phase_detail_order, rotation=18, ha='right')
ax.set_ylabel('Switches (%)')
ax.set_ylim(0, 100)
style_axes(ax, grid_axis='y')
ax.legend(frameon=False, fontsize=7, ncol=3, loc='upper center', bbox_to_anchor=(0.5, 1.18))
fig.tight_layout()
save_or_show(fig, ROOT, 'rq2_switch_selection_by_phase.pdf')

recovery_mask = switches['recovery_mode'].astype(str).str.lower().eq('true')
fd_pressure_mask = switches['fd_pressure'].astype(str).str.lower().eq('true')
state_series = switches['performance_state'].astype(str)
context_specs = [
    ('Recovery mode', recovery_mask),
    ('FD pressure', (~recovery_mask) & fd_pressure_mask),
    ('Stable state', (~recovery_mask) & (~fd_pressure_mask) & state_series.eq('stable')),
    ('Degraded/critical without FD pressure', (~recovery_mask) & (~fd_pressure_mask) & (~state_series.eq('stable'))),
]
context_rows = []
for context_label, mask in context_specs:
    group = switches.loc[mask].copy()
    if group.empty:
        continue
    selected_counts = group['selected_coord_label'].value_counts()
    dominant_mechanism = selected_counts.idxmax()
    dominant_share = 100 * selected_counts.max() / len(group)
    context_rows.append({
        'Adaptation context': context_label,
        'Switches': int(len(group)),
        'Share (%)': round(100 * len(group) / max(1, len(switches)), 1),
        'Selected mech.': f'{dominant_mechanism} ({dominant_share:.1f}%)',
        'Median pending ratio': round(group['pending_ratio'].median(), 2),
        'Median failure rate': round(group['failure_rate'].median(), 2),
        'Median msg. loss': round(group['message_loss_rate'].median(), 3),
        'Median score': round(group['performance_score'].median(), 2),
    })
rq2_context_table = pd.DataFrame(context_rows)

timeline_path = rq2 / 'adaptation_state_timeseries.csv.gz'
phase_path = rq2 / 'phase_schedule.csv'
if timeline_path.exists() and phase_path.exists():
    timeline = pd.read_csv(timeline_path)
    phases = pd.read_csv(phase_path)
    timeline = filter_task_expiration_configured(timeline, 'RQ2 adaptation_state_timeseries.csv.gz', required=False)
    if 'run_id' in phases.columns and 'run_id' in timeline.columns:
        phases = phases[phases['run_id'].astype(str).isin(set(timeline['run_id'].astype(str)))].copy()
    timeline = numeric(timeline, [
        'sim_time', 'latency', 'raw_latency', 'pending_tasks', 'sim_day',
        'phase_fail_prob', 'phase_msg_loss', 'phase_n_malicious',
    ])
    phases = numeric(phases, ['start', 'end', 'FAIL_PROB', 'COMM_FAIL_PROB', 'N_MALICIOUS'])

    candidate_runs = timeline.copy()
    if 'profile' in candidate_runs.columns:
        preferred = candidate_runs[candidate_runs['profile'].astype(str) == 'paper_daily_stress']
        if not preferred.empty:
            candidate_runs = preferred
    switched_flag = candidate_runs['switched'].astype(str).str.lower().eq('true')
    switch_counts = candidate_runs.assign(_switched=switched_flag).groupby('run_id')['_switched'].sum()
    selected_run = switch_counts.sort_values(ascending=False).index[0]

    trace_all = timeline[timeline['run_id'] == selected_run].copy().sort_values('sim_time')
    phase_trace_all = phases[phases['run_id'] == selected_run].copy().sort_values('start')
    latency_column = 'latency' if trace_all['latency'].notna().any() else 'raw_latency'

    phase_shades = {
        'load_failure_surge': '#d9d9d9',
        'load_fault_stress': '#d9d9d9',
        'comm_blackout': '#bdbdbd',
        'malicious_surge': '#a6a6a6',
        'recovery': '#eeeeee',
    }

    def plot_da_timeline_window(start_day, window_days, filename):
        start_time = (start_day - 1) * SECONDS_PER_DAY
        end_time = start_time + window_days * SECONDS_PER_DAY
        trace = trace_all[(trace_all['sim_time'] >= start_time) & (trace_all['sim_time'] <= end_time)].copy()
        phase_trace = phase_trace_all[(phase_trace_all['end'] >= start_time) & (phase_trace_all['start'] <= end_time)].copy()
        if trace.empty:
            return
        phase_trace['plot_start'] = phase_trace['start'].clip(lower=start_time, upper=end_time) / SECONDS_PER_DAY + 1
        phase_trace['plot_end'] = phase_trace['end'].clip(lower=start_time, upper=end_time) / SECONDS_PER_DAY + 1
        trace['latency_h'] = trace[latency_column].rolling(window=5, min_periods=1).mean() / 3600
        trace['pending_smooth'] = trace['pending_tasks'].rolling(window=5, min_periods=1).mean()
        trace['sim_day_axis'] = trace['sim_time'] / SECONDS_PER_DAY + 1

        fig, (ax_windows, ax_perf) = plt.subplots(
            2, 1, figsize=TIMELINE_FIGSIZE, sharex=True,
            gridspec_kw={'height_ratios': [0.35, 1.0], 'hspace': 0.08},
        )

        for _, phase in phase_trace.iterrows():
            label = str(phase.get('phase_label', '')).lower()
            shade = phase_shades.get(label)
            if shade:
                ax_windows.axvspan(
                    phase['plot_start'], phase['plot_end'],
                    color=shade, alpha=0.85, linewidth=0,
                )
        ax_windows.set_ylim(0, 1)
        ax_windows.set_yticks([])
        ax_windows.set_ylabel('Dynamic\nphases')
        ax_windows.spines['top'].set_visible(False)
        ax_windows.spines['right'].set_visible(False)
        ax_windows.spines['left'].set_visible(False)

        ax_perf.plot(trace['sim_day_axis'], trace['latency_h'], color='#222222', linewidth=1.0,
                     label='Latency')
        ax_perf.set_ylabel('Latency (h)')
        style_axes(ax_perf, grid_axis='y')

        ax_backlog = ax_perf.twinx()
        ax_backlog.plot(trace['sim_day_axis'], trace['pending_smooth'], color='#777777', linewidth=1.0,
                        linestyle='--', label='Backlog')
        ax_backlog.set_ylabel('Pending tasks')
        ax_backlog.spines['top'].set_visible(False)

        switch_trace = trace[trace['switched'].astype(str).str.lower().eq('true')].copy()
        seen_switch_labels = set()
        for _, switch in switch_trace.iterrows():
            selected = architecture_to_label(switch.get('selected_architecture', ''))
            x_value = switch['sim_day_axis']
            ax_perf.axvline(x_value, color=SWITCH_COLORS.get(selected, '#444444'),
                            linestyle=':', linewidth=0.8, alpha=0.85)
            ax_windows.scatter(
                [x_value], [0.5], s=20, marker=SWITCH_MARKERS.get(selected, 'o'),
                facecolor=SWITCH_COLORS.get(selected, '#444444'), edgecolor=EDGE_COLOR,
                linewidth=0.4, zorder=3,
            )
            seen_switch_labels.add(selected)

        line_handles = [
            Line2D([0], [0], color='#222222', lw=1.0, label='Latency'),
            Line2D([0], [0], color='#777777', lw=1.0, linestyle='--', label='Backlog'),
        ]
        switch_handles = [
            Line2D([0], [0], color=SWITCH_COLORS[label], marker=SWITCH_MARKERS[label],
                   linestyle=':', lw=0.8, markersize=4, label=f'Switch to {label}')
            for label in ['CE', 'SD', 'FD'] if label in seen_switch_labels
        ]
        ax_perf.legend(handles=line_handles + switch_handles, loc='upper left', ncol=2, frameon=False)
        ax_perf.set_xlabel('Simulation day')
        x_min = start_time / SECONDS_PER_DAY + 1
        x_max = end_time / SECONDS_PER_DAY + 1
        ax_perf.set_xlim(x_min, x_max)
        tick_step = 1 if window_days <= 7 else 3
        ax_perf.set_xticks(np.arange(x_min, x_max + 0.1, tick_step))
        fig.subplots_adjust(left=0.10, right=0.88, top=0.96, bottom=0.16, hspace=0.08)
        save_or_show(fig, ROOT, filename)

    plot_da_timeline_window(8, 7, 'rq2_da_intermediate_timeline_7d.pdf')
    plot_da_timeline_window(8, 15, 'rq2_da_intermediate_timeline_15d.pdf')

display(rq2_table)
display(rq2_context_table)