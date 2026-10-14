import argparse
import csv
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim import simulator


SCENARIO_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = SCENARIO_ROOT / 'results'

ARCHITECTURES = {
    'CE': 'centralized-impprox',
    'SD': 'semi-decentralized',
    'FD': 'decentralized',
}

TECHNIQUES = {
    'none': (False, False),
    'encryption': (True, False),
    'obfuscation': (False, True),
    'combined': (True, True),
}

TOPOLOGIES = {
    'mesh': 'mesh25',
    'ring': 'ring25',
    'star': 'star25',
}

WORKLOADS = {
    'low': 180.0,
    'medium': 90.0,
    'high': 30.0,
}

BASE_CONFIG = {
    'SIM_TIME': 3600,
    'TOPOLOGY_NAME': 'mesh25',
    'N_ROOMS': 25,
    'SOURCE': 0,
    'TARGETS': -1,
    'ITEM_SPAWNING_DISTR': 'exponential',
    'ITEM_SPAWNING_TRACE': '_',
    'IMPORTANCE_PROBABILITIES': [0.40, 0.35, 0.25],
    'EXPIRATION_TIME': [900, 600, 420],
    'EXPIRATION_DISTR': ['deterministic', 'deterministic', 'deterministic'],
    'N_ROBOTS': 12,
    'N_MALICIOUS': 0,
    'MALICIOUS_FAKE_FAILURES': True,
    'FIND_ROUTE_STRATEGY': 'breadth',
    'FAIL_PROB': 0.02,
    'COMM_FAIL_PROB': 0.003,
    'LOAD_TIME': 1.0,
    'LOAD_DISTR': 'exponential',
    'LOAD_TRACE': '_',
    'MOVEMENT_TIME': 5.0,
    'MOVEMENT_DISTR': 'exponential',
    'MOVEMENT_TRACE': '_',
    'DROP_TIME': 1.0,
    'DROP_DISTR': 'exponential',
    'DROP_TRACE': '_',
    'COMP_TIME': 0.05,
    'COMP_DISTR': 'exponential',
    'COMP_TRACE': '_',
    'COMM_TIME': 0.03,
    'COMM_DISTR': 'exponential',
    'COMM_TRACE': '_',
    'RECOVERY_TIME': 300.0,
    'RECOVERY_DISTR': 'exponential',
    'RECOVERY_TRACE': '_',
    'COORDINATOR_SERVICE_TIME': 0.25,
    'COORDINATOR_COMMAND_LOSS_PROB': -1.0,
    'COORDINATOR_FAILURE_PROB': 0.0,
    'COORDINATOR_AVAILABLE': True,
    'FD_PATROL_ENABLED': False,
    'FD_LOCAL_SEARCH_ENABLED': False,
    'PRIVACY_COMM_TIME_BONUS': [0.0, 0.0, 0.0],
    'PRIVACY_COMP_TIME_BONUS': [0.0, 0.0, 0.0],
    'PRIVACY_METRICS_ENABLED': True,
    'PRIVACY_LINK_BYTES_PER_SECOND': 125000.0,
    'PHASES': [],
    'LOG_ITEM': True,
    'LOG_DELIVERY': True,
    'LOG_LOAD': False,
    'LOG_DROP': False,
    'LOG_EXPIRE': True,
    'LOG_MOVE': False,
    'LOG_FAIL': True,
    'LOG_RECOVERY': True,
    'LOG_HELP': False,
    'LOG_FAKE': False,
    'LOG_RESCUE': False,
}


def parse_list(raw, allowed):
    values = [value.strip() for value in raw.split(',') if value.strip()]
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ValueError(f'Unsupported values: {", ".join(invalid)}')
    return values


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def write_rows(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def analyze_log(path, simulation_duration):
    created = 0
    delivered = 0
    expired = 0
    create_times = {}
    latencies = []
    with path.open(newline='') as handle:
        for row in csv.DictReader(handle):
            event = row['event']
            item_id = int(float(row['itemId']))
            event_time = float(row['simTime'])
            if event == 'create':
                created += 1
                create_times[item_id] = event_time
            elif event == 'deliver':
                delivered += 1
                if item_id in create_times:
                    latencies.append(event_time - create_times[item_id])
            elif event == 'expire':
                expired += 1
    return {
        'created': created,
        'delivered': delivered,
        'expired': expired,
        'throughput_tasks_per_hour': delivered / simulation_duration * 3600.0 if simulation_duration else 0.0,
        'success_rate': delivered / created if created else 0.0,
        'expiration_rate': expired / created if created else 0.0,
        'avg_latency_s': mean(latencies) if latencies else 0.0,
    }


def read_single_row(path):
    with path.open(newline='') as handle:
        return next(csv.DictReader(handle))


def numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def build_summary(rows):
    groups = {}
    for row in rows:
        if row.get('status') != 'ok':
            continue
        key = (
            row['topology_label'],
            row['topology_name'],
            row['architecture_label'],
            row['architecture'],
            row['technique'],
            row['workload'],
        )
        groups.setdefault(key, []).append(row)
    summary = []
    metric_names = [
        'created',
        'delivered',
        'expired',
        'throughput_tasks_per_hour',
        'success_rate',
        'expiration_rate',
        'avg_latency_s',
        'message_count',
        'adversary_success_rate',
        'expected_distance_error',
        'clear_bytes_total',
        'wire_bytes_total',
        'privacy_processing_seconds',
        'privacy_added_delay_seconds',
        'wall_time_s',
        'event_count',
    ]
    for key, group in sorted(groups.items()):
        record = {
            'topology_label': key[0],
            'topology_name': key[1],
            'architecture_label': key[2],
            'architecture': key[3],
            'technique': key[4],
            'workload': key[5],
            'repetitions': len(group),
        }
        for metric in metric_names:
            values = [numeric(row.get(metric)) for row in group]
            values = [value for value in values if not math.isnan(value)]
            summary_metric = metric if metric.startswith('avg_') else f'avg_{metric}'
            record[summary_metric] = mean(values) if values else ''
        summary.append(record)
    return summary


def run_campaign(args):
    architectures = parse_list(args.architectures, ARCHITECTURES)
    techniques = parse_list(args.techniques, TECHNIQUES)
    topologies = parse_list(args.topologies, TOPOLOGIES)
    workloads = parse_list(args.workloads, WORKLOADS)
    repetitions = 1 if args.smoke else args.repetitions
    sim_time = min(args.sim_time, 300.0) if args.smoke else args.sim_time
    results_root = RESULTS_ROOT / 'smoke' if args.smoke else RESULTS_ROOT
    config_root = results_root / 'configs'
    raw_root = results_root / 'raw_logs'
    runs_path = results_root / 'privacy_runs.csv'
    summary_path = results_root / 'privacy_summary.csv'
    metadata_path = results_root / 'campaign_metadata.json'
    existing = read_rows(runs_path)
    for row in existing:
        row['topology_label'] = row.get('topology_label') or 'mesh'
        row['topology_name'] = row.get('topology_name') or TOPOLOGIES[row['topology_label']]
    completed = {row['run_id'] for row in existing if row.get('status') == 'ok'}
    rows = [row for row in existing if row.get('run_id')]
    total = len(topologies) * len(architectures) * len(techniques) * len(workloads) * repetitions
    current = 0
    for topology_label in topologies:
        topology_name = TOPOLOGIES[topology_label]
        for workload_index, workload in enumerate(workloads):
            for repetition in range(1, repetitions + 1):
                seed = args.seed + workload_index * 1000 + repetition
                for architecture_label in architectures:
                    architecture = ARCHITECTURES[architecture_label]
                    for technique in techniques:
                        current += 1
                        legacy_run_id = f'{workload}__{architecture_label}__{technique}__r{repetition}'
                        run_id = legacy_run_id if topology_label == 'mesh' else f'{topology_label}__{legacy_run_id}'
                        if run_id in completed and not args.force:
                            print(f'[{current}/{total}] skip {run_id}', flush=True)
                            continue
                        print(f'[{current}/{total}] run {run_id}', flush=True)
                        run_dir = raw_root / run_id
                        config_path = config_root / f'{run_id}.json'
                        logfile = run_dir / 'simulation_log.csv'
                        encryption, obfuscation = TECHNIQUES[technique]
                        config = {
                            **BASE_CONFIG,
                            'SIM_TIME': sim_time,
                            'TOPOLOGY_NAME': topology_name,
                            'ARCHITECTURE': architecture,
                            'ITEM_SPAWNING_TIME': WORKLOADS[workload],
                            'RANDOM_SEED': seed,
                            'PRIVACY_ENCRYPTION_ENABLED': encryption,
                            'PRIVACY_OBFUSCATION_ENABLED': obfuscation,
                            'PRIVACY_LINK_BYTES_PER_SECOND': args.link_bytes_per_second,
                            'RESULTS_DIR': str(run_dir),
                            'LOGFILE': str(logfile),
                            'SIMTIME_LOGFILE': str(run_dir / 'sim_time.csv'),
                        }
                        config_path.parent.mkdir(parents=True, exist_ok=True)
                        run_dir.mkdir(parents=True, exist_ok=True)
                        config_path.write_text(json.dumps(config, indent=2))
                        rows = [row for row in rows if row.get('run_id') != run_id]
                        try:
                            _, wall_time, event_count = simulator.run(str(config_path))
                            operational = analyze_log(logfile, sim_time)
                            privacy = read_single_row(logfile.with_name('simulation_log_privacy_summary.csv'))
                            row = {
                                'run_id': run_id,
                                'status': 'ok',
                                'topology_label': topology_label,
                                'topology_name': topology_name,
                                'architecture_label': architecture_label,
                                'workload': workload,
                                'item_spawning_time_s': WORKLOADS[workload],
                                'repetition': repetition,
                                'random_seed': seed,
                                'sim_time_s': sim_time,
                                **operational,
                                **privacy,
                                'architecture': architecture,
                                'technique': technique,
                                'wall_time_s': wall_time,
                                'event_count': event_count,
                                'error': '',
                            }
                        except Exception as exc:
                            row = {
                                'run_id': run_id,
                                'status': 'error',
                                'topology_label': topology_label,
                                'topology_name': topology_name,
                                'architecture_label': architecture_label,
                                'architecture': architecture,
                                'technique': technique,
                                'workload': workload,
                                'repetition': repetition,
                                'random_seed': seed,
                                'sim_time_s': sim_time,
                                'error': str(exc),
                            }
                            rows.append(row)
                            write_rows(runs_path, rows)
                            if args.fail_fast:
                                raise
                            continue
                        rows.append(row)
                        write_rows(runs_path, rows)
                        write_rows(summary_path, build_summary(rows))
    metadata = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'architectures': architectures,
        'techniques': techniques,
        'topologies': [
            topology
            for topology in TOPOLOGIES
            if any(row.get('status') == 'ok' and row.get('topology_label') == topology for row in rows)
        ],
        'requested_topologies': topologies,
        'workloads': workloads,
        'repetitions': repetitions,
        'sim_time_s': sim_time,
        'seed': args.seed,
        'privacy_link_bytes_per_second': args.link_bytes_per_second,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2))
    write_rows(summary_path, build_summary(rows))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--sim-time', type=float, default=3600.0)
    parser.add_argument('--seed', type=int, default=26000)
    parser.add_argument('--link-bytes-per-second', type=float, default=125000.0)
    parser.add_argument('--architectures', default='CE,SD,FD')
    parser.add_argument('--techniques', default='none,encryption,obfuscation,combined')
    parser.add_argument('--topologies', default='mesh,ring,star')
    parser.add_argument('--workloads', default='low,medium,high')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--fail-fast', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    run_campaign(parse_args())
