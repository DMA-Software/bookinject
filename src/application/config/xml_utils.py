#!/usr/bin/env python3
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, register_namespace

NAMESPACE = "urn:bookinjector:config:1"

# Serialize our namespace as the default one instead of "ns0:"
register_namespace("", NAMESPACE)

_TRUE_VALUES = ("true", "1")
_FALSE_VALUES = ("false", "0")


def qname(tag: str) -> str:
    return f"{{{NAMESPACE}}}{tag}"


def localName(xmlElement: Element) -> str:
    return xmlElement.tag.rpartition("}")[2]


def checkTag(xmlElement: Element | None, expectedTag: str, owner: str) -> Element:
    if xmlElement is None or localName(xmlElement) != expectedTag:
        raise ValueError(f"Invalid XML element for {owner}: expected <{expectedTag}>")
    return xmlElement


def findChild(xmlElement: Element, tag: str) -> Element | None:
    # Accept both namespaced and plain tags so configs without xmlns still load
    child = xmlElement.find(qname(tag))
    if child is None:
        child = xmlElement.find(tag)
    return child


def findChildren(xmlElement: Element, tag: str) -> list[Element]:
    return xmlElement.findall(qname(tag)) + xmlElement.findall(tag)


def requireChild(xmlElement: Element, tag: str, owner: str) -> Element:
    child = findChild(xmlElement, tag)
    if child is None:
        raise ValueError(f"The '{tag}' element is missing in the XML for {owner}.")
    return child


def childText(xmlElement: Element, tag: str, owner: str, required: bool = True) -> str | None:
    child = findChild(xmlElement, tag)
    if child is None:
        if required:
            raise ValueError(f"The '{tag}' element is missing in the XML for {owner}.")
        return None
    return (child.text or "").strip()


def parseBool(text: str | None, what: str) -> bool:
    value = (text or "").strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean value '{text}' for {what}.")


def parseInt(text: str | None, what: str) -> int:
    try:
        return int((text or "").strip())
    except ValueError:
        raise ValueError(f"Invalid integer value '{text}' for {what}.") from None


def boolAttr(xmlElement: Element, name: str, owner: str) -> bool:
    value = xmlElement.get(name)
    if value is None:
        raise ValueError(f"The '{name}' attribute is missing in the XML for {owner}.")
    return parseBool(value, f"'{name}' attribute of {owner}")


def boolChild(xmlElement: Element, tag: str, owner: str) -> bool:
    return parseBool(childText(xmlElement, tag, owner), f"'{tag}' of {owner}")


def intChild(xmlElement: Element, tag: str, owner: str) -> int:
    return parseInt(childText(xmlElement, tag, owner), f"'{tag}' of {owner}")


def formatBool(value: bool) -> str:
    return "true" if value else "false"


def makeElement(tag: str, enabled: bool | None = None) -> Element:
    xmlElement = Element(qname(tag))
    if enabled is not None:
        xmlElement.set("enabled", formatBool(enabled))
    return xmlElement


def addChild(parent: Element, tag: str, text: str | int | bool | None = None) -> Element:
    child = SubElement(parent, qname(tag))
    if isinstance(text, bool):
        child.text = formatBool(text)
    elif text is not None:
        child.text = str(text)
    return child
