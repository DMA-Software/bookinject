"""Test package.

Tests of the services layer and ``MainApplication`` are written with
``twisted.trial`` and live in ``tests/services`` and ``tests/application``;
run them with ``python tools/run_tests.py`` (also the pre-commit hook).
"""
import logging

from src.constants import DEFAULT_MAIN_LOGGER_NAME

# Tests provoke errors on purpose. Without a handler on the "BookInjector"
# logger Python would print every one of them to stderr (logging.lastResort).
logging.getLogger(DEFAULT_MAIN_LOGGER_NAME).addHandler(logging.NullHandler())
