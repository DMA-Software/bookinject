#!/usr/bin/env python3
"""Validate a BookInjector XML config against the XSD schema.

Usage:
    python tools/validate_config.py                      # conf/bookinjector.xml
    python tools/validate_config.py path/to/config.xml
    python tools/validate_config.py config.xml --schema path/to/schema.xsd

Exit code: 0 - valid, 1 - invalid, 2 - file/schema error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xmlschema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "conf" / "bookinjector.xml"
DEFAULT_SCHEMA = PROJECT_ROOT / "conf" / "schemas" / "bookinjector.xsd"


def load_schema(schema_path: Path = DEFAULT_SCHEMA) -> xmlschema.XMLSchema10:
    return xmlschema.XMLSchema10(str(schema_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BookInjector XML config.")
    parser.add_argument("config", nargs="?", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    for path in (args.config, args.schema):
        if not path.is_file():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2

    try:
        schema = load_schema(args.schema)
    except xmlschema.XMLSchemaException as exc:
        print(f"ERROR: invalid schema {args.schema}:\n{exc}", file=sys.stderr)
        return 2

    errors = list(schema.iter_errors(str(args.config)))
    if not errors:
        print(f"OK: {args.config} is valid")
        return 0

    print(f"INVALID: {args.config} ({len(errors)} error(s))", file=sys.stderr)
    for err in errors:
        # err.path is an XPath to the failing node; err.reason is a short message
        print(f"  - {err.path}: {err.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
