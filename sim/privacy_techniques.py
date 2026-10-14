import csv
import json
import platform
import time
from collections import deque
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return ''


class PrivacyRuntime:
    def __init__(self, cfg, connections, source):
        self.cfg = cfg
        self.encryption_enabled = bool(getattr(cfg, 'PRIVACY_ENCRYPTION_ENABLED', False))
        self.obfuscation_enabled = bool(getattr(cfg, 'PRIVACY_OBFUSCATION_ENABLED', False))
        self.enabled = bool(
            getattr(cfg, 'PRIVACY_METRICS_ENABLED', False)
            or self.encryption_enabled
            or self.obfuscation_enabled
        )
        self.connections = {int(node): [int(neighbor) for neighbor in neighbors] for node, neighbors in connections.items()}
        self.source = int(source)
        self.link_bytes_per_second = max(1.0, float(getattr(cfg, 'PRIVACY_LINK_BYTES_PER_SECOND', 125000.0)))
        self.records = []
        self.mask_to_destination = {}
        self.destination_to_mask = {}
        self.fernet = None
        self.hash_string = None
        self.prior_destination = self._graph_medoid()
        if self.encryption_enabled:
            try:
                from cryptography.fernet import Fernet
            except ImportError as exc:
                raise RuntimeError('Encryption requires the cryptography package.') from exc
            self.fernet = Fernet(Fernet.generate_key())
        if self.obfuscation_enabled:
            try:
                from msticpy.data.data_obfus import hash_string
            except ImportError as exc:
                raise RuntimeError('Data obfuscation requires the msticpy package.') from exc
            self.hash_string = hash_string

    @property
    def technique(self):
        if self.encryption_enabled and self.obfuscation_enabled:
            return 'encryption+obfuscation'
        if self.encryption_enabled:
            return 'encryption'
        if self.obfuscation_enabled:
            return 'obfuscation'
        return 'none'

    def _distances_from(self, start):
        distances = {int(start): 0}
        queue = deque([int(start)])
        while queue:
            node = queue.popleft()
            for neighbor in self.connections.get(node, []):
                if neighbor not in distances:
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)
        return distances

    def _graph_medoid(self):
        candidates = sorted(self.connections)
        if not candidates:
            return self.source
        scored = []
        for candidate in candidates:
            distances = self._distances_from(candidate)
            score = sum(distances.get(node, len(candidates)) for node in candidates)
            scored.append((score, candidate))
        return min(scored)[1]

    def _distance(self, left, right):
        return self._distances_from(int(left)).get(int(right), len(self.connections))

    def _mask(self, destination):
        destination = int(destination)
        if destination not in self.destination_to_mask:
            masked = str(self.hash_string(str(destination)))
            self.destination_to_mask[destination] = masked
            self.mask_to_destination[masked] = destination
        return self.destination_to_mask[destination]

    def transmit(self, sim_time, message_type, sender, receiver, destination, fields=None):
        if not self.enabled:
            return 0.0
        actual_destination = int(destination)
        payload = {
            'message_type': str(message_type),
            'sender': str(sender),
            'receiver': str(receiver),
            'destination': actual_destination,
            **(fields or {}),
        }
        clear_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        obfuscation_ns = 0
        deobfuscation_ns = 0
        protected_payload = dict(payload)
        if self.obfuscation_enabled:
            started = time.perf_counter_ns()
            protected_payload['destination'] = self._mask(actual_destination)
            obfuscation_ns = time.perf_counter_ns() - started
        visible_bytes = json.dumps(protected_payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        encryption_ns = 0
        decryption_ns = 0
        wire_bytes = visible_bytes
        if self.encryption_enabled:
            started = time.perf_counter_ns()
            wire_bytes = self.fernet.encrypt(visible_bytes)
            encryption_ns = time.perf_counter_ns() - started
        communication_estimate = self.prior_destination
        if not self.encryption_enabled:
            observed = json.loads(wire_bytes.decode('utf-8'))
            if isinstance(observed.get('destination'), int):
                communication_estimate = observed['destination']
        received_bytes = wire_bytes
        if self.encryption_enabled:
            started = time.perf_counter_ns()
            received_bytes = self.fernet.decrypt(wire_bytes)
            decryption_ns = time.perf_counter_ns() - started
        received_payload = json.loads(received_bytes.decode('utf-8'))
        data_estimate = self.prior_destination
        if isinstance(received_payload.get('destination'), int):
            data_estimate = received_payload['destination']
        if self.obfuscation_enabled:
            started = time.perf_counter_ns()
            received_payload['destination'] = self.mask_to_destination[str(received_payload['destination'])]
            deobfuscation_ns = time.perf_counter_ns() - started
        if int(received_payload['destination']) != actual_destination:
            raise RuntimeError('The authorized receiver could not recover the destination.')
        processing_ns = encryption_ns + decryption_ns + obfuscation_ns + deobfuscation_ns
        size_overhead_seconds = max(0, len(wire_bytes) - len(clear_bytes)) / self.link_bytes_per_second
        added_delay_seconds = processing_ns / 1_000_000_000.0 + size_overhead_seconds
        self.records.append({
            'sim_time': float(sim_time),
            'architecture': self.cfg.current_architecture,
            'technique': self.technique,
            'message_type': str(message_type),
            'sender': str(sender),
            'receiver': str(receiver),
            'actual_destination': actual_destination,
            'communication_observer_estimate': int(communication_estimate),
            'communication_observer_success': int(int(communication_estimate) == actual_destination),
            'data_observer_estimate': int(data_estimate),
            'data_observer_distance_error': self._distance(data_estimate, actual_destination),
            'clear_bytes': len(clear_bytes),
            'wire_bytes': len(wire_bytes),
            'encryption_ns': encryption_ns,
            'decryption_ns': decryption_ns,
            'obfuscation_ns': obfuscation_ns,
            'deobfuscation_ns': deobfuscation_ns,
            'size_overhead_seconds': size_overhead_seconds,
            'added_delay_seconds': added_delay_seconds,
        })
        return added_delay_seconds

    def summary(self):
        count = len(self.records)
        successes = sum(row['communication_observer_success'] for row in self.records)
        distance_total = sum(row['data_observer_distance_error'] for row in self.records)
        processing_ns = sum(
            row['encryption_ns'] + row['decryption_ns'] + row['obfuscation_ns'] + row['deobfuscation_ns']
            for row in self.records
        )
        matched_asr = successes / count if count and (self.encryption_enabled or self.technique == 'none') else ''
        matched_distance = distance_total / count if count and (self.obfuscation_enabled or self.technique == 'none') else ''
        return {
            'architecture': self.cfg.current_architecture,
            'technique': self.technique,
            'encryption_enabled': self.encryption_enabled,
            'obfuscation_enabled': self.obfuscation_enabled,
            'message_count': count,
            'adversary_success_rate': matched_asr,
            'expected_distance_error': matched_distance,
            'communication_observer_success_rate_all_conditions': successes / count if count else '',
            'data_observer_mean_distance_error_all_conditions': distance_total / count if count else '',
            'clear_bytes_total': sum(row['clear_bytes'] for row in self.records),
            'wire_bytes_total': sum(row['wire_bytes'] for row in self.records),
            'privacy_processing_seconds': processing_ns / 1_000_000_000.0,
            'privacy_added_delay_seconds': sum(row['added_delay_seconds'] for row in self.records),
            'privacy_link_bytes_per_second': self.link_bytes_per_second,
            'observer_prior_destination': self.prior_destination,
            'python_version': platform.python_version(),
            'cryptography_version': _package_version('cryptography') if self.encryption_enabled else '',
            'msticpy_version': _package_version('msticpy') if self.obfuscation_enabled else '',
        }

    def write(self, logfile):
        if not self.enabled:
            return
        log_path = Path(logfile)
        message_path = log_path.with_name(f'{log_path.stem}_privacy_messages.csv')
        summary_path = log_path.with_name(f'{log_path.stem}_privacy_summary.csv')
        message_path.parent.mkdir(parents=True, exist_ok=True)
        if self.records:
            with message_path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(self.records[0]))
                writer.writeheader()
                writer.writerows(self.records)
        summary = self.summary()
        with summary_path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary))
            writer.writeheader()
            writer.writerow(summary)
