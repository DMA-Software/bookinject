#!/usr/bin/env python3
"""Run the whole test suite: trial suites first, then the pytest ones.

Usage:
    python tools/run_tests.py            # everything (what the pre-commit hook runs)
    python tools/run_tests.py -k name    # extra arguments go to both runners

Suites:
    trial  - tests/services, tests/application (twisted.trial, real reactor)
    pytest - the remaining tests/ (configuration); trial suites are skipped by
             tests/conftest.py

Exit code: 0 - all passed, otherwise 1.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRIAL_PACKAGES = ["tests.services", "tests.application"]
# Keeps _trial_temp out of the working tree root (tmp/ is git-ignored)
TRIAL_TEMP = PROJECT_ROOT / "tmp" / "_trial_temp"


def run(title: str, command: list[str]) -> bool:
    print(f"\n=== {title} ===", flush=True)
    return subprocess.run(command, cwd=PROJECT_ROOT).returncode == 0


def main(extra: list[str]) -> int:
    python = sys.executable
    results = [
        run(
            "trial",
            [python, "-m", "twisted.trial", f"--temp-directory={TRIAL_TEMP}", *extra, *TRIAL_PACKAGES],
        ),
        run("pytest", [python, "-m", "pytest", "-q", *extra, "tests"]),
    ]
    print("\n" + ("All tests passed" if all(results) else "TESTS FAILED"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
