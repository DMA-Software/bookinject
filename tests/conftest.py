"""pytest configuration.

The suites below are written with ``twisted.trial`` and need its reactor
handling; they are run by ``trial`` (see ``tools/run_tests.py``), not pytest.
"""

collect_ignore = ["services", "application"]
