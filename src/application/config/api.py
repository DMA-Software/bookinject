#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from .xml_utils import (
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
class TLSConfig:
    enabled: bool = field(
        default=False, metadata={"description": "Flag to enable or disable TLS."}
    )
    certificatePath: str | None = field(
        default="", metadata={"description": "Path to the TLS certificate file."}
    )
    keyPath: str | None = field(
        default="", metadata={"description": "Path to the TLS key file."}
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")  # noqa: TRY004

        if self.enabled:
            if not self.certificatePath or not isinstance(self.certificatePath, str):
                raise ValueError(
                    "certificatePath must be a non-empty string when TLS is enabled"
                )

            if not self.keyPath or not isinstance(self.keyPath, str):
                raise ValueError(
                    "keyPath must be a non-empty string when TLS is enabled"
                )

    def fromXML(self, xmlElement):
        owner = self.__class__.__name__
        checkTag(xmlElement, "TLS", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.certificatePath = childText(xmlElement, "CertificatePath", owner)
        if self.enabled and not self.certificatePath:
            raise ValueError(
                "certificatePath must be a non-empty string when TLS is enabled"
            )

        self.keyPath = childText(xmlElement, "KeyPath", owner)
        if self.enabled and not self.keyPath:
            raise ValueError(
                "keyPath must be a non-empty string when TLS is enabled"
            )

        self.validate()

    def toXML(self) -> Element:
        tls_element = makeElement("TLS", self.enabled)
        addChild(tls_element, "CertificatePath", self.certificatePath)
        addChild(tls_element, "KeyPath", self.keyPath)
        return tls_element

    def toJSON(self) -> dict:
        return {
            "enabled": self.enabled,
            "certificatePath": self.certificatePath,
            "keyPath": self.keyPath,
        }

    def fromJSON(self, jsonData: dict):
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for TLSConfig")

        self.enabled = jsonData.get("enabled", self.enabled)
        self.certificatePath = jsonData.get("certificatePath", self.certificatePath)
        self.keyPath = jsonData.get("keyPath", self.keyPath)

        self.validate()


@dataclass
class APIConfig:
    enabled: bool = field(
        default=False,
        metadata={"description": "Flag to enable or disable the API server."},
    )
    listenInterface: str | None = field(
        default="0.0.0.0",
        metadata={"description": "The network interface the API server listens on."},
    )
    listenPort: int = field(
        default=8080,
        metadata={"description": "The port number the API server listens on."},
    )
    tls: TLSConfig = field(
        default_factory=TLSConfig,
        metadata={"description": "TLS configuration for the API server."},
    )
    apiKey: str | None = field(
        default="default_api_key",
        metadata={"description": "The API key for authenticating requests."},
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

        if not isinstance(self.apiKey, str) or not self.apiKey:
            raise ValueError("apiKey must be a non-empty string")

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
        api_element = makeElement("API", self.enabled)
        addChild(api_element, "ListenInterface", self.listenInterface)
        addChild(api_element, "ListenPort", self.listenPort)
        api_element.append(self.tls.toXML())
        addChild(api_element, "APIKey", self.apiKey)
        addChild(api_element, "MaxConnections", self.maxConnections)

        allowed_ips_element = addChild(api_element, "AllowedIPs")
        for ip in self.allowedIPs:
            addChild(allowed_ips_element, "IP", ip)

        return api_element

    def fromXML(self, xmlElement):
        owner = self.__class__.__name__
        checkTag(xmlElement, "API", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.listenInterface = childText(xmlElement, "ListenInterface", owner)
        if self.enabled and not self.listenInterface:
            raise ValueError(
                "listenInterface must be a non-empty string when API is enabled"
            )

        self.listenPort = intChild(xmlElement, "ListenPort", owner)

        self.tls = TLSConfig()
        self.tls.fromXML(requireChild(xmlElement, "TLS", owner))

        self.apiKey = childText(xmlElement, "APIKey", owner)
        if self.enabled and not self.apiKey:
            raise ValueError("apiKey must be a non-empty string when API is enabled")

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
            "apiKey": self.apiKey,
            "maxConnections": self.maxConnections,
            "allowedIPs": list(self.allowedIPs),
        }

    def fromJSON(self, jsonData: dict):
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for APIConfig")

        self.enabled = jsonData.get("enabled", self.enabled)
        self.listenInterface = jsonData.get("listenInterface", self.listenInterface)
        self.listenPort = jsonData.get("listenPort", self.listenPort)
        if "tls" in jsonData:
            self.tls = TLSConfig()
            self.tls.fromJSON(jsonData["tls"])
        self.apiKey = jsonData.get("apiKey", self.apiKey)
        self.maxConnections = jsonData.get("maxConnections", self.maxConnections)
        self.allowedIPs = list(jsonData.get("allowedIPs", self.allowedIPs))

        self.validate()
