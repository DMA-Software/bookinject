#!/usr/bin/env python3
"""Logging bootstrap for Book Injector.

Configures the main and debug loggers from ``LoggerConfig``. Other modules do
not use this class directly; they obtain loggers via::

    logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
    debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)

The debug logger is a child of the main logger and owns no handlers: its
records propagate to the main logger's handlers, so both share one console
stream, one log file and one syslog connection.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys

from src.application.config.logger import (
    BaseLoggerConfig,
    ConsoleLoggerConfig,
    FileLoggerConfig,
    LoggerConfig,
    SyslogLoggerConfig,
)
from src.constants import (
    DEFAULT_DEBUG_LOGGER_NAME,
    DEFAULT_MAIN_LOGGER_NAME,
    TEXT_FORMATTER,
)
from src.enumerations import LogFormat

# Level that no record can reach; used to switch a logger off
_LOGGER_OFF_LEVEL = logging.CRITICAL + 1


class JsonFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object (JSON Lines).

    Unlike a %-style template, all values are escaped by ``json.dumps``, so
    Windows paths, quotes and multi-line tracebacks produce valid JSON.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialize ``record`` to a JSON string.

        Args:
            record: Log record to format.

        Returns:
            One-line JSON document. ``exception`` and ``stack`` keys are added
            only when the record carries exception or stack information.
        """
        payload: dict[str, object] = {
            "time": self.formatTime(record),
            "process": record.process,
            "name": record.name,
            "level": record.levelname,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


class HandlerLevelFilter(logging.Filter):
    """Per-handler level gate that always passes debug logger records.

    Replaces ``Handler.setLevel()``: the debug logger shares handlers with the
    main logger, and a plain handler level (e.g. INFO) would drop its DEBUG
    records.
    """

    def __init__(self, level: int, bypassLoggerName: str) -> None:
        """Create the filter.

        Args:
            level: Minimum level for records from any logger except the bypass one.
            bypassLoggerName: Logger whose records (and its children's) always pass.
        """
        super().__init__()
        self._level = level
        self._bypassLoggerName = bypassLoggerName
        self._bypassPrefix = bypassLoggerName + "."

    def filter(self, record: logging.LogRecord) -> bool:
        """Decide whether ``record`` is emitted by the handler.

        Args:
            record: Log record being handled.

        Returns:
            True if the record level is high enough or it comes from the
            bypass logger hierarchy.
        """
        return (
            record.levelno >= self._level
            or record.name == self._bypassLoggerName
            or record.name.startswith(self._bypassPrefix)
        )


class BILogger:
    """Configures Book Injector loggers from ``LoggerConfig``.

    Construction is idempotent: handlers left by a previous instance are
    detached and closed first, so re-creating ``BILogger`` (tests, config
    reload) never duplicates output.
    """

    def __init__(
        self,
        loggerConfig: LoggerConfig,
        enableDebugLogger: bool = False,
        daemonize: bool = True,
    ) -> None:
        """Validate the configuration and set up the main and debug loggers.

        Args:
            loggerConfig: Logger configuration; validated here once more so
                programmatically built configs are covered as well.
            enableDebugLogger: Emit records of the debug logger. When False,
                the debug logger is silenced but still safe to call.
            daemonize: Running as a daemon without a terminal. The console
                handler is never created in this mode, even if
                ``ConsoleLogger`` is enabled in the configuration.

        Raises:
            ValueError: If the configuration is invalid.
        """
        loggerConfig.validate()

        self._loggerConfig = loggerConfig
        self._enableDebugLogger = enableDebugLogger
        self._daemonize = daemonize

        self._initMainLogger()
        self._initDebugLogger()

    def _activeConfigs(self) -> list[BaseLoggerConfig]:
        """Return the handler configs that should produce a handler.

        Returns:
            Enabled handler configs; console is skipped in daemon mode.
        """
        activeConfigs: list[BaseLoggerConfig] = []
        if self._loggerConfig.consoleLogger.enabled and not self._daemonize:
            activeConfigs.append(self._loggerConfig.consoleLogger)
        if self._loggerConfig.fileLogger.enabled:
            activeConfigs.append(self._loggerConfig.fileLogger)
        if self._loggerConfig.syslogLogger.enabled:
            activeConfigs.append(self._loggerConfig.syslogLogger)
        return activeConfigs

    def _initMainLogger(self) -> None:
        """Attach the configured handlers to the main logger.

        The logger level is the lowest level among active handlers so that no
        record a handler wants is dropped early. Without active handlers a
        ``NullHandler`` is attached to keep ``logging.lastResort`` from
        printing to stderr.
        """
        mainLogger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
        self._resetLogger(mainLogger)
        mainLogger.propagate = False

        activeConfigs = self._activeConfigs()
        if not activeConfigs:
            mainLogger.setLevel(_LOGGER_OFF_LEVEL)
            mainLogger.addHandler(logging.NullHandler())
            return

        mainLogger.setLevel(min(int(cfg.logLevel) for cfg in activeConfigs))
        for cfg in activeConfigs:
            mainLogger.addHandler(self._buildHandler(cfg))

    def _initDebugLogger(self) -> None:
        """Configure the debug logger as a handler-less child of the main logger.

        Its records propagate to the main logger's handlers. When debug
        logging is disabled the logger level is set above CRITICAL.
        """
        debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)
        self._resetLogger(debugLogger)
        debugLogger.propagate = True
        debugLogger.setLevel(
            logging.DEBUG if self._enableDebugLogger else _LOGGER_OFF_LEVEL
        )

    def _buildHandler(self, cfg: BaseLoggerConfig) -> logging.Handler:
        """Create a handler for ``cfg`` and apply its level filter and formatter.

        Args:
            cfg: Enabled and validated handler configuration.

        Returns:
            Ready-to-attach handler.

        Raises:
            TypeError: If ``cfg`` is not a known handler config type.
        """
        handler: logging.Handler
        if isinstance(cfg, ConsoleLoggerConfig):
            handler = self._buildConsoleHandler()
        elif isinstance(cfg, FileLoggerConfig):
            handler = self._buildFileHandler(cfg)
        elif isinstance(cfg, SyslogLoggerConfig):
            handler = self._buildSyslogHandler(cfg)
        else:
            raise TypeError(f"Unsupported logger config: {type(cfg).__name__}")

        handler.addFilter(
            HandlerLevelFilter(int(cfg.logLevel), DEFAULT_DEBUG_LOGGER_NAME)
        )
        handler.setFormatter(self._formatterFor(cfg.logFormatterType))
        return handler

    @staticmethod
    def _buildConsoleHandler() -> logging.Handler:
        """Create a stdout stream handler.

        Returns:
            Console handler.
        """
        consoleLogger = logging.StreamHandler(stream=sys.stdout)
        return consoleLogger

    @staticmethod
    def _buildFileHandler(cfg: FileLoggerConfig) -> logging.Handler:
        """Create a size-based rotating file handler.

        The file is opened lazily on the first record (``delay=True``) and
        always written as UTF-8 regardless of the OS locale.

        Args:
            cfg: Validated file logger configuration.

        Returns:
            Rotating file handler.
        """
        fileLogger = logging.handlers.RotatingFileHandler(
            filename=str(cfg.logFilePath),
            maxBytes=cfg.maxLogFileSize,
            backupCount=cfg.maxLogFiles,
            encoding="utf-8",
            delay=True,
        )
        return fileLogger

    @staticmethod
    def _buildSyslogHandler(cfg: SyslogLoggerConfig) -> logging.Handler:
        """Create a UDP syslog handler.

        Args:
            cfg: Validated syslog logger configuration; the facility name has
                been checked against ``SysLogHandler.facility_names``.

        Returns:
            Syslog handler.
        """
        syslogLogger = logging.handlers.SysLogHandler(
            address=(str(cfg.syslogServerAddress), cfg.syslogServerPort),
            facility=logging.handlers.SysLogHandler.facility_names[
                str(cfg.syslogFacility).lower()
            ],
        )
        return syslogLogger

    @staticmethod
    def _formatterFor(logFormat: LogFormat) -> logging.Formatter:
        """Map a configured log format to a formatter instance.

        Args:
            logFormat: Validated log format (Text or Json).

        Returns:
            Shared formatter instance.
        """
        if logFormat == LogFormat.Text:
            return TEXT_FORMATTER

        JSON_FORMATTER = JsonFormatter()
        return JSON_FORMATTER

    @staticmethod
    def _resetLogger(logger: logging.Logger) -> None:
        """Detach and close all handlers of ``logger``.

        Args:
            logger: Logger to clean up before (re)configuration.
        """
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
