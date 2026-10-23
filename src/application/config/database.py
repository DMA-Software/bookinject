#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from src.application.config.xml_utils import (
    addChild,
    boolAttr,
    checkTag,
    childText,
    findChild,
    intChild,
    localName,
    makeElement,
)

SUPPORTED_SQLITE_VERSIONS = (3,)
PG_IDENTIFIER_MAX_LENGTH = 63  # NAME_DATA_LEN - 1


@dataclass
class SQLiteConfig:
    dataSource: str = field(
        default="", metadata={"description": "Optional data source name."}
    )
    version: int = field(default=3, metadata={"description": "SQLite major version."})
    dbFilePath: str | None = field(
        default="", metadata={"description": "Path to the SQLite database file."}
    )
    maxConnections: int = field(
        default=10, metadata={"description": "Maximum number of open connections."}
    )
    connectionTimeout: int = field(
        default=30, metadata={"description": "Connection timeout in seconds."}
    )

    def validate(self):
        if not isinstance(self.dataSource, str):
            raise ValueError("dataSource must be a string")  # noqa: TRY004

        if self.version not in SUPPORTED_SQLITE_VERSIONS:
            raise ValueError(f"Unsupported SQLite version: {self.version}")

        if not isinstance(self.dbFilePath, str) or not self.dbFilePath.strip():
            raise ValueError("dbFilePath must be a non-empty string")

        if not isinstance(self.maxConnections, int) or self.maxConnections <= 0:
            raise ValueError("maxConnections must be a positive integer")

        if not isinstance(self.connectionTimeout, int) or self.connectionTimeout <= 0:
            raise ValueError("connectionTimeout must be a positive integer")

    def toXML(self) -> Element:
        sqlite_element = makeElement("SQLite")
        if self.dataSource:
            addChild(sqlite_element, "DataSource", self.dataSource)
        addChild(sqlite_element, "Version", self.version)
        addChild(sqlite_element, "DBFilePath", self.dbFilePath)
        addChild(sqlite_element, "MaxConnections", self.maxConnections)
        addChild(sqlite_element, "ConnectionTimeout", self.connectionTimeout)
        return sqlite_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "SQLite", owner)

        # DataSource is optional in the schema
        self.dataSource = (
            childText(xmlElement, "DataSource", owner, required=False) or ""
        )
        self.version = intChild(xmlElement, "Version", owner)
        self.dbFilePath = childText(xmlElement, "DBFilePath", owner)
        if not self.dbFilePath:
            raise ValueError("dbFilePath must be a non-empty string")

        self.maxConnections = intChild(xmlElement, "MaxConnections", owner)
        self.connectionTimeout = intChild(xmlElement, "ConnectionTimeout", owner)

        self.validate()

    def toJSON(self) -> dict:
        return {
            "dataSource": self.dataSource,
            "version": self.version,
            "dbFilePath": self.dbFilePath,
            "maxConnections": self.maxConnections,
            "connectionTimeout": self.connectionTimeout,
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for SQLiteConfig")

        self.dataSource = jsonData.get("dataSource", self.dataSource)
        self.version = jsonData.get("version", self.version)
        self.dbFilePath = jsonData.get("dbFilePath", self.dbFilePath)
        self.maxConnections = jsonData.get("maxConnections", self.maxConnections)
        self.connectionTimeout = jsonData.get(
            "connectionTimeout", self.connectionTimeout
        )

        self.validate()


@dataclass
class PostgreSQLConfig:
    host: str | None = field(
        default="localhost", metadata={"description": "PostgreSQL server host."}
    )
    port: int = field(default=5432, metadata={"description": "PostgreSQL server port."})
    username: str | None = field(
        default="", metadata={"description": "Database user name."}
    )
    password: str = field(
        default="", metadata={"description": "Database user password."}
    )
    database: str | None = field(default="", metadata={"description": "Database name."})
    maxConnections: int = field(
        default=10, metadata={"description": "Maximum number of open connections."}
    )
    connectionTimeout: int = field(
        default=30, metadata={"description": "Connection timeout in seconds."}
    )

    def validate(self):
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")

        if not isinstance(self.port, int) or not (0 < self.port < 65536):
            raise ValueError("port must be an integer between 1 and 65535")

        for name, value in (("username", self.username), ("database", self.database)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            if len(value) > PG_IDENTIFIER_MAX_LENGTH:
                raise ValueError(
                    f"{name} must not exceed {PG_IDENTIFIER_MAX_LENGTH} characters"
                )

        if not isinstance(self.password, str) or not self.password:
            raise ValueError("password must be a non-empty string")

        if not isinstance(self.maxConnections, int) or self.maxConnections <= 0:
            raise ValueError("maxConnections must be a positive integer")

        if not isinstance(self.connectionTimeout, int) or self.connectionTimeout <= 0:
            raise ValueError("connectionTimeout must be a positive integer")

    def toXML(self) -> Element:
        postgresql_element = makeElement("PostgreSQL")
        addChild(postgresql_element, "Host", self.host)
        addChild(postgresql_element, "Port", self.port)
        addChild(postgresql_element, "Username", self.username)
        addChild(postgresql_element, "Password", self.password)
        addChild(postgresql_element, "Database", self.database)
        addChild(postgresql_element, "MaxConnections", self.maxConnections)
        addChild(postgresql_element, "ConnectionTimeout", self.connectionTimeout)
        return postgresql_element

    def fromXML(self, xmlElement) -> None:
        owner = self.__class__.__name__
        checkTag(xmlElement, "PostgreSQL", owner)

        self.host = childText(xmlElement, "Host", owner)
        if not self.host:
            raise ValueError("host must be a non-empty string")

        self.port = intChild(xmlElement, "Port", owner)

        self.username = childText(xmlElement, "Username", owner)
        if not self.username:
            raise ValueError("username must be a non-empty string")

        # Password whitespace is significant (xs:string in the schema), so no strip()
        password_element = findChild(xmlElement, "Password")
        if password_element is None:
            raise ValueError(
                f"The 'Password' element is missing in the XML for {owner}."
            )
        self.password = password_element.text or ""

        self.database = childText(xmlElement, "Database", owner)
        if not self.database:
            raise ValueError("database must be a non-empty string")

        self.maxConnections = intChild(xmlElement, "MaxConnections", owner)
        self.connectionTimeout = intChild(xmlElement, "ConnectionTimeout", owner)

        self.validate()

    def toJSON(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "maxConnections": self.maxConnections,
            "connectionTimeout": self.connectionTimeout,
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError("Invalid JSON data for PostgreSQLConfig")

        self.host = jsonData.get("host", self.host)
        self.port = jsonData.get("port", self.port)
        self.username = jsonData.get("username", self.username)
        self.password = jsonData.get("password", self.password)
        self.database = jsonData.get("database", self.database)
        self.maxConnections = jsonData.get("maxConnections", self.maxConnections)
        self.connectionTimeout = jsonData.get(
            "connectionTimeout", self.connectionTimeout
        )

        self.validate()


# Engine element name -> config class (xs:choice in DatabaseType)
DATABASE_ENGINES: dict[str, (type[SQLiteConfig | PostgreSQLConfig])] = {
    "SQLite": SQLiteConfig,
    "PostgreSQL": PostgreSQLConfig,
}


@dataclass
class DatabaseConfig:
    """Shared shape of LocalDatabase / RemoteDatabase."""

    xmlTag: str = field(
        default="",
        metadata={"description": "XML element name of this database section."},
    )
    enabled: bool = field(
        default=False,
        metadata={"description": "Flag to enable or disable this database."},
    )
    engine: SQLiteConfig | PostgreSQLConfig = field(
        default_factory=SQLiteConfig,
        metadata={"description": "Engine-specific connection settings."},
    )

    @property
    def engineName(self) -> str:
        return "SQLite" if isinstance(self.engine, SQLiteConfig) else "PostgreSQL"

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError(f"{self.xmlTag}: enabled must be a boolean")  # noqa: TRY004

        if not isinstance(self.engine, (SQLiteConfig, PostgreSQLConfig)):
            raise TypeError(
                f"{self.xmlTag}: engine must be SQLiteConfig or PostgreSQLConfig"
            )
        self.engine.validate()

    def toXML(self) -> Element:
        database_element = makeElement(self.xmlTag, self.enabled)
        database_element.append(self.engine.toXML())
        return database_element

    def fromXML(self, xmlElement) -> None:
        if xmlElement is None:
            raise ValueError(f"Invalid XML element for {self.__class__.__name__}")
        self.xmlTag = localName(xmlElement)
        owner = f"{self.__class__.__name__}({self.xmlTag})"

        self.enabled = boolAttr(xmlElement, "enabled", owner)

        engine_elements = list(xmlElement)
        if len(engine_elements) != 1:
            raise ValueError(
                f"{owner} must contain exactly one engine element: {', '.join(DATABASE_ENGINES)}"
            )
        engine_name = localName(engine_elements[0])
        engine_class = DATABASE_ENGINES.get(engine_name)
        if engine_class is None:
            raise ValueError(f"Unsupported database engine '{engine_name}' in {owner}")

        self.engine = engine_class()
        self.engine.fromXML(engine_elements[0])

        self.validate()

    def toJSON(self) -> dict:
        return {
            "enabled": self.enabled,
            "engine": self.engineName,
            "settings": self.engine.toJSON(),
        }

    def fromJSON(self, jsonData: dict) -> None:
        if not jsonData or not isinstance(jsonData, dict):
            raise ValueError(f"Invalid JSON data for {self.xmlTag}")

        self.enabled = jsonData.get("enabled", self.enabled)
        if "engine" in jsonData:
            engine_class = DATABASE_ENGINES.get(jsonData["engine"])
            if engine_class is None:
                raise ValueError(f"Unsupported database engine '{jsonData['engine']}'")
            self.engine = engine_class()
        if "settings" in jsonData:
            self.engine.fromJSON(jsonData["settings"])

        self.validate()
