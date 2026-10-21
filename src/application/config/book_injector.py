#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, ParseError, indent, parse

from .database import DatabaseConfig, PostgreSQLConfig, SQLiteConfig
from .instance import Instance
from .ocr import OCRConfig
from .watch_folder import WatchFolderConfig
from .xml_utils import checkTag, makeElement, requireChild


@dataclass
class BookInjector:
    instance: Instance = field(
        default_factory=Instance,
        metadata={"description": "Instance-level settings (API, Web UI, logging)."},
    )
    watchFolder: WatchFolderConfig = field(
        default_factory=WatchFolderConfig,
        metadata={"description": "Watch folder configuration."},
    )
    ocr: OCRConfig = field(
        default_factory=OCRConfig,
        metadata={"description": "OCR configuration."},
    )
    localDatabase: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(xmlTag="LocalDatabase", engine=SQLiteConfig()),
        metadata={"description": "Local database configuration."},
    )
    remoteDatabase: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(xmlTag="RemoteDatabase", engine=PostgreSQLConfig()),
        metadata={"description": "Remote database configuration."},
    )

    def validate(self):
        self.instance.validate()
        self.watchFolder.validate()
        self.ocr.validate()
        self.localDatabase.validate()
        self.remoteDatabase.validate()

    def toXML(self) -> Element:
        root_element = makeElement("BookInjector")
        root_element.append(self.instance.toXML())
        root_element.append(self.watchFolder.toXML())
        root_element.append(self.ocr.toXML())
        root_element.append(self.localDatabase.toXML())
        root_element.append(self.remoteDatabase.toXML())
        return root_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "BookInjector", owner)

        self.instance = Instance()
        self.instance.fromXML(requireChild(xmlElement, "Instance", owner))

        self.watchFolder = WatchFolderConfig()
        self.watchFolder.fromXML(requireChild(xmlElement, "WatchFolder", owner))

        self.ocr = OCRConfig()
        self.ocr.fromXML(requireChild(xmlElement, "OCR", owner))

        self.localDatabase = DatabaseConfig()
        self.localDatabase.fromXML(requireChild(xmlElement, "LocalDatabase", owner))

        self.remoteDatabase = DatabaseConfig()
        self.remoteDatabase.fromXML(requireChild(xmlElement, "RemoteDatabase", owner))

    def fromFile(self, filePath: str | Path) -> None:
        try:
            root_element = parse(filePath).getroot()
        except (OSError, ParseError) as exc:
            raise ValueError(f"Cannot read configuration file '{filePath}': {exc}") from exc
        self.fromXML(root_element)

    def toFile(self, filePath: str | Path) -> None:
        tree = ElementTree(self.toXML())
        indent(tree, space="    ")
        tree.write(filePath, encoding="utf-8", xml_declaration=True)

    def toJSON(self) -> dict:
        return {
            "instance": self.instance.toJSON(),
            "watchFolder": self.watchFolder.toJSON(),
            "ocr": self.ocr.toJSON(),
            "localDatabase": self.localDatabase.toJSON(),
            "remoteDatabase": self.remoteDatabase.toJSON(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for BookInjector")

        if "instance" in jsonData:
            self.instance = Instance()
            self.instance.fromJSON(jsonData["instance"])
        if "watchFolder" in jsonData:
            self.watchFolder = WatchFolderConfig()
            self.watchFolder.fromJSON(jsonData["watchFolder"])
        if "ocr" in jsonData:
            self.ocr = OCRConfig()
            self.ocr.fromJSON(jsonData["ocr"])
        if "localDatabase" in jsonData:
            self.localDatabase.fromJSON(jsonData["localDatabase"])
        if "remoteDatabase" in jsonData:
            self.remoteDatabase.fromJSON(jsonData["remoteDatabase"])
