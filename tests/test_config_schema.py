"""Schema tests for conf/schemas/bookinjector.xsd.

Run:  python -m pytest tests -v
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import xmlschema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Test-only reference config with stable placeholder values (see the file header)
CONFIG_PATH = PROJECT_ROOT / "tests" / "fixtures" / "bookinjector.xml"
SCHEMA_PATH = PROJECT_ROOT / "conf" / "schemas" / "bookinjector.xsd"

NS = {"bi": "urn:bookinjector:config:1"}
LOGGERS = ["ConsoleLogger", "FileLogger", "SyslogLogger"]


@pytest.fixture(scope="session")
def schema() -> xmlschema.XMLSchema10:
    return xmlschema.XMLSchema10(str(SCHEMA_PATH))


@pytest.fixture(scope="session")
def base_xml() -> str:
    return CONFIG_PATH.read_text(encoding="utf-8")


def mutate(base: str, old: str, new: str) -> str:
    """Replace the first occurrence of `old`; fail loudly if the anchor is gone."""
    assert old in base, f"anchor not found in config: {old!r}"
    return base.replace(old, new, 1)


def edit_element(base: str, xpath: str, *, text: str | None = None,
                 remove: bool = False) -> str:
    """Change text of / remove the element at `xpath` (relative to root, prefix `bi:`).

    Structure-aware alternative to `mutate` for targeting a specific occurrence
    (e.g. LogFormatter inside FileLogger) independently of indentation.
    """
    root = ET.fromstring(base.encode("utf-8"))
    parent_path, _, child = xpath.rpartition("/")
    parent = root.find(parent_path, NS) if parent_path else root
    assert parent is not None, f"parent not found: {parent_path}"
    node = parent.find(child, NS)
    assert node is not None, f"element not found: {xpath}"
    if remove:
        parent.remove(node)
    else:
        node.text = text
    return ET.tostring(root, encoding="unicode")


def logger_xpath(logger: str, child: str) -> str:
    return f"bi:Instance/bi:Logger/bi:{logger}/bi:{child}"


def test_reference_config_is_valid(schema):
    schema.validate(str(CONFIG_PATH))


# (test id, old fragment, new fragment)
VALID_CASES = [
    ("pg-host-ipv4", "<Host>localhost</Host>", "<Host>10.0.0.5</Host>"),
    ("pg-host-fqdn", "<Host>localhost</Host>", "<Host>db.example.com</Host>"),
    ("listen-ipv6-any", "<ListenInterface>0.0.0.0</ListenInterface>",
     "<ListenInterface>::</ListenInterface>"),
    ("syslog-ipv4", "<SyslogServer>localhost</SyslogServer>",
     "<SyslogServer>192.168.1.10</SyslogServer>"),
    ("password-special-chars", "<Password>your_password</Password>",
     "<Password>1P@ss w0rd!&amp;-</Password>"),
    ("allowed-ips-multiple", "<IP>0.0.0.0/0</IP>",
     "<IP>10.0.0.0/8</IP><IP>192.168.1.5</IP><IP>fe80::/10</IP>"),
    ("loglevel-lowercase", "<LogLevel>INFO</LogLevel>", "<LogLevel>warn</LogLevel>"),
    ("ocr-lang-script-variant", '<Language enabled="true">aze</Language>',
     '<Language enabled="true">aze_cyrl</Language>'),
    ("max-log-files-zero", "<MaxLogFiles>5</MaxLogFiles>", "<MaxLogFiles>0</MaxLogFiles>"),
    ("log-formatter-json", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>json</LogFormatter>"),
    ("log-formatter-JSON", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>JSON</LogFormatter>"),
    ("log-formatter-TEXT", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>TEXT</LogFormatter>"),
    ("log-formatter-before-level",
     "<LogLevel>INFO</LogLevel>\n                <LogFormatter>text</LogFormatter>",
     "<LogFormatter>text</LogFormatter>\n                <LogLevel>INFO</LogLevel>"),
    ("element-order-free",
     "<ListenInterface>0.0.0.0</ListenInterface>\n            <ListenPort>18080</ListenPort>",
     "<ListenPort>18080</ListenPort>\n            <ListenInterface>0.0.0.0</ListenInterface>"),
]

INVALID_CASES = [
    ("host-bad-ipv4", "<Host>localhost</Host>", "<Host>999.1.1.1</Host>"),
    ("port-zero", "<Port>5432</Port>", "<Port>0</Port>"),
    ("port-overflow", "<SyslogPort>514</SyslogPort>", "<SyslogPort>70000</SyslogPort>"),
    ("loglevel-unknown", "<LogLevel>INFO</LogLevel>", "<LogLevel>VERBOSE</LogLevel>"),
    ("ocr-engine-unknown", 'ocrType="Tesseract"', 'ocrType="Foo"'),
    ("timeout-zero", "<ConnectionTimeout>30</ConnectionTimeout>",
     "<ConnectionTimeout>0</ConnectionTimeout>"),
    ("apikey-too-short", "<APIKey>your_api_key_here</APIKey>", "<APIKey>abc</APIKey>"),
    ("filetype-duplicate", '<FileType enabled="true">epub</FileType>',
     '<FileType enabled="true">pdf</FileType>'),
    ("filetype-uppercase", '<FileType enabled="true">epub</FileType>',
     '<FileType enabled="true">EPUB</FileType>'),
    ("ocr-lang-duplicate", '<Language enabled="true">rus</Language>',
     '<Language enabled="true">eng</Language>'),
    ("allowed-ip-duplicate", "<IP>0.0.0.0/0</IP>",
     "<IP>0.0.0.0/0</IP><IP>0.0.0.0/0</IP>"),
    ("ipv4-cidr-33", "<IP>0.0.0.0/0</IP>", "<IP>10.0.0.0/33</IP>"),
    ("sqlite-with-host", "<Version>3</Version>", "<Version>3</Version><Host>x</Host>"),
    ("sqlite-version-2", "<Version>3</Version>", "<Version>2</Version>"),
    ("pg-with-dbfilepath", "<Database>bookinjector</Database>",
     "<Database>bookinjector</Database><DBFilePath>/x</DBFilePath>"),
    ("path-blank", "<Path>/path/to/watch/folder</Path>", "<Path>  </Path>"),
    ("enabled-missing", '<TLS enabled="false">', "<TLS>"),
    ("enabled-not-bool", '<TLS enabled="false">', '<TLS enabled="maybe">'),
    ("required-element-missing", "<KeepOriginalFiles>false</KeepOriginalFiles>", ""),
    ("log-formatter-unknown", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>xml</LogFormatter>"),
    ("log-formatter-mixed-case", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>Json</LogFormatter>"),
    ("log-formatter-empty", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter></LogFormatter>"),
    ("log-formatter-duplicate", "<LogFormatter>text</LogFormatter>",
     "<LogFormatter>text</LogFormatter><LogFormatter>json</LogFormatter>"),
]


@pytest.mark.parametrize("old,new", [c[1:] for c in VALID_CASES],
                         ids=[c[0] for c in VALID_CASES])
def test_valid_variants(schema, base_xml, old, new):
    errors = list(schema.iter_errors(mutate(base_xml, old, new)))
    assert not errors, "\n".join(f"{e.path}: {e.reason}" for e in errors)


@pytest.mark.parametrize("old,new", [c[1:] for c in INVALID_CASES],
                         ids=[c[0] for c in INVALID_CASES])
def test_invalid_variants(schema, base_xml, old, new):
    assert not schema.is_valid(mutate(base_xml, old, new))


# ---------------------------------------------------------------------------
# LogFormatter: checked per logger, independent of element order/indentation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("logger", LOGGERS)
def test_log_formatter_present_in_reference_config(base_xml, logger):
    root = ET.fromstring(base_xml.encode("utf-8"))
    assert root.find(logger_xpath(logger, "LogFormatter"), NS) is not None


@pytest.mark.parametrize("logger", LOGGERS)
def test_log_formatter_required(schema, base_xml, logger):
    xml = edit_element(base_xml, logger_xpath(logger, "LogFormatter"), remove=True)
    assert not schema.is_valid(xml)


@pytest.mark.parametrize("value", ["text", "json", "TEXT", "JSON"])
@pytest.mark.parametrize("logger", LOGGERS)
def test_log_formatter_allowed_values(schema, base_xml, logger, value):
    xml = edit_element(base_xml, logger_xpath(logger, "LogFormatter"), text=value)
    errors = list(schema.iter_errors(xml))
    assert not errors, "\n".join(f"{e.path}: {e.reason}" for e in errors)


@pytest.mark.parametrize("value", ["xml", "Json", "Text", "", " ", "plain"])
@pytest.mark.parametrize("logger", LOGGERS)
def test_log_formatter_rejected_values(schema, base_xml, logger, value):
    xml = edit_element(base_xml, logger_xpath(logger, "LogFormatter"), text=value)
    assert not schema.is_valid(xml)
