import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass
class TaskRecord:
    created_at: float
    minimum_delivery_time: float
    outcome: str | None = None
    ended_at: float | None = None


@dataclass
class RunResult:
    logfile: str
    wall_time: float
    event_count: int
    metrics: dict
    tasks: dict[int, TaskRecord] = field(default_factory=dict)


def summarize_run(sim_time, last_time, created, expired, failed, recovered, deliveries, switches, overhead):
    latencies = sorted(latency for latency, _ in deliveries)
    delivered = len(deliveries)
    switch_counts = {
        'fd_switch_count': sum(arch == 'decentralized' for _, arch in switches),
        'sd_switch_count': sum(arch == 'semi-decentralized' for _, arch in switches),
        'ce_switch_count': sum(arch == 'centralized-impprox' for _, arch in switches),
    }
    total_overheads = sorted(sample['total_overhead_ms'] for sample in overhead)
    return {
        'created': created,
        'delivered': delivered,
        'expired': expired,
        'pending': created - delivered - expired,
        'failed': failed,
        'recovered': recovered,
        'success_rate': delivered / created if created else 0.0,
        'completion_rate': delivered / created if created else 0.0,
        'expiration_rate': expired / created if created else 0.0,
        'terminal_rate': (delivered + expired) / created if created else 0.0,
        'throughput_per_hour': delivered / (sim_time / 3600.0) if sim_time else 0.0,
        'avg_latency_s': statistics.mean(latencies) if latencies else None,
        'avg_relative_latency_s': statistics.mean(relative for _, relative in deliveries) if deliveries else None,
        'median_latency_s': statistics.median(latencies) if latencies else None,
        'p95_latency_s': latencies[round((delivered - 1) * 0.95)] if latencies else None,
        'max_latency_s': latencies[-1] if latencies else None,
        'switch_count': len(switches),
        **switch_counts,
        'first_switch_time': switches[0][0] if switches else None,
        'last_sim_time': last_time,
        'adapt_checks': len(overhead),
        'adapt_switches_overhead': sum(sample['switched'] for sample in overhead),
        'adapt_overhead_ms_total': sum(sample['total_overhead_ms'] for sample in overhead),
        'adapt_overhead_ms_mean': statistics.mean(total_overheads) if overhead else None,
        'adapt_overhead_ms_p95': total_overheads[round((len(overhead) - 1) * 0.95)] if overhead else None,
        'rtlola_query_ms_mean': statistics.mean(sample['rtlola_query_ms'] for sample in overhead) if overhead else None,
        'scoring_ms_mean': statistics.mean(sample['scoring_ms'] for sample in overhead) if overhead else None,
    }


def summary_path(logfile):
    return Path(logfile).with_suffix('.summary.json')


def write_summary(result):
    path = summary_path(result.logfile)
    stream = NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False)
    temporary_path = Path(stream.name)
    try:
        with stream:
            json.dump({
                'wall_time_s': result.wall_time,
                'event_count': result.event_count,
                'metrics': result.metrics,
            }, stream, allow_nan=False)
            stream.write('\n')
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
