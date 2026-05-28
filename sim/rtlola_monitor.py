"""
RTLola Monitor Module
Manages RTLola subprocess for runtime monitoring and architecture adaptation.
"""

import os
import platform
import shutil
import sys
import queue
import subprocess
import threading
import time
from typing import Optional, Dict, Any


def _candidate_label(path: str) -> str:
    try:
        return os.path.abspath(path)
    except Exception:
        return path


def _make_executable(path: str) -> None:
    if sys.platform == "win32" or not os.path.exists(path) or os.access(path, os.X_OK):
        return
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | 0o111)
    except Exception as e:
        print(f"[RTLola] Warning: Could not make binary executable: {e}")


def _usable_rtlola_binary(candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return None

    resolved = shutil.which(candidate) or candidate
    if not os.path.exists(resolved):
        return None

    _make_executable(resolved)
    try:
        subprocess.run(
            [resolved, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[RTLola] Skipping unusable binary '{resolved}': {e}")
        return None

    return resolved


def _platform_rtlola_names() -> list[str]:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        os_names = ["macos", "darwin"]
    elif system == "linux":
        os_names = ["linux"]
    elif system == "windows":
        os_names = ["windows", "win"]
    else:
        os_names = [system]

    if machine in {"x86_64", "amd64"}:
        arch_names = ["x86_64", "amd64"]
    elif machine in {"aarch64", "arm64"}:
        arch_names = ["aarch64", "arm64"]
    else:
        arch_names = [machine]

    names = []
    for os_name in os_names:
        for arch_name in arch_names:
            names.extend([
                f"rtlola-cli-{os_name}-{arch_name}",
                f"rtlola-cli-{os_name}_{arch_name}",
            ])
        names.append(f"rtlola-cli-{os_name}")

    if sys.platform == "win32":
        names.extend([f"{name}.exe" for name in list(names)])
        names.append("rtlola-cli.exe")
    names.append("rtlola-cli")
    return list(dict.fromkeys(names))


def _venv_bin_dirs(project_root: str) -> list[str]:
    venvs = []
    env_venv = os.environ.get("VIRTUAL_ENV")
    if env_venv:
        venvs.append(env_venv)
    venvs.append(os.path.join(project_root, ".venv"))

    dirs = []
    for venv in venvs:
        dirs.append(os.path.join(venv, "Scripts" if sys.platform == "win32" else "bin"))
    return list(dict.fromkeys(dirs))


def _rtlola_candidates(project_root: str, script_dir: str) -> list[Optional[str]]:
    names = _platform_rtlola_names()
    candidates: list[Optional[str]] = []

    for bin_dir in _venv_bin_dirs(project_root):
        for name in names:
            candidates.append(os.path.join(bin_dir, name))

    for base_dir in (
        os.path.join(project_root, "bin"),
        os.path.join(project_root, "tools"),
        project_root,
        script_dir,
    ):
        for name in names:
            candidates.append(os.path.join(base_dir, name))

    candidates.extend([
        shutil.which("rtlola-cli"),
        os.path.expanduser("~/.cargo/bin/rtlola-cli"),
    ])

    seen = set()
    unique = []
    for candidate in candidates:
        key = _candidate_label(candidate) if candidate else ""
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


class RTLolaMonitor:
    """
    Manages RTLola CLI process for monitoring simulation events and extracting metrics.
    """
    
    def __init__(self, spec_file: str, rtlola_binary: str = None):
        """
        Initialize RTLola monitor.
        
        Args:
            spec_file: Path to RTLola specification file
            rtlola_binary: Path to rtlola-cli binary (default: searches PATH, then ~/.cargo/bin/rtlola-cli)
        """
        if rtlola_binary is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)

            for candidate in _rtlola_candidates(project_root, script_dir):
                rtlola_binary = _usable_rtlola_binary(candidate)
                if rtlola_binary is not None:
                    break
        else:
            rtlola_binary = _usable_rtlola_binary(rtlola_binary)
        
        self.spec_file = spec_file
        self.rtlola_binary = rtlola_binary
        self.proc: Optional[subprocess.Popen] = None
        self.stdout_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Metric storage
        self.latest_metrics: Dict[str, float] = {}
        self.metrics_lock = threading.Lock()
        
        self.event_counter = 0
        
        # Verify RTLola binary exists
        if not self.rtlola_binary:
            raise FileNotFoundError(
                "No usable RTLola binary found. Please install RTLola "
                "(e.g., 'cargo install rtlola-cli') or specify a Linux-compatible binary."
            )
        
        # Verify spec file exists
        if not os.path.exists(self.spec_file):
            raise FileNotFoundError(f"RTLola spec file not found: {self.spec_file}")
        
        self._start_process()
    
    def _start_process(self):
        """Start the RTLola CLI process."""
        try:
            self.proc = subprocess.Popen(
                [
                    self.rtlola_binary,
                    "monitor",
                    "--stdin",
                    self.spec_file,
                    "--offline",
                    "relative",
                    "--csv-time-column",
                    "1",
                    "-v",
                    "outputs"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Start thread to read stdout
            self.running = True
            self.stdout_thread = threading.Thread(
                target=self._read_stdout,
                args=(self.proc.stdout,),
                daemon=True
            )
            self.stdout_thread.start()
            
            # Start thread to read stderr
            self.stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(self.proc.stderr,),
                daemon=True
            )
            self.stderr_thread.start()
            
            # Send CSV header for spec2.rtlola format. In offline mode, column
            # 1 is also used as the monitor timestamp, so RTLola windows are
            # evaluated over simulation time rather than wall-clock time.
            # We write this directly to ensure it goes first
            header = "time,itemId,event,destination\n"
            self.proc.stdin.write(header)
            self.proc.stdin.flush()
            # Give the CLI a short startup window before the simulator begins
            # streaming accelerated traces; otherwise the first adaptation
            # query can race with monitor initialization.
            time.sleep(0.2)
            
            # print(f"[RTLola] Monitor started with PID {self.proc.pid}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to start RTLola process: {e}")



    def _read_stderr(self, pipe):
        """Read stderr from RTLola process and print it."""
        try:
            with pipe:
                for line in pipe:
                    print(f"[RTLola STDERR] {line.strip()}")
        except Exception as e:
            print(f"[RTLola] Error reading stderr: {e}")
    
    def _read_stdout(self, pipe):
        """Read stdout from RTLola process and update metrics."""
        try:
            with pipe:
                for line in pipe:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # print(f"[DEBUG] RTLola output: {line}") # Uncomment to see all output
                        
                    # Parse metric from line
                    # RTLola format: [timestamp][Output][stream_name][Value] = value
                    if '=' in line and '[Output]' in line and '[Value]' in line:
                        try:
                            # Extract stream name: ...[Output][stream_name][Value]...
                            parts = line.split('=')
                            value_str = parts[1].strip()
                            
                            # Extract name between [Output] and [Value]
                            left_part = parts[0]
                            start_idx = left_part.find('[Output]') + 8
                            end_idx = left_part.find('[Value]')
                            
                            if start_idx < end_idx:
                                raw_name = left_part[start_idx:end_idx]
                                # Clean up brackets if any (e.g. "[mean_latency]")
                                metric_name = raw_name.strip('[] ')
                                
                                try:
                                    value = float(value_str)
                                    with self.metrics_lock:
                                        self.latest_metrics[metric_name] = value
                                    # print(f"[DEBUG] Updated metric '{metric_name}' to {value}")
                                except ValueError:
                                    pass
                        except Exception as e:
                            print(f"[DEBUG] Error parsing line '{line}': {e}")
                            
        except Exception as e:
            print(f"[RTLola] Error reading stdout: {e}")
    
    def send_event(self, simTime: float, robotId: int, itemId: int, 
                   itemImportance: int, position: int, destination: int, event: str):
        """
        Send a simulation event to RTLola.
        
        Args:
            simTime: Simulation time
            robotId: Robot ID (-1 for item events)
            itemId: Item ID (-1 if no item)
            itemImportance: Item importance level
            position: Current position (room ID)
            destination: Destination (room ID)
            event: Event type (create, move, deliver, fail, etc.)
        """
        if not self.running:
            return
        
        # Format for spec2.rtlola: time,itemId,event,destination
        line = f"{simTime},{itemId},{event},{destination}\n"
        
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
            self.event_counter += 1
                
        except Exception as e:
            print(f"[RTLola] Error sending event: {e}")
    
    def get_metric(self, metric_name: str, timeout: float = 0.0) -> Optional[float]:
        """
        Get the latest value for a specific metric.
        
        Args:
            metric_name: Name of the metric to extract
            timeout: Optional time to wait for the metric to appear.
        
        Returns:
            Metric value as float, or None if not found yet
        """
        deadline = time.time() + max(0.0, timeout)
        while True:
            with self.metrics_lock:
                value = self.latest_metrics.get(metric_name)
            if value is not None or time.time() >= deadline:
                return value
            time.sleep(0.001)
    
    def get_all_metrics(self, timeout: float = 0.0) -> Dict[str, float]:
        """
        Get all available metrics.
        
        Args:
            timeout: Optional time to wait for at least one metric.
        
        Returns:
            Dictionary of metric_name -> value
        """
        deadline = time.time() + max(0.0, timeout)
        while True:
            with self.metrics_lock:
                metrics = self.latest_metrics.copy()
            if metrics or time.time() >= deadline:
                return metrics
            time.sleep(0.001)
    
    def is_running(self) -> bool:
        """Check if RTLola process is still running."""
        return self.proc is not None and self.proc.poll() is None
    
    def shutdown(self):
        """Gracefully shutdown the RTLola process."""
        if self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=5)
                # print("[RTLola] Monitor shutdown successfully")
            except Exception as e:
                print(f"[RTLola] Error during shutdown: {e}")
                self.proc.kill()
            finally:
                self.proc = None
                self.running = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


# Example usage
if __name__ == "__main__":
    # Test RTLola monitor
    spec_file = "spec2.rtlola"
    
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} not found")
        sys.exit(1)
    
    try:
        with RTLolaMonitor(spec_file) as monitor:
            print("RTLola monitor initialized successfully")
            
            # Send some test events
            monitor.send_event(0.0, -1, 0, 2, 0, 5, "create")
            time.sleep(0.1)
            
            monitor.send_event(1.0, 0, 0, 2, 0, 1, "startLoading")
            time.sleep(0.1)
            
            monitor.send_event(10.0, 0, 0, 2, 5, 5, "deliver")
            time.sleep(0.2)
            
            # Get metrics
            latency = monitor.get_metric("mean_latency_1h")
            if latency is not None:
                print(f"Mean latency (1h): {latency}")
            
            all_metrics = monitor.get_all_metrics()
            print(f"All metrics: {all_metrics}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
