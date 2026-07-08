"""
Conservative contextual-bandit policy for Dynamic Adaptation.

The policy learns online during a simulation.  It keeps one linear value
estimator per coordination mechanism and updates only the mechanism used in the
previous adaptation window.
"""

import math
import random


ACTIONS = (
    'centralized-impprox',
    'semi-decentralized',
    'decentralized',
)

ACTION_LABELS = {
    'centralized-impprox': 'CE',
    'semi-decentralized': 'SD',
    'decentralized': 'FD',
}

FEATURE_NAMES = (
    'bias',
    'latency_norm',
    'latency_missing',
    'pending_norm',
    'failure_norm',
    'message_loss_rate',
    'deadline_miss_rate',
    'throughput_norm',
    'idle_ratio',
    'malicious_ratio',
    'configured_failure_prob',
    'configured_comm_loss_prob',
    'is_ce',
    'is_sd',
    'is_fd',
)

BANDIT_POLICIES = {'bandit', 'contextual-bandit', 'conservative-bandit', 'online-learning'}


def cfg_float(cfg, name, default):
    try:
        return float(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def cfg_int(cfg, name, default):
    try:
        return int(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def cfg_bool(cfg, name, default):
    value = getattr(cfg, name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def safe_float(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return value


def normalized_bad_weights(cfg):
    weights = {
        'latency': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_LATENCY', 0.20)),
        'pending': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_PENDING', 0.30)),
        'failure': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_FAILURE', 0.05)),
        'message_loss': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_MESSAGE_LOSS', 0.10)),
        'deadline_miss': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_DEADLINE_MISS', 0.30)),
        'throughput_shortfall': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_THROUGHPUT_SHORTFALL', 0.25)),
        'idle_when_pending': max(0.0, cfg_float(cfg, 'BANDIT_WEIGHT_IDLE_WHEN_PENDING', 0.05)),
    }
    total = sum(weights.values())
    if total <= 0.0:
        return {'latency': 1.0, 'pending': 0.0, 'failure': 0.0, 'message_loss': 0.0,
                'deadline_miss': 0.0, 'throughput_shortfall': 0.0, 'idle_when_pending': 0.0}
    return {name: value / total for name, value in weights.items()}


def build_context(cfg, metrics, latency, current_architecture):
    """Build a normalized context dictionary and feature vector."""
    metrics = metrics or {}

    latency_ref = max(1e-9, cfg_float(
        cfg,
        'BANDIT_LATENCY_REF',
        cfg_float(cfg, 'LATENCY_THRESHOLD_HIGH', 40.0),
    ))
    pending_ref = max(1e-9, cfg_float(cfg, 'BANDIT_PENDING_REF',
                                      cfg_float(cfg, 'ADAPTATION_PENDING_REF', 1.0)))
    failure_ref = max(1e-9, cfg_float(cfg, 'BANDIT_FAILURE_REF',
                                      cfg_float(cfg, 'ADAPTATION_FAILURE_REF', 0.50)))

    latency_available = latency is not None
    latency_value = safe_float(latency, 0.0) if latency_available else 0.0
    latency_norm = clamp(latency_value / latency_ref) if latency_available else 0.0

    pending_ratio = max(0.0, safe_float(metrics.get('pending_ratio'), 0.0))
    failure_rate = max(0.0, safe_float(metrics.get('failure_rate'), 0.0))
    message_loss_rate = clamp(max(0.0, safe_float(metrics.get('message_loss_rate'), 0.0)))
    deadline_miss_rate = clamp(max(0.0, safe_float(metrics.get('deadline_miss_rate'), 0.0)))
    throughput_norm = clamp(max(0.0, safe_float(metrics.get('throughput_norm'), 0.0)))
    idle_ratio = clamp(max(0.0, safe_float(metrics.get('idle_ratio'), 0.0)))

    try:
        malicious_ratio = float(getattr(cfg, 'N_MALICIOUS', 0)) / max(1, int(getattr(cfg, 'N_ROBOTS', 1)))
    except (TypeError, ValueError):
        malicious_ratio = 0.0
    malicious_ratio = clamp(malicious_ratio)

    configured_failure_prob = clamp(max(0.0, cfg_float(cfg, 'FAIL_PROB', 0.0)))
    configured_comm_loss_prob = clamp(max(0.0, cfg_float(cfg, 'COMM_FAIL_PROB', 0.0)))

    is_ce = 1.0 if current_architecture == 'centralized-impprox' else 0.0
    is_sd = 1.0 if current_architecture == 'semi-decentralized' else 0.0
    is_fd = 1.0 if current_architecture == 'decentralized' else 0.0

    context = {
        'latency': latency_value if latency_available else None,
        'latency_available': latency_available,
        'latency_norm': latency_norm,
        'latency_missing': 0.0 if latency_available else 1.0,
        'pending_ratio': pending_ratio,
        'pending_norm': clamp(pending_ratio / pending_ref),
        'failure_rate': failure_rate,
        'failure_norm': clamp(failure_rate / failure_ref),
        'message_loss_rate': message_loss_rate,
        'deadline_miss_rate': deadline_miss_rate,
        'throughput_rate': max(0.0, safe_float(metrics.get('throughput_rate'), 0.0)),
        'throughput_norm': throughput_norm,
        'idle_ratio': idle_ratio,
        'malicious_ratio': malicious_ratio,
        'configured_failure_prob': configured_failure_prob,
        'configured_comm_loss_prob': configured_comm_loss_prob,
        'is_ce': is_ce,
        'is_sd': is_sd,
        'is_fd': is_fd,
    }
    context['features'] = [context[name] if name != 'bias' else 1.0 for name in FEATURE_NAMES]
    return context


def context_reward(cfg, context, switched):
    """Compute the reward observed after one adaptation window."""
    weights = normalized_bad_weights(cfg)
    active = {
        'latency': bool(context.get('latency_available')),
        'pending': True,
        'failure': True,
        'message_loss': True,
        'deadline_miss': True,
        'throughput_shortfall': True,
        'idle_when_pending': True,
    }
    components = {
        'latency': context.get('latency_norm', 0.0),
        'pending': context.get('pending_norm', 0.0),
        'failure': context.get('failure_norm', 0.0),
        'message_loss': context.get('message_loss_rate', 0.0),
        'deadline_miss': context.get('deadline_miss_rate', 0.0),
        'throughput_shortfall': 1.0 - context.get('throughput_norm', 0.0),
        'idle_when_pending': context.get('idle_ratio', 0.0) * context.get('pending_norm', 0.0),
    }
    active_weight = sum(weights[name] for name, enabled in active.items() if enabled)
    if active_weight <= 0.0:
        badness = 0.0
    else:
        badness = sum(weights[name] * components[name] for name, enabled in active.items() if enabled) / active_weight

    throughput_bonus = cfg_float(cfg, 'BANDIT_WEIGHT_THROUGHPUT', 0.20) * context.get('throughput_norm', 0.0)
    switch_penalty = cfg_float(cfg, 'BANDIT_SWITCH_PENALTY', 0.03) if switched else 0.0
    reward = 1.0 - badness + throughput_bonus - switch_penalty
    reward = clamp(reward, -1.0, 1.0)

    return reward, {
        'reward': reward,
        'badness': badness,
        'throughput_bonus': throughput_bonus,
        'switch_penalty': switch_penalty,
        'reward_latency': components['latency'],
        'reward_pending': components['pending'],
        'reward_failure': components['failure'],
        'reward_message_loss': components['message_loss'],
        'reward_deadline_miss': components['deadline_miss'],
        'reward_throughput_shortfall': components['throughput_shortfall'],
        'reward_idle_when_pending': components['idle_when_pending'],
    }


def critical_override_architecture(cfg, context):
    """Return a safety override architecture when critical evidence is present."""
    if not cfg_bool(cfg, 'BANDIT_CRITICAL_OVERRIDE', True):
        return None, {}

    pending_ratio = context.get('pending_ratio', 0.0)
    failure_rate = context.get('failure_rate', 0.0)
    message_loss_rate = context.get('message_loss_rate', 0.0)
    malicious_ratio = context.get('malicious_ratio', 0.0)
    configured_comm_loss = context.get('configured_comm_loss_prob', 0.0)

    pending_critical = cfg_float(cfg, 'ADAPTATION_PENDING_CRITICAL_RATIO', 2.0)
    failure_critical = cfg_float(cfg, 'ADAPTATION_FAILURE_CRITICAL_RATE', 1.25)
    message_critical = cfg_float(cfg, 'ADAPTATION_MESSAGE_CRITICAL_LOSS', 0.60)

    pending_is_critical = pending_ratio >= pending_critical
    failure_is_critical = failure_rate >= failure_critical
    message_is_critical = message_loss_rate >= message_critical
    backlog_override_requires_fault = cfg_bool(cfg, 'BANDIT_BACKLOG_OVERRIDE_REQUIRES_FAULT', True)
    if pending_is_critical and backlog_override_requires_fault:
        pending_is_critical = failure_is_critical or message_is_critical

    critical = pending_is_critical or failure_is_critical or message_is_critical
    if not critical:
        return None, {
            'critical_override': False,
            'fd_pressure': False,
            'critical_reason': None,
        }

    fd_pressure = (
        message_loss_rate >= cfg_float(cfg, 'ADAPTATION_FD_MESSAGE_LOSS_THRESHOLD', 0.35)
        or configured_comm_loss >= cfg_float(cfg, 'ADAPTATION_FD_COMM_FAIL_PROB_THRESHOLD', 0.35)
        or malicious_ratio >= cfg_float(cfg, 'ADAPTATION_FD_MALICIOUS_RATIO_THRESHOLD', 0.50)
        or failure_rate >= cfg_float(cfg, 'ADAPTATION_FD_FAILURE_RATE_THRESHOLD', 999.0)
    )
    critical_reason = 'fd_pressure' if fd_pressure else 'critical_congestion'
    return 'decentralized' if fd_pressure else 'semi-decentralized', {
        'critical_override': True,
        'fd_pressure': fd_pressure,
        'critical_reason': critical_reason,
    }


class ConservativeContextualBandit:
    def __init__(self, cfg):
        self.cfg = cfg
        self.actions = ACTIONS
        self.feature_names = FEATURE_NAMES
        self.weights = {}
        self.counts = {}
        for action in self.actions:
            self.weights[action] = [0.0 for _ in self.feature_names]
            self.counts[action] = 0
        self.lr = cfg_float(cfg, 'BANDIT_LEARNING_RATE', 0.05)
        self.l2 = cfg_float(cfg, 'BANDIT_L2', 0.001)
        self.epsilon = cfg_float(cfg, 'BANDIT_EXPLORATION_EPSILON', 0.08)
        self.min_epsilon = cfg_float(cfg, 'BANDIT_MIN_EXPLORATION_EPSILON', 0.02)
        self.epsilon_decay = cfg_float(cfg, 'BANDIT_EXPLORATION_DECAY', 0.995)
        self.improvement_margin = cfg_float(cfg, 'BANDIT_IMPROVEMENT_MARGIN', 0.02)
        self.exploration_margin = cfg_float(cfg, 'BANDIT_EXPLORATION_VALUE_FLOOR', 0.10)

    def values(self, context):
        features = context['features']
        return {
            action: sum(w * x for w, x in zip(self.weights[action], features))
            for action in self.actions
        }

    def update(self, action, context, reward):
        if action not in self.weights or context is None or reward is None:
            return None
        features = context['features']
        prediction = sum(w * x for w, x in zip(self.weights[action], features))
        error = reward - prediction
        updated = []
        for weight, feature in zip(self.weights[action], features):
            updated.append(weight + self.lr * (error * feature - self.l2 * weight))
        self.weights[action] = updated
        self.counts[action] += 1
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        return {
            'updated_action': action,
            'prediction_before_update': prediction,
            'prediction_error': error,
            'updates_for_action': self.counts[action],
        }

    def select(self, context, current_architecture):
        values = self.values(context)
        current_value = values.get(current_architecture, 0.0)
        greedy_arch = max(values, key=values.get)
        selected_arch = greedy_arch
        explored = False
        reason = 'bandit_greedy'

        if random.random() < self.epsilon:
            selected_arch = random.choice(self.actions)
            explored = True
            reason = 'bandit_explore'

        override_arch, override_details = critical_override_architecture(self.cfg, context)
        if override_arch is not None:
            selected_arch = override_arch
            explored = False
            reason = 'critical_override'

        if selected_arch != current_architecture and override_arch is None:
            selected_value = values.get(selected_arch, 0.0)
            if explored:
                if selected_value < current_value - self.exploration_margin:
                    selected_arch = current_architecture
                    reason = 'exploration_rejected_value_floor'
            elif selected_value < current_value + self.improvement_margin:
                selected_arch = current_architecture
                reason = 'conservative_margin'

        return {
            'candidate_architecture': selected_arch,
            'greedy_architecture': greedy_arch,
            'estimated_values': values,
            'scores': values,
            'explored': explored,
            'epsilon': self.epsilon,
            'reason': reason,
            'improvement_margin': self.improvement_margin,
            'critical_override': override_details.get('critical_override', False),
            'fd_pressure': override_details.get('fd_pressure', False),
            'critical_reason': override_details.get('critical_reason'),
        }
