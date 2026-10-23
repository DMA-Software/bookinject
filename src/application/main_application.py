#!/usr/bin/env python3

from __future__ import annotations

import logging
import os

from src.application.config.book_injector import BookInjector
from src.application.logger import BILogger
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


    def run(self) -> None:
        self.logger.info("Starting main application")

    def terminate(self) -> None:
        self.logger.info("Terminating main application")

    def restart(self) -> None:
        self.logger.info("Restarting main application")
