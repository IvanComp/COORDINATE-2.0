import csv
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sim import simulator
from sim.contextual_bandit import ConservativeContextualBandit, REWARD_VERSION, context_reward, service_status
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

    def test_phase_boundaries_apply_the_new_arrival_rate_and_restore_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_scenario(
                root / 'deterministic', collect_tasks=True, SIM_TIME=325, ITEM_SPAWNING_TIME=100,
                PHASES=[{'start': 150, 'end': 225, 'ITEM_SPAWNING_TIME': 50}],
            )
            self.assertEqual([task.created_at for task in result.tasks.values()], [100, 175, 225, 325])

            settings = dict(SIM_TIME=600, ITEM_SPAWNING_TIME=100, ITEM_SPAWNING_DISTR='exponential',
                            TARGETS=-1, PHASES=[{'start': 20, 'end': 310, 'ITEM_SPAWNING_TIME': 50}])
            histories = []
            for arch in ('centralized-impprox', 'decentralized'):
                run = self.run_scenario(root / arch, ARCHITECTURE=arch, **settings)
                with Path(run.logfile).open() as stream:
                    histories.append([row for row in csv.DictReader(stream) if row['event'] == 'create'])
            self.assertEqual(histories[0], histories[1])
            budget = simulator.np.random.default_rng(simulator.np.random.SeedSequence([4, 1])).exponential()
            self.assertGreater(budget, 0.2)
            self.assertLess(budget, 6)
            self.assertAlmostEqual(float(histories[0][0]['simTime']), 20 + (budget - 0.2) * 50)

    def test_fault_phase_preserves_a_repair_already_scheduled(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_scenario(
                Path(directory) / 'repair', SIM_TIME=8, MOVEMENT_TIME=1, RECOVERY_TIME=1,
                LOG_RECOVERY=True, PHASES=[{'start': 2, 'end': 3, 'FAIL_PROB': 1, 'RECOVERY_TIME': 5}],
            )
            with Path(run.logfile).open() as stream:
                rows = [(row['event'], float(row['simTime'])) for row in csv.DictReader(stream)
                        if row['event'] in {'fail', 'recover'}]
            self.assertEqual(rows, [('fail', 2), ('recover', 7)])

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

    def test_zero_rtlola_latency_is_valid_only_for_a_populated_window(self):
        metrics = {'mean_relative_latency_1h': 0.0, 'latest_relative_latency': 83.0}
        self.assertEqual(simulator._get_rtlola_latency({
            **metrics, 'monitor_delivered_tasks_1h': 3,
        }), (0.0, 'mean_relative_latency_1h'))
        self.assertEqual(simulator._get_rtlola_latency({
            **metrics, 'monitor_delivered_tasks_1h': 0,
        }), (None, None))

    def test_rtlola_uses_the_configured_monitor_window(self):
        binary = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / 'sim'))
        if binary is None:
            self.skipTest('RTLola CLI is unavailable')
        spec = str(PROJECT_ROOT / 'spec2.rtlola')
        with RTLolaMonitor(spec, binary, adaptation_window=300, service_window=150) as monitor:
            monitor.send_event(0, -1, 1, -1, -1, -1, 'create')
            monitor.send_event(25, -1, 1, -1, -1, 22, 'deliver', minimum_delivery_time=17.0)
            early = monitor.snapshot(101)
            middle = monitor.snapshot(201)
            late = monitor.snapshot(601)
        self.assertEqual((early['coordinate_window_end'], early['monitor_delivered_tasks_1h']), (100, 1))
        self.assertEqual((late['coordinate_window_end'], late['monitor_delivered_tasks_1h']), (600, 0))
        self.assertEqual((middle['coordinate_service_window_end'], middle['service_delivered_tasks']), (200, 0))
        self.assertEqual(middle['monitor_delivered_tasks_1h'], 1)
        self.assertEqual(simulator._rtlola_service_metrics(early)[1], 8)
        self.assertEqual(simulator._get_rtlola_latency(late), (None, None))

    def test_bandit_reward_distinguishes_missing_data_from_failed_service(self):
        context = {
            'terminal_tasks_window': 3, 'completion_available': True, 'completion_rate': 0.0,
            'latency_available': False,
        }
        for mode, expected in (
            ('latency-only', 0.0), ('weighted', 0.0),
            ('completion-only', 0.0), ('completion-constrained', -1.0),
        ):
            with self.subTest(mode=mode):
                cfg = SimpleNamespace(BANDIT_OBJECTIVE_MODE=mode)
                reward, details = context_reward(cfg, context)
                self.assertEqual(reward, expected)
                self.assertTrue(details['no_service'])
                self.assertEqual(details['reward_version'], REWARD_VERSION)
                self.assertIsNone(context_reward(cfg, {**context, 'terminal_tasks_window': 2})[0])

        successful = {**context, 'completion_rate': 1.0}
        for mode in ('weighted', 'completion-constrained'):
            cfg = SimpleNamespace(BANDIT_OBJECTIVE_MODE=mode)
            reward, details = context_reward(cfg, successful)
            self.assertIsNone(reward)
            self.assertEqual(details['reward_mode'], 'insufficient_latency_observations')
            self.assertEqual(context_reward(cfg, {
                **successful, 'latency_available': True, 'latency_norm': 0.0,
            })[0], 1.0)

    def test_bandit_waits_for_evidence_and_reassesses_sustained_failure(self):
        binary = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / 'sim'))
        if binary is None:
            self.skipTest('RTLola CLI is unavailable')
        settings = dict(
            ARCHITECTURE='dynamic-adaptation', INITIAL_ARCHITECTURE='semi-decentralized',
            RTLOLA_SPEC_FILE=str(PROJECT_ROOT / 'spec2.rtlola'), RTLOLA_BINARY_PATH=binary,
            ADAPTATION_WINDOW=300, ADAPTATION_CHECK_INTERVAL=300, BANDIT_FEEDBACK_WINDOW=300,
            ADAPTATION_SERVICE_WINDOW=300,
            ADAPTATION_MIN_SWITCH_INTERVAL=0, BANDIT_OBJECTIVE_MODE='weighted',
            BANDIT_COMPLETION_WEIGHT=0.5, BANDIT_MIN_TERMINAL_OUTCOMES=3, SIM_TIME=1800,
            ITEM_SPAWNING_TIME=100, MOVEMENT_TIME=5, COMM_TIME=1, RECOVERY_TIME=50,
            FD_PATROL_ENABLED=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, expiry, first_failure in (
                ('all-expire', 60, 0), ('early-delivery', 60, 200), ('no-terminal', -1, 0),
            ):
                with self.subTest(scenario=name):
                    phases = [{'start': first_failure, 'end': 1801, 'FAIL_PROB': 1}]
                    result = self.run_scenario(
                        root / name, **settings, EXPIRATION_TIME=[expiry] * 3, PHASES=phases,
                    )
                    with Path(result.logfile).with_name('events_overhead.csv').open() as events:
                        checks = list(csv.DictReader(events))
                    self.assertEqual(checks[0]['selected_architecture'], 'semi-decentralized')
                    self.assertEqual(checks[0]['bandit_reward'], '')
                    self.assertTrue(all(row['monitor_window_s'] == '300.0' for row in checks))
                    if expiry < 0:
                        self.assertEqual(result.metrics['switch_count'], 0)
                        self.assertTrue(all(row['bandit_reward'] == '' for row in checks))
                        self.assertEqual(checks[-1]['switch_reason'], 'waiting_terminal_outcomes')
                    else:
                        self.assertGreater(result.metrics['switch_count'], 0)
                        for row in checks:
                            if row['switched'] == 'True':
                                self.assertEqual(row['service_state'], 'degraded')
                                self.assertGreaterEqual(
                                    int(row['service_degraded_checks']), int(row['service_required_checks']),
                                )
                        rewards = [row for row in checks if row['bandit_reward']]
                        self.assertTrue(rewards)
                        for row in rewards:
                            self.assertEqual(row['bandit_reward'], '0.0')
                            self.assertEqual(row['bandit_reward_no_service'], 'True')
                            self.assertEqual(row['context_latency_missing'], 'True')
                            self.assertEqual((row['raw_latency'], row['latency']), ('', ''))
                            self.assertGreaterEqual(float(row['bandit_feedback_elapsed_s']), 300)
                    if first_failure:
                        self.assertEqual(result.metrics['delivered'], 1)
                        self.assertGreater(float(checks[0]['latency']), 0)

    def test_rescue_reservation_and_verification_are_not_idle_time(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = simulator._build_cfg(str(self.scenario_config(Path(directory) / 'run', N_ROBOTS=3)))
            rooms = [Room(i) for i in range(4)]
            space = Space(cfg, rooms, topologyName_dict['line4'], Clock())
            reserved, verifying, _ = [Robot(cfg, i, False, space, cfg.LOGFILE) for i in range(3)]
            reserved.rescueReserved = True
            verifying.rescueMission = {'verification_pending': True}
            metrics, *_ = simulator._runtime_adaptation_metrics(cfg, space, 0, [], [], [], [], 300)
            self.assertEqual(metrics['idle_agents'], 1)

    def test_service_gate_requires_enough_data_and_accepts_exact_targets(self):
        cfg = SimpleNamespace(BANDIT_MIN_TERMINAL_OUTCOMES=3, BANDIT_COMPLETION_TARGET=0.65,
                              LATENCY_THRESHOLD_HIGH=40)
        metrics = {'terminal_tasks_window': 20, 'completion_available': True,
                   'completion_rate': 0.65, 'delivered_window': 13}
        self.assertEqual(service_status(cfg, metrics, 40), ('healthy', 'targets_met'))
        self.assertEqual(service_status(cfg, metrics, 41), ('degraded', 'latency_above_limit'))
        self.assertEqual(service_status(cfg, {**metrics, 'completion_rate': 0.1, 'delivered_window': 2}, None),
                         ('degraded', 'completion_below_target'))
        self.assertEqual(service_status(cfg, {**metrics, 'terminal_tasks_window': 2, 'delivered_window': 2}, 90)[0],
                         'unknown')

    def test_healthy_service_keeps_the_active_architecture_while_learning(self):
        binary = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / 'sim'))
        if binary is None:
            self.skipTest('RTLola CLI is unavailable')
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ConservativeContextualBandit, 'select_recovery') as choose:
                result = self.run_scenario(
                    Path(directory) / 'healthy',
                    ARCHITECTURE='dynamic-adaptation', INITIAL_ARCHITECTURE='semi-decentralized',
                    RTLOLA_SPEC_FILE=str(PROJECT_ROOT / 'spec2.rtlola'), RTLOLA_BINARY_PATH=binary,
                    SIM_TIME=1800, ITEM_SPAWNING_TIME=30, MOVEMENT_TIME=1, ADAPTATION_WINDOW=300,
                    ADAPTATION_CHECK_INTERVAL=100, BANDIT_FEEDBACK_WINDOW=300, FD_PATROL_ENABLED=False,
                    BANDIT_EXPLORATION_EPSILON=1.0,
                )
            choose.assert_not_called()
            with Path(result.logfile).with_name('events_overhead.csv').open() as events:
                checks = list(csv.DictReader(events))
            self.assertEqual(result.metrics['switch_count'], 0)
            self.assertTrue(any(row['bandit_updated_action'] for row in checks))
            self.assertTrue(all(row['selected_architecture'] == 'semi-decentralized' for row in checks))

    def test_latency_degradation_waits_for_post_switch_evidence(self):
        binary = resolve_rtlola_binary(str(PROJECT_ROOT), str(PROJECT_ROOT / 'sim'))
        if binary is None:
            self.skipTest('RTLola CLI is unavailable')

        with tempfile.TemporaryDirectory() as directory:
            for expected, stopped_by in ((0.8, 'waiting_latency_reassessment'),
                                        (0.5, 'insufficient_expected_latency_recovery')):
                with self.subTest(expected=expected):
                    def prefer_alternative(policy, context, current):
                        self.assertFalse(hasattr(policy.cfg, 'PHASES'))
                        ce, sd, _ = policy.actions
                        candidate = sd if current == ce else ce
                        return {'candidate_architecture': candidate, 'initial_sampling': False,
                                'estimated_values': {current: 0.5, candidate: expected}}

                    with patch.object(ConservativeContextualBandit, 'select_recovery', prefer_alternative):
                        result = self.run_scenario(
                            Path(directory) / str(expected), ARCHITECTURE='dynamic-adaptation',
                            RTLOLA_BINARY_PATH=binary, SIM_TIME=1000, ITEM_SPAWNING_TIME=2, MOVEMENT_TIME=5,
                            ADAPTATION_CHECK_INTERVAL=30, ADAPTATION_WINDOW=120, ADAPTATION_SERVICE_WINDOW=60,
                            BANDIT_FEEDBACK_WINDOW=120, ADAPTATION_MIN_SWITCH_INTERVAL=0, LATENCY_THRESHOLD_HIGH=0,
                            PHASES=[{'start': 125, 'end': 500, 'FAIL_PROB': 0}],
                        )
                    with Path(result.logfile).with_name('events_overhead.csv').open() as events:
                        checks = list(csv.DictReader(events))
                    held = [row for row in checks if row['switch_reason'] == stopped_by]
                    self.assertTrue(held)
                    self.assertTrue(all(row['service_reason'] == 'latency_above_limit' for row in held))
                    switches = [float(row['sim_time']) for row in checks if row['switched'] == 'True']
                    if expected > 0.5:
                        self.assertGreater(len(switches), 1)
                        self.assertTrue(all(second - first >= 360 for first, second in zip(switches, switches[1:])))
                    else:
                        self.assertEqual(switches, [])

    def test_recovery_ranks_alternatives_against_observed_service(self):
        cfg = SimpleNamespace(BANDIT_OBJECTIVE_MODE='completion-only')
        bandit = ConservativeContextualBandit(cfg)
        ce, sd, fd = bandit.actions
        bandit.counts = {ce: 8, sd: 8, fd: 8}
        observed = {'completion_rate': 0.5, 'completion_available': True, 'terminal_tasks_window': 6}
        learned = {ce: 0.9, sd: 0.49, fd: 0.34}
        confidence = dict.fromkeys(bandit.actions, 0.0)
        with patch.object(bandit, 'values', return_value=(learned, confidence, learned)):
            self.assertEqual(bandit.select_recovery(observed, ce)['candidate_architecture'], ce)
        revised = {**learned, fd: 0.7}
        with patch.object(bandit, 'values', return_value=(revised, confidence, revised)):
            self.assertEqual(bandit.select_recovery(observed, ce)['candidate_architecture'], fd)

    def test_delivering_robot_returns_even_if_another_task_waits_at_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = simulator._build_cfg(str(self.scenario_config(Path(directory) / 'run', **QUIET_LOGS)))
            rooms = [Room(i) for i in range(4)]
            clock = Clock()
            space = Space(cfg, rooms, topologyName_dict['line4'], clock)
            robot = Robot(cfg, 0, False, space, cfg.LOGFILE)
            shipped = Item(cfg, cfg.LOGFILE, 0, space, 0, imp=1, target=rooms[1])
            waiting = Item(cfg, cfg.LOGFILE, 1, space, 0, imp=1, target=rooms[1])
            waiting.setLocation(rooms[1])
            space.availItems.extend((shipped, waiting))
            robot.loadItem(shipped, 0)
            ts, event = clock.getNextEvent()
            self.assertEqual(event, 'move-0')
            self.assertIs(robot.move(ts), shipped)
            self.assertEqual(robot.optRoute, [rooms[0]])
            self.assertEqual(clock.getNextEvent(), (20.0, 'move-0'))
