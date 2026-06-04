"""
Adaptation Overhead Tracking Module

Provides utilities to measure and report the computational overhead
of dynamic adaptation in the COORDINATE 2.0 simulator.
"""

import csv
import os
from typing import List, Dict


def log_overhead_statistics(
    adaptation_check_count: int,
    adaptation_switch_count: int,
    adaptation_overhead_total: float,
    adaptation_overhead_samples: List[Dict],
    wall_time: float,
    logfile: str
):
    """
    Log and save adaptation overhead statistics.
    
    Args:
        adaptation_check_count: Number of adaptation checks performed
        adaptation_switch_count: Number of architecture switches
        adaptation_overhead_total: Total wall-clock time spent on adaptation (seconds)
        adaptation_overhead_samples: List of individual overhead measurements
        wall_time: Total simulation wall time (seconds)
        logfile: Path to the main simulation log file
    """
    if adaptation_check_count == 0:
        return
    
    avg_overhead_ms = (adaptation_overhead_total / adaptation_check_count) * 1000
    overhead_percentage = (adaptation_overhead_total / wall_time) * 100
    
    print("\n" + "="*70)
    print("DYNAMIC ADAPTATION OVERHEAD STATISTICS")
    print("="*70)
    print(f"Total adaptation checks:     {adaptation_check_count}")
    print(f"Architecture switches:       {adaptation_switch_count}")
    print(f"Total overhead time:         {adaptation_overhead_total:.3f}s ({adaptation_overhead_total*1000:.2f}ms)")
    print(f"Average overhead per check:  {avg_overhead_ms:.2f}ms")
    print(f"Overhead as % of wall time:  {overhead_percentage:.3f}%")
    print(f"Total wall time:             {wall_time:.3f}s")
    print("="*70 + "\n")
    
    # Save detailed overhead data to CSV
    overhead_csv = logfile.replace('.csv', '_overhead.csv')
    try:
        with open(overhead_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'sim_time', 'total_overhead_ms', 'rtlola_query_ms',
                'scoring_ms', 'switched', 'latency', 'raw_latency', 'latency_source',
                'threshold_low', 'threshold_high', 'threshold_mode',
                'threshold_history_size', 'performance_score', 'performance_state',
                'fd_pressure', 'recovery_mode',
                'score_latency', 'score_pending', 'score_failure', 'score_message_loss',
                'score_deadline_miss', 'score_throughput', 'score_idle',
                'pending_tasks', 'created_window', 'delivered_window', 'expired_window', 'pending_ratio',
                'failures_window', 'failure_rate',
                'messages_sent', 'messages_lost', 'message_loss_rate',
                'deadline_miss_rate', 'throughput_rate', 'throughput_norm',
                'idle_agents', 'idle_ratio',
                'adaptation_policy',
                'bandit_reward', 'bandit_badness', 'bandit_throughput_bonus',
                'bandit_switch_penalty',
                'bandit_reward_latency', 'bandit_reward_pending',
                'bandit_reward_failure', 'bandit_reward_message_loss',
                'bandit_reward_deadline_miss', 'bandit_reward_idle_when_pending',
                'bandit_updated_action', 'bandit_prediction_before_update',
                'bandit_prediction_error', 'bandit_updates_for_action',
                'bandit_epsilon', 'bandit_explored', 'bandit_improvement_margin',
                'bandit_current_value', 'bandit_selected_value',
                'bandit_value_ce', 'bandit_value_sd', 'bandit_value_fd',
                'bandit_greedy_architecture', 'bandit_critical_reason',
                'context_latency_norm', 'context_latency_missing',
                'context_pending_norm', 'context_failure_norm',
                'context_message_loss_rate', 'context_deadline_miss_rate',
                'context_throughput_norm', 'context_idle_ratio',
                'context_malicious_ratio', 'context_failure_prob',
                'context_comm_loss_prob', 'context_is_ce', 'context_is_sd',
                'context_is_fd',
                'current_architecture', 'candidate_architecture',
                'selected_architecture', 'switch_reason'
            ], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(adaptation_overhead_samples)
        print(f"[OVERHEAD] Detailed overhead data saved to: {os.path.basename(overhead_csv)}")
    except Exception as e:
        print(f"[WARNING] Could not save overhead CSV: {e}")


def calculate_overhead_metrics(adaptation_overhead_samples: List[Dict]) -> Dict:
    """
    Calculate statistical metrics from overhead samples.
    
    Args:
        adaptation_overhead_samples: List of overhead measurements
        
    Returns:
        Dictionary with min, max, mean, median overhead values
    """
    if not adaptation_overhead_samples:
        return {}
    
    total_overheads = [s['total_overhead_ms'] for s in adaptation_overhead_samples]
    rtlola_overheads = [s['rtlola_query_ms'] for s in adaptation_overhead_samples]
    scoring_overheads = [s['scoring_ms'] for s in adaptation_overhead_samples]
    
    return {
        'total_min_ms': min(total_overheads),
        'total_max_ms': max(total_overheads),
        'total_mean_ms': sum(total_overheads) / len(total_overheads),
        'rtlola_mean_ms': sum(rtlola_overheads) / len(rtlola_overheads),
        'scoring_mean_ms': sum(scoring_overheads) / len(scoring_overheads),
        'num_switches': sum(1 for s in adaptation_overhead_samples if s['switched'])
    }
