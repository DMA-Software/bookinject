#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from src.application.config.api import TLSConfig
from src.application.config.xml_utils import (
    addChild,
    boolAttr,
    checkTag,
    childText,
    findChildren,
    intChild,
    makeElement,
    requireChild,
)


@dataclass
class WebUIConfig:
    enabled: bool = field(
        default=False,
        metadata={"description": "Flag to enable or disable the Web UI server."},
    )
    listenInterface: str = field(
        default="0.0.0.0",
        metadata={"description": "The network interface the Web UI server listens on."},
    )
    listenPort: int = field(
        default=8080,
        metadata={"description": "The port number the Web UI server listens on."},
    )
    tls: TLSConfig = field(
        default_factory=TLSConfig,
        metadata={"description": "TLS configuration for the Web UI server."},
    )
    maxConnections: int = field(
        default=100,
        metadata={
            "description": "The maximum number of concurrent connections allowed."
        },
    )
    allowedIPs: list[str] = field(
        default_factory=list[str],
        metadata={"description": "List of allowed IP addresses."},
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.listenInterface, str) or not self.listenInterface:
            raise ValueError("listenInterface must be a non-empty string")

        if not isinstance(self.listenPort, int) or not (0 < self.listenPort < 65536):
            raise ValueError("listenPort must be an integer between 1 and 65535")

        if not isinstance(self.tls, TLSConfig):
            raise ValueError("tls must be a TLSConfig instance")  # noqa: TRY004
        self.tls.validate()

        if not isinstance(self.maxConnections, int) or self.maxConnections <= 0:
            raise ValueError("maxConnections must be a positive integer")

        if (
            not isinstance(self.allowedIPs, list)
            or not self.allowedIPs
            or any(not isinstance(ip, str) or not ip for ip in self.allowedIPs)
        ):
            raise ValueError("allowedIPs must be a non-empty list of non-empty strings")

        if len(set(self.allowedIPs)) != len(self.allowedIPs):
            raise ValueError("allowedIPs must not contain duplicates")

    def toXML(self) -> Element:
        webui_element = makeElement("WebUI", self.enabled)
        addChild(webui_element, "ListenInterface", self.listenInterface)
        addChild(webui_element, "ListenPort", self.listenPort)
        webui_element.append(self.tls.toXML())
        addChild(webui_element, "MaxConnections", self.maxConnections)

        allowed_ips_element = addChild(webui_element, "AllowedIPs")
        for ip in self.allowedIPs:
            addChild(allowed_ips_element, "IP", ip)

        return webui_element

    def fromXML(self, xmlElement):
        owner = self.__class__.__name__
        checkTag(xmlElement, "WebUI", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.listenInterface = childText(xmlElement, "ListenInterface", owner)
        self.listenPort = intChild(xmlElement, "ListenPort", owner)

        self.tls = TLSConfig()
        self.tls.fromXML(requireChild(xmlElement, "TLS", owner))

        self.maxConnections = intChild(xmlElement, "MaxConnections", owner)

        allowed_ips_element = requireChild(xmlElement, "AllowedIPs", owner)
        self.allowedIPs = [
            (ip_element.text or "").strip()
            for ip_element in findChildren(allowed_ips_element, "IP")
        ]

        self.validate()

    def toJSON(self) -> dict:
        return {
            "enabled": self.enabled,
            "listenInterface": self.listenInterface,
            "listenPort": self.listenPort,
            "tls": self.tls.toJSON(),
            "maxConnections": self.maxConnections,
            "allowedIPs": list(self.allowedIPs),
        }

    def fromJSON(self, jsonData: dict):
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for WebUIConfig")

        self.enabled = jsonData.get("enabled", self.enabled)
        self.listenInterface = jsonData.get("listenInterface", self.listenInterface)
        self.listenPort = jsonData.get("listenPort", self.listenPort)
        if "tls" in jsonData:
            self.tls = TLSConfig()
            self.tls.fromJSON(jsonData["tls"])
        self.maxConnections = jsonData.get("maxConnections", self.maxConnections)
        self.allowedIPs = list(jsonData.get("allowedIPs", self.allowedIPs))

        self.validate()
