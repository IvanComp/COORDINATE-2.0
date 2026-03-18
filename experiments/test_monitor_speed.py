
import time
import os
import sys
from sim.rtlola_monitor import RTLolaMonitor

def test_monitor_speed():
    print("Testing RTLolaMonitor speed...")
    
    # Ensure spec file exists
    if not os.path.exists("spec2.rtlola"):
        with open("spec2.rtlola", "w") as f:
            f.write("input i: Int8\noutput o := i\n")
            
    try:
        monitor = RTLolaMonitor("spec2.rtlola")
        
        # Warm up
        monitor.get_metric("foo")
        
        start_time = time.time()
        n_checks = 1000
        for _ in range(n_checks):
            monitor.get_metric("global_latency", timeout=0.1)
        
        total_time = time.time() - start_time
        avg_time_ms = (total_time / n_checks) * 1000
        
        print(f"Total time for {n_checks} checks: {total_time:.4f}s")
        print(f"Average time per check: {avg_time_ms:.4f}ms")
        
        monitor.shutdown()
        
        if avg_time_ms > 1.0:
            print("[FAIL] Monitor is too slow!")
            sys.exit(1)
        else:
            print("[PASS] Monitor is fast enough.")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_monitor_speed()
