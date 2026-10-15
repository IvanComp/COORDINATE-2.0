import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cryptography.exceptions import InvalidSignature

from sim.privacy_techniques import PrivacyRuntime


def config(encryption=False, obfuscation=False):
    return SimpleNamespace(
        PRIVACY_METRICS_ENABLED=True,
        PRIVACY_ENCRYPTION_ENABLED=encryption,
        PRIVACY_OBFUSCATION_ENABLED=obfuscation,
        PRIVACY_LINK_BYTES_PER_SECOND=125000.0,
        PRIVACY_PADDING_BYTES=4096,
        PRIVACY_CLOAKING_SIZE=3,
        PRIVACY_SIGNING_KEY_ROTATION_MESSAGES=2,
        current_architecture='semi-decentralized',
    )


class PrivacyTechniquesTest(unittest.TestCase):
    def setUp(self):
        self.topology = {0: [1], 1: [0, 2], 2: [1]}

    def test_baseline_is_fully_visible(self):
        runtime = PrivacyRuntime(config(), self.topology, 0)
        delay = runtime.transmit(0.0, 'assignment', 'coordinator', 'agent:1', 2)
        summary = runtime.summary()
        self.assertEqual(delay, 0.0)
        self.assertEqual(summary['adversary_success_rate'], 1.0)
        self.assertEqual(summary['expected_distance_error'], 0.0)

    def test_encryption_executes_real_round_trip(self):
        runtime = PrivacyRuntime(config(encryption=True), self.topology, 0)
        delay = runtime.transmit(0.0, 'assignment', 'coordinator', 'agent:1', 2)
        record = runtime.records[0]
        self.assertGreater(record['wire_bytes'], record['clear_bytes'])
        self.assertGreater(record['encryption_ns'], 0)
        self.assertGreater(record['decryption_ns'], 0)
        self.assertGreaterEqual(record['padding_bytes'], 1)
        self.assertGreater(record['wire_bytes'], 4096)
        self.assertGreater(delay, 0.0)
        self.assertEqual(runtime.summary()['expected_distance_error'], '')

    def test_obfuscation_executes_real_masking_round_trip(self):
        runtime = PrivacyRuntime(config(obfuscation=True), self.topology, 0)
        delay = runtime.transmit(0.0, 'assignment', 'coordinator', 'agent:1', 2)
        record = runtime.records[0]
        self.assertGreater(record['obfuscation_ns'], 0)
        self.assertGreater(record['deobfuscation_ns'], 0)
        self.assertEqual(record['cloaking_candidates'], 3)
        self.assertGreater(delay, 0.0)
        self.assertEqual(runtime.summary()['adversary_success_rate'], '')
        self.assertGreater(runtime.summary()['expected_distance_error'], 0.0)

    def test_encryption_rejects_tampered_ciphertext(self):
        runtime = PrivacyRuntime(config(encryption=True), self.topology, 0)
        envelope = runtime._encrypt(b'protected', 'coordinator', 'agent:1', 'assignment')
        changed = bytearray(envelope['ciphertext'])
        changed[-1] ^= 1
        envelope['ciphertext'] = bytes(changed)
        with self.assertRaises(InvalidSignature):
            runtime._decrypt(envelope)

    def test_obfuscated_destinations_remain_distinct(self):
        topology = {node: [] for node in range(25)}
        runtime = PrivacyRuntime(config(obfuscation=True), topology, 0)
        masks = [runtime._mask(destination) for destination in topology]
        self.assertEqual(len(set(masks)), len(topology))
        self.assertNotEqual(runtime._mask(1), runtime._mask(1))
        for destination in topology:
            runtime.transmit(0.0, 'assignment', 'coordinator', 'agent:1', destination)

    def test_combined_condition_writes_both_metrics(self):
        runtime = PrivacyRuntime(config(encryption=True, obfuscation=True), self.topology, 0)
        runtime.transmit(0.0, 'assignment', 'coordinator', 'agent:1', 2)
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / 'simulation_log.csv'
            runtime.write(logfile)
            self.assertTrue((Path(directory) / 'simulation_log_privacy_messages.csv').exists())
            self.assertTrue((Path(directory) / 'simulation_log_privacy_summary.csv').exists())
        summary = runtime.summary()
        self.assertNotEqual(summary['adversary_success_rate'], '')
        self.assertNotEqual(summary['expected_distance_error'], '')


if __name__ == '__main__':
    unittest.main()
