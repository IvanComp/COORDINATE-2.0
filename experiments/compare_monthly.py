"""
Monthly Latency Comparison Script

Runs 1-month simulations for all 4 coordination mechanisms and tracks
hourly average latency for comparison.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "monthly_comparison"
RESULTS_DIR.mkdir(exist_ok=True)

# Configuration for 1-month simulation
MONTH_CONFIG = {
    "RESULTS_DIR": str(RESULTS_DIR),
    "SIM_TIME": 30 * 24 * 3600,  # 30 days
    "TOPOLOGY_NAME": "GUH73",
    "N_ROOMS": 73,
    "SOURCE": 0,
    "TARGETS": -1,
    "ITEM_SPAWNING_TIME": 90,
    "ITEM_SPAWNING_DISTR": "exponential",
    "ITEM_SPAWNING_TRACE": "_",
    "IMPORTANCE_PROBABILITIES": [0.5, 0.1, 0.4],
    "EXPIRATION_TIME": [-1, -1, -1],
    "EXPIRATION_DISTR": ["exponential", "exponential", "exponential"],
    "N_ROBOTS": 20,
    "N_MALICIOUS": 13,  # 65%
    "MALICIOUS_FAKE_FAILURES": True,
    "FIND_ROUTE_STRATEGY": "breadth",
    "FAIL_PROB": 0.66,
    "COMM_FAIL_PROB": 0.1,
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
    "ADAPTATION_CHECK_INTERVAL": 3600.0,  # 1 hour
    "INITIAL_ARCHITECTURE": "centralized-impprox",
}

ARCHITECTURES = {
    "CE": "centralized-impprox",
    "SD": "semi-decentralized",
    "FD": "decentralized",
    "DA": "dynamic-adaptation",
}

def calculate_hourly_latencies(csv_path):
    """
    Calculate average latency for each hour of the simulation.
    
    Returns:
        dict: {hour: avg_latency}
    """
    hourly_latencies = {}
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            create_times = {}
            deliveries_by_hour = {}  # {hour: [latencies]}
            
            for row in reader:
                event = row['event']
                item_id = int(row['itemId'])
                sim_time = float(row['simTime'])
                hour = int(sim_time / 3600)
                
                if event == 'create':
                    create_times[item_id] = sim_time
                elif event == 'deliver':
                    if item_id in create_times:
                        latency = sim_time - create_times[item_id]
                        if hour not in deliveries_by_hour:
                            deliveries_by_hour[hour] = []
                        deliveries_by_hour[hour].append(latency)
            
            # Calculate average for each hour
            for hour, latencies in deliveries_by_hour.items():
                if latencies:
                    hourly_latencies[hour] = sum(latencies) / len(latencies)
        
        return hourly_latencies
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return {}

def run_architecture(arch_name, arch_value):
    """Run 1-month simulation for a specific architecture."""
    print(f"\n{'='*70}")
    print(f"Running {arch_name} ({arch_value}) - 30 days")
    print(f"{'='*70}")
    
    config = dict(MONTH_CONFIG)
    config["ARCHITECTURE"] = arch_value
    
    # Create config file
    config_path = RESULTS_DIR / f"config_{arch_name}.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Run simulation
    cmd = [sys.executable, "-m", "sim.simulator", str(config_path)]
    print(f"Starting simulation... (this will take several minutes)")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR running {arch_name}:")
        print(result.stderr)
        return None
    
    print(result.stdout.split('\n')[-3:])  # Print last few lines
    
    # Find the generated CSV - use more flexible pattern matching
    csv_files = list(RESULTS_DIR.glob("*.csv"))
    csv_files = [f for f in csv_files if not f.name.endswith('_overhead.csv') and not f.name.endswith('simTime.csv')]
    
    # Filter by architecture name pattern
    if arch_name == "CE":
        csv_files = [f for f in csv_files if "centralizedImpprox" in f.name or "centralized-impprox" in f.name]
    elif arch_name == "SD":
        csv_files = [f for f in csv_files if "semi" in f.name and "decentralized" not in f.name.replace("semi-decentralized", "")]
    elif arch_name == "FD":
        csv_files = [f for f in csv_files if "fully" in f.name or f.name.startswith("decentralized")]
    elif arch_name == "DA":
        csv_files = [f for f in csv_files if "dynamic-adaptation" in f.name]
    
    if not csv_files:
        print(f"No CSV found for {arch_name}")
        return None
    
    csv_path = csv_files[-1]
    hourly_latencies = calculate_hourly_latencies(csv_path)
    
    print(f"✓ {arch_name}: Calculated latencies for {len(hourly_latencies)} hours")
    
    return hourly_latencies

def export_hourly_data(results):
    """Export hourly latency data to CSV."""
    output_path = RESULTS_DIR / "hourly_latencies.csv"
    
    # Get all unique hours
    all_hours = set()
    for hourly_data in results.values():
        all_hours.update(hourly_data.keys())
    all_hours = sorted(all_hours)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Hour', 'CE', 'SD', 'FD', 'DA'])
        
        for hour in all_hours:
            row = [hour]
            for arch_name in ["CE", "SD", "FD", "DA"]:
                if arch_name in results and hour in results[arch_name]:
                    row.append(f"{results[arch_name][hour]:.2f}")
                else:
                    row.append('')
            writer.writerow(row)
    
    print(f"\n✓ Hourly data saved to: {output_path}")

def save_summary(results):
    """Save summary statistics to CSV."""
    summary_path = RESULTS_DIR / "monthly_summary.csv"
    
    with open(summary_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Architecture', 'Avg Latency (s)', 'Min Latency (s)', 'Max Latency (s)', 'Hours with Data'])
        
        for arch_name in ["CE", "SD", "FD", "DA"]:
            if arch_name in results and results[arch_name]:
                hourly_data = results[arch_name]
                latencies = list(hourly_data.values())
                
                avg_lat = sum(latencies) / len(latencies)
                min_lat = min(latencies)
                max_lat = max(latencies)
                hours = len(hourly_data)
                
                writer.writerow([
                    f"{arch_name} ({ARCHITECTURES[arch_name]})",
                    f"{avg_lat:.2f}",
                    f"{min_lat:.2f}",
                    f"{max_lat:.2f}",
                    hours
                ])
    
    print(f"✓ Summary saved to: {summary_path}")

def main():
    """Run monthly comparison for all architectures."""
    print("="*70)
    print("MONTHLY LATENCY COMPARISON - ALL ARCHITECTURES")
    print("="*70)
    print(f"Simulation Duration: 30 days ({MONTH_CONFIG['SIM_TIME']}s)")
    print(f"Item Spawn Rate: {MONTH_CONFIG['ITEM_SPAWNING_TIME']}s")
    print(f"Robots: {MONTH_CONFIG['N_ROBOTS']} (Malicious: {MONTH_CONFIG['N_MALICIOUS']})")
    print(f"Fail Prob: {MONTH_CONFIG['FAIL_PROB']}, Msg Loss: {MONTH_CONFIG['COMM_FAIL_PROB']}")
    print("="*70)
    
    results = {}
    
    for arch_name, arch_value in ARCHITECTURES.items():
        hourly_latencies = run_architecture(arch_name, arch_value)
        if hourly_latencies:
            results[arch_name] = hourly_latencies
    
    if results:
        print("\n" + "="*70)
        print("EXPORTING RESULTS")
        print("="*70)
        export_hourly_data(results)
        save_summary(results)
    
    print("\n" + "="*70)
    print("MONTHLY COMPARISON COMPLETED")
    print("="*70)
    print(f"Results saved in: {RESULTS_DIR}")
    print("="*70)

if __name__ == "__main__":
    main()
