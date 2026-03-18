"""
Scenario A: Time-Varying Variability

This script runs a simulation with changing conditions to demonstrate
Dynamic Adaptation's ability to switch architectures on the fly.

Phases:
1. Normal (0-1200s): Low load, low failure -> Centralized optimal
2. Stress (1200-2400s): High load, high failure -> Decentralized optimal
3. Normal (2400-3600s): Low load, low failure -> Centralized optimal
"""

import json
import subprocess
import sys
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "scenario_variability"
RESULTS_DIR.mkdir(exist_ok=True)

# Configuration with Phases
SCENARIO_CONFIG = {
    "SIM_TIME": 3600,
    "TOPOLOGY_NAME": "GUH73",
    "N_ROOMS": 73,
    "SOURCE": 0,
    "TARGETS": -1,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.5, 0.1, 0.4],
    "EXPIRATION_TIME": [-1, -1, -1],
    "EXPIRATION_DISTR": ["exponential", "exponential", "exponential"],
    "N_ROBOTS": 20,
    "N_MALICIOUS": 3,  # 15%
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
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
    "LOG_LOAD": False,
    "LOG_DROP": False,
    "LOG_EXPIRE": False,
    "LOG_MOVE": False,
    "LOG_FAIL": False,
    "LOG_RECOVERY": False,
    "LOG_HELP": False,
    "LOG_FAKE": False,
    "LOG_RESCUE": False,
    "ADAPTATION_CHECK_INTERVAL": 60.0,  # Check every minute
    "INITIAL_ARCHITECTURE": "centralized-impprox",
    
    # Default parameters (Phase 1 & 3)
    "FAIL_PROB": 0.05,
    "COMM_FAIL_PROB": 0.01,
    "ITEM_SPAWNING_TIME": 120,
    
    # Dynamic Phases
    "PHASES": [
        {
            "start": 0,
            "end": 1200,
            "name": "Normal 1",
            "FAIL_PROB": 0.05,
            "COMM_FAIL_PROB": 0.01,
            "ITEM_SPAWNING_TIME": 120
        },
        {
            "start": 1200,
            "end": 2400,
            "name": "Stress",
            "FAIL_PROB": 0.20,      # High failure
            "COMM_FAIL_PROB": 0.20, # High comm loss (breaks centralized)
            "ITEM_SPAWNING_TIME": 60 # High load
        },
        {
            "start": 2400,
            "end": 3600,
            "name": "Normal 2",
            "FAIL_PROB": 0.05,
            "COMM_FAIL_PROB": 0.01,
            "ITEM_SPAWNING_TIME": 120
        }
    ]
}

ARCHITECTURES = ["centralized-impprox", "decentralized", "dynamic-adaptation"]

def run_simulation(arch):
    """Run simulation for a specific architecture."""
    print(f"Running {arch}...", end=' ', flush=True)
    
    config = dict(SCENARIO_CONFIG)
    config["ARCHITECTURE"] = arch
    config["RESULTS_DIR"] = str(RESULTS_DIR)
    
    config_path = RESULTS_DIR / f"config_{arch}.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    result = subprocess.run(
        [sys.executable, "-m", "sim.simulator", str(config_path)],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr)
        return None
    
    # Find CSV
    csv_files = list(RESULTS_DIR.glob("*.csv"))
    # Filter for this architecture and exclude overhead/simTime
    if arch == "centralized-impprox":
        pattern = "centralizedImpprox"
    elif arch == "decentralized":
        pattern = "fully" # or decentralized
    else:
        pattern = "dynamic-adaptation"
        
    csv_files = [f for f in csv_files if pattern in f.name and not f.name.endswith('_overhead.csv') and not f.name.endswith('simTime.csv')]
    
    # Sort by modification time to get the latest
    csv_files.sort(key=lambda x: x.stat().st_mtime)
    
    if not csv_files:
        print("No CSV found")
        return None
        
    print("DONE")
    return csv_files[-1]

def analyze_results(csv_paths):
    """Analyze results and print phase-based summary."""
    print("\n" + "="*70)
    print("SCENARIO ANALYSIS")
    print("="*70)
    
    phases = [
        (0, 1200, "Phase 1 (Normal)"),
        (1200, 2400, "Phase 2 (Stress)"),
        (2400, 3600, "Phase 3 (Normal)")
    ]
    
    results = {}
    
    for arch, csv_path in csv_paths.items():
        phase_latencies = {0: [], 1: [], 2: []}
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            create_times = {}
            
            for row in reader:
                event = row['event']
                item_id = int(row['itemId'])
                sim_time = float(row['simTime'])
                
                if event == 'create':
                    create_times[item_id] = sim_time
                elif event == 'deliver':
                    if item_id in create_times:
                        latency = sim_time - create_times[item_id]
                        
                        # Assign to phase
                        for i, (start, end, _) in enumerate(phases):
                            if start <= sim_time < end:
                                phase_latencies[i].append(latency)
                                break
        
        results[arch] = phase_latencies
    
    # Print Summary Table
    print(f"{'Phase':<20} {'Centralized':<15} {'Decentralized':<15} {'Dynamic Adaptation':<20}")
    print("-" * 75)
    
    for i, (_, _, name) in enumerate(phases):
        row = [name]
        for arch in ["centralized-impprox", "decentralized", "dynamic-adaptation"]:
            latencies = results.get(arch, {}).get(i, [])
            if latencies:
                avg = sum(latencies) / len(latencies)
                row.append(f"{avg:.2f}s")
            else:
                row.append("N/A")
        
        print(f"{row[0]:<20} {row[1]:<15} {row[2]:<15} {row[3]:<20}")
    
    print("="*70)
    
    # Export full data to CSV
    output_path = RESULTS_DIR / "scenario_results.csv"
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Architecture', 'Phase', 'Avg_Latency', 'Num_Deliveries'])
        
        for arch, phase_data in results.items():
            for i, (_, _, name) in enumerate(phases):
                latencies = phase_data.get(i, [])
                if latencies:
                    avg = sum(latencies) / len(latencies)
                    count = len(latencies)
                    writer.writerow([arch, name, f"{avg:.2f}", count])
    
    print(f"Detailed results saved to {output_path}")

def main():
    print("="*70)
    print("SCENARIO A: TIME-VARYING VARIABILITY")
    print("="*70)
    
    csv_paths = {}
    for arch in ARCHITECTURES:
        csv_path = run_simulation(arch)
        if csv_path:
            csv_paths[arch] = csv_path
            
    if csv_paths:
        analyze_results(csv_paths)

if __name__ == "__main__":
    main()
