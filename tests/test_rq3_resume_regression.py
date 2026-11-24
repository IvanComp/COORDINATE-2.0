import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RQ3ResumeRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paper_dir = Path(__file__).resolve().parents[1] / 'Paper Results'
        with patch.object(sys, 'path', [str(paper_dir), *sys.path]):
            cls.rq3 = importlib.import_module('run_rq3_experiments')
            cls.paper_utils = importlib.import_module('paper_experiment_utils')

    def test_resume_skips_a_compatible_completed_row(self):
        rq3 = self.rq3
        argv = ['rq3', '--quick', '--sim-days', '1', '--repetitions', '1',
                '--coord-labels', 'CE', '--workers', '1', '--no-reuse-rq1']
        with patch.object(sys, 'argv', argv):
            args = rq3.parse_args()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch.object(rq3, 'RESULTS_ROOT', path):
                rq3.run_campaign(args)
                rows = rq3.read_rows(path / 'runs.csv')
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['status'], 'ok')
                rows[0].pop('fd_policy_version')
                rq3.write_rows(path / 'runs.csv', rows)
                with patch.object(rq3, 'execute_rq3_job') as execute:
                    rq3.run_campaign(args)
                    execute.assert_not_called()

            params, = rq3.campaign(args)
            expected = rq3.expiration_metadata({**rq3.BASE_CONFIG, 'EXPIRATION_TIME': [28800, 14400, 7200]})
            for field, value in (
                ('seed', params['seed'] + 1),
                ('sim_days', args.sim_days + 1),
                ('log_expire', 'False'),
                ('fd_policy_version', 'different-version'),
                ('expiration_time_high_s', 3600),
            ):
                with self.subTest(field=field):
                    self.assertFalse(rq3.matches_completed_rq3(
                        {**rows[0], field: value}, params, args.sim_days, expected,
                    ))

    def test_rq1_reuse_requires_matching_saved_configuration(self):
        utils = self.paper_utils
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_log = root / 'events.csv'
            source_log.touch()
            source_config = root / 'config.json'
            requested = {
                'LOGFILE': str(root / 'requested.csv'),
                'LOG_EXPIRE': True,
                'EXPIRATION_TIME': [28800, 14400, 7200],
                'RANDOM_SEED': 813,
                'SIM_TIME': 86400,
            }
            matching = {
                'coord_label': 'CE', 'rep': 1, 'topology': 'ring25', 'n_rooms': 25,
                'item_spawning_time': 120, 'n_robots': 20, 'malicious_ratio': 0.6,
                'fail_prob': 0.09, 'msg_loss_prob': 0.03,
            }
            row = {
                **matching, **utils.expiration_metadata(requested),
                'status': 'ok', 'fd_policy_version': utils.FD_POLICY_VERSION,
                'seed': 813, 'logfile': str(source_log), 'config_path': str(source_config),
            }
            with patch.object(utils, 'read_rows', return_value=[row]):
                source_config.write_text(json.dumps({**requested, 'LOGFILE': str(source_log)}))
                self.assertIs(utils.find_matching_rq1_row(cfg=requested, **matching), row)
                for override in ({'SIM_TIME': 172800}, {'RANDOM_SEED': 814}):
                    with self.subTest(override=override):
                        source_config.write_text(json.dumps({**requested, **override}))
                        self.assertIsNone(utils.find_matching_rq1_row(cfg=requested, **matching))
