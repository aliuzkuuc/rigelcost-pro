from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from ctypes import wintypes
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QStandardPaths


@dataclass(frozen=True)
class DatabaseSettings:
    """Rigel'in merkezi SQL Server bağlantı ayarları."""

    mode: str = "sqlserver"
    server: str = ""
    database: str = "RIGEL_COST_PRO"
    trusted_connection: bool = True
    username: str = ""
    password: str = ""
    attachment_share: str = ""
    encrypt: bool = True
    trust_server_certificate: bool = True

    def validated(self) -> "DatabaseSettings":
        mode = self.mode.strip().lower()
        if mode not in {"sqlserver", "sqlite"}:
            raise ValueError("Veritabanı tipi sqlserver veya sqlite olmalıdır.")
        if mode == "sqlserver" and not self.server.strip():
            raise ValueError("SQL Server adresi boş bırakılamaz.")
        if not self.database.strip():
            raise ValueError("Veritabanı adı boş bırakılamaz.")
        if mode == "sqlserver" and not self.trusted_connection and not self.username.strip():
            raise ValueError(
                "SQL kullanıcı adı girin veya Windows hesabıyla bağlantıyı seçin."
            )
        return replace(
            self,
            mode=mode,
            server=self.server.strip(),
            database=self.database.strip(),
            username=self.username.strip(),
            attachment_share=self.attachment_share.strip(),
        )


class WindowsDpapi:
    """SQL parolasını yalnız aynı Windows kullanıcısının açabileceği biçimde saklar."""

    class DataBlob(ctypes.Structure):
        _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte)))

    @classmethod
    def available(cls) -> bool:
        return sys.platform.startswith("win") and hasattr(ctypes, "windll")

    @classmethod
    def _blob(cls, payload: bytes) -> tuple["WindowsDpapi.DataBlob", object]:
        buffer = ctypes.create_string_buffer(payload)
        blob = cls.DataBlob(
            len(payload),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
        )
        return blob, buffer

    @classmethod
    def protect(cls, value: str) -> str:
        if not value:
            return ""
        if not cls.available():
            raise RuntimeError("Parola yalnız Windows DPAPI ile güvenli saklanabilir.")
        source, source_buffer = cls._blob(value.encode("utf-8"))
        result = cls.DataBlob()
        crypt_protect = ctypes.windll.crypt32.CryptProtectData
        crypt_protect.argtypes = (
            ctypes.POINTER(cls.DataBlob),
            wintypes.LPCWSTR,
            ctypes.POINTER(cls.DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(cls.DataBlob),
        )
        crypt_protect.restype = wintypes.BOOL
        ok = crypt_protect(
            ctypes.byref(source),
            "Rigel Cost Pro SQL Parolası",
            None,
            None,
            None,
            0,
            ctypes.byref(result),
        )
        _ = source_buffer
        if not ok:
            raise ctypes.WinError()
        try:
            encrypted = ctypes.string_at(result.pbData, result.cbData)
            return base64.b64encode(encrypted).decode("ascii")
        finally:
            local_free = ctypes.windll.kernel32.LocalFree
            local_free.argtypes = (ctypes.c_void_p,)
            local_free.restype = ctypes.c_void_p
            local_free(ctypes.cast(result.pbData, ctypes.c_void_p))

    @classmethod
    def unprotect(cls, protected: str) -> str:
        if not protected:
            return ""
        if not cls.available():
            return ""
        encrypted = base64.b64decode(protected.encode("ascii"), validate=True)
        source, source_buffer = cls._blob(encrypted)
        result = cls.DataBlob()
        crypt_unprotect = ctypes.windll.crypt32.CryptUnprotectData
        crypt_unprotect.argtypes = (
            ctypes.POINTER(cls.DataBlob),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(cls.DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(cls.DataBlob),
        )
        crypt_unprotect.restype = wintypes.BOOL
        ok = crypt_unprotect(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(result),
        )
        _ = source_buffer
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(result.pbData, result.cbData).decode("utf-8")
        finally:
            local_free = ctypes.windll.kernel32.LocalFree
            local_free.argtypes = (ctypes.c_void_p,)
            local_free.restype = ctypes.c_void_p
            local_free(ctypes.cast(result.pbData, ctypes.c_void_p))


class DatabaseConfigStore:
    """Sunucu ayarlarını kaydeder; parolayı hiçbir zaman düz metin yazmaz."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            root = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
            path = Path(root or Path.home() / ".rigelcost") / "database.json"
        self.path = Path(path)

    def save(
        self,
        settings: DatabaseSettings,
        *,
        remember_password: bool = False,
    ) -> None:
        settings = settings.validated()
        payload = asdict(settings)
        password = str(payload.pop("password", ""))
        payload["password_protected"] = (
            WindowsDpapi.protect(password)
            if remember_password and password
            else ""
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def load(self) -> DatabaseSettings | None:
        if not self.path.is_file():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        protected = str(payload.pop("password_protected", "") or "")
        payload.pop("password", None)
        allowed = set(DatabaseSettings.__dataclass_fields__)
        settings = DatabaseSettings(
            **{key: value for key, value in payload.items() if key in allowed},
            password=WindowsDpapi.unprotect(protected) if protected else "",
        )
        return settings.validated()


def select_sql_server_driver(drivers: Iterable[str]) -> str:
    installed = list(drivers)
    priorities = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    )
    for requested in priorities:
        for available in installed:
            if requested.casefold() == available.casefold():
                return available
    fallback = next(
        (driver for driver in installed if "sql server" in driver.casefold()),
        "",
    )
    if not fallback:
        raise RuntimeError(
            "Microsoft SQL Server ODBC sürücüsü bulunamadı. "
            "Windows paketindeki ODBC Driver 18 kurulmalıdır."
        )
    return fallback


def sql_server_connection_string(
    settings: DatabaseSettings,
    drivers: Iterable[str],
    *,
    database: str | None = None,
) -> str:
    settings = settings.validated()
    if settings.mode != "sqlserver":
        raise ValueError("Bu bağlantı dizesi yalnız SQL Server içindir.")
    driver = select_sql_server_driver(drivers)
    target_database = (database or settings.database).strip()
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={settings.server}",
        f"DATABASE={target_database}",
        "APP=Rigel Cost Pro",
        f"Encrypt={'yes' if settings.encrypt else 'no'}",
        (
            "TrustServerCertificate=yes"
            if settings.trust_server_certificate
            else "TrustServerCertificate=no"
        ),
        "MARS_Connection=yes",
    ]
    if settings.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend((f"UID={settings.username}", f"PWD={settings.password}"))
    return ";".join(parts)


class SqlServerConnectionFactory:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings.validated()

    def connect(
        self,
        *,
        database: str | None = None,
        timeout: int = 8,
        autocommit: bool = False,
    ):
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:
            raise RuntimeError("SQL Server bağlantı bileşeni kurulu değil.") from exc
        connection_string = sql_server_connection_string(
            self.settings,
            pyodbc.drivers(),
            database=database,
        )
        return pyodbc.connect(
            connection_string,
            timeout=max(1, int(timeout)),
            autocommit=bool(autocommit),
        )

    def ensure_database(self) -> bool:
        """Yetkili SQL hesabıyla Rigel veritabanını yoksa oluşturur."""
        database = self.settings.database.strip()
        if not database.replace("_", "").isalnum():
            raise ValueError(
                "Veritabanı adı yalnız harf, rakam ve alt çizgi içerebilir."
            )
        connection = self.connect(database="master", autocommit=True)
        try:
            exists = connection.cursor().execute(
                "SELECT DB_ID(?)",
                database,
            ).fetchone()[0]
            if exists is not None:
                return False
            connection.cursor().execute(f"CREATE DATABASE [{database}]")
            return True
        finally:
            connection.close()

    def test_connection(self) -> dict[str, str]:
        connection = self.connect()
        try:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT DB_NAME(), CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), "
                "CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(64))"
            ).fetchone()
            connection.rollback()
            return {
                "database": str(row[0] or ""),
                "server": str(row[1] or ""),
                "version": str(row[2] or ""),
            }
        finally:
            connection.close()


class SqlServerMigrator:
    """Sıralı .sql dosyalarını tek tek transaction içinde uygular."""

    def __init__(self, factory: SqlServerConnectionFactory, migration_root: str | Path) -> None:
        self.factory = factory
        self.migration_root = Path(migration_root)

    @staticmethod
    def split_batches(script: str) -> list[str]:
        batches: list[str] = []
        current: list[str] = []
        for line in script.splitlines():
            if line.strip().upper() == "GO":
                batch = "\n".join(current).strip()
                if batch:
                    batches.append(batch)
                current = []
            else:
                current.append(line)
        batch = "\n".join(current).strip()
        if batch:
            batches.append(batch)
        return batches

    def migration_files(self) -> list[Path]:
        return sorted(self.migration_root.glob("[0-9][0-9][0-9]_*.sql"))

    def migrate(self) -> list[str]:
        connection = self.factory.connect()
        applied: list[str] = []
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF OBJECT_ID('dbo.schema_versions', 'U') IS NULL
                CREATE TABLE dbo.schema_versions (
                    version_no int NOT NULL PRIMARY KEY,
                    migration_name nvarchar(200) NOT NULL,
                    applied_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                )
                """
            )
            connection.commit()
            existing = {
                int(row[0])
                for row in cursor.execute(
                    "SELECT version_no FROM dbo.schema_versions"
                ).fetchall()
            }
            for path in self.migration_files():
                version_text = path.name.split("_", 1)[0]
                version = int(version_text)
                if version in existing:
                    continue
                try:
                    for batch in self.split_batches(path.read_text(encoding="utf-8")):
                        cursor.execute(batch)
                    cursor.execute(
                        "INSERT INTO dbo.schema_versions(version_no, migration_name) "
                        "VALUES (?, ?)",
                        version,
                        path.name,
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                applied.append(path.name)
            return applied
        finally:
            connection.close()


def central_database_enabled() -> bool:
    return os.environ.get("RIGELCOST_DATABASE", "").strip().lower() == "sqlserver"
