#!/usr/bin/env python3
from __future__ import annotations

from enum import Enum


class LogLevel(Enum):
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
        if label < 0 or label > 50:
            return LogLevel.Invalid
        return LogLevel.fromStr(LogLevel(label).name.lower())


class LogFormat(Enum):
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
    This class represents the different HTTP request methods.

    Attributes:
        Invalid (RequestMethods): Represents an invalid request method.
        Unknown (RequestMethods): Represents an unknown request method.
        Get (RequestMethods): Represents the GET request method.
        Post (RequestMethods): Represents the POST request method.
        Put (RequestMethods): Represents the PUT request method.
        Delete (RequestMethods): Represents the DELETE request method.
        Update (RequestMethods): Represents the UPDATE request method.
        Head (RequestMethods): Represents the HEAD request method.
        Options (RequestMethods): Represents the OPTIONS request method.

    Methods:
        __str__(self):
            Returns the lowercase string representation of the request method.

        __repr__(self):
            Returns the lowercase string representation of the request method.

        fromStr(label: str):
            Static method that returns the corresponding RequestMethods enum
            value based on the provided string label. If the label is not recognized,
            it returns the Invalid enum value.

        fromInt(value: int):
            Static method that returns the corresponding RequestMethods enum
            value based on the provided integer value. If the value is not recognized,
            it returns the Invalid enum value.
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
    """
    The RequestBodyType class represents the type of request body.

    Attributes:
        Invalid: An invalid request body type.
        Unknown: An unknown request body type.
        Json: A JSON request body type.
        Xml: An XML request body type.
        Text: A text request body type.
        Binary: A binary request body type.
        Image: An image request body type.
        Video: A video request body type.
        Audio: An audio request body type.
        Application: An application request body type.
        Multipart: A multipart request body type.

    Methods:
        __str__(self):
            Returns the lowercase string representation of the request body type.

        __repr__(self):
            Returns the lowercase string representation of the request body type.

        fromStr(label: str):
            Static method that returns the corresponding RequestBodyType enum
            value based on the provided string label. If the label is not recognized,
            it returns the Invalid enum value.

        fromInt(value: int):
            Static method that returns the corresponding RequestBodyType enum
            value based on the provided integer value. If the value is not recognized,
            it returns the Invalid enum value.
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
