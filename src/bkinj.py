#!/usr/bin/env python3
from __future__ import annotations


def parse_cli_args():
    import argparse

    parser = argparse.ArgumentParser(description="Starting Book Injector service...")
    _ = parser.add_argument(
        "--config",
        type=str,
        default="boolinjector.xml",
        dest="configfile",
        help="Path to the configuration file (default: boolinjector.xml)",
    )
    _ = parser.add_argument(
        "--verbose",
        action="store_true",
        dest="verbose",
        help="Enable verbose logging (default: False)",
    )
    return parser.parse_args()


if __name__ == '__main__':
    cli_args = parse_cli_args()
