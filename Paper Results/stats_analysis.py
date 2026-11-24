#!/usr/bin/env python3
"""Statistical analysis of repeated (10x) COORDINATE 2.0 campaigns.

Addresses the statistical comments of the TII reviews (R1.5, R1.12, R2.3,
R3.5, R3.6): every mean comes with a 95% confidence interval, every DA
comparison is paired by seed and tested, multiple comparisons are corrected,
effect sizes are reported, and the headline numbers are defined explicitly
(absolute difference / percentage points and relative %, averaged over
configurations) with a two-stage bootstrap CI.

Design assumed (as produced by the runners): for each configuration and each
repetition r, all mechanisms share the same seed, so DA and a baseline form a
pair (config, r).

Outputs in --out:
  descriptive.csv     n, mean, sd, median, 95% t-CI per configuration x mechanism x metric
  paired.csv          DA vs CE / SD / FD / best-static / per-seed oracle, per configuration:
                      mean difference + 95% CI, relative %, Wilcoxon signed-rank and paired t
                      p-values, Holm and Benjamini-Hochberg adjusted, Cohen's dz, Vargha-Delaney A12
  friedman.csv        Friedman test across all mechanisms per configuration (+ Kendall's W)
  headline.csv        aggregate over configurations (and per analysis slice), two-stage bootstrap CI,
                      win / tie / loss counts and a global Wilcoxon test over configurations
  da_worse.csv        configurations in which DA is significantly worse (R1.5)
  headline.tex        LaTeX table of the headline comparison
  report.md           summary + a methods paragraph ready to adapt for the paper

Examples:
  python "Paper Results/stats_analysis.py" --rq RQ1
  python "Paper Results/stats_analysis.py" --rq RQ1 --runs "Paper Results/leonardo_10x/RQ1/runs.csv" \
         --out "Paper Results/leonardo_10x/stats/RQ1"
"""

from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PAPER_ROOT = Path(__file__).resolve().parent

# metric -> (direction, label, scale). direction +1: higher is better; -1: lower is better.
METRICS = {
    "RQ1": {
        "completion_rate": (+1, "Completion rate (%)", 100.0),
        "expiration_rate": (-1, "Expiration rate (%)", 100.0),
        "avg_relative_latency_s": (-1, "Relative latency (min)", 1 / 60),
        "avg_latency_s": (-1, "Latency (min)", 1 / 60),
        "p95_latency_s": (-1, "P95 latency (min)", 1 / 60),
        "throughput_per_hour": (+1, "Throughput (tasks/h)", 1.0),
        "pending": (-1, "Pending at end (tasks)", 1.0),
    },
    "RQ3": {
        "wall_time_s": (-1, "Wall time (s)", 1.0),
        "adapt_overhead_wall_pct": (-1, "Adaptation overhead (% wall)", 1.0),
        "adapt_overhead_ms_mean": (-1, "Overhead per check (ms)", 1.0),
        "event_count": (-1, "Events", 1.0),
        "completion_rate": (+1, "Completion rate (%)", 100.0),
    },
    "RQ4": {
        "wall_time_s": (-1, "Wall time (s)", 1.0),
        "max_rss_mb": (-1, "Peak memory (MB)", 1.0),
        "events_per_wall_s": (+1, "Events per second", 1.0),
        "total_output_size_mb": (-1, "Output size (MB)", 1.0),
    },
    "RQ2": {
        "completion_rate": (+1, "Completion rate (%)", 100.0),
        "expiration_rate": (-1, "Expiration rate (%)", 100.0),
        "avg_latency_s": (-1, "Latency (min)", 1 / 60),
        "switch_count": (0, "Switches", 1.0),
        "adapt_overhead_ms_mean": (-1, "Overhead per check (ms)", 1.0),
    },
}
METRICS["RQ1"]["switch_count"] = (0, "Switches (DA)", 1.0)

CONFIG_KEYS = {
    "RQ1": ["topology", "n_rooms", "item_spawning_time", "n_robots", "n_malicious", "fail_prob", "msg_loss"],
    "RQ3": ["topology", "n_rooms", "item_spawning_time", "n_robots", "malicious_ratio", "fail_prob",
            "msg_loss_prob", "comp_time", "comm_time", "sim_days"],
    "RQ4": ["machine_label", "topology", "n_rooms", "item_spawning_time", "n_robots", "malicious_ratio",
            "fail_prob", "msg_loss_prob", "sim_days"],
    "RQ2": ["profile"],
}


# --------------------------------------------------------------------------- helpers

def t_ci(values: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    values = values[~np.isnan(values)]
    n = len(values)
    if n < 2:
        return (math.nan, math.nan)
    m = values.mean()
    se = values.std(ddof=1) / math.sqrt(n)
    if se == 0:
        return (m, m)
    h = stats.t.ppf(0.5 + level / 2, n - 1) * se
    return (m - h, m + h)


def holm(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    out = np.full_like(p, np.nan)
    mask = ~np.isnan(p)
    pv = p[mask]
    m = len(pv)
    if m == 0:
        return out
    order = np.argsort(pv)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pv[idx])
        adj[idx] = min(1.0, running)
    out[mask] = adj
    return out


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    out = np.full_like(p, np.nan)
    mask = ~np.isnan(p)
    pv = p[mask]
    m = len(pv)
    if m == 0:
        return out
    order = np.argsort(pv)
    ranked = pv[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adj = np.empty(m)
    adj[order] = np.minimum(ranked, 1.0)
    out[mask] = adj
    return out


def a12(x: np.ndarray, y: np.ndarray) -> float:
    """Vargha-Delaney A12: P(X > Y) + 0.5 P(X = Y)."""
    x, y = x[~np.isnan(x)], y[~np.isnan(y)]
    if len(x) == 0 or len(y) == 0:
        return math.nan
    gt = (x[:, None] > y[None, :]).sum()
    eq = (x[:, None] == y[None, :]).sum()
    return (gt + 0.5 * eq) / (len(x) * len(y))


def a12_magnitude(a: float) -> str:
    if math.isnan(a):
        return ""
    d = abs(a - 0.5)
    if d < 0.06:
        return "negligible"
    if d < 0.14:
        return "small"
    if d < 0.21:
        return "medium"
    return "large"


def wilcoxon_p(d: np.ndarray) -> float:
    d = d[~np.isnan(d)]
    if len(d) < 2 or np.all(d == 0):
        return 1.0 if len(d) >= 2 else math.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return float(stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue)
        except ValueError:
            return math.nan


def paired_t_p(d: np.ndarray) -> float:
    d = d[~np.isnan(d)]
    if len(d) < 2:
        return math.nan
    if np.std(d, ddof=1) == 0:
        return 1.0 if np.mean(d) == 0 else 0.0
    return float(stats.ttest_1samp(d, 0.0).pvalue)


def fmt_config(row: pd.Series, keys: list[str]) -> str:
    return ", ".join(f"{k}={row[k]}" for k in keys)


# --------------------------------------------------------------------------- analysis

def load(args) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = pd.read_csv(args.runs, low_memory=False)
    if "status" in df.columns:
        df = df[df["status"].astype(str) == "ok"].copy()
    keys = [k for k in CONFIG_KEYS[args.rq] if k in df.columns]
    if "msg_loss" not in df.columns and "msg_loss_prob" in df.columns and args.rq == "RQ1":
        keys = [k if k != "msg_loss" else "msg_loss_prob" for k in keys]
    for k in keys:
        if df[k].dtype == float:
            df[k] = df[k].round(6)
    mechs = [m for m in args.mechanisms.split(",") if m in set(df["coord_label"])]
    df = df[df["coord_label"].isin(mechs)].copy()
    df["config_id"] = df.groupby(keys, dropna=False).ngroup() + 1
    return df, keys, mechs


def descriptive(df, keys, metrics):
    rows = []
    for (cfg, mech), g in df.groupby(["config_id", "coord_label"]):
        base = g.iloc[0]
        for metric, (_, label, scale) in metrics.items():
            if metric not in g.columns:
                continue
            v = pd.to_numeric(g[metric], errors="coerce").to_numpy(float) * scale
            v = v[~np.isnan(v)]
            if len(v) == 0:
                continue
            lo, hi = t_ci(v)
            rows.append({"config_id": cfg, **{k: base[k] for k in keys}, "coord_label": mech, "metric": metric,
                         "label": label, "n": len(v), "mean": v.mean(), "sd": v.std(ddof=1) if len(v) > 1 else math.nan,
                         "median": np.median(v), "ci95_low": lo, "ci95_high": hi})
    return pd.DataFrame(rows)


def pair_matrix(df, metric, mechs, scale):
    """Wide table indexed by (config_id, rep) with one column per mechanism."""
    w = df.pivot_table(index=["config_id", "rep"], columns="coord_label", values=metric, aggfunc="first")
    return w.reindex(columns=mechs) * scale


def check_pairing(df):
    if "seed" not in df.columns:
        return 0
    s = df.groupby(["config_id", "rep"])["seed"].nunique()
    return int((s > 1).sum())


def paired_analysis(df, keys, mechs, metrics, target, alpha):
    statics = [m for m in mechs if m != target]
    cfg_info = df.groupby("config_id").first()
    rows = []
    for metric, (direction, label, scale) in metrics.items():
        if direction == 0 or metric not in df.columns:
            continue
        w = pair_matrix(df, metric, mechs, scale)
        if target not in w.columns:
            continue
        # best static per configuration (by mean, in the metric's better direction)
        means = w[statics].groupby(level=0).mean()
        best = (means.idxmax(axis=1) if direction > 0 else means.idxmin(axis=1))
        # per-seed hindsight oracle among static mechanisms
        oracle = w[statics].max(axis=1) if direction > 0 else w[statics].min(axis=1)
        comparisons = {m: w[m] for m in statics}
        comparisons["best_static"] = pd.Series(
            [w.loc[idx, best.loc[idx[0]]] if pd.notna(best.loc[idx[0]]) else np.nan for idx in w.index], index=w.index)
        comparisons["oracle_static"] = oracle
        # Per-seed average of the static mechanisms: the reference implied by
        # averaging DA against all static mechanisms (as in the rejected draft).
        comparisons["mean_static"] = w[statics].mean(axis=1)
        for comp, base_series in comparisons.items():
            for cfg, g in w.groupby(level=0):
                x = g[target].to_numpy(float)
                y = base_series.loc[g.index].to_numpy(float)
                ok = ~np.isnan(x) & ~np.isnan(y)
                x, y = x[ok], y[ok]
                if len(x) == 0:
                    continue
                d = x - y
                lo, hi = t_ci(d)
                ymean = y.mean()
                sd = d.std(ddof=1) if len(d) > 1 else math.nan
                a = a12(x, y)
                rows.append({
                    "config_id": cfg, **{k: cfg_info.loc[cfg, k] for k in keys},
                    "analysis_slices": cfg_info.loc[cfg, "analysis_slices"] if "analysis_slices" in cfg_info.columns else "",
                    "metric": metric, "label": label, "direction": direction,
                    "comparison": f"{target}_vs_{comp}",
                    "baseline_used": best.loc[cfg] if comp == "best_static" else comp,
                    "n_pairs": len(d), "target_mean": x.mean(), "baseline_mean": ymean,
                    "mean_diff": d.mean(), "diff_ci95_low": lo, "diff_ci95_high": hi,
                    "rel_diff_pct": 100 * d.mean() / ymean if ymean not in (0, 0.0) else math.nan,
                    "improvement": direction * d.mean(),
                    "p_wilcoxon": wilcoxon_p(d), "p_ttest": paired_t_p(d),
                    "cohen_dz": d.mean() / sd if sd and sd > 0 else math.nan,
                    # A12 oriented so that > 0.5 means DA is better
                    "a12_target_better": a if direction > 0 else (1 - a if not math.isnan(a) else a),
                })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["a12_magnitude"] = out["a12_target_better"].map(a12_magnitude)
    # Families: one per (comparison, metric) across all configurations.
    for _, idx in out.groupby(["comparison", "metric"]).groups.items():
        out.loc[idx, "p_wilcoxon_holm"] = holm(out.loc[idx, "p_wilcoxon"].to_numpy())
        out.loc[idx, "p_wilcoxon_bh"] = bh(out.loc[idx, "p_wilcoxon"].to_numpy())
        out.loc[idx, "p_ttest_holm"] = holm(out.loc[idx, "p_ttest"].to_numpy())
        out.loc[idx, "p_ttest_bh"] = bh(out.loc[idx, "p_ttest"].to_numpy())

    def outcome(r):
        if pd.isna(r["p_wilcoxon_bh"]) or r["p_wilcoxon_bh"] >= alpha:
            return "tie"
        return "win" if r["improvement"] > 0 else "loss"

    out["outcome_bh"] = out.apply(outcome, axis=1)
    return out


def friedman(df, keys, mechs, metrics):
    rows = []
    cfg_info = df.groupby("config_id").first()
    for metric, (direction, label, scale) in metrics.items():
        if direction == 0 or metric not in df.columns:
            continue
        w = pair_matrix(df, metric, mechs, scale).dropna()
        for cfg, g in w.groupby(level=0):
            if len(g) < 3 or len(mechs) < 3:
                continue
            try:
                chi2, p = stats.friedmanchisquare(*[g[m].to_numpy() for m in mechs])
            except ValueError:
                chi2, p = math.nan, math.nan
            n, k = len(g), len(mechs)
            rows.append({"config_id": cfg, **{kk: cfg_info.loc[cfg, kk] for kk in keys}, "metric": metric,
                         "n_blocks": n, "chi2": chi2, "p": p,
                         "kendall_w": chi2 / (n * (k - 1)) if not math.isnan(chi2) else math.nan})
    out = pd.DataFrame(rows)
    if not out.empty:
        for _, idx in out.groupby("metric").groups.items():
            out.loc[idx, "p_bh"] = bh(out.loc[idx, "p"].to_numpy())
    return out


def two_stage_bootstrap(diff_lists, baseline_lists, n_boot, rng):
    """Resample configurations, then repetitions within each configuration.

    Returns bootstrap distributions of (mean absolute diff, mean relative diff %).
    """
    C = len(diff_lists)
    n_max = max(len(d) for d in diff_lists)
    D = np.full((C, n_max), np.nan)
    Y = np.full((C, n_max), np.nan)
    ns = np.array([len(d) for d in diff_lists])
    for i, (d, y) in enumerate(zip(diff_lists, baseline_lists)):
        D[i, : len(d)] = d
        Y[i, : len(y)] = y
    abs_b = np.empty(n_boot)
    rel_b = np.empty(n_boot)
    chunk = max(1, min(n_boot, int(2e7 // max(1, C * n_max))))
    for start in range(0, n_boot, chunk):
        b = min(chunk, n_boot - start)
        ci = rng.integers(0, C, size=(b, C))
        u = rng.random(size=(b, C, n_max))
        ri = np.floor(u * ns[ci][..., None]).astype(int)
        dd = D[ci[..., None], ri]
        yy = Y[ci[..., None], ri]
        valid = np.arange(n_max)[None, None, :] < ns[ci][..., None]
        dd = np.where(valid, dd, np.nan)
        yy = np.where(valid, yy, np.nan)
        dmean = np.nanmean(dd, axis=2).mean(axis=1)
        ymean = np.nanmean(yy, axis=2).mean(axis=1)
        abs_b[start:start + b] = dmean
        # Relative change = mean difference / mean baseline (ratio of means), which
        # stays stable when some configurations have baseline values close to zero.
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_b[start:start + b] = np.where(ymean != 0, 100 * dmean / ymean, np.nan)
    return abs_b, rel_b


def headline(df, paired, mechs, metrics, target, n_boot, seed):
    rng = np.random.default_rng(seed)
    statics = [m for m in mechs if m != target]
    rows = []
    slices = {"all": None}
    if "analysis_slices" in paired.columns:
        for s in sorted({x for v in paired["analysis_slices"].dropna() for x in str(v).split(",") if x}):
            slices[s] = s
    for metric, (direction, label, scale) in metrics.items():
        if direction == 0 or metric not in df.columns:
            continue
        w = pair_matrix(df, metric, mechs, scale)
        means = w[statics].groupby(level=0).mean()
        best = means.idxmax(axis=1) if direction > 0 else means.idxmin(axis=1)
        oracle = w[statics].max(axis=1) if direction > 0 else w[statics].min(axis=1)
        comp_series = {m: w[m] for m in statics}
        comp_series["best_static"] = pd.Series(
            [w.loc[i, best.loc[i[0]]] for i in w.index], index=w.index)
        comp_series["oracle_static"] = oracle
        comp_series["mean_static"] = w[statics].mean(axis=1)
        # "all static pooled": what the original paper averaged (R3.5)
        for comp, ser in comp_series.items():
            name = f"{target}_vs_{comp}"
            sub_all = paired[(paired["comparison"] == name) & (paired["metric"] == metric)]
            for slice_name, sl in slices.items():
                sub = sub_all if sl is None else sub_all[sub_all["analysis_slices"].astype(str).str.split(",").map(lambda xs: sl in xs)]
                if sub.empty:
                    continue
                diff_lists, base_lists = [], []
                for cfg in sub["config_id"]:
                    g = w.loc[cfg]
                    x = g[target].to_numpy(float)
                    y = ser.loc[cfg].to_numpy(float)
                    ok = ~np.isnan(x) & ~np.isnan(y)
                    diff_lists.append(x[ok] - y[ok])
                    base_lists.append(y[ok])
                abs_b, rel_b = two_stage_bootstrap(diff_lists, base_lists, n_boot, rng)
                cfg_means = sub["mean_diff"].to_numpy()
                p_global = wilcoxon_p(cfg_means) if len(cfg_means) >= 6 else math.nan
                rows.append({
                    "comparison": name, "metric": metric, "label": label, "direction": direction, "slice": slice_name,
                    "n_configs": len(sub), "pairs_per_config_min": int(sub["n_pairs"].min()),
                    "target_mean": sub["target_mean"].mean(), "baseline_mean": sub["baseline_mean"].mean(),
                    "mean_abs_diff": sub["mean_diff"].mean(),
                    "abs_diff_ci95_low": np.nanpercentile(abs_b, 2.5), "abs_diff_ci95_high": np.nanpercentile(abs_b, 97.5),
                    "mean_rel_diff_pct": 100 * sub["mean_diff"].mean() / sub["baseline_mean"].mean()
                    if sub["baseline_mean"].mean() else math.nan,
                    "rel_diff_ci95_low": np.nanpercentile(rel_b, 2.5), "rel_diff_ci95_high": np.nanpercentile(rel_b, 97.5),
                    "wins_bh": int((sub["outcome_bh"] == "win").sum()),
                    "ties_bh": int((sub["outcome_bh"] == "tie").sum()),
                    "losses_bh": int((sub["outcome_bh"] == "loss").sum()),
                    "configs_better_mean": int((sub["improvement"] > 0).sum()),
                    "p_global_wilcoxon_over_configs": p_global,
                    "median_a12_target_better": sub["a12_target_better"].median(),
                })
    return pd.DataFrame(rows)


def latex_table(head: pd.DataFrame, target: str) -> str:
    h = head[head["slice"] == "all"]
    lines = [
        r"\begin{table}[t]", r"\centering",
        rf"\caption{{{target} against static mechanisms, averaged over configurations (10 paired repetitions each). "
        r"$\Delta$: mean of per-configuration differences (percentage points for rates); 95\% CI from a two-stage bootstrap "
        r"(configurations, then repetitions). W/T/L: configurations where the difference is significant in favour of / not significant / "
        r"against " + target + r" (Wilcoxon signed-rank, Benjamini--Hochberg, $\alpha=0.05$).}",
        r"\label{tab:stats-headline}", r"\small",
        r"\begin{tabular}{llrrrc}", r"\toprule",
        r"Metric & Baseline & $\Delta$ & 95\% CI & Rel. (\%) & W/T/L \\", r"\midrule",
    ]
    names = {"CE": "CE", "SD": "SD", "FD": "FD", "best_static": "Best static", "oracle_static": "Oracle (per seed)",
             "mean_static": "Mean of static"}
    for metric, g in h.groupby("metric", sort=False):
        for _, r in g.iterrows():
            comp = r["comparison"].split("_vs_", 1)[1]
            lines.append(
                f"{r['label'].replace('%', chr(92) + '%')} & {names.get(comp, comp)} & {r['mean_abs_diff']:+.2f} & "
                f"[{r['abs_diff_ci95_low']:+.2f}, {r['abs_diff_ci95_high']:+.2f}] & {r['mean_rel_diff_pct']:+.1f} & "
                f"{r['wins_bh']}/{r['ties_bh']}/{r['losses_bh']} \\\\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines += [r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def write_report(out, args, df, keys, mechs, desc, paired, head, worse, unpaired):
    n_cfg = df["config_id"].nunique()
    reps = df.groupby(["config_id", "coord_label"])["rep"].nunique()
    L = [f"# Statistical analysis: {args.rq}", "",
         f"Input: `{args.runs}`  ", f"Configurations: {n_cfg}; mechanisms: {', '.join(mechs)}; "
         f"repetitions per cell: min {reps.min()}, max {reps.max()}; ok runs: {len(df)}.  ",
         f"Configuration keys: {', '.join(keys)}.  "]
    if unpaired:
        L.append(f"**Warning:** {unpaired} (configuration, repetition) cells have different seeds across mechanisms.")
    else:
        L.append("Pairing check: every (configuration, repetition) uses one seed for all mechanisms.")
    min_p = 2 / 2 ** int(reps.min()) if len(reps) else math.nan
    L += ["", "## Headline (all configurations)", "",
          "| Metric | Comparison | Δ (abs) | 95% CI | Rel. % | 95% CI | W/T/L (BH) | global p |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in head[head["slice"] == "all"].iterrows():
        L.append(f"| {r['label']} | {r['comparison']} | {r['mean_abs_diff']:+.3f} | "
                 f"[{r['abs_diff_ci95_low']:+.3f}, {r['abs_diff_ci95_high']:+.3f}] | {r['mean_rel_diff_pct']:+.2f} | "
                 f"[{r['rel_diff_ci95_low']:+.2f}, {r['rel_diff_ci95_high']:+.2f}] | "
                 f"{r['wins_bh']}/{r['ties_bh']}/{r['losses_bh']} | {r['p_global_wilcoxon_over_configs']:.2g} |")
    L += ["", "Rates are in percentage points (Δ); Rel. % = mean Δ / mean baseline over configurations; latencies in minutes. "
          "Positive Δ means DA has the larger value; check the metric direction (completion: higher is better; "
          "expiration and latency: lower is better).", ""]
    if not worse.empty:
        L += ["## Configurations where DA is significantly worse (BH, α=0.05)", "",
              "| Metric | Comparison | Configuration | Δ | 95% CI |", "|---|---|---|---|---|"]
        for _, r in worse.head(60).iterrows():
            L.append(f"| {r['label']} | {r['comparison']} | {fmt_config(r, keys)} | {r['mean_diff']:+.3f} | "
                     f"[{r['diff_ci95_low']:+.3f}, {r['diff_ci95_high']:+.3f}] |")
        if len(worse) > 60:
            L.append(f"| … | {len(worse) - 60} more rows in da_worse.csv | | | |")
        L.append("")
    L += ["## Power note", "",
          f"With n = {int(reps.min())} paired repetitions, the smallest two-sided p-value an exact Wilcoxon signed-rank "
          f"test can return is {min_p:.4f}. A Holm correction over {n_cfg} configurations requires p < {0.05 / max(n_cfg,1):.5f} "
          "for the first rejection, so per-configuration Holm-significant differences are impossible by construction. "
          "For this reason the per-configuration outcomes use Benjamini–Hochberg (false discovery rate), Holm-adjusted values "
          "are reported in paired.csv for completeness, and headline claims rest on the aggregate CI and on the global test "
          "over configurations.", "",
          "## Methods paragraph (draft for the paper)", "",
          f"Each configuration was simulated {int(reps.min())} times per mechanism. Repetition $r$ of a configuration "
          "uses the same random seed for all mechanisms, so DA and each static mechanism form paired samples. "
          "For every mean we report a 95% confidence interval based on the Student t distribution. "
          "For each configuration we test the paired differences between DA and each baseline with a two-sided "
          "Wilcoxon signed-rank test, correct p-values across configurations with the Benjamini–Hochberg procedure "
          "(α = 0.05), and report the Vargha–Delaney A12 effect size. Besides the individual static mechanisms, "
          "DA is compared with the best static mechanism of each configuration (selected on the same data, which favours "
          "the baseline) and with a per-seed hindsight oracle that picks the best static mechanism for every repetition. "
          "Aggregate improvements are the mean of per-configuration differences, expressed in percentage points for rates, "
          "and as relative change (mean difference divided by the mean baseline value over configurations); their 95% confidence intervals come from a two-stage "
          f"bootstrap ({args.n_boot} resamples) that resamples configurations and then repetitions within each configuration. "
          "Differences between all mechanisms within a configuration are additionally tested with the Friedman test.", ""]
    (out / "report.md").write_text("\n".join(L))


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rq", default="RQ1", choices=sorted(METRICS))
    p.add_argument("--runs", type=Path, default=None, help="runs.csv (default: Paper Results/<RQ>/runs.csv)")
    p.add_argument("--out", type=Path, default=None, help="Output dir (default: Paper Results/stats/<RQ>)")
    p.add_argument("--mechanisms", default="CE,SD,FD,DA")
    p.add_argument("--target", default="DA")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--n-boot", type=int, default=5000)
    p.add_argument("--seed", type=int, default=12345)
    args = p.parse_args()
    args.runs = args.runs or PAPER_ROOT / args.rq / "runs.csv"
    out = args.out or PAPER_ROOT / "stats" / args.rq
    out.mkdir(parents=True, exist_ok=True)

    df, keys, mechs = load(args)
    metrics = {m: v for m, v in METRICS[args.rq].items() if m in df.columns}
    desc = descriptive(df, keys, metrics)
    desc.to_csv(out / "descriptive.csv", index=False)
    print(f"[stats] {args.rq}: {df['config_id'].nunique()} configurations, {len(df)} ok runs, mechanisms {mechs}")

    if args.target not in mechs or len(mechs) < 2:
        print("[stats] Only descriptive statistics (no paired comparison possible).")
        L = [f"# Descriptive statistics: {args.rq}", "", f"Input: `{args.runs}`", "",
             "| Configuration | Metric | n | mean | 95% CI |", "|---|---|---|---|---|"]
        for _, r in desc.iterrows():
            L.append(f"| {fmt_config(r, keys)} | {r['label']} | {r['n']} | {r['mean']:.3f} | "
                     f"[{r['ci95_low']:.3f}, {r['ci95_high']:.3f}] |")
        (out / "report.md").write_text("\n".join(L) + "\n")
        return

    unpaired = check_pairing(df)
    paired = paired_analysis(df, keys, mechs, metrics, args.target, args.alpha)
    paired.to_csv(out / "paired.csv", index=False)
    friedman(df, keys, mechs, metrics).to_csv(out / "friedman.csv", index=False)
    head = headline(df, paired, mechs, metrics, args.target, args.n_boot, args.seed)
    head.to_csv(out / "headline.csv", index=False)
    worse = paired[paired["outcome_bh"] == "loss"].sort_values(["metric", "comparison", "config_id"])
    worse.to_csv(out / "da_worse.csv", index=False)
    (out / "headline.tex").write_text(latex_table(head, args.target))
    write_report(out, args, df, keys, mechs, desc, paired, head, worse, unpaired)
    print(f"[stats] wrote {out}")


if __name__ == "__main__":
    main()
