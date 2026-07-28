"""Contextual LinUCB policy for Dynamic Adaptation.

The policy separates observable operating conditions from the performance
objective. Faults, network probes, workload, and anomaly signals are context
features: they describe the conditions under which a coordination mechanism is
chosen.
The reward contains only task outcomes that the choice is intended to improve.
Its objective mode is configurable: completion only, relative latency only, a
weighted combination, or completion-constrained latency optimisation.
"""

from __future__ import annotations

import math
import random

import numpy as np


ACTIONS = (
    "centralized-impprox",
    "semi-decentralized",
    "decentralized",
)

ACTION_LABELS = {
    "centralized-impprox": "CE",
    "semi-decentralized": "SD",
    "decentralized": "FD",
}

BANDIT_POLICIES = {"bandit", "contextual-bandit", "conservative-bandit", "online-learning"}
OBJECTIVE_MODES = {
    "completion-only",
    "latency-only",
    "weighted",
    "completion-constrained",
}

# Each feature describes an observable operating condition available before
# choosing the next coordination mechanism. Performance outcomes are not
# features: completion, latency, and backlog are affected by the preceding
# action and are therefore reserved for the reward.
# Configured experimental factors such as FAIL_PROB and N_MALICIOUS are
# deliberately absent: the policy may only observe their runtime effects.
FEATURE_NAMES = (
    "bias",
    "arrival_rate_norm",
    "failure_norm",
    "network_probe_loss_rate",
    "suspicion_norm",
)


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


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def safe_float(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def build_context(cfg, metrics, latency, current_architecture):
    """Build action-independent context from monitored operating evidence."""
    metrics = metrics or {}

    latency_ref = max(1e-9, cfg_float(
        cfg,
        "BANDIT_LATENCY_REF",
        cfg_float(cfg, "LATENCY_THRESHOLD_HIGH", 40.0),
    ))
    failure_ref = max(1e-9, cfg_float(
        cfg,
        "BANDIT_FAILURE_REF",
        cfg_float(cfg, "ADAPTATION_FAILURE_REF", 0.50),
    ))
    arrival_ref = max(1.0, cfg_float(cfg, "BANDIT_CREATED_TASKS_REF", 40.0))
    suspicion_ref = max(1.0, cfg_float(cfg, "BANDIT_SUSPICION_REF", 10.0))

    latency_available = latency is not None
    latency_value = safe_float(latency, 0.0) if latency_available else 0.0

    terminal_tasks = max(0, int(safe_float(metrics.get("terminal_tasks_window"), 0.0)))
    completion_available = bool(metrics.get("completion_available", terminal_tasks > 0))
    completion_rate = safe_float(metrics.get("completion_rate"), 0.0)
    if not completion_available:
        completion_rate = 0.0

    created_window = max(0.0, safe_float(metrics.get("created_window"), 0.0))
    failure_rate = max(0.0, safe_float(metrics.get("failure_rate"), 0.0))
    network_probe_loss_rate = clamp(max(0.0, safe_float(
        metrics.get("network_probe_loss_rate"), 0.0,
    )))
    suspicious_signals = max(0.0, safe_float(
        metrics.get("suspicious_signals_window"), 0.0,
    ))

    context = {
        "completion_rate": completion_rate if completion_available else None,
        "completion_available": completion_available,
        "terminal_tasks_window": terminal_tasks,
        "latency": latency_value if latency_available else None,
        "latency_available": latency_available,
        "latency_norm": clamp(latency_value / latency_ref) if latency_available else 0.0,
        "created_window": created_window,
        "arrival_rate_norm": clamp(created_window / arrival_ref),
        "failure_rate": failure_rate,
        "failure_norm": clamp(failure_rate / failure_ref),
        "network_probe_loss_rate": network_probe_loss_rate,
        "suspicious_signals_window": suspicious_signals,
        "suspicion_norm": clamp(suspicious_signals / suspicion_ref),
        "current_architecture": current_architecture,
    }
    context["features"] = [context[name] if name != "bias" else 1.0 for name in FEATURE_NAMES]
    return context


def context_reward(cfg, context):
    """Return the configured performance-objective reward for one action window.

    Completion is measured over terminal task outcomes in the rolling monitoring
    window: delivered / (delivered + expired).  This avoids treating still
    pending tasks as successful and keeps the feedback bounded.  Pending work,
    faults, and message loss remain context only; including them in the reward
    would reward an action for a benign environment it did not cause.
    """
    terminal_tasks = max(0, int(safe_float(context.get("terminal_tasks_window"), 0.0)))
    min_outcomes = max(1, cfg_int(cfg, "BANDIT_MIN_TERMINAL_OUTCOMES", 3))
    completion_available = bool(context.get("completion_available"))
    latency_available = bool(context.get("latency_available"))
    target = clamp(cfg_float(cfg, "BANDIT_COMPLETION_TARGET", 0.65), 1e-6, 1.0)
    objective_mode = str(getattr(cfg, "BANDIT_OBJECTIVE_MODE", "completion-constrained")).strip().lower()
    if objective_mode not in OBJECTIVE_MODES:
        raise ValueError(
            "BANDIT_OBJECTIVE_MODE must be one of "
            f"{', '.join(sorted(OBJECTIVE_MODES))}; got {objective_mode!r}."
        )
    completion_weight = clamp(cfg_float(cfg, "BANDIT_COMPLETION_WEIGHT", 0.5))
    details = {
        "reward_version": "completion-constrained-v1",
        "reward_ready": False,
        "reward_mode": "insufficient_terminal_outcomes",
        "objective_mode": objective_mode,
        "completion_weight": completion_weight,
        "completion_target": target,
        "completion_rate": context.get("completion_rate"),
        "terminal_tasks_window": terminal_tasks,
        "latency_norm": context.get("latency_norm") if latency_available else None,
        "completion_deficit": None,
        "switch_penalty": 0.0,
    }

    needs_completion = (
        objective_mode in {"completion-only", "completion-constrained"}
        or (objective_mode == "weighted" and completion_weight > 0.0)
    )
    needs_latency = (
        objective_mode == "latency-only"
        or (objective_mode == "weighted" and completion_weight < 1.0)
    )
    if needs_completion and (not completion_available or terminal_tasks < min_outcomes):
        return None, details
    if needs_latency and not latency_available:
        details["reward_mode"] = "insufficient_latency_observations"
        return None, details

    completion = clamp(safe_float(context.get("completion_rate"), 0.0))
    deficit = max(0.0, target - completion) / target
    details["reward_ready"] = True
    details["completion_deficit"] = deficit
    latency_quality = 0.5
    if latency_available:
        latency_quality = 1.0 - clamp(safe_float(context.get("latency_norm"), 1.0))
    details["latency_quality"] = latency_quality

    if objective_mode == "completion-only":
        reward = completion
        details["reward_mode"] = "completion_optimisation"
    elif objective_mode == "latency-only":
        reward = latency_quality
        details["reward_mode"] = "latency_optimisation"
    elif objective_mode == "weighted":
        reward = completion_weight * completion + (1.0 - completion_weight) * latency_quality
        details["reward_mode"] = "weighted_optimisation"
    elif completion < target:
        # Below the service floor, recovering successful task completion is the
        # only optimisation goal. Latency cannot compensate for failed tasks.
        reward = -deficit
        details["reward_mode"] = "completion_recovery"
    else:
        # Once service is reliable, minimize latency. A small completion margin
        # breaks ties without allowing it to outweigh the latency objective.
        completion_margin = (completion - target) / max(1e-9, 1.0 - target)
        reward = 0.90 * latency_quality + 0.10 * clamp(completion_margin)
        details["reward_mode"] = "latency_optimisation"
        details["completion_margin"] = clamp(completion_margin)

    reward = max(-1.0, min(1.0, reward))
    details["reward"] = reward
    return reward, details


class ConservativeContextualBandit:
    """Linear-UCB contextual bandit with one model per candidate mechanism."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.actions = ACTIONS
        self.feature_names = FEATURE_NAMES
        self.dimension = len(self.feature_names)
        self.ridge = max(1e-9, cfg_float(cfg, "BANDIT_RIDGE", 1.0))
        self.ucb_alpha = max(0.0, cfg_float(cfg, "BANDIT_UCB_ALPHA", 0.35))
        self.epsilon = clamp(cfg_float(cfg, "BANDIT_EXPLORATION_EPSILON", 0.0))
        self.min_epsilon = clamp(cfg_float(cfg, "BANDIT_MIN_EXPLORATION_EPSILON", 0.0))
        self.epsilon_decay = clamp(cfg_float(cfg, "BANDIT_EXPLORATION_DECAY", 1.0), 0.0, 1.0)
        self.improvement_margin = max(0.0, cfg_float(cfg, "BANDIT_IMPROVEMENT_MARGIN", 0.02))
        self.selection_switch_cost = max(0.0, cfg_float(cfg, "BANDIT_SWITCH_PENALTY", 0.03))
        self.initial_samples_per_action = max(0, cfg_int(cfg, "BANDIT_INITIAL_SAMPLES_PER_ACTION", 1))
        self.context_min_samples_per_action = max(
            0, cfg_int(cfg, "BANDIT_CONTEXT_MIN_SAMPLES_PER_ACTION", 1),
        )
        self.context_bin_threshold = clamp(
            cfg_float(cfg, "BANDIT_CONTEXT_BIN_THRESHOLD", 0.5),
        )
        self.design = {action: np.eye(self.dimension) * self.ridge for action in self.actions}
        self.outcomes = {action: np.zeros(self.dimension) for action in self.actions}
        self.counts = {action: 0 for action in self.actions}
        self.context_counts = {action: {} for action in self.actions}

    def _features(self, context):
        return np.asarray(context["features"], dtype=float)

    def _estimate(self, action, features):
        design = self.design[action]
        outcome = self.outcomes[action]
        try:
            theta = np.linalg.solve(design, outcome)
            confidence = math.sqrt(max(0.0, float(features @ np.linalg.solve(design, features))))
        except np.linalg.LinAlgError:
            theta = np.zeros(self.dimension)
            confidence = float(np.linalg.norm(features))
        expected_reward = float(theta @ features)
        ucb = expected_reward + self.ucb_alpha * confidence
        return expected_reward, confidence, ucb

    def values(self, context):
        features = self._features(context)
        estimates = {}
        confidences = {}
        scores = {}
        for action in self.actions:
            estimate, confidence, score = self._estimate(action, features)
            estimates[action] = estimate
            confidences[action] = confidence
            scores[action] = score
        return estimates, confidences, scores

    def update(self, action, context, reward):
        if action not in self.actions or context is None or reward is None:
            return None
        features = self._features(context)
        expected_reward, confidence, _ = self._estimate(action, features)
        self.design[action] += np.outer(features, features)
        self.outcomes[action] += float(reward) * features
        self.counts[action] += 1
        context_key = self._context_key(context)
        self.context_counts[action][context_key] = self.context_counts[action].get(context_key, 0) + 1
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        return {
            "updated_action": action,
            "prediction_before_update": expected_reward,
            "prediction_error": float(reward) - expected_reward,
            "confidence_before_update": confidence,
            "updates_for_action": self.counts[action],
        }

    def _least_observed_action(self, candidates):
        return min(candidates, key=lambda action: (self.counts[action], self.actions.index(action)))

    def _initial_sample_action(self):
        candidates = [
            action for action in self.actions
            if self.counts[action] < self.initial_samples_per_action
        ]
        return self._least_observed_action(candidates) if candidates else None

    def _context_key(self, context):
        """Coarsely identify a monitored operating condition for warm-up only."""
        return tuple(
            int(safe_float(context.get(feature), 0.0) >= self.context_bin_threshold)
            for feature in (
                "arrival_rate_norm",
                "failure_norm",
                "network_probe_loss_rate",
                "suspicion_norm",
            )
        )

    def _context_sample_action(self, context):
        if self.context_min_samples_per_action <= 0:
            return None
        context_key = self._context_key(context)
        candidates = [
            action for action in self.actions
            if self.context_counts[action].get(context_key, 0) < self.context_min_samples_per_action
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda action: (self.context_counts[action].get(context_key, 0), self.counts[action], self.actions.index(action)),
        )

    def select(self, context, current_architecture):
        estimates, confidences, raw_scores = self.values(context)
        scores = {
            action: raw_scores[action] - (self.selection_switch_cost if action != current_architecture else 0.0)
            for action in self.actions
        }
        current_value = scores.get(current_architecture, 0.0)
        greedy_architecture = max(self.actions, key=lambda action: (scores[action], -self.counts[action]))
        candidate = greedy_architecture
        explored = False
        initial_sampling = False
        reason = "linucb"

        initial_action = self._initial_sample_action()
        if initial_action is not None:
            candidate = initial_action
            explored = True
            initial_sampling = True
            reason = "initial_balanced_exploration"
        else:
            context_action = self._context_sample_action(context)
            if context_action is not None:
                candidate = context_action
                explored = True
                initial_sampling = True
                reason = "context_balanced_exploration"
        if not initial_sampling and random.random() < self.epsilon:
            candidate = self._least_observed_action(self.actions)
            explored = True
            reason = "epsilon_least_observed"

        if candidate != current_architecture and not initial_sampling:
            candidate_value = scores[candidate]
            if candidate_value < current_value + self.improvement_margin:
                candidate = current_architecture
                reason = "insufficient_ucb_improvement"

        return {
            "candidate_architecture": candidate,
            "greedy_architecture": greedy_architecture,
            "scores": scores,
            "raw_ucb_values": raw_scores,
            "estimated_values": estimates,
            "confidence_bounds": confidences,
            "selection_switch_cost": self.selection_switch_cost,
            "epsilon": self.epsilon,
            "explored": explored,
            "initial_sampling": initial_sampling,
            "improvement_margin": self.improvement_margin,
            "reason": reason,
            "critical_override": False,
            "fd_pressure": False,
            "critical_reason": None,
            "context_key": self._context_key(context),
        }
