#!/usr/bin/env python3
from __future__ import annotations

from enum import Enum


class LogLevel(Enum):
    """Enumerates logging levels with corresponding severity values.

    Provides methods to convert log levels from strings or integers to enum
    members, and custom string/int representations.

    Attributes:
        Invalid (int): Invalid log level with a value of -1.
        Unknown (int): Default unknown log level with a value of 0.
        NOTSET (int): Alias for `Unknown`.
        Debug (int): Debug log level with a value of 10.
        Info (int): Informational log level with a value of 20.
        Warning (int): Warning log level with a value of 30.
        Error (int): Error log level with a value of 40.
        Critical (int): Critical log level with a value of 50.
        Fatal (int): Alias for `Critical`.
    """
    Invalid = -1
    Unknown = 0
    NOTSET = Unknown
    Debug = 10
    Info = 20
    Warning = 30
    Error = 40
    Critical = 50
    Fatal = Critical

    def __str__(self):
        if self == LogLevel.Warning:
            return "warn"
        return self.name.lower()

    def __int__(self):
        return self.value

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        """
        Return the LogLevel corresponding to the given label.

        This method maps a string label to its corresponding LogLevel. If the label
        does not match any known LogLevel, it defaults to LogLevel.Invalid.

        Args:
            label (str): The string label representing the log level.

        Returns:
            LogLevel: The corresponding LogLevel for the given label. Defaults to
            LogLevel.Invalid if the label is unrecognized.

        Examples:
            >>> LogLevel.fromStr("info")
            <LogLevel.Info>
            >>> LogLevel.fromStr("unknown")
            <LogLevel.Invalid>
        """
        retValue: dict[str, LogLevel] = {
            "debug": LogLevel.Debug,
            "info": LogLevel.Info,
            "warning": LogLevel.Warning,
            "warn": LogLevel.Warning,
            "error": LogLevel.Error,
            "critical": LogLevel.Critical,
            "crit": LogLevel.Critical,
            "fatal": LogLevel.Critical,
        }
        return retValue.get(label.lower(), LogLevel.Invalid)

    @staticmethod
    def fromInt(label: int):
        """
        Module for handling log levels with utility methods for creating instances from
        integers and strings.
        """
        if label < 0 or label > 50:
            return LogLevel.Invalid
        return LogLevel.fromStr(LogLevel(label).name.lower())


class LogFormat(Enum):
    """Representation of different logging formats.

    Defines the types of logging formats and provides utility methods to
    handle and convert between formats.

    Attributes:
        Invalid (int): Represents an invalid log format (-1).
        Unknown (int): Represents an unknown log format (0).
        Json (int): Represents JSON log format (1).
        Text (int): Represents plain text log format (2).
    """
    Invalid = -1
    Unknown = 0
    Json = 1
    Text = 2

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        label = label.lower()
        retValue = LogFormat.Unknown
        
        if label == "json":
            retValue = LogFormat.Json
        elif label == "text":
            retValue = LogFormat.Text
        else:
            retValue = LogFormat.Invalid
        return retValue

    @staticmethod
    def fromInt(label: int):
        try:
            return LogFormat(label)
        except ValueError:
            return LogFormat.Invalid


class OCREngine(Enum):
    """Enumerates supported OCR engines.

    This class provides an enumeration of OCR engines and utility methods to
    convert between string and integer representations of these enumerations.

    Attributes:
        Invalid (int): Represents an invalid OCR engine (-1).
        Unknown (int): Represents an unknown OCR engine (0).
        Tesseract (int): Represents the Tesseract OCR engine (1).
        EasyOCR (int): Represents the EasyOCR engine (2).
        PaddleOCR (int): Represents the PaddleOCR engine (3).
    """
    Invalid = -1
    Unknown = 0
    Tesseract = 1
    EasyOCR = 2
    PaddleOCR = 3

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        switchObject = {
            "tesseract": OCREngine.Tesseract,
            "easyocr": OCREngine.EasyOCR,
            "paddleocr": OCREngine.PaddleOCR,
        }
        return switchObject.get(label.lower(), OCREngine.Invalid)

    @staticmethod
    def fromInt(label: int):
        try:
            return OCREngine(label)
        except ValueError:
            return OCREngine.Invalid


class RequestMethods(Enum):
    """
    Enum representing HTTP request methods.

    This class provides an enumeration of HTTP methods, their associated integer
    values, and utility methods for converting between string, integer, and
    enumeration representations.

    Attributes:
        Invalid (int): Represents an invalid method (-1).
        Unknown (int): Represents an unknown method (0).
        Get (int): Represents the HTTP GET method (1).
        Post (int): Represents the HTTP POST method (2).
        Put (int): Represents the HTTP PUT method (3).
        Delete (int): Represents the HTTP DELETE method (4).
        Update (int): Represents the HTTP UPDATE method (5).
        Head (int): Represents the HTTP HEAD method (6).
        Options (int): Represents the HTTP OPTIONS method (7).
    """

    Invalid = -1
    Unknown = 0
    Get = 1
    Post = 2
    Put = 3
    Delete = 4
    Update = 5
    Head = 6
    Options = 7

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return self.name.lower()

    @staticmethod
    def fromStr(label: str) -> RequestMethods:
        label = label.lower()
        switchObject = {
            "unknown": RequestMethods.Unknown,
            "get": RequestMethods.Get,
            "post": RequestMethods.Post,
            "put": RequestMethods.Put,
            "delete": RequestMethods.Delete,
            "update": RequestMethods.Update,
            "head": RequestMethods.Head,
            "options": RequestMethods.Options,
        }
        return switchObject.get(label, RequestMethods.Invalid)

    @staticmethod
    def fromInt(value: int) -> RequestMethods:
        switchObject = {
            0: RequestMethods.Unknown,
            1: RequestMethods.Get,
            2: RequestMethods.Post,
            3: RequestMethods.Put,
            4: RequestMethods.Delete,
            5: RequestMethods.Update,
            6: RequestMethods.Head,
            7: RequestMethods.Options,
        }
        return switchObject.get(value, RequestMethods.Invalid)


class RequestBodyType(Enum):
    """Defines various types of request body content.

    This enumeration represents different types of content that may be included
    in HTTP requests, such as JSON, XML, text, binary data, and others. It also
    provides utility methods for converting between string/int representations
    and enum members.

    Attributes:
        Invalid (int): Represents an invalid request body type (-1).
        Unknown (int): Represents an unknown request body type (0).
        NoneType (int): Represents no request body type (1).
        Json (int): Represents JSON request body type (2).
        Xml (int): Represents XML request body type (3).
        Text (int): Represents text request body type (4).
        Binary (int): Represents binary request body type (5).
        Image (int): Represents image request body type (6).
        Video (int): Represents video request body type (7).
        Audio (int): Represents audio request body type (8).
        Application (int): Represents application-specific request body type (9).
        Multipart (int): Represents multipart request body type (10).
    """

    Invalid = -1
    Unknown = 0
    NoneType = 1
    Json = 2
    Xml = 3
    Text = 4
    Binary = 5
    Image = 6
    Video = 7
    Audio = 8
    Application = 9
    Multipart = 10

    def __str__(self):
        if self == RequestBodyType.NoneType:
            return "none"
        return self.name.lower()

    def __repr__(self):
        return self.name.lower()

    @staticmethod
    def fromStr(label: str) -> RequestBodyType:
        label = label.lower()
        switchObject = {
            "unknown": RequestBodyType.Unknown,
            "none": RequestBodyType.NoneType,
            "json": RequestBodyType.Json,
            "xml": RequestBodyType.Xml,
            "text": RequestBodyType.Text,
            "binary": RequestBodyType.Binary,
            "image": RequestBodyType.Image,
            "video": RequestBodyType.Video,
            "audio": RequestBodyType.Audio,
            "application": RequestBodyType.Application,
            "multipart": RequestBodyType.Multipart,
        }
        return switchObject.get(label, RequestBodyType.Invalid)

    @staticmethod
    def fromInt(value: int) -> RequestBodyType:
        switchObject = {
            0: RequestBodyType.Unknown,
            1: RequestBodyType.NoneType,
            2: RequestBodyType.Json,
            3: RequestBodyType.Xml,
            4: RequestBodyType.Text,
            5: RequestBodyType.Binary,
            6: RequestBodyType.Image,
            7: RequestBodyType.Video,
            8: RequestBodyType.Audio,
            9: RequestBodyType.Application,
            10: RequestBodyType.Multipart,
        }
        return switchObject.get(value, RequestBodyType.Invalid)


class ServiceState(Enum):
    """Enumeration of possible service states.

    This enum defines possible states a service can take during its lifecycle.

    Attributes:
        Invalid (int): State representing an invalid or unrecognized value.
        Unknown (int): State when the service status is not determined.
        New (int): State indicating the service has been created but not started.
        Starting (int): State when the service is in the process of starting.
        Running (int): State indicating the service is actively running.
        Stopping (int): State when the service is shutting down.
        Stopped (int): State indicating the service has been stopped.
        Failed (int): State when the service has encountered an error.
    """
    Invalid = -1
    Unknown = 0
    New = 1
    Starting = 2
    Running = 3
    Stopping = 4
    Stopped = 5
    Failed = 6

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        for state in ServiceState:
            if state.name.lower() == label.lower():
                return state
        return ServiceState.Invalid

    @staticmethod
    def fromInt(label: int):
        try:
            return ServiceState(label)
        except ValueError:
            return ServiceState.Invalid


class MetricSource(Enum):
    """Represents the source type of a metric in a system.

    Metric sources can be invalid, unknown, measured, attributed, or reported.
    Each source type provides information about how the metric data was
    obtained or computed.

    Attributes:
        Invalid (int): Represents an invalid source (-1).
        Unknown (int): Represents an unknown source (0).
        Measured (int): Represents a measured source (1). This source is exact
            for its scope, e.g., OS counters, a worker thread's CPU time.
        Attributed (int): Represents an attributed source (2). This source is
            an estimated share of a resource that multiple services use
            together.
        Reported (int): Represents a reported source (3). This source is counted
            directly by the service itself.
    """

    Invalid = -1
    Unknown = 0
    Measured = 1  # Exact for its scope (OS counters, a worker thread's CPU time)
    Attributed = 2  # Estimated share of a resource the services use together
    Reported = 3  # Counted by the service itself

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        for source in MetricSource:
            if source.name.lower() == label.lower():
                return source
        return MetricSource.Invalid

    @staticmethod
    def fromInt(label: int):
        try:
            return MetricSource(label)
        except ValueError:
            return MetricSource.Invalid


class FailurePolicy(Enum):
    """Enumeration of failure handling policies.

    Defines different strategies for handling failures in a system. Each
    strategy specifies a distinct way to manage errors or failures, such as
    stopping all services, logging the error, or ignoring it altogether.

    Attributes:
        Invalid (int): Represents an invalid policy (-1).
        Unknown (int): Represents an unknown policy (0).
        FailFast (int): Stop all services and the reactor (1).
        Ignore (int): Log the failure, keep the other services running (2).
    """

    Invalid = -1
    Unknown = 0
    FailFast = 1  # Stop all services and the reactor
    Ignore = 2  # Log the failure, keep the other services running

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def fromStr(label: str):
        for policy in FailurePolicy:
            if policy.name.lower() == label.lower():
                return policy
        return FailurePolicy.Invalid

    @staticmethod
    def fromInt(label: int):
        try:
            return FailurePolicy(label)
        except ValueError:
            return FailurePolicy.Invalid
