import unittest
from types import SimpleNamespace

from sim.contextual_bandit import (
    ACTIONS,
    FEATURE_NAMES,
    ConservativeContextualBandit,
    build_context,
    context_reward,
)


def cfg(**overrides):
    values = {
        "LATENCY_THRESHOLD_HIGH": 100.0,
        "ADAPTATION_PENDING_REF": 1.0,
        "ADAPTATION_FAILURE_REF": 0.5,
        "BANDIT_COMPLETION_TARGET": 0.65,
        "BANDIT_MIN_TERMINAL_OUTCOMES": 3,
        "BANDIT_SWITCH_PENALTY": 0.03,
        "BANDIT_RIDGE": 1.0,
        "BANDIT_UCB_ALPHA": 0.35,
        "BANDIT_EXPLORATION_EPSILON": 0.0,
        "BANDIT_MIN_EXPLORATION_EPSILON": 0.0,
        "BANDIT_EXPLORATION_DECAY": 1.0,
        "BANDIT_IMPROVEMENT_MARGIN": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def metrics(*, delivered=8, expired=2, **overrides):
    values = {
        "terminal_tasks_window": delivered + expired,
        "completion_available": delivered + expired > 0,
        "completion_rate": delivered / (delivered + expired) if delivered + expired else 0.0,
        "pending_ratio": 0.2,
        "failure_rate": 0.1,
        "message_loss_rate": 0.1,
        "network_probe_loss_rate": 0.1,
        "suspicion_rate": 0.0,
        "coordinator_outage_rate": 0.0,
    }
    values.update(overrides)
    return values


class CompletionConstrainedBanditTest(unittest.TestCase):
    def test_completion_below_target_has_negative_reward_regardless_of_latency(self):
        policy_cfg = cfg()
        context = build_context(
            policy_cfg,
            metrics(delivered=3, expired=7, failure_rate=0.0, message_loss_rate=0.0),
            latency=1.0,
            current_architecture=ACTIONS[0],
        )

        reward, details = context_reward(policy_cfg, context)

        self.assertLess(reward, 0.0)
        self.assertEqual(details["reward_mode"], "completion_recovery")
        self.assertAlmostEqual(details["completion_deficit"], (0.65 - 0.3) / 0.65)

    def test_latency_decides_only_after_completion_target_is_met(self):
        policy_cfg = cfg()
        fast = build_context(policy_cfg, metrics(delivered=8, expired=2), 10.0, ACTIONS[0])
        slow = build_context(policy_cfg, metrics(delivered=8, expired=2), 90.0, ACTIONS[0])

        fast_reward, fast_details = context_reward(policy_cfg, fast)
        slow_reward, slow_details = context_reward(policy_cfg, slow)

        self.assertGreater(fast_reward, slow_reward)
        self.assertEqual(fast_details["reward_mode"], "latency_optimisation")
        self.assertEqual(slow_details["reward_mode"], "latency_optimisation")

    def test_no_reward_is_fabricated_without_terminal_task_outcomes(self):
        policy_cfg = cfg()
        context = build_context(policy_cfg, metrics(delivered=0, expired=0), 10.0, ACTIONS[0])

        reward, details = context_reward(policy_cfg, context)

        self.assertIsNone(reward)
        self.assertFalse(details["reward_ready"])

    def test_initial_linucb_scores_have_no_architecture_specific_prior(self):
        policy_cfg = cfg()
        policy = ConservativeContextualBandit(policy_cfg)
        context = build_context(policy_cfg, metrics(), 10.0, ACTIONS[0])

        _, _, scores = policy.values(context)

        self.assertEqual(len({round(value, 12) for value in scores.values()}), 1)

    def test_update_is_attributed_to_the_action_selected_in_its_context(self):
        policy_cfg = cfg()
        policy = ConservativeContextualBandit(policy_cfg)
        context = build_context(policy_cfg, metrics(), 10.0, ACTIONS[0])

        update = policy.update(ACTIONS[1], context, 0.8)

        self.assertEqual(update["updated_action"], ACTIONS[1])
        self.assertEqual(policy.counts[ACTIONS[1]], 1)
        self.assertEqual(policy.counts[ACTIONS[0]], 0)

    def test_initial_exploration_covers_each_mechanism_without_a_regime_prior(self):
        policy_cfg = cfg(BANDIT_INITIAL_SAMPLES_PER_ACTION=1)
        policy = ConservativeContextualBandit(policy_cfg)
        context = build_context(policy_cfg, metrics(), 10.0, ACTIONS[0])

        first = policy.select(context, ACTIONS[0])
        policy.update(ACTIONS[0], context, 0.8)
        second = policy.select(context, ACTIONS[0])

        self.assertEqual(first["candidate_architecture"], ACTIONS[0])
        self.assertTrue(first["initial_sampling"])
        self.assertEqual(second["candidate_architecture"], ACTIONS[1])
        self.assertTrue(second["initial_sampling"])

    def test_context_excludes_action_dependent_performance_outcomes(self):
        policy_cfg = cfg()
        calm = build_context(policy_cfg, metrics(delivered=9, expired=1), 10.0, ACTIONS[0])
        delayed = build_context(policy_cfg, metrics(delivered=3, expired=7), 90.0, ACTIONS[0])

        self.assertNotIn("completion_norm", FEATURE_NAMES)
        self.assertNotIn("latency_norm", FEATURE_NAMES)
        self.assertNotIn("pending_norm", FEATURE_NAMES)
        self.assertEqual(calm["features"], delayed["features"])

    def test_context_normalises_only_observable_runtime_evidence(self):
        policy_cfg = cfg(BANDIT_CREATED_TASKS_REF=40.0, BANDIT_FAILURE_REF=2.5)
        context = build_context(
            policy_cfg,
            metrics(
                created_window=20,
                failure_rate=1.25,
                network_probe_loss_rate=0.5,
                suspicious_signals_window=2.5,
            ),
            latency=10.0,
            current_architecture=ACTIONS[0],
        )

        self.assertEqual(
            context["features"],
            [1.0, 0.5, 0.5, 0.5, 0.25],
        )

    def test_context_coverage_restarts_exploration_for_a_new_observed_condition(self):
        policy_cfg = cfg(
            BANDIT_INITIAL_SAMPLES_PER_ACTION=0,
            BANDIT_CONTEXT_MIN_SAMPLES_PER_ACTION=1,
            BANDIT_CONTEXT_BIN_THRESHOLD=0.5,
        )
        policy = ConservativeContextualBandit(policy_cfg)
        quiet = build_context(
            policy_cfg,
            metrics(created_window=10, failure_rate=0.1, network_probe_loss_rate=0.0),
            10.0,
            ACTIONS[0],
        )
        degraded = build_context(
            policy_cfg,
            metrics(created_window=30, failure_rate=2.0, network_probe_loss_rate=0.8),
            10.0,
            ACTIONS[0],
        )

        first = policy.select(quiet, ACTIONS[0])
        policy.update(first["candidate_architecture"], quiet, 0.8)
        new_condition = policy.select(degraded, ACTIONS[0])

        self.assertEqual(first["reason"], "context_balanced_exploration")
        self.assertNotEqual(new_condition["candidate_architecture"], first["candidate_architecture"])
        self.assertEqual(new_condition["reason"], "context_balanced_exploration")


if __name__ == "__main__":
    unittest.main()
