#!/usr/bin/env python3
"""
Script to add overhead logging call to simulator.py
This is a one-time patch to integrate the overhead tracking module.
"""

import os
import sys

def patch_simulator():
    """Add the overhead logging call to simulator.py"""
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    simulator_path = os.path.join(script_dir, '..', 'sim', 'simulator.py')
    
    # Read the current file
    with open(simulator_path, 'r') as f:
        lines = f.readlines()
    
    # Find the line with the final print statement
    target_line = None
    for i, line in enumerate(lines):
        if "print(os.path.basename(logfile), '-->" in line and "Simulation time (wall)" in line:
            target_line = i
            break
    
    if target_line is None:
        print("ERROR: Could not find target line")
        return False
    
    # Insert the overhead logging call before the print statement
    overhead_call = """    
    # Log adaptation overhead statistics
    log_overhead_statistics(
        adaptation_check_count,
        adaptation_switch_count,
        adaptation_overhead_total,
        adaptation_overhead_samples,
        wall_time,
        logfile
    )
    
"""
    
    # Insert the new lines
    lines.insert(target_line, overhead_call)
    
    # Write back
    with open(simulator_path, 'w') as f:
        f.writelines(lines)
    
    print("✓ Successfully patched simulator.py")
    print("✓ Added overhead logging call")
    return True

if __name__ == '__main__':
    success = patch_simulator()
    sys.exit(0 if success else 1)
