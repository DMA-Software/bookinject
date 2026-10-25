#!/usr/bin/env python3
"""Shared helper functions and procedures of Book Injector.

All module-independent helpers live here and nowhere else.
"""

from __future__ import annotations

import math


def isMetricNumber(value: object) -> bool:
    """True for a finite int or float.

    ``bool`` is rejected although it is an ``int`` (a flag is not a measurement),
    and so are ``NaN`` and ``inf``: they would poison every later sum and
    produce invalid JSON.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
