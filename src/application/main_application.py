#!/usr/bin/env python3

from __future__ import annotations

import logging
import os

from twisted.internet.defer import ensureDeferred

from src.application.config.book_injector import BookInjector
from src.application.logger import BILogger
from src.application.services import EventBus, ServiceManager
from src.constants import DEFAULT_DEBUG_LOGGER_NAME, DEFAULT_MAIN_LOGGER_NAME


class MainApplication:
    def __init__(
        self,
        mainConfigFile: str,
        enableDebugLogger: bool = False,
        daemonize: bool = True,
    ):
        if not mainConfigFile:
            raise ValueError("mainConfigFile must be provided")

        if not os.path.exists(mainConfigFile):
            raise ValueError(f"mainConfigFile must exist: {mainConfigFile}")

        if not os.access(mainConfigFile, os.R_OK):
            raise ValueError("mainConfigFile must be readable")

        if not os.path.isfile(mainConfigFile):
            raise ValueError("mainConfigFile must be a file")

        if not os.path.getsize(mainConfigFile):
            raise ValueError("mainConfigFile must not be empty")

        # self.enableDebugLogger = enableDebugLogger
        # self.daemonize = daemonize

        # Read and parse XML configuration (raises ValueError on any problem)
        self.appConfig = BookInjector()
        self.appConfig.fromFile(mainConfigFile)

        # Initialize logger
        self.biLogger = BILogger(
            self.appConfig.instance.logger, enableDebugLogger, daemonize
        )

        self.logger = logging.getLogger(DEFAULT_MAIN_LOGGER_NAME)
        self.debugLogger = logging.getLogger(DEFAULT_DEBUG_LOGGER_NAME)

        self.events = EventBus()
        self.services = ServiceManager(self.events)
        self.exitCode = 0

    def run(self) -> int:
        """Start the services and run the reactor until it stops.

        Blocks. The services are stopped in the reactor's "before shutdown"
        phase (Ctrl-C, SIGTERM, ``reactor.stop()``).

        Returns:
            Process exit code: 0 on a clean run, 1 if the services failed to start.
        """
        from twisted.internet import reactor

        self.logger.info("Starting main application")

        reactor.addSystemEventTrigger(
            # pyrefly: ignore[bad-argument-type]
            "before", "shutdown", lambda: ensureDeferred(self._stopServices())
        )
        reactor.callWhenRunning(lambda: ensureDeferred(self._startServices()))
        # pyrefly: ignore[bad-argument-count]
        reactor.run()  # pyright: ignore[reportAttributeAccessIssue]
        return self.exitCode

    async def _startServices(self) -> None:
        """Start all services; stop the application if that is not possible."""
        if await self.services.startAll():
            self.logger.info("Main application started")
            return

        self.logger.error("Services failed to start, shutting down")
        self.exitCode = 1
        self.services.shutdown()

    async def _stopServices(self) -> None:
        """Stop all services unless ``ServiceManager.shutdown()`` already did."""
        if self.services.isShuttingDown:
            self.debugLogger.debug("Services are already being stopped, waiting for it")
            await self.services.shutdown()
            return

        await self.services.stopAll()

    def terminate(self) -> None:
        self.logger.info("Terminating main application")

    def restart(self) -> None:
        self.logger.info("Restarting main application")
