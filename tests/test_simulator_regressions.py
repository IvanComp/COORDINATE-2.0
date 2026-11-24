import csv
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sim import simulator
from sim.rtlola_monitor import RTLolaMonitor, resolve_rtlola_binary


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SimulatorRegressions(unittest.TestCase):
    def run_scenario(self, directory, **updates):
        directory.mkdir()
        cfg = {
            'RESULTS_DIR': str(directory),
            'LOGFILE': str(directory / 'events.csv'),
            'ARCHITECTURE': 'centralized-impprox',
            'TOPOLOGY_NAME': 'line4',
            'N_ROOMS': 4,
            'SOURCE': 0,
            'TARGETS': [1],
            'N_ROBOTS': 1,
            'N_MALICIOUS': 0,
            'RANDOM_SEED': 4,
            'SIM_TIME': 8,
            'ITEM_SPAWNING_TIME': 1,
            'ITEM_SPAWNING_DISTR': 'deterministic',
            'IMPORTANCE_PROBABILITIES': [1.0, 0.0, 0.0],
            'EXPIRATION_TIME': [-1, -1, -1],
            'EXPIRATION_DISTR': ['deterministic'] * 3,
            'FAIL_PROB': 0.0,
            'COMM_FAIL_PROB': 0.0,
            'LOAD_TIME': 0.0,
            'DROP_TIME': 0.0,
            'MOVEMENT_TIME': 10.0,
            'COMM_TIME': 0.0,
            'COMP_TIME': 0.0,
            'RECOVERY_TIME': 1800.0,
            'LOG_LOAD': True,
            'LOG_FAIL': True,
            'LOG_DROP': True,
        }
        for activity in ('LOAD', 'DROP', 'MOVEMENT', 'COMM', 'COMP', 'RECOVERY'):
            cfg[f'{activity}_DISTR'] = 'deterministic'
        cfg.update(updates)
        path = directory / 'config.json'
        path.write_text(json.dumps(cfg), encoding='utf-8')
        logfile, _, event_count = simulator.run(str(path))
        return Path(logfile), event_count

    def test_expiry_releases_robot_to_load_waiting_item(self):
        with tempfile.TemporaryDirectory() as directory:
            logfile, _ = self.run_scenario(Path(directory) / 'scenario', EXPIRATION_TIME=[2.5, -1, -1])
            with logfile.open() as events:
                loaded = [(row['simTime'], row['itemId']) for row in csv.DictReader(events)
                          if row['event'] == 'startLoading']
        self.assertEqual(loaded[:2], [('1.0', '0'), ('3.5', '1')])

    def test_failed_arrival_remains_pending_until_unloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            for deadline in (-1, 6):
                with self.subTest(deadline=deadline):
                    logfile, _ = self.run_scenario(
                        Path(directory) / str(deadline),
                        N_ROBOTS=2, ITEM_SPAWNING_TIME=10, LOAD_TIME=1, MOVEMENT_TIME=1, DROP_TIME=2,
                        SIM_TIME=18, EXPIRATION_TIME=[deadline, -1, -1],
                        PHASES=[
                            {'start': 14.0, 'end': 14.1, 'FAIL_PROB': 1.0},
                            {'start': 14.1, 'end': 18.0, 'FAIL_PROB': 0.0},
                        ],
                    )
                    with logfile.open() as events:
                        rows = list(csv.DictReader(events))
                    outcome = [(row['event'], float(row['simTime'])) for row in rows
                               if row['itemId'] == '0' and row['event'] in {'fail', 'deliver', 'expire'}]
                    expected = ('deliver', 17.25) if deadline == -1 else ('expire', 16.0)
                    self.assertEqual(outcome, [('fail', 14.0), expected])
                    if deadline == -1:
                        failed = next(row for row in rows if row['event'] == 'fail')
                        delivered = next(row for row in rows if row['event'] == 'deliver')
                        self.assertNotEqual(delivered['robotId'], failed['robotId'])

    def test_rtlola_uses_delivery_reference_and_checks_are_repeatable(self):
        binary = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / 'sim'))
        if binary is None:
            self.skipTest('RTLola CLI is unavailable')
        spec = str(PROJECT_ROOT / 'spec2.rtlola')
        with RTLolaMonitor(spec, binary) as monitor:
            monitor.send_event(0, -1, 1, -1, -1, -1, 'create')
            monitor.send_event(25, -1, 1, -1, -1, 22, 'deliver', minimum_delivery_time=17.0)
            self.assertEqual(monitor.snapshot(31)['mean_relative_latency_1h'], 8.0)
            self.assertEqual(monitor.snapshot(32)['global_relative_latency'], 8.0)

        with tempfile.TemporaryDirectory() as directory:
            settings = dict(
                ARCHITECTURE='dynamic-adaptation', RTLOLA_SPEC_FILE=spec, RTLOLA_BINARY_PATH=binary,
                SIM_TIME=3600, ADAPTATION_CHECK_INTERVAL=120, ITEM_SPAWNING_TIME=30,
                ITEM_SPAWNING_DISTR='exponential', FAIL_PROB=0.09, COMM_FAIL_PROB=0.03,
                N_ROBOTS=5, N_MALICIOUS=2, TOPOLOGY_NAME='ring25', N_ROOMS=25,
                TARGETS=-1, LOAD_TIME=1, DROP_TIME=1, MOVEMENT_TIME=5,
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.run_scenario, Path(directory) / 'first', **settings)
                second = pool.submit(self.run_scenario, Path(directory) / 'second', **settings)
                results = [first.result(), second.result()]
            (first_log, first_count), (second_log, second_count) = results
            self.assertEqual(first_count, second_count)
            self.assertEqual(first_log.read_bytes(), second_log.read_bytes())
            excluded = {'total_overhead_ms', 'rtlola_query_ms', 'scoring_ms'}
            decisions = []
            for path, _ in results:
                with path.with_name('events_overhead.csv').open() as f:
                    decisions.append([{k: v for k, v in row.items() if k not in excluded}
                                      for row in csv.DictReader(f)])
            self.assertGreater(len(decisions[0]), 10)
            self.assertEqual(*decisions)
