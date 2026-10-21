"""Deserialization tests for conf/bookinjector.xml -> BookInjector dataclasses.

Run:  python -m pytest tests -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
import xmlschema

from src.application.config.book_injector import BookInjector
from src.application.config.database import PostgreSQLConfig, SQLiteConfig
from src.enumerations import LogFormat, LogLevel, OCREngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "conf" / "bookinjector.xml"
SCHEMA_PATH = PROJECT_ROOT / "conf" / "schemas" / "bookinjector.xsd"

# FileLoggerConfig.validate() requires an existing writable log directory
LOG_PATH_ANCHOR = "/path/to/log/file.log"


@pytest.fixture
def base_xml(tmp_path) -> str:
    xml = CONFIG_PATH.read_text(encoding="utf-8")
    return xml.replace(LOG_PATH_ANCHOR, (tmp_path / "file.log").as_posix())


def load(tmp_path: Path, xml: str) -> BookInjector:
    config_file = tmp_path / "config.xml"
    config_file.write_text(xml, encoding="utf-8")
    config = BookInjector()
    config.fromFile(config_file)
    return config


def mutate(base: str, old: str, new: str) -> str:
    assert old in base, f"anchor not found in config: {old!r}"
    return base.replace(old, new, 1)


def test_reference_config_values(tmp_path, base_xml):
    config = load(tmp_path, base_xml)

    instance = config.instance
    assert instance.name == "BookInjector"
    assert instance.api.enabled is True
    assert instance.api.listenPort == 18080
    assert instance.api.tls.enabled is False
    assert instance.api.tls.certificatePath == "/path/to/tls/certificate.pem"
    assert instance.api.apiKey == "your_api_key_here"
    assert instance.api.allowedIPs == ["0.0.0.0/0"]
    assert instance.webUI.listenPort == 8080
    assert instance.webUI.maxConnections == 100

    logger = instance.logger
    assert logger.consoleLogger.logLevel == LogLevel.Info
    assert logger.consoleLogger.logFormatterType == LogFormat.Text
    assert logger.consoleLogger.colorize is False
    assert logger.fileLogger.maxLogFileSize == 10485760
    assert logger.fileLogger.maxLogFiles == 5
    assert logger.syslogLogger.enabled is False
    assert logger.syslogLogger.logFormatterType == LogFormat.Json
    assert logger.syslogLogger.syslogServerPort == 514

    watch_folder = config.watchFolder
    assert watch_folder.path == "/path/to/watch/folder"
    assert [ft.extension for ft in watch_folder.fileTypes] == [
        "pdf", "epub", "mobi", "png", "jpg", "jpeg", "tiff",
    ]
    assert watch_folder.scanIntervalInSeconds == 60
    assert watch_folder.keepOriginalFiles is False
    assert watch_folder.moveFailedFiles.destinationPath == "/path/to/failed/folder"
    assert watch_folder.listOfProcessedFiles.xmlTag == "ListOfProcessedFiles"

    assert config.ocr.enabled is True
    assert config.ocr.autoDetectLanguage is True
    assert config.ocr.ocrType == OCREngine.Tesseract
    assert [lang.code for lang in config.ocr.languages][:3] == ["eng", "rus", "aze"]

    assert isinstance(config.localDatabase.engine, SQLiteConfig)
    assert config.localDatabase.engine.dbFilePath == "/path/to/database/bookinjector.db"
    assert config.remoteDatabase.enabled is False
    assert isinstance(config.remoteDatabase.engine, PostgreSQLConfig)
    assert config.remoteDatabase.engine.port == 5432


def test_xml_roundtrip_is_schema_valid_and_lossless(tmp_path, base_xml):
    config = load(tmp_path, base_xml)
    out_file = tmp_path / "out.xml"
    config.toFile(out_file)

    xmlschema.XMLSchema10(str(SCHEMA_PATH)).validate(str(out_file))

    reloaded = BookInjector()
    reloaded.fromFile(out_file)
    assert reloaded == config


def test_json_roundtrip_is_lossless(tmp_path, base_xml):
    config = load(tmp_path, base_xml)
    reloaded = BookInjector()
    reloaded.fromJSON(config.toJSON())
    assert reloaded == config


def test_config_without_namespace_loads(tmp_path, base_xml):
    xml = mutate(base_xml, 'xmlns="urn:bookinjector:config:1"', "")
    assert load(tmp_path, xml).instance.api.listenPort == 18080


def test_database_engine_is_selected_by_element(tmp_path, base_xml):
    xml = mutate(base_xml, "<RemoteDatabase enabled=\"false\">",
                 "<RemoteDatabase enabled=\"false\"><SQLite><Version>3</Version>"
                 "<DBFilePath>/x.db</DBFilePath><MaxConnections>1</MaxConnections>"
                 "<ConnectionTimeout>1</ConnectionTimeout></SQLite>")
    # Two engines inside one database section is rejected
    with pytest.raises(ValueError, match="exactly one engine"):
        load(tmp_path, xml)


def test_xs_boolean_numeric_values(tmp_path, base_xml):
    xml = mutate(base_xml, "<KeepOriginalFiles>false</KeepOriginalFiles>",
                 "<KeepOriginalFiles>1</KeepOriginalFiles>")
    assert load(tmp_path, xml).watchFolder.keepOriginalFiles is True


INVALID_CASES = [
    ("enabled-missing", '<TLS enabled="false">', "<TLS>"),
    ("enabled-not-bool", '<TLS enabled="false">', '<TLS enabled="maybe">'),
    ("port-not-int", "<ListenPort>18080</ListenPort>", "<ListenPort>abc</ListenPort>"),
    ("port-zero", "<ListenPort>18080</ListenPort>", "<ListenPort>0</ListenPort>"),
    ("required-element-missing", "<KeepOriginalFiles>false</KeepOriginalFiles>", ""),
    ("log-formatter-unknown", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>xml</LogFormatter>"),
    ("ocr-engine-unknown", 'ocrType="Tesseract"', 'ocrType="Foo"'),
    ("filetype-duplicate", '<FileType enabled="true">epub</FileType>',
     '<FileType enabled="true">pdf</FileType>'),
    ("filetype-uppercase", '<FileType enabled="true">epub</FileType>',
     '<FileType enabled="true">EPUB</FileType>'),
    ("ocr-lang-duplicate", '<Language enabled="true">rus</Language>',
     '<Language enabled="true">eng</Language>'),
    ("sqlite-version-2", "<Version>3</Version>", "<Version>2</Version>"),
    ("db-engine-unknown", "<SQLite>", "<MySQL>"),
    ("timeout-zero", "<ConnectionTimeout>30</ConnectionTimeout>",
     "<ConnectionTimeout>0</ConnectionTimeout>"),
    ("tls-enabled-without-path",
     '<TLS enabled="false">\n                <CertificatePath>/path/to/tls/certificate.pem</CertificatePath>',
     '<TLS enabled="true">\n                <CertificatePath></CertificatePath>'),
    ("wrong-root", "<BookInjector ", "<NotBookInjector "),
]


@pytest.mark.parametrize("old,new", [c[1:] for c in INVALID_CASES],
                         ids=[c[0] for c in INVALID_CASES])
def test_invalid_config_rejected(tmp_path, base_xml, old, new):
    xml = mutate(base_xml, old, new)
    if old == "<BookInjector ":
        xml = xml.replace("</BookInjector>", "</NotBookInjector>")
    if old == "<SQLite>":
        xml = xml.replace("</SQLite>", "</MySQL>")
    with pytest.raises(ValueError):
        load(tmp_path, xml)


def test_unreadable_file_raises_value_error(tmp_path):
    with pytest.raises(ValueError, match="Cannot read configuration file"):
        BookInjector().fromFile(tmp_path / "missing.xml")
