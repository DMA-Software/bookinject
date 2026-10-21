#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from src.enumerations import OCREngine

from .xml_utils import (
    addChild,
    boolAttr,
    checkTag,
    findChildren,
    formatBool,
    makeElement,
    requireChild,
)

# Tesseract traineddata code: ISO 639-2 + optional script/variant (see LanguageCodeType in the XSD)
_LANGUAGE_CODE_PATTERN = re.compile(r"[a-z]{3}(_[a-z]+)*")


@dataclass
class OCRLanguageConfig:
    code: str = field(
        default="", metadata={"description": "Tesseract language code (e.g. eng, aze_cyrl)."}
    )
    enabled: bool = field(
        default=True, metadata={"description": "Flag to enable or disable this language."}
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.code, str) or not _LANGUAGE_CODE_PATTERN.fullmatch(self.code):
            raise ValueError(f"Invalid OCR language code '{self.code}'")

    def toXML(self) -> Element:
        language_element = makeElement("Language", self.enabled)
        language_element.text = self.code
        return language_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "Language", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.code = (xmlElement.text or "").strip()

        self.validate()

    def toJSON(self) -> dict:
        return {"code": self.code, "enabled": self.enabled}

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for OCRLanguageConfig")

        self.code = jsonData.get("code", self.code)
        self.enabled = jsonData.get("enabled", self.enabled)

        self.validate()


@dataclass
class OCRConfig:
    enabled: bool = field(
        default=False, metadata={"description": "Flag to enable or disable OCR."}
    )
    autoDetectLanguage: bool = field(
        default=True, metadata={"description": "Detect document language automatically."}
    )
    ocrType: OCREngine = field(
        default=OCREngine.Tesseract, metadata={"description": "OCR engine to use."}
    )
    languages: list[OCRLanguageConfig] = field(
        default_factory=list[OCRLanguageConfig],
        metadata={"description": "Languages available to the OCR engine."},
    )

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.autoDetectLanguage, bool):
            raise ValueError("autoDetectLanguage must be a boolean")  # noqa: TRY004

        if self.ocrType in [OCREngine.Unknown, OCREngine.Invalid]:
            raise ValueError(
                f"Invalid OCR engine: {self.ocrType}. Must be one of Tesseract, EasyOCR, PaddleOCR."
            )

        if not isinstance(self.languages, list) or not self.languages:
            raise ValueError("languages must be a non-empty list")
        for language in self.languages:
            language.validate()

        codes = [language.code for language in self.languages]
        if len(set(codes)) != len(codes):
            raise ValueError("languages must not contain duplicate codes")

    def toXML(self) -> Element:
        ocr_element = makeElement("OCR", self.enabled)
        ocr_element.set("autoDetectLanguage", formatBool(self.autoDetectLanguage))
        ocr_element.set("ocrType", str(self.ocrType))

        languages_element = addChild(ocr_element, "Languages")
        for language in self.languages:
            languages_element.append(language.toXML())
        return ocr_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "OCR", owner)

        self.enabled = boolAttr(xmlElement, "enabled", owner)
        self.autoDetectLanguage = boolAttr(xmlElement, "autoDetectLanguage", owner)

        ocr_type_text = xmlElement.get("ocrType")
        if ocr_type_text is None:
            raise ValueError(f"The 'ocrType' attribute is missing in the XML for {owner}.")
        self.ocrType = OCREngine.from_str(ocr_type_text)

        self.languages = []
        languages_element = requireChild(xmlElement, "Languages", owner)
        for language_element in findChildren(languages_element, "Language"):
            language = OCRLanguageConfig()
            language.fromXML(language_element)
            self.languages.append(language)

        self.validate()

    def toJSON(self) -> dict:
        return {
            "enabled": self.enabled,
            "autoDetectLanguage": self.autoDetectLanguage,
            "ocrType": str(self.ocrType),
            "languages": [language.toJSON() for language in self.languages],
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for OCRConfig")

        self.enabled = jsonData.get("enabled", self.enabled)
        self.autoDetectLanguage = jsonData.get("autoDetectLanguage", self.autoDetectLanguage)
        if "ocrType" in jsonData:
            self.ocrType = OCREngine.from_str(jsonData["ocrType"])
        if "languages" in jsonData:
            self.languages = []
            for language_data in jsonData["languages"]:
                language = OCRLanguageConfig()
                language.fromJSON(language_data)
                self.languages.append(language)

        self.validate()
