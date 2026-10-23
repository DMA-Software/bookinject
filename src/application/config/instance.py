#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from src.application.config.api import APIConfig
from src.application.config.logger import LoggerConfig
from src.application.config.webui import WebUIConfig
from src.application.config.xml_utils import (
    addChild,
    checkTag,
    childText,
    makeElement,
    requireChild,
)


@dataclass
class Instance:
    name: str | None = field(
        default="default_instance",
        metadata={"description": "The name of the instance."},
    )
    description: str = field(
        default="Default instance description.",
        metadata={"description": "A brief description of the instance."},
    )
    api: APIConfig = field(
        default_factory=APIConfig,
        metadata={"description": "API configuration for the instance."},
    )
    webUI: WebUIConfig = field(
        default_factory=WebUIConfig,
        metadata={"description": "Web UI configuration for the instance."},
    )
    logger: LoggerConfig = field(
        default_factory=LoggerConfig,
        metadata={"description": "Logger configuration for the instance."},
    )

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        if not isinstance(self.description, str):
            raise ValueError("description must be a string")  # noqa: TRY004

        self.api.validate()
        self.webUI.validate()
        self.logger.validate()

    def toXML(self) -> Element:
        instance_element = makeElement("Instance")
        addChild(instance_element, "Name", self.name)
        addChild(instance_element, "Description", self.description)
        instance_element.append(self.api.toXML())
        instance_element.append(self.webUI.toXML())
        instance_element.append(self.logger.toXML())
        return instance_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "Instance", owner)

        self.name = childText(xmlElement, "Name", owner)
        if not self.name:
            raise ValueError("Application name must be a string and not empty")
        # Description is optional in the schema
        self.description = childText(xmlElement, "Description", owner, required=False) or ""

        self.api = APIConfig()
        self.api.fromXML(requireChild(xmlElement, "API", owner))

        self.webUI = WebUIConfig()
        self.webUI.fromXML(requireChild(xmlElement, "WebUI", owner))

        self.logger = LoggerConfig()
        self.logger.fromXML(requireChild(xmlElement, "Logger", owner))

        self.validate()

    def toJSON(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "api": self.api.toJSON(),
            "webUI": self.webUI.toJSON(),
            "logger": self.logger.toJSON(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for Instance")

        self.name = jsonData.get("name", self.name)
        self.description = jsonData.get("description", self.description)
        if "api" in jsonData:
            self.api = APIConfig()
            self.api.fromJSON(jsonData["api"])
        if "webUI" in jsonData:
            self.webUI = WebUIConfig()
            self.webUI.fromJSON(jsonData["webUI"])
        if "logger" in jsonData:
            self.logger = LoggerConfig()
            self.logger.fromJSON(jsonData["logger"])

        self.validate()
