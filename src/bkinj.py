#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Project modules are imported as "src.*". Make that the only valid form
# regardless of how the script is started (python src/bkinj.py,
# python -m src.bkinj, from another cwd):
#  - the project root must be on sys.path so that "src" is importable;
#  - the "src" directory itself must NOT be on sys.path, otherwise
#    "import enumerations" also works and loads a second copy of the module
#    (different enum classes -> broken comparisons).
_SRC_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_DIR.parent

sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _SRC_DIR]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.application.main_application import MainApplication


def parse_cli_args():
    import argparse

    parser = argparse.ArgumentParser(description="Starting Book Injector service...")
    _ = parser.add_argument(
        "--config",
        type=str,
        default="conf/bookinjector.xml",
        dest="configfile",
        help="Path to the configuration file (default: boolinjector.xml)",
    )
    _ = parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        dest="debug",
        help="Enable debug logging (default: False)",
    )
    _ = parser.add_argument(
        "--no-daemonize",
        action="store_true",
        dest="no_daemonize",
        help="Run the service in the foreground (default: False)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_cli_args()

    main_application = MainApplication(
        mainConfigFile=cli_args.configfile, enableDebugLogger=cli_args.debug
    )

    exit_code = main_application.run()

    main_application.terminate()
    sys.exit(exit_code)
