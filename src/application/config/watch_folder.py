#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from src.application.config.xml_utils import (
    addChild,
    boolAttr,
    boolChild,
    checkTag,
    childText,
    findChildren,
    intChild,
    localName,
    makeElement,
    requireChild,
)

# Extension without leading dot, lowercase (see FileExtensionType in the XSD)
_FILE_EXTENSION_PATTERN = re.compile(r"[a-z0-9]{1,16}")


@dataclass
class FileTypeConfig:
    extension: str = field(
        default="", metadata={"description": "File extension without leading dot."}
    )
    enabled: bool = field(
        default=True, metadata={"description": "Flag to enable or disable this file type."}
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.extension, str) or not _FILE_EXTENSION_PATTERN.fullmatch(self.extension):
            raise ValueError(
                f"Invalid file extension '{self.extension}': expected 1-16 lowercase letters/digits without dot"
            )

    def toXML(self) -> Element:
        file_type_element = makeElement("FileType", self.enabled)
        file_type_element.text = self.extension
        return file_type_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "FileType", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.extension = (xmlElement.text or "").strip()

        self.validate()

    def toJSON(self) -> dict:
        return {"extension": self.extension, "enabled": self.enabled}

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for FileTypeConfig")

        self.extension = jsonData.get("extension", self.extension)
        self.enabled = jsonData.get("enabled", self.enabled)

        self.validate()


@dataclass
class DestinationConfig:
    """Shared shape of MoveProcessedFiles / MoveFailedFiles / ListOf*Files."""

    xmlTag: str = field(
        default="", metadata={"description": "XML element name of this destination."}
    )
    enabled: bool = field(
        default=False, metadata={"description": "Flag to enable or disable this destination."}
    )
    destinationPath: str = field(
        default="", metadata={"description": "Destination path (folder or list file)."}
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError(f"{self.xmlTag}: enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.destinationPath, str) or not self.destinationPath.strip():
            raise ValueError(f"{self.xmlTag}: destinationPath must be a non-empty string")

    def toXML(self) -> Element:
        destination_element = makeElement(self.xmlTag, self.enabled)
        addChild(destination_element, "DestinationPath", self.destinationPath)
        return destination_element

    def fromXML(self, xmlElement) -> None:
        if xmlElement is None:
            raise ValueError(f"Invalid XML element for {self.__class__.__name__}")
        self.xmlTag = localName(xmlElement)
        owner = f"{self.__class__.__name__}({self.xmlTag})"

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.destinationPath = childText(xmlElement, "DestinationPath", owner)

        self.validate()

    def toJSON(self) -> dict:
        return {"enabled": self.enabled, "destinationPath": self.destinationPath}

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError(f"Invalid JSON data for {self.xmlTag}")

        self.enabled = jsonData.get("enabled", self.enabled)
        self.destinationPath = jsonData.get("destinationPath", self.destinationPath)

        self.validate()


@dataclass
class WatchFolderConfig:
    path: str = field(
        default="", metadata={"description": "Folder to watch for incoming files."}
    )
    fileTypes: list[FileTypeConfig] = field(
        default_factory=list[FileTypeConfig],
        metadata={"description": "File types picked up from the watch folder."},
    )
    scanIntervalInSeconds: int = field(
        default=60, metadata={"description": "Interval between folder scans in seconds."}
    )
    keepOriginalFiles: bool = field(
        default=False, metadata={"description": "Keep original files after processing."}
    )
    moveProcessedFiles: DestinationConfig = field(
        default_factory=lambda: DestinationConfig(xmlTag="MoveProcessedFiles"),
        metadata={"description": "Where to move successfully processed files."},
    )
    moveFailedFiles: DestinationConfig = field(
        default_factory=lambda: DestinationConfig(xmlTag="MoveFailedFiles"),
        metadata={"description": "Where to move files that failed processing."},
    )
    listOfProcessedFiles: DestinationConfig = field(
        default_factory=lambda: DestinationConfig(xmlTag="ListOfProcessedFiles"),
        metadata={"description": "File that lists processed files."},
    )
    listOfFailedFiles: DestinationConfig = field(
        default_factory=lambda: DestinationConfig(xmlTag="ListOfFailedFiles"),
        metadata={"description": "File that lists failed files."},
    )

    def validate(self):
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be a non-empty string")

        if not isinstance(self.fileTypes, list) or not self.fileTypes:
            raise ValueError("fileTypes must be a non-empty list")
        for file_type in self.fileTypes:
            file_type.validate()

        extensions = [file_type.extension for file_type in self.fileTypes]
        if len(set(extensions)) != len(extensions):
            raise ValueError("fileTypes must not contain duplicate extensions")

        if not isinstance(self.scanIntervalInSeconds, int) or self.scanIntervalInSeconds <= 0:
            raise ValueError("scanIntervalInSeconds must be a positive integer")

        if not isinstance(self.keepOriginalFiles, bool):
            raise ValueError("keepOriginalFiles must be a boolean")  # noqa: TRY004

        self.moveProcessedFiles.validate()
        self.moveFailedFiles.validate()
        self.listOfProcessedFiles.validate()
        self.listOfFailedFiles.validate()

    def toXML(self) -> Element:
        watch_folder_element = makeElement("WatchFolder")
        addChild(watch_folder_element, "Path", self.path)

        file_types_element = addChild(watch_folder_element, "FileTypes")
        for file_type in self.fileTypes:
            file_types_element.append(file_type.toXML())

        addChild(watch_folder_element, "ScanIntervalInSeconds", self.scanIntervalInSeconds)
        addChild(watch_folder_element, "KeepOriginalFiles", self.keepOriginalFiles)
        watch_folder_element.append(self.moveProcessedFiles.toXML())
        watch_folder_element.append(self.moveFailedFiles.toXML())
        watch_folder_element.append(self.listOfProcessedFiles.toXML())
        watch_folder_element.append(self.listOfFailedFiles.toXML())
        return watch_folder_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "WatchFolder", owner)

        self.path = childText(xmlElement, "Path", owner)

        self.fileTypes = []
        file_types_element = requireChild(xmlElement, "FileTypes", owner)
        for file_type_element in findChildren(file_types_element, "FileType"):
            file_type = FileTypeConfig()
            file_type.fromXML(file_type_element)
            self.fileTypes.append(file_type)

        self.scanIntervalInSeconds = intChild(xmlElement, "ScanIntervalInSeconds", owner)
        self.keepOriginalFiles = boolChild(xmlElement, "KeepOriginalFiles", owner)

        for attr_name, tag in (
            ("moveProcessedFiles", "MoveProcessedFiles"),
            ("moveFailedFiles", "MoveFailedFiles"),
            ("listOfProcessedFiles", "ListOfProcessedFiles"),
            ("listOfFailedFiles", "ListOfFailedFiles"),
        ):
            destination = DestinationConfig(xmlTag=tag)
            destination.fromXML(requireChild(xmlElement, tag, owner))
            setattr(self, attr_name, destination)

        self.validate()

    def toJSON(self) -> dict:
        return {
            "path": self.path,
            "fileTypes": [file_type.toJSON() for file_type in self.fileTypes],
            "scanIntervalInSeconds": self.scanIntervalInSeconds,
            "keepOriginalFiles": self.keepOriginalFiles,
            "moveProcessedFiles": self.moveProcessedFiles.toJSON(),
            "moveFailedFiles": self.moveFailedFiles.toJSON(),
            "listOfProcessedFiles": self.listOfProcessedFiles.toJSON(),
            "listOfFailedFiles": self.listOfFailedFiles.toJSON(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for WatchFolderConfig")

        self.path = jsonData.get("path", self.path)
        if "fileTypes" in jsonData:
            self.fileTypes = []
            for file_type_data in jsonData["fileTypes"]:
                file_type = FileTypeConfig()
                file_type.fromJSON(file_type_data)
                self.fileTypes.append(file_type)
        self.scanIntervalInSeconds = jsonData.get("scanIntervalInSeconds", self.scanIntervalInSeconds)
        self.keepOriginalFiles = jsonData.get("keepOriginalFiles", self.keepOriginalFiles)

        for attr_name in (
            "moveProcessedFiles",
            "moveFailedFiles",
            "listOfProcessedFiles",
            "listOfFailedFiles",
        ):
            if attr_name in jsonData:
                getattr(self, attr_name).fromJSON(jsonData[attr_name])

        self.validate()
