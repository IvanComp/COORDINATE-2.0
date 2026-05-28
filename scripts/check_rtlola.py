#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import platform
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.rtlola_monitor import _rtlola_candidates, _usable_rtlola_binary


def main() -> int:
    root = ROOT
    script_dir = root / "sim"
    candidates = _rtlola_candidates(str(root), str(script_dir))

    print(f"[rtlola-check] Project: {root}")
    print(f"[rtlola-check] Platform: {platform.system()} {platform.machine()}")
    print("[rtlola-check] Candidate order:")
    for index, candidate in enumerate(candidates, start=1):
        exists = Path(candidate).exists()
        marker = "exists" if exists else "missing"
        print(f"  {index:02d}. {candidate} [{marker}]")

    selected = None
    for candidate in candidates:
        selected = _usable_rtlola_binary(candidate)
        if selected:
            break

    if not selected:
        print("[rtlola-check] ERROR: no usable rtlola-cli binary found.")
        print("[rtlola-check] Run: bash scripts/setup_experiments.sh")
        return 1

    print(f"[rtlola-check] Selected: {selected}")
    result = subprocess.run([selected, "--version"], text=True, capture_output=True, check=True)
    print(result.stdout.strip() or result.stderr.strip())

    file_bin = shutil.which("file")
    if file_bin:
        file_cmd = subprocess.run([file_bin, selected], text=True, capture_output=True)
        if file_cmd.returncode == 0:
            print(f"[rtlola-check] File: {file_cmd.stdout.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
