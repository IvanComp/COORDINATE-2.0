import csv
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

TOPOLOGY_NAME = "GUH73"
N_ROOMS = 73
SOURCE = 0
TARGETS = -1
SIM_TIME_SECONDS = 1 * 30 * 24 * 60 * 60
N_REPETITIONS = 1

ITEM_SPAWNING_TIMES = [150, 120, 90]
N_ROBOTS_LIST = [10,30]
FAIL_PROBS = [0.33, 0.66]
COORD_LABELS = ["DA"]
MSG_LOSS_PROBS = [0.1]
MALICIOUS_PCT_SINGLE =  [0.33, 0.66]

#ITEM_SPAWNING_TIMES = [90, 120, 150]
#N_ROBOTS_LIST = [10, 20, 30]
#FAIL_PROBS = [0.33, 0.66, 1.0]
#COORD_LABELS = ["CE","SD","FD","DA"]
#MSG_LOSS_PROBS = [0.1]
#MALICIOUS_PCT_SINGLE =  [0.0, 0.33, 0.66, 1.0]

COORD_TO_ARCH = {
    "FD": "decentralized",
    "SD": "semi-decentralized",
    "CE": "centralized-impprox",
    "DA": "dynamic-adaptation",
}

BASE_CONFIG = {
    "RESULTS_DIR": "results",
    "SIM_TIME": SIM_TIME_SECONDS,
    "ARCHITECTURE": "centralized-impprox",
    "TOPOLOGY_NAME": TOPOLOGY_NAME,
    "N_ROOMS": N_ROOMS,
    "SOURCE": SOURCE,
    "TARGETS": TARGETS,
    "ITEM_SPAWNING_TIME": 120,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.5, 0.1, 0.4],
    "EXPIRATION_TIME": [-1, -1, -1],
    "EXPIRATION_DISTR": ["exponential", "exponential", "exponential"],
    "N_ROBOTS": 20,
    "N_MALICIOUS": 0,
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
    "FAIL_PROB": 0.05,
    "COMM_FAIL_PROB": 0.003,
    "LOAD_TIME": 1.0,
    "LOAD_DISTR": "exponential",
    "LOAD_TRACE": "_",
    "MOVEMENT_TIME": 5.0,
    "MOVEMENT_DISTR": "exponential",
    "MOVEMENT_TRACE": "_",
    "DROP_TIME": 1.0,
    "DROP_DISTR": "exponential",
    "DROP_TRACE": "_",
    "COMP_TIME": 2.0,
    "COMP_DISTR": "exponential",
    "COMP_TRACE": "_",
    "COMM_TIME": 0.5,
    "COMM_DISTR": "exponential",
    "COMM_TRACE": "_",
    "RECOVERY_TIME": 1800.0,
    "RECOVERY_DISTR": "exponential",
    "RECOVERY_TRACE": "_",
    "LOG_ITEM": True,
    "LOG_DELIVERY": True,
    "LOG_LOAD": True,
    "LOG_DROP": True,
    "LOG_EXPIRE": True,
    "LOG_MOVE": True,
    "LOG_FAIL": True,
    "LOG_RECOVERY": True,
    "LOG_HELP": True,
    "LOG_FAKE": True,
    "LOG_RESCUE": True,
    "ADAPTATION_CHECK_INTERVAL": 3600.0,
}

RESULTS_ROOT = BASE_DIR / "batch_results"
RESULTS_ROOT.mkdir(exist_ok=True)


def collect_overhead_stats(logfile_path):
    """
    Collect overhead statistics from the _overhead.csv file if it exists.
    
    Args:
        logfile_path: Path to the main simulation log file
        
    Returns:
        Dictionary with overhead metrics or None if not a DA experiment
    """
    overhead_csv = str(logfile_path).replace('.csv', '_overhead.csv')
    overhead_path = Path(overhead_csv)
    
    if not overhead_path.exists():
        return None
    
    try:
        with open(overhead_path, 'r') as f:
            reader = csv.DictReader(f)
            samples = list(reader)
            
        if not samples:
            return None
            
        # Calculate statistics
        total_overhead_ms = sum(float(s['total_overhead_ms']) for s in samples)
        rtlola_overhead_ms = sum(float(s['rtlola_query_ms']) for s in samples)
        scoring_overhead_ms = sum(float(s['scoring_ms']) for s in samples)
        num_checks = len(samples)
        num_switches = sum(1 for s in samples if s['switched'] == 'True')
        
        avg_overhead_ms = total_overhead_ms / num_checks if num_checks > 0 else 0
        
        return {
            'num_checks': num_checks,
            'num_switches': num_switches,
            'total_overhead_ms': total_overhead_ms,
            'avg_overhead_ms': avg_overhead_ms,
            'rtlola_overhead_ms': rtlola_overhead_ms,
            'scoring_overhead_ms': scoring_overhead_ms,
        }
    except Exception as e:
        print(f"[WARNING] Could not read overhead stats from {overhead_csv}: {e}")
        return None



def run_single_experiment(cfg_dict, exp_idx, rep_idx):
    exp_name = f"exp_{exp_idx:04d}"
    results_dir = RESULTS_ROOT / exp_name
    results_dir.mkdir(parents=True, exist_ok=True)
    cfg_dict["RESULTS_DIR"] = str(results_dir)
    cfg_dict["SIMTIME_LOGFILE"] = str(RESULTS_ROOT / "simTime.csv")
    logfile_path = results_dir / f"{exp_name}_r{rep_idx}.csv"
    cfg_dict["LOGFILE"] = str(logfile_path)

    cfg_path = results_dir / "config.json"
    with cfg_path.open("w") as f:
        json.dump(cfg_dict, f, indent=2)

    print(
        f"Running {exp_name} (r{rep_idx}) | ARCH={cfg_dict['ARCHITECTURE']} "
    )

    cmd = [sys.executable, "-m", "sim.simulator", str(cfg_path)]
    subprocess.run(cmd, check=False)
    
    # Collect overhead stats if this is a DA experiment
    overhead_stats = collect_overhead_stats(logfile_path)
    return overhead_stats


def main():
    """
    Generate all combinations of experimental parameters and run simulations.
    
    Parameters varied:
    - ITEM_SPAWNING_TIMES: [90, 120, 150]
    - N_ROBOTS_LIST: [10, 20, 30, 40]
    - FAIL_PROBS: [0.0, 0.33, 0.66, 1.0]
    - COORD_LABELS: ["FD", "SD", "CE", "DA"]
    - MSG_LOSS_PROBS: [0.0, 0.33, 0.66, 1.0]
    - MALICIOUS_PCT_SINGLE: [0.0, 0.33, 0.66, 1.0]
    """
    combinations = []
    
    # Generate all combinations
    for item_spawn in ITEM_SPAWNING_TIMES:
        for n_robots in N_ROBOTS_LIST:
            for fail_prob in FAIL_PROBS:
                for coord_label in COORD_LABELS:
                    for msg_loss in MSG_LOSS_PROBS:
                        for mal_pct in MALICIOUS_PCT_SINGLE:
                            combinations.append(
                                (item_spawn, n_robots, mal_pct, fail_prob, coord_label, msg_loss)
                            )
    
    print("=" * 70)
    print("EXPERIMENTAL DESIGN")
    print("=" * 70)
    print(f"Item spawning times:     {ITEM_SPAWNING_TIMES}")
    print(f"Number of robots:        {N_ROBOTS_LIST}")
    print(f"Failure probabilities:   {FAIL_PROBS}")
    print(f"Coordination mechanisms: {COORD_LABELS}")
    print(f"Message loss probs:      {MSG_LOSS_PROBS}")
    print(f"Malicious percentages:   {MALICIOUS_PCT_SINGLE}")
    print("-" * 70)
    print(f"Total combinations:      {len(combinations)}")
    print(f"Repetitions per combo:   {N_REPETITIONS}")
    print(f"Total simulation runs:   {len(combinations) * N_REPETITIONS}")
    print("=" * 70)
    
    print()
    
    # Prepare overhead tracking
    overhead_records = []
    
    # Run all experiments
    exp_idx = 0
    for item_spawn, n_robots, mal_pct, fail_prob, coord_label, msg_loss in combinations:
        exp_idx += 1
        for rep_idx in range(1, N_REPETITIONS + 1):
            cfg = dict(BASE_CONFIG)
            cfg["ITEM_SPAWNING_TIME"] = item_spawn
            cfg["N_ROBOTS"] = n_robots
            cfg["N_MALICIOUS"] = int(round(mal_pct * n_robots))
            cfg["FAIL_PROB"] = fail_prob
            cfg["COMM_FAIL_PROB"] = msg_loss
            cfg["ARCHITECTURE"] = COORD_TO_ARCH[coord_label]
            
            print(f"\n[{exp_idx}/{len(combinations)}] Rep {rep_idx}/{N_REPETITIONS}")
            print(f"  Spawn={item_spawn}s, Robots={n_robots}, Fail={fail_prob:.2f}, "
                  f"Coord={coord_label}, MsgLoss={msg_loss:.2f}, Mal={mal_pct:.2f}")
            
            overhead_stats = run_single_experiment(cfg, exp_idx, rep_idx)
            
            # If this was a DA experiment with overhead data, record it
            if overhead_stats is not None:
                overhead_record = {
                    'exp_id': f"exp_{exp_idx:04d}",
                    'repetition': rep_idx,
                    'coord_mechanism': coord_label,
                    'architecture': COORD_TO_ARCH[coord_label],
                    'item_spawn_time': item_spawn,
                    'n_robots': n_robots,
                    'n_malicious': int(round(mal_pct * n_robots)),
                    'fail_prob': fail_prob,
                    'msg_loss_prob': msg_loss,
                    'malicious_pct': mal_pct,
                    **overhead_stats
                }
                overhead_records.append(overhead_record)
                
                # Print overhead summary for this run
                print(f"  [OVERHEAD] Checks: {overhead_stats['num_checks']}, "
                      f"Switches: {overhead_stats['num_switches']}, "
                      f"Avg: {overhead_stats['avg_overhead_ms']:.2f}ms, "
                      f"Total: {overhead_stats['total_overhead_ms']:.2f}ms")
    
    # Save overhead summary
    if overhead_records:
        overhead_summary_path = RESULTS_ROOT / "overhead_summary.csv"
        try:
            with open(overhead_summary_path, 'w', newline='') as f:
                fieldnames = [
                    'exp_id', 'repetition', 'coord_mechanism', 'architecture',
                    'item_spawn_time', 'n_robots', 'n_malicious', 'fail_prob',
                    'msg_loss_prob', 'malicious_pct', 'num_checks', 'num_switches',
                    'total_overhead_ms', 'avg_overhead_ms', 'rtlola_overhead_ms',
                    'scoring_overhead_ms'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(overhead_records)
            print(f"\n[OVERHEAD] Summary saved to: {overhead_summary_path}")
        except Exception as e:
            print(f"\n[WARNING] Could not save overhead summary: {e}")
    
    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETED")
    print("=" * 70)
    print(f"Results and configs saved in: {RESULTS_ROOT}")
    if overhead_records:
        print(f"DA overhead summary: {RESULTS_ROOT / 'overhead_summary.csv'}")
        print(f"Total DA experiments with overhead data: {len(overhead_records)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
