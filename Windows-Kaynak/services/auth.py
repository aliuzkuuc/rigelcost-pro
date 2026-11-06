from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QStandardPaths


VIEW_DASHBOARD = "view:dashboard"
VIEW_COST = "view:cost"
VIEW_SALES = "view:sales"
VIEW_PURCHASE = "view:purchase"
VIEW_MATERIAL = "view:material"
VIEW_DIE = "view:die"
VIEW_PRODUCTION = "view:production"
VIEW_SHIPPING = "view:shipping"
VIEW_MAINTENANCE = "view:maintenance"
VIEW_REPORTS = "view:reports"
VIEW_SETTINGS = "view:settings"

ERP_CREATE = "erp:create"
ERP_EDIT = "erp:edit"
ERP_DELETE = "erp:delete"
EXPORT_REPORTS = "reports:export"
UPDATE_MARKET = "market:update"
MANAGE_USERS = "manage:users"


PERMISSION_LABELS: dict[str, str] = {
    VIEW_DASHBOARD: "Ana sayfa",
    VIEW_COST: "Maliyet modülü",
    VIEW_SALES: "Satış",
    VIEW_PURCHASE: "Satın alma",
    VIEW_MATERIAL: "Malzeme yönetimi ve stok",
    VIEW_DIE: "Kalıphane",
    VIEW_PRODUCTION: "Üretim",
    VIEW_SHIPPING: "Sevkiyat",
    VIEW_MAINTENANCE: "Bakım",
    VIEW_REPORTS: "Raporlar",
    VIEW_SETTINGS: "Ayarlar",
    ERP_CREATE: "Yeni işletme kaydı oluşturma",
    ERP_EDIT: "İşletme kayıtlarını düzenleme",
    ERP_DELETE: "İşletme kayıtlarını silme",
    EXPORT_REPORTS: "Excel/PDF raporu alma",
    UPDATE_MARKET: "Kur ve LME güncelleme",
    MANAGE_USERS: "Kullanıcı ve yetki yönetimi",
}

ALL_PERMISSIONS = frozenset(PERMISSION_LABELS)

_BASE_EDIT = {VIEW_DASHBOARD, ERP_CREATE, ERP_EDIT}
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "PATRON": ALL_PERMISSIONS,
    "YÖNETİCİ": frozenset(
        ALL_PERMISSIONS.difference({MANAGE_USERS})
    ),
    "MALİYET": frozenset(
        {VIEW_DASHBOARD, VIEW_COST, VIEW_REPORTS, EXPORT_REPORTS, UPDATE_MARKET}
    ),
    "SATIŞ": frozenset(_BASE_EDIT | {VIEW_SALES, VIEW_REPORTS, EXPORT_REPORTS}),
    "SATIN ALMA": frozenset(
        _BASE_EDIT | {VIEW_PURCHASE, VIEW_MATERIAL, VIEW_REPORTS}
    ),
    "MALZEME": frozenset(_BASE_EDIT | {VIEW_MATERIAL, VIEW_REPORTS}),
    "KALIPHANE": frozenset(_BASE_EDIT | {VIEW_DIE, VIEW_REPORTS}),
    "ÜRETİM": frozenset(
        _BASE_EDIT | {VIEW_PRODUCTION, VIEW_DIE, VIEW_MATERIAL, VIEW_REPORTS}
    ),
    "SEVKİYAT": frozenset(
        _BASE_EDIT | {VIEW_SHIPPING, VIEW_SALES, VIEW_MATERIAL, VIEW_REPORTS}
    ),
    "BAKIM": frozenset(
        _BASE_EDIT | {VIEW_MAINTENANCE, VIEW_PRODUCTION, VIEW_REPORTS}
    ),
    "GÖRÜNTÜLEME": frozenset({VIEW_DASHBOARD, VIEW_REPORTS}),
}


@dataclass(frozen=True)
class UserSession:
    user_id: int
    username: str
    display_name: str
    role: str
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    @classmethod
    def owner(cls, username: str = "") -> "UserSession":
        display = username.strip()
        return cls(0, display.casefold() or "patron", display, "PATRON", ALL_PERMISSIONS)


class AuthService:
    """Yerel kullanıcı, parola ve modül yetkilerini güvenli biçimde saklar."""

    PBKDF2_ITERATIONS = 600_000

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else self.default_database_path()
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @staticmethod
    def default_database_path() -> Path:
        override = os.environ.get("RIGELCOST_DATA_DIR")
        if override:
            return Path(override) / "security.db"
        location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        return Path(location or Path.home() / ".rigelcost") / "security.db"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    PRIMARY KEY(user_id, permission),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS security_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_time TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_security_audit_time
                    ON security_audit(event_time DESC);
                """
            )
            connection.commit()

    def has_users(self) -> bool:
        with closing(self.connect()) as connection:
            return bool(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    @staticmethod
    def _validate_username(username: str) -> str:
        value = username.strip()
        if len(value) < 3:
            raise ValueError("Kullanıcı adı en az 3 karakter olmalıdır.")
        if len(value) > 64:
            raise ValueError("Kullanıcı adı en fazla 64 karakter olabilir.")
        if any(character.isspace() for character in value):
            raise ValueError("Kullanıcı adında boşluk bulunamaz.")
        return value

    @staticmethod
    def _validate_password(password: str) -> str:
        if len(password) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır.")
        if not any(character.isalpha() for character in password):
            raise ValueError("Şifre en az bir harf içermelidir.")
        if not any(character.isdigit() for character in password):
            raise ValueError("Şifre en az bir rakam içermelidir.")
        return password

    @classmethod
    def _hash_password(cls, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.PBKDF2_ITERATIONS,
        )

    @staticmethod
    def permissions_for_role(role: str) -> frozenset[str]:
        normalized = role.strip().upper()
        if normalized not in ROLE_PERMISSIONS:
            raise ValueError("Geçersiz kullanıcı rolü.")
        return ROLE_PERMISSIONS[normalized]

    def _write_permissions(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        permissions: Iterable[str],
    ) -> None:
        valid = sorted(
            set(permissions).intersection(ALL_PERMISSIONS).union({VIEW_DASHBOARD})
        )
        connection.execute(
            "DELETE FROM user_permissions WHERE user_id = ?",
            (int(user_id),),
        )
        connection.executemany(
            "INSERT INTO user_permissions(user_id, permission) VALUES (?, ?)",
            ((int(user_id), permission) for permission in valid),
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        username: str,
        event_type: str,
        detail: str = "",
    ) -> None:
        connection.execute(
            """
            INSERT INTO security_audit(event_time, username, event_type, detail)
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                username.strip(),
                event_type,
                detail[:1000],
            ),
        )

    def create_user(
        self,
        username: str,
        display_name: str,
        password: str,
        role: str,
        *,
        permissions: Iterable[str] | None = None,
        active: bool = True,
        actor: str = "",
    ) -> int:
        username = self._validate_username(username)
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Ad soyad boş bırakılamaz.")
        password = self._validate_password(password)
        role = role.strip().upper()
        role_permissions = self.permissions_for_role(role)
        selected = (
            ALL_PERMISSIONS
            if role == "PATRON"
            else (role_permissions if permissions is None else frozenset(permissions))
        )
        salt = secrets.token_bytes(24)
        password_hash = self._hash_password(password, salt)
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with closing(self.connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        username, display_name, role, password_salt,
                        password_hash, active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        display_name,
                        role,
                        salt,
                        password_hash,
                        int(active),
                        now,
                        now,
                    ),
                )
                user_id = int(cursor.lastrowid)
                self._write_permissions(connection, user_id, selected)
                self._audit(
                    connection,
                    actor or username,
                    "USER_CREATED",
                    f"Kullanıcı: {username}; Rol: {role}",
                )
                connection.commit()
                return user_id
        except sqlite3.IntegrityError as exc:
            raise ValueError("Bu kullanıcı adı zaten kullanılıyor.") from exc

    def create_first_owner(
        self,
        username: str,
        display_name: str,
        password: str,
    ) -> int:
        if self.has_users():
            raise ValueError("İlk yönetici hesabı daha önce oluşturulmuş.")
        return self.create_user(
            username,
            display_name,
            password,
            "PATRON",
            permissions=ALL_PERMISSIONS,
            actor=username,
        )

    def authenticate(self, username: str, password: str) -> UserSession | None:
        normalized = username.strip()
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
                (normalized,),
            ).fetchone()
            if row is None or not bool(row["active"]):
                self._audit(connection, normalized, "LOGIN_FAILED", "Kullanıcı bulunamadı veya pasif.")
                connection.commit()
                return None
            now = datetime.now()
            locked_until = str(row["locked_until"] or "")
            if locked_until:
                try:
                    lock_end = datetime.fromisoformat(locked_until)
                except ValueError:
                    lock_end = now
                if lock_end > now:
                    self._audit(
                        connection,
                        normalized,
                        "LOGIN_LOCKED",
                        "Çok sayıda hatalı giriş nedeniyle hesap geçici olarak kilitli.",
                    )
                    connection.commit()
                    return None
                connection.execute(
                    "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                    (int(row["id"]),),
                )
                failed_attempts = 0
            else:
                failed_attempts = int(row["failed_attempts"] or 0)
            calculated = self._hash_password(password, bytes(row["password_salt"]))
            if not hmac.compare_digest(calculated, bytes(row["password_hash"])):
                failed_attempts += 1
                new_lock = (
                    (now + timedelta(minutes=15)).isoformat(timespec="seconds")
                    if failed_attempts >= 5
                    else None
                )
                connection.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (failed_attempts, new_lock, int(row["id"])),
                )
                detail = (
                    "Hatalı şifre; hesap 15 dakika kilitlendi."
                    if new_lock
                    else "Hatalı şifre."
                )
                self._audit(connection, normalized, "LOGIN_FAILED", detail)
                connection.commit()
                return None
            connection.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                (int(row["id"]),),
            )
            permission_rows = connection.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ?",
                (int(row["id"]),),
            ).fetchall()
            permissions = frozenset(item["permission"] for item in permission_rows)
            self._audit(connection, normalized, "LOGIN_SUCCESS", f"Rol: {row['role']}")
            connection.commit()
        return UserSession(
            int(row["id"]),
            str(row["username"]),
            str(row["display_name"]),
            str(row["role"]),
            permissions,
        )

    def list_users(self) -> list[dict[str, object]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, username, display_name, role, active, created_at, updated_at
                FROM users ORDER BY active DESC, display_name COLLATE NOCASE
                """
            ).fetchall()
            results: list[dict[str, object]] = []
            for row in rows:
                permissions = connection.execute(
                    "SELECT permission FROM user_permissions WHERE user_id = ? ORDER BY permission",
                    (int(row["id"]),),
                ).fetchall()
                item = dict(row)
                item["permissions"] = frozenset(value["permission"] for value in permissions)
                results.append(item)
            return results

    def get_user(self, user_id: int) -> dict[str, object] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT id, username, display_name, role, active, created_at, updated_at
                FROM users WHERE id = ?
                """,
                (int(user_id),),
            ).fetchone()
            if row is None:
                return None
            permissions = connection.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ?",
                (int(user_id),),
            ).fetchall()
        result = dict(row)
        result["permissions"] = frozenset(item["permission"] for item in permissions)
        return result

    def update_user(
        self,
        user_id: int,
        *,
        display_name: str,
        role: str,
        permissions: Iterable[str],
        active: bool,
        actor: str,
    ) -> None:
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Ad soyad boş bırakılamaz.")
        role = role.strip().upper()
        self.permissions_for_role(role)
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT username, role FROM users WHERE id = ?",
                (int(user_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Kullanıcı bulunamadı.")
            if row["role"] == "PATRON" and (not active or role != "PATRON"):
                active_owner_count = connection.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'PATRON' AND active = 1",
                ).fetchone()[0]
                if active_owner_count <= 1:
                    raise ValueError(
                        "Son aktif patron hesabı pasif yapılamaz veya başka role çevrilemez."
                    )
            connection.execute(
                """
                UPDATE users
                SET display_name = ?, role = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name,
                    role,
                    int(active),
                    datetime.now().isoformat(timespec="seconds"),
                    int(user_id),
                ),
            )
            self._write_permissions(
                connection,
                int(user_id),
                ALL_PERMISSIONS if role == "PATRON" else permissions,
            )
            self._audit(
                connection,
                actor,
                "USER_UPDATED",
                f"Kullanıcı: {row['username']}; Rol: {role}; Aktif: {active}",
            )
            connection.commit()

    def change_password(
        self,
        user_id: int,
        new_password: str,
        *,
        actor: str,
    ) -> None:
        password = self._validate_password(new_password)
        salt = secrets.token_bytes(24)
        password_hash = self._hash_password(password, salt)
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE id = ?",
                (int(user_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Kullanıcı bulunamadı.")
            connection.execute(
                """
                UPDATE users
                SET password_salt = ?, password_hash = ?, failed_attempts = 0,
                    must_change_password = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    salt,
                    password_hash,
                    datetime.now().isoformat(timespec="seconds"),
                    int(user_id),
                ),
            )
            self._audit(connection, actor, "PASSWORD_CHANGED", f"Kullanıcı: {row['username']}")
            connection.commit()
