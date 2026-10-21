#!/usr/bin/env python3
from __future__ import annotations

from logging import Formatter
from typing import Final

# Default values for various configurations
KB_TO_BYTE: Final[int] = 1024  # It's one kilobyte in bytes
MB_TO_BYTE: Final[int] = 1024 * KB_TO_BYTE  # It's one megabyte in bytes
GB_TO_BYTE: Final[int] = 1024 * MB_TO_BYTE  # It's one gigabyte in bytes
TB_TO_BYTE: Final[int] = 1024 * GB_TO_BYTE  # It's one terabyte in bytes

# Log formatter
JSON_FORMATTER = Formatter(
    '{"time": "%(asctime)s", '
    '"process": "%(process)d", '
    '"name": "%(name)s", '
    '"level": "%(levelname)s", '
    '"pathname": "%(pathname)s", '
    '"lineno": "%(lineno)d", '
    '"funcName": "%(funcName)s", '
    '"message": "%(message)s"}'
)
TEXT_FORMATTER = Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(pathname)s | %(lineno)d | %(funcName)s | %(message)s"
)

DEFAULT_MAX_LOG_FILE_SIZE: Final[int] = 50  # Default maximum log file size for rotation (50 MB)
DEFAULT_MAX_LOG_FILE_BACKUP_COUNT: Final[int] = 5  # Default maximum number of log file backups to keep
