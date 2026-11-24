import csv
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sim import simulator
from sim.core import Clock, Item, Robot, Room, Space
from sim.env_maps import topologyName_dict
from sim.rtlola_monitor import RTLolaMonitor, resolve_rtlola_binary
from sim.run_statistics import summary_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUIET_LOGS = {f'LOG_{name}': False for name in (
    'ITEM', 'DELIVERY', 'LOAD', 'DROP', 'EXPIRE', 'MOVE', 'FAIL', 'RECOVERY', 'HELP', 'FAKE', 'RESCUE',
)}
TRACE_AND_RUNTIME_FIELDS = {
    'trace_rows', 'adapt_overhead_ms_total', 'adapt_overhead_ms_mean', 'adapt_overhead_ms_p95',
    'rtlola_query_ms_mean', 'scoring_ms_mean',
}


class SimulatorRegressions(unittest.TestCase):
    def scenario_config(self, directory, **updates):
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
        return path

    def run_scenario(self, directory, *, collect_tasks=False, **updates):
        path = self.scenario_config(directory, **updates)
        return simulator.run_with_stats(str(path), collect_tasks=collect_tasks)

    def test_target_validation_and_source_exclusion(self):
        invalid = ([], [-1], [4], [True], [1.0], ['1'], [0], '-1', -1.0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for idx, targets in enumerate(invalid):
                with self.subTest(targets=targets):
                    path = self.scenario_config(root / str(idx), TARGETS=targets, SIM_TIME=0)
                    with self.assertRaisesRegex(ValueError, 'TARGETS'):
                        simulator.run(str(path))
            for targets in (-1, [0, 2]):
                path = self.scenario_config(root / str(targets), TARGETS=targets)
                cfg = simulator._build_cfg(str(path))
                rooms = [Room(i) for i in range(4)]
                result = simulator.getTargetRoom(cfg, rooms)
                self.assertIs(result, None if targets == -1 else rooms[2])

    def test_rescuer_resumes_work_after_interrupted_item_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for has_local_work in (False, True):
                with self.subTest(has_local_work=has_local_work):
                    cfg = simulator._build_cfg(str(self.scenario_config(root / str(has_local_work), **QUIET_LOGS)))
                    rooms = [Room(i) for i in range(4)]
                    clock = Clock()
                    space = Space(cfg, rooms, topologyName_dict['line4'], clock)
                    robot = Robot(cfg, 0, False, space, cfg.LOGFILE)
                    robot.setLocation(rooms[1])
                    item = Item(cfg, cfg.LOGFILE, 1, space, 0, imp=1, target=rooms[3])
                    item.setLocation(rooms[1])
                    space.availItems.append(item)
                    robot.loadItem(item, 0)
                    self.assertTrue(robot._abortMission(4, rooms[1], 0, fake=True))
                    space.expireItem(item, 0)
                    replacement = Item(cfg, cfg.LOGFILE, 2, space, 0, imp=0, target=rooms[3])
                    if has_local_work:
                        replacement.setLocation(rooms[1])
                        space.availItems.append(replacement)
                    ts, event = clock.getNextEvent()
                    self.assertTrue(event.startswith('rescue-verification-'))
                    robot.completeRescueVerification(ts)
                    self.assertFalse(robot.isRescuing())
                    self.assertEqual(clock.getNextEvent(), (10.0, 'move-0'))
                    if has_local_work:
                        self.assertIs(robot.getItem(), replacement)
                    else:
                        self.assertTrue(robot.isFree())
                        self.assertEqual(robot.optRoute, [rooms[0]])

    def test_proximity_strategies_skip_ineligible_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = simulator._build_cfg(str(self.scenario_config(Path(directory) / 'run', **QUIET_LOGS)))
            rooms = [Room(i) for i in range(4)]
            space = Space(cfg, rooms, topologyName_dict['line4'], Clock())
            requester, nearby, farther = [Robot(cfg, i, False, space, cfg.LOGFILE) for i in range(3)]
            nearby.setLocation(rooms[1])
            farther.setLocation(rooms[3])
            nearby.setItem(Item(cfg, cfg.LOGFILE, 0, space, 0, imp=2, target=rooms[3]))
            for strategy in ('proximity', 'proximp'):
                with self.subTest(strategy=strategy):
                    self.assertIs(space._selectCentralHelper(requester, 0, rooms[1], strategy), farther)
            self.assertTrue(farther._abortMission(0, rooms[1], 0))

    def test_proximity_uses_distance_from_helper_to_rescue(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = simulator._build_cfg(str(self.scenario_config(Path(directory) / 'run', **QUIET_LOGS)))
            rooms = [Room(i) for i in range(36)]
            space = Space(cfg, rooms, topologyName_dict['mesh36'], Clock())
            requester, nearby, farther = [Robot(cfg, i, False, space, cfg.LOGFILE) for i in range(3)]
            requester.setLocation(rooms[4])
            nearby.setLocation(rooms[12])
            farther.setLocation(rooms[32])
            self.assertEqual(
                space.getRobotsByProximity(requester, [farther, nearby], rooms[4]), [nearby],
            )

    def test_expiry_releases_robot_to_load_waiting_item(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_scenario(Path(directory) / 'scenario', EXPIRATION_TIME=[2.5, -1, -1])
            with Path(result.logfile).open() as events:
                loaded = [(row['simTime'], row['itemId']) for row in csv.DictReader(events)
                          if row['event'] == 'startLoading']
        self.assertEqual(loaded[:2], [('1.0', '0'), ('3.5', '1')])

    def test_failed_arrival_remains_pending_until_unloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            for deadline in (-1, 6):
                with self.subTest(deadline=deadline):
                    result = self.run_scenario(
                        Path(directory) / str(deadline),
                        N_ROBOTS=2, ITEM_SPAWNING_TIME=10, LOAD_TIME=1, MOVEMENT_TIME=1, DROP_TIME=2,
                        SIM_TIME=18, EXPIRATION_TIME=[deadline, -1, -1],
                        PHASES=[
                            {'start': 14.0, 'end': 14.1, 'FAIL_PROB': 1.0},
                            {'start': 14.1, 'end': 18.0, 'FAIL_PROB': 0.0},
                        ],
                    )
                    with Path(result.logfile).open() as events:
                        rows = list(csv.DictReader(events))
                    outcome = [(row['event'], float(row['simTime'])) for row in rows
                               if row['itemId'] == '0' and row['event'] in {'fail', 'deliver', 'expire'}]
                    expected = ('deliver', 17.25) if deadline == -1 else ('expire', 16.0)
                    self.assertEqual(outcome, [('fail', 14.0), expected])
                    if deadline == -1:
                        failed = next(row for row in rows if row['event'] == 'fail')
                        delivered = next(row for row in rows if row['event'] == 'deliver')
                        self.assertNotEqual(delivered['robotId'], failed['robotId'])

    def test_horizon_includes_all_events_at_the_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            at_limit = self.run_scenario(
                root / 'at-limit', SIM_TIME=2, MOVEMENT_TIME=1, FAIL_PROB=1,
                RECOVERY_TIME=0, LOG_RECOVERY=True,
            )
            with Path(at_limit.logfile).open() as events:
                rows = list(csv.DictReader(events))
            self.assertEqual([row['event'] for row in rows if float(row['simTime']) == 2],
                             ['create', 'fail', 'drop', 'recover', 'startLoading'])
            self.assertTrue(all(float(row['simTime']) <= 2 for row in rows))
            self.assertEqual(at_limit.metrics['last_sim_time'], 2)
            self.assertEqual(at_limit.metrics['recovered'], 1)

            beyond_limit = self.run_scenario(
                root / 'beyond-limit', SIM_TIME=5, ITEM_SPAWNING_TIME=10, FD_PATROL_ENABLED=False,
            )
            with Path(beyond_limit.logfile).open() as events:
                self.assertEqual(list(csv.DictReader(events)), [])
            self.assertEqual(beyond_limit.event_count, 0)
            self.assertEqual(beyond_limit.metrics['created'], 0)

    def test_simulation_statistics_do_not_depend_on_trace_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = dict(
                collect_tasks=True, MOVEMENT_TIME=1, RECOVERY_TIME=1, EXPIRATION_TIME=[3, -1, -1],
                PHASES=[
                    {'start': 2, 'end': 2.1, 'FAIL_PROB': 1},
                    {'start': 2.1, 'end': 9, 'FAIL_PROB': 0},
                ],
            )
            verbose = self.run_scenario(Path(directory) / 'verbose', **settings, LOG_RECOVERY=True)
            quiet = self.run_scenario(Path(directory) / 'quiet', **settings, **QUIET_LOGS)
            self.assertEqual(verbose.event_count, quiet.event_count)
            self.assertEqual(verbose.tasks, quiet.tasks)
            self.assertGreater(verbose.metrics['trace_rows'], 0)
            self.assertEqual(quiet.metrics['trace_rows'], 0)
            for metric in ('created', 'delivered', 'expired', 'failed', 'recovered', 'pending'):
                self.assertGreater(verbose.metrics[metric], 0)
            self.assertEqual(
                {k: v for k, v in verbose.metrics.items() if k != 'trace_rows'},
                {k: v for k, v in quiet.metrics.items() if k != 'trace_rows'},
            )
            saved = json.loads(summary_path(quiet.logfile).read_text())
            self.assertEqual(saved['metrics'], quiet.metrics)

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
            self.assertEqual(results[0].event_count, results[1].event_count)
            self.assertEqual(Path(results[0].logfile).read_bytes(), Path(results[1].logfile).read_bytes())
            results.append(self.run_scenario(Path(directory) / 'quiet', **settings, **QUIET_LOGS))
            excluded = {'total_overhead_ms', 'rtlola_query_ms', 'scoring_ms'}
            decisions = []
            for result in results:
                with Path(result.logfile).with_name('events_overhead.csv').open() as f:
                    decisions.append([{k: v for k, v in row.items() if k not in excluded}
                                      for row in csv.DictReader(f)])
            self.assertGreater(len(decisions[0]), 10)
            for index in (1, 2):
                self.assertEqual(decisions[0], decisions[index])
                self.assertEqual(
                    {k: v for k, v in results[0].metrics.items() if k not in TRACE_AND_RUNTIME_FIELDS},
                    {k: v for k, v in results[index].metrics.items() if k not in TRACE_AND_RUNTIME_FIELDS},
                )
