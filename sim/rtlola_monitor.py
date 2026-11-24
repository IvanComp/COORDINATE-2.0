"""
RTLola Monitor Module
Manages RTLola subprocess for runtime monitoring and architecture adaptation.
"""

import json
import os
import platform
import re
import shutil
import sys
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Dict


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
    python_bin_dir = os.path.dirname(os.path.abspath(sys.executable))
    if python_bin_dir:
        dirs = [python_bin_dir]
    else:
        dirs = []

    env_venv = os.environ.get("VIRTUAL_ENV")
    if env_venv:
        venvs.append(env_venv)
    for name in (".venv", "venv", "env"):
        venvs.append(os.path.join(project_root, name))

    for venv in venvs:
        dirs.append(os.path.join(venv, "Scripts" if sys.platform == "win32" else "bin"))
    return list(dict.fromkeys(dirs))


def _rtlola_candidates(project_root: str, script_dir: str) -> list[Optional[str]]:
    names = _platform_rtlola_names()
    candidates: list[Optional[str]] = []

    env_binary = os.environ.get("RTLOLA_BINARY_PATH") or os.environ.get("COORDINATE_RTLOLA_BINARY")
    if env_binary:
        candidates.append(env_binary)

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


def resolve_rtlola_binary(project_root: str, script_dir: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return _usable_rtlola_binary(explicit)
    for candidate in _rtlola_candidates(project_root, script_dir):
        resolved = _usable_rtlola_binary(candidate)
        if resolved is not None:
            return resolved
    return None


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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        rtlola_binary = resolve_rtlola_binary(project_root, script_dir, explicit=rtlola_binary)
        
        self.spec_file = spec_file
        self.rtlola_binary = rtlola_binary
        self.proc: Optional[subprocess.Popen] = None
        self.stdout_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Metric storage
        self.latest_metrics: Dict[str, float] = {}
        self.metrics_lock = threading.Condition()
        self.completed_checks = 0
        self.check_metrics = {}
        self.reader_closed = False
        self.reader_error = None
        
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

        spec = Path(spec_file).read_text(encoding="utf-8")
        self.has_delivery_reference = bool(re.search(r"(?m)^\s*input\s+minimum_delivery_time\s*:", spec))
        self.spec_directory = tempfile.TemporaryDirectory(prefix="coordinate-rtlola-")
        try:
            runtime_spec = Path(self.spec_directory.name) / "monitor.rtlola"
            runtime_spec.write_text(
                spec + '\noutput coordinate_check_complete eval when event == "adaptation_check" with 1\n',
                encoding="utf-8",
            )
            self._start_process(str(runtime_spec))
        except BaseException:
            self.shutdown()
            raise
    
    def _start_process(self, runtime_spec):
        """Start the RTLola CLI process."""
        try:
            self.proc = subprocess.Popen(
                [
                    self.rtlola_binary,
                    "monitor",
                    "--stdin",
                    runtime_spec,
                    "--offline",
                    "relative",
                    "--csv-time-column",
                    "1",
                    "-v",
                    "outputs",
                    "--output-format",
                    "json",
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
            header = "time,itemId,event,destination"
            if self.has_delivery_reference:
                header += ",minimum_delivery_time"
            self.proc.stdin.write(header + "\n")
            self.proc.stdin.flush()
            
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
        try:
            with pipe:
                for line in pipe:
                    if not line.strip():
                        continue
                    verdict = json.loads(line)
                    checkpoint = verdict.pop("coordinate_check_complete", None)
                    verdict.pop("time", None)
                    values = {}
                    for metric, updates in verdict.items():
                        if isinstance(updates, list):
                            for update in updates:
                                value = update.get("eval")
                                if type(value) in (int, float):
                                    values[metric] = float(value)
                    with self.metrics_lock:
                        self.latest_metrics.update(values)
                        if checkpoint:
                            self.check_metrics = self.latest_metrics.copy()
                            self.completed_checks += 1
                            self.metrics_lock.notify_all()
        except Exception as e:
            self.reader_error = e
        finally:
            with self.metrics_lock:
                self.reader_closed = True
                self.metrics_lock.notify_all()

    def snapshot(self, sim_time: float) -> Dict[str, float]:
        with self.metrics_lock:
            expected = self.completed_checks + 1
        self.send_event(sim_time, -1, -1, -1, -1, -1, "adaptation_check")
        with self.metrics_lock:
            received = self.metrics_lock.wait_for(
                lambda: self.completed_checks == expected or self.reader_closed,
                timeout=30.0,
            )
            if not received or self.completed_checks != expected:
                raise RuntimeError(f"RTLola did not acknowledge the adaptation check at {sim_time}s") from self.reader_error
            return self.check_metrics.copy()
    
    def send_event(self, simTime: float, robotId: int, itemId: int, 
                   itemImportance: int, position: int, destination: int, event: str,
                   *, minimum_delivery_time: float = 0.0):
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
        if not self.running or self.reader_closed:
            raise RuntimeError(f"RTLola is unavailable at {simTime}s") from self.reader_error

        line = f"{simTime},{itemId},{event},{destination}"
        if self.has_delivery_reference:
            line += f",{minimum_delivery_time}"
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            self.event_counter += 1
        except OSError as e:
            raise RuntimeError(f"Failed to send {event} to RTLola at {simTime}s") from e
    
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
        self.spec_directory.cleanup()
    
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
