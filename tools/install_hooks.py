#!/usr/bin/env python3
"""Enable the versioned git hooks of this repository (.githooks/).

Git does not version .git/hooks, so every clone runs this once:

    python tools/install_hooks.py

Exit code: 0 - enabled, 1 - git failed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ".githooks"


def main() -> int:
    for hook in (PROJECT_ROOT / HOOKS_DIR).iterdir():
        hook.chmod(hook.stat().st_mode | 0o111)  # no-op on Windows, needed on POSIX

    result = subprocess.run(
        ["git", "config", "core.hooksPath", HOOKS_DIR], cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        return 1

    print(f"git hooks enabled: core.hooksPath = {HOOKS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
