import csv
import json
import platform
import secrets
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
        self.padding_bytes = max(256, int(getattr(cfg, 'PRIVACY_PADDING_BYTES', 8192)))
        self.cloaking_size = max(2, int(getattr(cfg, 'PRIVACY_CLOAKING_SIZE', 25)))
        self.obfuscation_token_bytes = max(64, int(getattr(cfg, 'PRIVACY_OBFUSCATION_TOKEN_BYTES', 256)))
        self.signing_rotation_messages = max(1, int(getattr(cfg, 'PRIVACY_SIGNING_KEY_ROTATION_MESSAGES', 32)))
        self.records = []
        self.mask_to_value = {}
        self.signing_keys = {}
        self.signing_counts = {}
        self.obfuscation_secret = secrets.token_hex(32)
        self.hash_string = None
        self.crypto = None
        self.prior_destination = self._graph_medoid()
        if self.encryption_enabled:
            try:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            except ImportError as exc:
                raise RuntimeError('Encryption requires the cryptography package.') from exc
            self.crypto = {
                'hashes': hashes,
                'Ed25519PrivateKey': Ed25519PrivateKey,
                'Ed25519PublicKey': Ed25519PublicKey,
                'X25519PrivateKey': X25519PrivateKey,
                'X25519PublicKey': X25519PublicKey,
                'AESGCM': AESGCM,
                'HKDF': HKDF,
            }
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

    def _mask(self, value, label='destination', salt=None, width=None):
        salt = salt or secrets.token_hex(16)
        masked = str(self.hash_string(f'{self.obfuscation_secret}:{salt}:{label}:{value}'))
        if width and len(masked) < width:
            remaining = width - len(masked)
            masked += secrets.token_hex((remaining + 1) // 2)[:remaining]
        self.mask_to_value[masked] = value
        return masked

    def _cloaking_candidates(self, destination):
        nodes = sorted(self.connections)
        if destination not in nodes:
            nodes.append(destination)
        distances = self._distances_from(destination)
        alternatives = sorted(
            (node for node in nodes if node != destination),
            key=lambda node: (-distances.get(node, len(nodes)), node),
        )
        return [destination] + alternatives[:max(0, min(self.cloaking_size, len(nodes)) - 1)]

    def _signing_key(self, sender):
        count = self.signing_counts.get(sender, 0)
        if sender not in self.signing_keys or count >= self.signing_rotation_messages:
            self.signing_keys[sender] = self.crypto['Ed25519PrivateKey'].generate()
            count = 0
        self.signing_counts[sender] = count + 1
        return self.signing_keys[sender]

    def _derive_key(self, shared_secret, salt, info):
        return self.crypto['HKDF'](
            algorithm=self.crypto['hashes'].SHA256(),
            length=32,
            salt=salt,
            info=info,
        ).derive(shared_secret)

    def _encrypt(self, payload, sender, receiver, message_type):
        started = time.perf_counter_ns()
        sender_ephemeral = self.crypto['X25519PrivateKey'].generate()
        receiver_prekey = self.crypto['X25519PrivateKey'].generate()
        sender_public = sender_ephemeral.public_key().public_bytes_raw()
        receiver_public = receiver_prekey.public_key().public_bytes_raw()
        shared_secret = sender_ephemeral.exchange(receiver_prekey.public_key())
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        aad = json.dumps(
            {'message_type': str(message_type), 'sender': str(sender), 'receiver': str(receiver)},
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
        key = self._derive_key(shared_secret, salt, aad)
        content = len(payload).to_bytes(4, 'big') + payload
        padding_size = (-len(content)) % self.padding_bytes
        padded = content + secrets.token_bytes(padding_size)
        ciphertext = self.crypto['AESGCM'](key).encrypt(nonce, padded, aad)
        signer = self._signing_key(str(sender))
        signing_public = signer.public_key().public_bytes_raw()
        signed = sender_public + receiver_public + signing_public + salt + nonce + ciphertext + aad
        signature = signer.sign(signed)
        wire_bytes = sender_public + receiver_public + signing_public + salt + nonce + signature + ciphertext
        encryption_ns = time.perf_counter_ns() - started
        return {
            'wire_bytes': wire_bytes,
            'sender_public': sender_public,
            'receiver_private': receiver_prekey,
            'receiver_public': receiver_public,
            'signing_public': signing_public,
            'salt': salt,
            'nonce': nonce,
            'signature': signature,
            'ciphertext': ciphertext,
            'aad': aad,
            'padding_size': padding_size,
            'encryption_ns': encryption_ns,
        }

    def _decrypt(self, envelope):
        started = time.perf_counter_ns()
        signed = (
            envelope['sender_public']
            + envelope['receiver_public']
            + envelope['signing_public']
            + envelope['salt']
            + envelope['nonce']
            + envelope['ciphertext']
            + envelope['aad']
        )
        self.crypto['Ed25519PublicKey'].from_public_bytes(envelope['signing_public']).verify(envelope['signature'], signed)
        sender_public = self.crypto['X25519PublicKey'].from_public_bytes(envelope['sender_public'])
        shared_secret = envelope['receiver_private'].exchange(sender_public)
        key = self._derive_key(shared_secret, envelope['salt'], envelope['aad'])
        padded = self.crypto['AESGCM'](key).decrypt(envelope['nonce'], envelope['ciphertext'], envelope['aad'])
        content_size = int.from_bytes(padded[:4], 'big')
        payload = padded[4:4 + content_size]
        decryption_ns = time.perf_counter_ns() - started
        return payload, decryption_ns

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
        candidate_count = 0
        if self.obfuscation_enabled:
            started = time.perf_counter_ns()
            salt = secrets.token_hex(16)
            candidates = self._cloaking_candidates(actual_destination)
            protected_payload['destination'] = self._mask(actual_destination, 'destination', salt, self.obfuscation_token_bytes)
            protected_payload['destination_candidates'] = [
                self._mask(node, 'candidate', salt, self.obfuscation_token_bytes)
                for node in candidates
            ]
            protected_payload['sender'] = self._mask(str(sender), 'sender', salt)
            protected_payload['receiver'] = self._mask(str(receiver), 'receiver', salt)
            if 'item_id' in protected_payload:
                protected_payload['item_id'] = self._mask(protected_payload['item_id'], 'item_id', salt)
            candidate_count = len(candidates)
            obfuscation_ns = time.perf_counter_ns() - started
        visible_bytes = json.dumps(protected_payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        encryption_ns = 0
        decryption_ns = 0
        padding_size = 0
        wire_bytes = visible_bytes
        envelope = None
        if self.encryption_enabled:
            envelope = self._encrypt(visible_bytes, sender, receiver, message_type)
            wire_bytes = envelope['wire_bytes']
            encryption_ns = envelope['encryption_ns']
        communication_estimate = self.prior_destination
        if not self.encryption_enabled:
            observed = json.loads(wire_bytes.decode('utf-8'))
            if isinstance(observed.get('destination'), int):
                communication_estimate = observed['destination']
        received_bytes = wire_bytes
        if self.encryption_enabled:
            received_bytes, decryption_ns = self._decrypt(envelope)
            padding_size = envelope['padding_size']
        received_payload = json.loads(received_bytes.decode('utf-8'))
        data_estimate = self.prior_destination
        if isinstance(received_payload.get('destination'), int):
            data_estimate = received_payload['destination']
        if self.obfuscation_enabled:
            started = time.perf_counter_ns()
            received_payload['destination'] = self.mask_to_value[str(received_payload['destination'])]
            received_payload['sender'] = self.mask_to_value[str(received_payload['sender'])]
            received_payload['receiver'] = self.mask_to_value[str(received_payload['receiver'])]
            if 'item_id' in received_payload:
                received_payload['item_id'] = self.mask_to_value[str(received_payload['item_id'])]
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
            'padding_bytes': padding_size,
            'cloaking_candidates': candidate_count,
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
            'privacy_padding_bytes': self.padding_bytes if self.encryption_enabled else 0,
            'privacy_cloaking_size': self.cloaking_size if self.obfuscation_enabled else 0,
            'privacy_obfuscation_token_bytes': self.obfuscation_token_bytes if self.obfuscation_enabled else 0,
            'privacy_signing_key_rotation_messages': self.signing_rotation_messages if self.encryption_enabled else 0,
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
