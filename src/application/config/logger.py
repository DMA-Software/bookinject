#!/usr/bin/env python3
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

# pyrefly: ignore [missing-module-attribute]
from src.constants import (
    DEFAULT_MAX_LOG_FILE_BACKUP_COUNT,
    DEFAULT_MAX_LOG_FILE_SIZE,
    MB_TO_BYTE,
)
from src.enumerations import LogFormat, LogLevel

from .xml_utils import (
    addChild,
    boolAttr,
    boolChild,
    checkTag,
    childText,
    intChild,
    makeElement,
    requireChild,
)


@dataclass
class BaseLoggerConfig(ABC):
    enabled: bool = field(
        default=True, metadata={"description": "Enable or disable logging"}
    )

    logLevel: LogLevel = field(
        default=LogLevel.NOTSET,
        metadata={
            "description": "Logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)"
        },
    )

    logFormatterType: LogFormat = field(
        default=LogFormat.Unknown,
        metadata={"description": "Logging format type (e.g., TEXT, JSON)"},
    )

    @property
    @abstractmethod
    def xmlTag(self) -> str:
        pass

    def validate(self):
        if not self.enabled:
            print("Logging is disabled. No further validation required.")
            return

        if self.logLevel in [
            LogLevel.NOTSET,
            LogLevel.Unknown,
            LogLevel.Invalid,
        ]:
            raise ValueError(
                f"Invalid log level: {self.logLevel}. Must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        if self.logFormatterType in [LogFormat.Unknown, LogFormat.Invalid]:
            raise ValueError(
                f"Invalid log formatter: {self.logFormatterType}. Must be one of TEXT, JSON."
            )

    def toXML(self) -> Element:
        logger_element = makeElement(self.xmlTag, self.enabled)
        addChild(logger_element, "LogLevel", str(self.logLevel).upper())
        addChild(logger_element, "LogFormatter", str(self.logFormatterType).upper())
        return logger_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, self.xmlTag, owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)

        log_level_text = childText(xmlElement, "LogLevel", owner)
        if not log_level_text:
            print(
                f"Invalid log level '{log_level_text}' provided. Defaulting to ERROR."
            )
            self.logLevel = LogLevel.Error
            return

        self.logLevel = LogLevel.fromStr(log_level_text)
        if self.logLevel == LogLevel.Invalid:
            print(
                f"Invalid log level '{log_level_text}' provided. Defaulting to ERROR."
            )
            self.logLevel = LogLevel.Error

        log_formatter_text = childText(xmlElement, "LogFormatter", owner)
        if not log_formatter_text:
            raise ValueError(f"Invalid log formatter '{log_formatter_text}' provided.")

        self.logFormatterType = LogFormat.from_str(log_formatter_text)

    def toJSON(self) -> dict:
        return {
            "enabled": self.enabled,
            "logLevel": str(self.logLevel).upper(),
            "logFormatterType": str(self.logFormatterType).upper(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError(f"Invalid JSON data for {self.__class__.__name__}")

        self.enabled = jsonData.get("enabled", self.enabled)
        if "logLevel" in jsonData:
            self.logLevel = LogLevel.fromStr(jsonData["logLevel"])
        if "logFormatterType" in jsonData:
            self.logFormatterType = LogFormat.from_str(jsonData["logFormatterType"])


@dataclass
class ConsoleLoggerConfig(BaseLoggerConfig):
    colorize: bool = field(
        default=False,
        metadata={"description": "Enable or disable colorized console output"},
    )

    @property
    def xmlTag(self) -> str:
        return "ConsoleLogger"

    def validate(self):
        super().validate()

        if not isinstance(self.colorize, bool):
            raise ValueError("The 'Colorize' attribute must be a boolean.")  # noqa: TRY004

    def toXML(self) -> Element:
        console_logger_element = super().toXML()
        addChild(console_logger_element, "Colorize", self.colorize)
        return console_logger_element

    def fromXML(self, xmlElement) -> None:
        super().fromXML(xmlElement)

        self.colorize = boolChild(xmlElement, "Colorize", self.__class__.__name__)

        self.validate()

    def toJSON(self) -> dict:
        return {**super().toJSON(), "colorize": self.colorize}

    def fromJSON(self, jsonData: dict) -> None:
        super().fromJSON(jsonData)
        self.colorize = jsonData.get("colorize", self.colorize)
        self.validate()


@dataclass
class FileLoggerConfig(BaseLoggerConfig):
    logFilePath: str | None = field(
        default="app.log", metadata={"description": "Path to the log file"}
    )

    maxLogFileSize: int = field(
        default=DEFAULT_MAX_LOG_FILE_SIZE * MB_TO_BYTE,
        metadata={
            "description": "Maximum size of the log file in bytes before rotation"
        },
    )

    maxLogFiles: int = field(
        default=DEFAULT_MAX_LOG_FILE_BACKUP_COUNT,
        metadata={"description": "Maximum number of log files to keep after rotation"},
    )

    @property
    def xmlTag(self) -> str:
        return "FileLogger"

    def validate(self):
        if not self.enabled:
            print("File logging is disabled. No further validation required.")
            return

        super().validate()

        if (
            not self.logFilePath
            or not isinstance(self.logFilePath, str)
            or not self.logFilePath.strip()
        ):
            raise ValueError("logFilePath must be a non-empty string.")

        if not self.logFilePath.endswith(".log"):
            self.logFilePath = self.logFilePath + ".log"

        # A bare file name means the current working directory
        log_dir = os.path.dirname(self.logFilePath) or "."

        if not os.path.exists(log_dir):
            raise ValueError("The directory for logFilePath does not exist.")

        if not os.access(log_dir, os.W_OK):
            raise ValueError("The directory for logFilePath is not writable.")

        if os.path.exists(self.logFilePath) and not os.access(
            self.logFilePath, os.W_OK
        ):
            raise ValueError("The log file is not writable.")

        if not isinstance(self.maxLogFileSize, int) or self.maxLogFileSize <= 0:
            raise ValueError("maxLogFileSize must be a positive integer.")
        # 0 means no rotation backups (matches the XSD nonNegativeInteger)
        if not isinstance(self.maxLogFiles, int) or self.maxLogFiles < 0:
            raise ValueError("maxLogFiles must be a non-negative integer.")

    def toXML(self) -> Element:
        file_logger_element = super().toXML()
        addChild(file_logger_element, "LogFilePath", self.logFilePath)
        addChild(file_logger_element, "MaxLogFileSize", self.maxLogFileSize)
        addChild(file_logger_element, "MaxLogFiles", self.maxLogFiles)
        return file_logger_element

    def fromXML(self, xmlElement) -> None:
        super().fromXML(xmlElement)

        owner = self.__class__.__name__
        self.logFilePath = childText(xmlElement, "LogFilePath", owner)
        if not self.logFilePath:
            raise ValueError(f"Invalid log file path '{self.logFilePath}' provided.")

        self.maxLogFileSize = intChild(xmlElement, "MaxLogFileSize", owner)
        self.maxLogFiles = intChild(xmlElement, "MaxLogFiles", owner)

        self.validate()

    def toJSON(self) -> dict:
        return {
            **super().toJSON(),
            "logFilePath": self.logFilePath,
            "maxLogFileSize": self.maxLogFileSize,
            "maxLogFiles": self.maxLogFiles,
        }

    def fromJSON(self, jsonData: dict) -> None:
        super().fromJSON(jsonData)
        self.logFilePath = jsonData.get("logFilePath", self.logFilePath)
        self.maxLogFileSize = jsonData.get("maxLogFileSize", self.maxLogFileSize)
        self.maxLogFiles = jsonData.get("maxLogFiles", self.maxLogFiles)
        self.validate()


@dataclass
class SyslogLoggerConfig(BaseLoggerConfig):
    syslogServerAddress: str | None = field(
        default="localhost", metadata={"description": "Syslog server address"}
    )

    syslogServerPort: int = field(
        default=514, metadata={"description": "Syslog server port"}
    )

    @property
    def xmlTag(self) -> str:
        return "SyslogLogger"

    def validate(self):
        if not self.enabled:
            print("Syslog logging is disabled. No further validation required.")
            return

        super().validate()

        if not self.syslogServerAddress or not isinstance(
            self.syslogServerAddress, str
        ):
            raise ValueError("Syslog server address must be defined.")

        if (
            not isinstance(self.syslogServerPort, int)
            or not 0 < self.syslogServerPort < 65536
        ):
            raise ValueError(
                "Syslog server port must be a positive integer between 0 and 65536"
            )

    def toXML(self) -> Element:
        syslog_logger_element = super().toXML()
        addChild(syslog_logger_element, "SyslogServer", self.syslogServerAddress)
        addChild(syslog_logger_element, "SyslogPort", self.syslogServerPort)
        return syslog_logger_element

    def fromXML(self, xmlElement) -> None:
        super().fromXML(xmlElement)

        owner = self.__class__.__name__
        self.syslogServerAddress = childText(xmlElement, "SyslogServer", owner)
        if not self.syslogServerAddress:
            raise ValueError(f"Invalid syslog server address '{self.syslogServerAddress}' provided.")

        self.syslogServerPort = intChild(xmlElement, "SyslogPort", owner)

        self.validate()

    def toJSON(self) -> dict:
        return {
            **super().toJSON(),
            "syslogServerAddress": self.syslogServerAddress,
            "syslogServerPort": self.syslogServerPort,
        }

    def fromJSON(self, jsonData: dict) -> None:
        super().fromJSON(jsonData)
        self.syslogServerAddress = jsonData.get(
            "syslogServerAddress", self.syslogServerAddress
        )
        self.syslogServerPort = jsonData.get("syslogServerPort", self.syslogServerPort)
        self.validate()


@dataclass
class LoggerConfig:
    consoleLogger: ConsoleLoggerConfig = field(
        default_factory=ConsoleLoggerConfig,
        metadata={"description": "Console logger configuration."},
    )

    fileLogger: FileLoggerConfig = field(
        default_factory=FileLoggerConfig,
        metadata={"description": "File logger configuration."},
    )

    syslogLogger: SyslogLoggerConfig = field(
        default_factory=SyslogLoggerConfig,
        metadata={"description": "Syslog logger configuration."},
    )

    def validate(self):
        self.consoleLogger.validate()
        self.fileLogger.validate()
        self.syslogLogger.validate()

    def toXML(self) -> Element:
        logger_element = makeElement("Logger")
        logger_element.append(self.consoleLogger.toXML())
        logger_element.append(self.fileLogger.toXML())
        logger_element.append(self.syslogLogger.toXML())
        return logger_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "Logger", owner)

        self.consoleLogger = ConsoleLoggerConfig()
        self.consoleLogger.fromXML(requireChild(xmlElement, "ConsoleLogger", owner))

        self.fileLogger = FileLoggerConfig()
        self.fileLogger.fromXML(requireChild(xmlElement, "FileLogger", owner))

        self.syslogLogger = SyslogLoggerConfig()
        self.syslogLogger.fromXML(requireChild(xmlElement, "SyslogLogger", owner))

    def toJSON(self) -> dict:
        return {
            "consoleLogger": self.consoleLogger.toJSON(),
            "fileLogger": self.fileLogger.toJSON(),
            "syslogLogger": self.syslogLogger.toJSON(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for LoggerConfig")

        if "consoleLogger" in jsonData:
            self.consoleLogger = ConsoleLoggerConfig()
            self.consoleLogger.fromJSON(jsonData["consoleLogger"])
        if "fileLogger" in jsonData:
            self.fileLogger = FileLoggerConfig()
            self.fileLogger.fromJSON(jsonData["fileLogger"])
        if "syslogLogger" in jsonData:
            self.syslogLogger = SyslogLoggerConfig()
            self.syslogLogger.fromJSON(jsonData["syslogLogger"])
