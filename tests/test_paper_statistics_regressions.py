import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd


class PaperStatisticsRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paper_dir = Path(__file__).resolve().parents[1] / 'Paper Results'
        with patch.object(sys, 'path', [str(paper_dir), *sys.path]):
            cls.analysis = importlib.import_module('stats_analysis')
            cls.rq4 = importlib.import_module('run_rq4_experiments')

    def test_pairing_uses_seed_and_ignores_rep_number(self):
        data = pd.DataFrame([
            {'config_id': 1, 'rep': 1, 'seed': 7, 'coord_label': 'DA', 'value': 12},
            {'config_id': 1, 'rep': 1, 'seed': 8, 'coord_label': 'CE', 'value': 1},
            {'config_id': 1, 'rep': 3, 'seed': 7, 'coord_label': 'CE', 'value': 10},
            {'config_id': 1, 'rep': 1, 'seed': 9, 'coord_label': 'FD', 'value': 1},
        ])
        paired = self.analysis.paired_analysis(
            data, [], ['DA', 'CE', 'FD'], {'value': (1, 'Value', 1.0)}, 'DA', 0.05,
        )
        self.assertEqual(set(paired['comparison']), {'DA_vs_CE', 'DA_vs_best_static'})
        direct = paired[paired['comparison'] == 'DA_vs_CE'].iloc[0]
        self.assertEqual((direct['n_pairs'], direct['mean_diff']), (1, 2.0))
        duplicate = pd.concat([data, data.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, 'Duplicate runs'):
            self.analysis.pair_matrix(duplicate, 'value', ['DA', 'CE', 'FD'], 1.0)

    def test_rq2_weights_are_separate_configurations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'runs.csv'
            pd.DataFrame([
                {'profile': 'cycle', 'coord_label': 'DA', 'status': 'ok',
                 'bandit_completion_weight': weight, 'completion_rate': weight}
                for weight in (0.0, 0.5, 1.0) for _ in range(2)
            ]).to_csv(path, index=False)
            runs, keys, _ = self.analysis.load(SimpleNamespace(rq='RQ2', runs=path, mechanisms='DA'))
            result = self.analysis.descriptive(
                runs, keys, {'completion_rate': (1, 'Completion', 1.0)},
            )
            self.assertEqual(result['n'].tolist(), [2, 2, 2])
            self.assertEqual(result['mean'].tolist(), [0.0, 0.5, 1.0])

    def test_rq4_configuration_identity_covers_seed_and_effective_deadlines(self):
        rq4 = self.rq4
        cfg = {'RANDOM_SEED': 7, 'EXPIRATION_TIME': [28800, 14400, 7200], 'LOGFILE': 'run.csv'}
        digest = rq4.configuration_hash(cfg, 1)
        self.assertEqual(digest, rq4.configuration_hash({**cfg, 'LOGFILE': 'different.csv'}, 1))
        self.assertNotEqual(digest, rq4.configuration_hash({**cfg, 'RANDOM_SEED': 8}, 1))
        self.assertNotEqual(digest, rq4.configuration_hash({**cfg, 'EXPIRATION_TIME': [28800, 7200, 3600]}, 1))
        self.assertNotEqual(digest, rq4.configuration_hash(cfg, 2))
        row = {
            'configuration_sha256': digest, 'status': 'ok',
            'experiment_profile': rq4.RQ4_EXPERIMENT_PROFILE,
            'rss_measurement': rq4.RSS_MEASUREMENT, 'peak_process_tree_rss_mb': '64',
        }
        self.assertEqual(rq4.completed_configuration_hashes([row]), {digest})
        self.assertEqual(rq4.completed_configuration_hashes([{
            **row, 'experiment_profile': 'extended-wallclock-v2',
        }]), set())
