from __future__ import annotations

import json
import hashlib
import math
import mimetypes
import os
import socket
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

from PySide6.QtCore import QStandardPaths

from services.order_line_status import recalculate_order_line_status
from models.factory_config import factory_config
from services import master_data as master_data_service


class LocalWorkflowService:
    """SQL Server'a geçmeden önce aynı ilişkileri yerelde çalıştıran ERP çekirdeği."""

    # Fiş numarası kuralları — prefix bazlı genişlik ve format.
    SEQUENCE_RULES: dict[str, dict[str, object]] = {
        "R": {"width": 7, "year": True},          # R260000209
        "UE": {"width": 7, "year": True},         # UE260000001
        "IE": {"width": 8, "year": False, "prefix": ""},  # 000017392
        "PF": {"width": 10, "year": False, "prefix": ""},  # 0000005499 pres fişi
        "PK": {"width": 6, "year": True},
        "CL": {"width": 6, "year": True},
        "SV": {"width": 6, "year": True},
        "FAT": {"width": 6, "year": True},
        "STF": {"width": 6, "year": True},
        "TA": {"width": 6, "year": True},
        "SA": {"width": 6, "year": True},
        "MG": {"width": 6, "year": True},
        "ELF": {"width": 6, "year": True},
        "BKM": {"width": 6, "year": True},
        "SAF": {"width": 6, "year": True},
        "TEK": {"width": 6, "year": True},
        "STK": {"width": 6, "year": True},
        "SK": {"width": 6, "year": True},
        "KT": {"width": 6, "year": True},
        "KIE": {"width": 6, "year": True},
        "FL": {"width": 6, "year": True},
        "KFS": {"width": 6, "year": True},
        "KPR": {"width": 6, "year": True},
    }

    def _sequence_rule(self, prefix: str) -> dict[str, object]:
        defaults: dict[str, object] = {"width": 6, "year": True, "prefix": prefix}
        if prefix in self.SEQUENCE_RULES:
            defaults.update(self.SEQUENCE_RULES[prefix])
        return defaults

    def _format_sequence_no(self, prefix: str, value: int) -> str:
        rule = self._sequence_rule(prefix)
        seq_prefix = str(rule.get("prefix", prefix))
        width = int(rule["width"])
        if rule.get("year"):
            return f"{seq_prefix}{date.today():%y}{value:0{width}d}"
        return f"{value:0{width}d}"

    def peek_next_no(self, prefix: str) -> str:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT last_value FROM local_sequences WHERE prefix = ?",
                (prefix,),
            ).fetchone()
            next_value = int(row[0] if row else 0) + 1
            return self._format_sequence_no(prefix, next_value)

    DEFAULT_WAREHOUSES = (
        ("HAMMADDE", "Hammadde", "HAMMADDE"),
        ("PRES", "Pres Çıkış", "YARI MAMUL"),
        ("TERMIK_ON", "Termik Giriş", "YARI MAMUL"),
        ("TERMIK", "Termik Çıkış", "YARI MAMUL"),
        ("ELOKSAL_ON", "Eloksal Ön", "YARI MAMUL"),
        ("BOYA_ON", "Boya Ön", "YARI MAMUL"),
        ("YUZEY", "Yüzey İşlem", "YARI MAMUL"),
        ("FASON", "Fason", "YARI MAMUL"),
        ("HURDA", "Hurda", "HURDA"),
        ("SARF", "Sarf", "SARF"),
        ("MAMUL_STOK", "Mamul Stok", "MAMUL"),
        ("SEVK_ON", "Sevk Ön", "MAMUL"),
        ("SEVK_HAZIR", "Sevk Hazır", "MAMUL"),
    )

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.organization_code = (
            os.environ.get("RIGELCOST_ORGANIZATION_CODE", "RIGEL").strip().upper()
            or "RIGEL"
        )
        self.organization_default_name = (
            os.environ.get("RIGELCOST_ORGANIZATION_NAME", "Rigel Alüminyum").strip()
            or "Rigel Alüminyum"
        )
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else self.default_database_path()
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path = (
            Path(__file__).resolve().parents[1]
            / "database"
            / "sqlite"
            / "001_core.sql"
        )
        self.initialize()

    @staticmethod
    def default_database_path() -> Path:
        override = os.environ.get("RIGELCOST_DATA_DIR")
        if override:
            return Path(override) / "rigel_operations.db"
        root = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        return Path(root or Path.home() / ".rigelcost") / "rigel_operations.db"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        if not self.schema_path.is_file():
            raise RuntimeError("Yerel ERP şema dosyası bulunamadı.")
        with closing(self.connect()) as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            for migration_path in sorted(self.schema_path.parent.glob("*.sql")):
                try:
                    version = int(migration_path.stem.split("_", 1)[0])
                except ValueError:
                    continue
                applied = connection.execute(
                    "SELECT 1 FROM local_schema_versions WHERE version_no = ?",
                    (version,),
                ).fetchone()
                if applied is None:
                    if version == 9:
                        self._ensure_supplier_purchase_columns(connection)
                    elif version == 10:
                        self._ensure_warehouse_policy_columns(connection)
                    connection.executescript(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT OR IGNORE INTO organizations(code, name) VALUES (?, ?)",
                (self.organization_code, self.organization_default_name),
            )
            if os.environ.get("RIGELCOST_ORGANIZATION_NAME", "").strip():
                connection.execute(
                    "UPDATE organizations SET name = ? WHERE code = ?",
                    (self.organization_default_name, self.organization_code),
                )
            organization_id = int(
                connection.execute(
                    "SELECT id FROM organizations WHERE code = ?",
                    (self.organization_code,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO branches(organization_id, code, name)
                VALUES (?, 'FABRIKA', 'Fabrika')
                """,
                (organization_id,),
            )
            default_branch_id = int(
                connection.execute(
                    "SELECT id FROM branches WHERE organization_id = ? AND code = 'FABRIKA'",
                    (organization_id,),
                ).fetchone()[0]
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO warehouses(
                    organization_id, code, name, warehouse_type
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (organization_id, code, name, warehouse_type)
                    for code, name, warehouse_type in self.DEFAULT_WAREHOUSES
                ],
            )
            connection.execute(
                "UPDATE warehouses SET branch_id = ? WHERE organization_id = ? AND branch_id IS NULL",
                (default_branch_id, organization_id),
            )
            connection.executemany(
                """
                UPDATE warehouses
                SET name = ?, warehouse_type = ?
                WHERE organization_id = ? AND code = ?
                """,
                [
                    (name, warehouse_type, organization_id, code)
                    for code, name, warehouse_type in self.DEFAULT_WAREHOUSES
                ],
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO stock_items(
                    organization_id, code, name, stock_group, unit, tracks_lot
                ) VALUES (?, 'AL-BILLET', 'ALÜMİNYUM BİLLET', 'HAMMADDE', 'KG', 1)
                """,
                (organization_id,),
            )
            master_data_service.seed_master_data(connection, organization_id)
            connection.commit()

    @staticmethod
    def _ensure_supplier_purchase_columns(connection: sqlite3.Connection) -> None:
        """009'u eski ve yarım kalmış kurulumlarda veri kaybetmeden tamamlar."""
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(suppliers)").fetchall()
        }
        definitions = {
            "tax_office": "TEXT NOT NULL DEFAULT ''",
            "tax_number": "TEXT NOT NULL DEFAULT ''",
            "contact_name": "TEXT NOT NULL DEFAULT ''",
            "phone": "TEXT NOT NULL DEFAULT ''",
            "email": "TEXT NOT NULL DEFAULT ''",
            "address": "TEXT NOT NULL DEFAULT ''",
            "city": "TEXT NOT NULL DEFAULT ''",
            "currency": "TEXT NOT NULL DEFAULT 'TRY'",
        }
        for column, definition in definitions.items():
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE suppliers ADD COLUMN {column} {definition}"
                )

    @staticmethod
    def _ensure_warehouse_policy_columns(connection: sqlite3.Connection) -> None:
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(warehouses)").fetchall()
        }
        definitions = {
            "branch_id": "INTEGER REFERENCES branches(id)",
            "negative_stock_policy": "TEXT NOT NULL DEFAULT 'İZİN'",
            "allow_mixed_lots": "INTEGER NOT NULL DEFAULT 1",
        }
        for column, definition in definitions.items():
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE warehouses ADD COLUMN {column} {definition}"
                )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _number(value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        raw = str(value or "").strip().replace(" ", "")
        if not raw:
            return 0.0
        if "," in raw and "." in raw:
            raw = (
                raw.replace(".", "").replace(",", ".")
                if raw.rfind(",") > raw.rfind(".")
                else raw.replace(",", "")
            )
        elif "," in raw:
            raw = raw.replace(",", ".")
        return float(raw)

    def _table_exists(self, connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def organization_id(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT id FROM organizations WHERE code = ?",
            (self.organization_code,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Kurulu işletme kaydı bulunamadı.")
        return int(row[0])

    def organization(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT id, code, name, active FROM organizations WHERE code = ?",
                (self.organization_code,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Kurulu işletme kaydı bulunamadı.")
        return dict(row)

    def organization_name(self) -> str:
        return str(self.organization()["name"])

    def list_warehouses(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT w.id, w.code, w.name, w.warehouse_type, w.branch_id,
                       COALESCE(b.code, '') AS branch_code,
                       COALESCE(b.name, '') AS branch_name,
                       w.negative_stock_policy, w.allow_mixed_lots, w.active
                FROM warehouses w
                LEFT JOIN branches b ON b.id = w.branch_id
                WHERE w.organization_id = ?
                ORDER BY b.name, w.name
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_branches(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT b.id, b.code, b.name, b.city, b.address, b.active,
                       COUNT(w.id) AS warehouse_count
                FROM branches b
                LEFT JOIN warehouses w ON w.branch_id = b.id
                WHERE b.organization_id = ? AND (? OR b.active = 1)
                GROUP BY b.id, b.code, b.name, b.city, b.address, b.active
                ORDER BY b.name
                """,
                (self.organization_id(connection), 1 if include_inactive else 0),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_branch(
        self, code: str, name: str, *, city: str = "", address: str = "",
        active: bool = True, username: str,
    ) -> int:
        normalized_code = code.strip().upper()
        normalized_name = name.strip()
        if not normalized_code or not normalized_name:
            raise ValueError("Şube kodu ve şube adı boş bırakılamaz.")
        with closing(self.connect()) as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO branches(organization_id, code, name, city, address, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (self.organization_id(connection), normalized_code, normalized_name,
                     city.strip(), address.strip(), 1 if active else 0),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{normalized_code} kodlu şube zaten var.") from exc
            branch_id = int(cursor.lastrowid)
            self._audit(
                connection, username=username, action="CREATE", entity_type="BRANCH",
                entity_id=branch_id, record_key=normalized_code,
                after={"name": normalized_name, "city": city},
            )
            connection.commit()
        return branch_id

    def create_warehouse(
        self, code: str, name: str, *, warehouse_type: str, branch_id: int,
        negative_stock_policy: str = "İZİN", allow_mixed_lots: bool = True,
        active: bool = True, username: str,
    ) -> int:
        normalized_code = code.strip().upper()
        normalized_name = name.strip()
        policy = negative_stock_policy.strip().upper()
        if not normalized_code or not normalized_name:
            raise ValueError("Ambar kodu ve ambar adı boş bırakılamaz.")
        if policy not in {"ENGELLE", "UYAR", "İZİN"}:
            raise ValueError("Negatif stok politikası ENGELLE, UYAR veya İZİN olmalıdır.")
        with closing(self.connect()) as connection:
            branch = connection.execute(
                "SELECT id FROM branches WHERE id = ? AND organization_id = ? AND active = 1",
                (int(branch_id), self.organization_id(connection)),
            ).fetchone()
            if branch is None:
                raise ValueError("Aktif şube seçilmelidir.")
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO warehouses(
                        organization_id, code, name, warehouse_type, branch_id,
                        negative_stock_policy, allow_mixed_lots, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (self.organization_id(connection), normalized_code, normalized_name,
                     warehouse_type.strip().upper(), int(branch_id), policy,
                     1 if allow_mixed_lots else 0, 1 if active else 0),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{normalized_code} kodlu ambar zaten var.") from exc
            warehouse_id = int(cursor.lastrowid)
            self._audit(
                connection, username=username, action="CREATE", entity_type="WAREHOUSE",
                entity_id=warehouse_id, record_key=normalized_code,
                after={"name": normalized_name, "branch_id": branch_id,
                       "negative_stock_policy": policy},
            )
            connection.commit()
        return warehouse_id

    def update_warehouse_policy(
        self, warehouse_id: int, *, branch_id: int,
        negative_stock_policy: str, allow_mixed_lots: bool,
        active: bool = True, username: str,
    ) -> None:
        policy = negative_stock_policy.strip().upper()
        if policy not in {"ENGELLE", "UYAR", "İZİN"}:
            raise ValueError("Geçersiz negatif stok politikası.")
        with closing(self.connect()) as connection:
            before = connection.execute(
                "SELECT * FROM warehouses WHERE id = ? AND organization_id = ?",
                (int(warehouse_id), self.organization_id(connection)),
            ).fetchone()
            if before is None:
                raise ValueError("Ambar bulunamadı.")
            if policy == "ENGELLE":
                negative = connection.execute(
                    """
                    SELECT 1 FROM stock_movements
                    WHERE warehouse_id = ?
                    GROUP BY stock_item_id, lot_no
                    HAVING SUM(direction * quantity) < -0.0005
                    LIMIT 1
                    """,
                    (int(warehouse_id),),
                ).fetchone()
                if negative is not None:
                    raise ValueError(
                        "Bu ambarda negatif bakiye var. ENGELLE politikasından önce bakiyeleri düzeltin."
                    )
            connection.execute(
                """
                UPDATE warehouses
                SET branch_id = ?, negative_stock_policy = ?,
                    allow_mixed_lots = ?, active = ?
                WHERE id = ? AND organization_id = ?
                """,
                (int(branch_id), policy, 1 if allow_mixed_lots else 0,
                 1 if active else 0, int(warehouse_id), self.organization_id(connection)),
            )
            self._audit(
                connection, username=username, action="UPDATE", entity_type="WAREHOUSE",
                entity_id=int(warehouse_id), record_key=str(before["code"]),
                before=dict(before), after={"branch_id": branch_id,
                    "negative_stock_policy": policy,
                    "allow_mixed_lots": bool(allow_mixed_lots), "active": bool(active)},
            )
            connection.commit()

    def create_stock_document(
        self, *, document_type: str, document_date: str,
        source_warehouse_id: int | None = None,
        target_warehouse_id: int | None = None,
        reference_no: str = "", note: str = "",
        lines: Iterable[dict[str, Any]], username: str,
    ) -> int:
        kind = document_type.strip().upper()
        if kind not in {"GİRİŞ", "ÇIKIŞ", "TRANSFER"}:
            raise ValueError("Stok fişi türü GİRİŞ, ÇIKIŞ veya TRANSFER olmalıdır.")
        if kind in {"ÇIKIŞ", "TRANSFER"} and source_warehouse_id is None:
            raise ValueError("Kaynak ambar seçilmelidir.")
        if kind in {"GİRİŞ", "TRANSFER"} and target_warehouse_id is None:
            raise ValueError("Hedef ambar seçilmelidir.")
        if kind == "TRANSFER" and int(source_warehouse_id or 0) == int(target_warehouse_id or 0):
            raise ValueError("Kaynak ve hedef ambar aynı olamaz.")
        prepared = list(lines)
        if not prepared:
            raise ValueError("Stok fişine en az bir satır eklenmelidir.")
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            warehouse_ids = {
                int(row[0]) for row in connection.execute(
                    "SELECT id FROM warehouses WHERE organization_id = ? AND active = 1",
                    (organization_id,),
                ).fetchall()
            }
            for selected in (source_warehouse_id, target_warehouse_id):
                if selected is not None and int(selected) not in warehouse_ids:
                    raise ValueError("Seçilen ambar aktif değil veya bu işletmeye ait değil.")
            document_no = self._next_no(connection, "STF")
            cursor = connection.execute(
                """
                INSERT INTO stock_documents(
                    organization_id, document_no, document_type, document_date,
                    source_warehouse_id, target_warehouse_id, reference_no,
                    note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (organization_id, document_no, kind, document_date,
                 source_warehouse_id, target_warehouse_id, reference_no.strip(),
                 note.strip(), username.strip() or "sistem"),
            )
            document_id = int(cursor.lastrowid)
            try:
                for line_no, values in enumerate(prepared, 1):
                    stock_item_id = int(values.get("stock_item_id") or 0)
                    quantity = self._number(values.get("quantity"))
                    lot_no = str(values.get("lot_no") or "").strip()
                    if quantity <= 0:
                        raise ValueError(f"{line_no}. satır miktarı sıfırdan büyük olmalıdır.")
                    stock = connection.execute(
                        "SELECT id, tracks_lot FROM stock_items WHERE id = ? AND organization_id = ? AND active = 1",
                        (stock_item_id, organization_id),
                    ).fetchone()
                    if stock is None:
                        raise ValueError(f"{line_no}. satırda aktif stok kartı seçilmelidir.")
                    if bool(stock["tracks_lot"]) and not lot_no:
                        raise ValueError(f"{line_no}. satır için lot / şarj numarası zorunludur.")
                    connection.execute(
                        """
                        INSERT INTO stock_document_lines(
                            stock_document_id, line_no, stock_item_id, quantity, lot_no, note
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (document_id, line_no, stock_item_id, quantity, lot_no,
                         str(values.get("note") or "").strip()),
                    )
                    movement_values = []
                    if kind in {"ÇIKIŞ", "TRANSFER"}:
                        movement_values.append((int(source_warehouse_id), -1, f"STOK FİŞİ {kind} ÇIKIŞ"))
                    if kind in {"GİRİŞ", "TRANSFER"}:
                        movement_values.append((int(target_warehouse_id), 1, f"STOK FİŞİ {kind} GİRİŞ"))
                    for warehouse_id, direction, movement_type in movement_values:
                        connection.execute(
                            """
                            INSERT INTO stock_movements(
                                organization_id, stock_item_id, warehouse_id,
                                movement_type, direction, quantity, lot_no,
                                document_no, movement_at, created_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (organization_id, stock_item_id, warehouse_id,
                             movement_type, direction, quantity, lot_no,
                             document_no, document_date, username.strip() or "sistem"),
                        )
            except sqlite3.IntegrityError as exc:
                if "NEGATIVE_STOCK_BLOCKED" in str(exc):
                    raise ValueError(
                        "Kaynak ambarın ENGELLE politikası nedeniyle negatif stok oluşturulamaz."
                    ) from exc
                raise
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="STOCK_DOCUMENT", entity_id=document_id,
                record_key=document_no,
                after={"document_type": kind, "line_count": len(prepared)},
            )
            connection.commit()
        return document_id

    def list_stock_documents(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT sd.id, sd.document_no, sd.document_type, sd.document_date,
                       sd.reference_no, sd.note, sd.created_by, sd.created_at,
                       COALESCE(sw.name, '') AS source_warehouse_name,
                       COALESCE(sw.code, '') AS source_warehouse_code,
                       COALESCE(tw.name, '') AS target_warehouse_name,
                       COALESCE(tw.code, '') AS target_warehouse_code,
                       COUNT(sdl.id) AS line_count,
                       COALESCE(SUM(sdl.quantity), 0) AS total_quantity
                FROM stock_documents sd
                LEFT JOIN warehouses sw ON sw.id = sd.source_warehouse_id
                LEFT JOIN warehouses tw ON tw.id = sd.target_warehouse_id
                LEFT JOIN stock_document_lines sdl ON sdl.stock_document_id = sd.id
                WHERE sd.organization_id = ?
                GROUP BY sd.id, sd.document_no, sd.document_type, sd.document_date,
                         sd.reference_no, sd.note, sd.created_by, sd.created_at,
                         sw.name, sw.code, tw.name, tw.code
                ORDER BY sd.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_stock_document_lines(self, document_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT sdl.id, sdl.line_no, sdl.quantity, sdl.lot_no, sdl.note,
                       si.code AS stock_code, si.name AS stock_name, si.unit
                FROM stock_document_lines sdl
                JOIN stock_items si ON si.id = sdl.stock_item_id
                JOIN stock_documents sd ON sd.id = sdl.stock_document_id
                WHERE sdl.stock_document_id = ? AND sd.organization_id = ?
                ORDER BY sdl.line_no
                """,
                (int(document_id), self.organization_id(connection)),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def calculate_press_theory(
        *,
        quantity: float,
        result_length_mm: float,
        profile_weight_kg_m: float,
        billet_count: int,
        billet_diameter_mm: float = 152.4,
        billet_density_kg_m3: float = 2700.0,
        fire_pct: float = 3.0,
    ) -> dict[str, float]:
        """Profil/billet gramaj ilişkisini deterministik hesaplar."""
        quantity_value = max(0.0, float(quantity or 0))
        length_mm = max(0.0, float(result_length_mm or 0))
        profile_weight = max(0.0, float(profile_weight_kg_m or 0))
        diameter_m = max(0.0, float(billet_diameter_mm or 0)) / 1000.0
        density = max(0.0, float(billet_density_kg_m3 or 0))
        count = max(0, int(billet_count or 0))
        fire = min(99.0, max(0.0, float(fire_pct or 0)))
        net_metre = quantity_value * length_mm / 1000.0
        theoretical_net_kg = net_metre * profile_weight
        theoretical_billet_kg = (
            theoretical_net_kg / (1.0 - fire / 100.0)
            if theoretical_net_kg > 0
            else 0.0
        )
        billet_weight_kg_m = math.pi * (diameter_m ** 2) * density / 4.0
        billet_length_mm = (
            theoretical_billet_kg / (count * billet_weight_kg_m) * 1000.0
            if count > 0 and billet_weight_kg_m > 0
            else 0.0
        )
        return {
            "net_metre": net_metre,
            "theoretical_net_kg": theoretical_net_kg,
            "theoretical_billet_kg": theoretical_billet_kg,
            "billet_weight_kg_m": billet_weight_kg_m,
            "billet_length_mm": billet_length_mm,
        }

    def warehouse_id(self, connection: sqlite3.Connection, code: str) -> int:
        row = connection.execute(
            "SELECT id FROM warehouses WHERE organization_id = ? AND code = ?",
            (self.organization_id(connection), code),
        ).fetchone()
        if row is None:
            raise ValueError(f"Ambar bulunamadı: {code}")
        return int(row[0])

    def list_stock_items(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT si.id, si.code, si.name, si.stock_group, si.unit,
                       si.tracks_lot, si.minimum_quantity, si.active,
                       si.unit_set_id,
                       COALESCE(p.profile_code, '') AS profile_code,
                       COALESCE(us.code, '') AS unit_set_code,
                       COALESCE(us.name, '') AS unit_set_name,
                       COALESCE(SUM(sm.direction * sm.quantity), 0) AS balance
                FROM stock_items si
                LEFT JOIN profiles p ON p.id = si.profile_id
                LEFT JOIN unit_sets us ON us.id = si.unit_set_id
                LEFT JOIN stock_movements sm ON sm.stock_item_id = si.id
                WHERE si.organization_id = ? AND (? OR si.active = 1)
                GROUP BY si.id, si.code, si.name, si.stock_group, si.unit,
                         si.tracks_lot, si.minimum_quantity, si.active,
                         si.unit_set_id, p.profile_code, us.code, us.name
                ORDER BY si.code
                """,
                (self.organization_id(connection), 1 if include_inactive else 0),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            values["active_display"] = "AKTİF" if bool(values.get("active")) else "PASİF"
            values["tracks_lot_display"] = "EVET" if bool(values.get("tracks_lot")) else "HAYIR"
            result.append(values)
        return result

    def stock_item(self, stock_item_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM stock_items WHERE organization_id = ? AND id = ?",
                (self.organization_id(connection), int(stock_item_id)),
            ).fetchone()
        if row is None:
            raise ValueError("Stok kartı bulunamadı.")
        return dict(row)

    def create_stock_item(
        self,
        code: str,
        name: str,
        *,
        stock_group: str,
        unit: str,
        tracks_lot: bool = False,
        minimum_quantity: float = 0,
        active: bool = True,
        unit_set_id: int | None = None,
        username: str,
    ) -> int:
        normalized_code = code.strip().upper()
        normalized_name = name.strip()
        if not normalized_code or not normalized_name:
            raise ValueError("Stok kodu ve stok adı boş bırakılamaz.")
        with closing(self.connect()) as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO stock_items(
                        organization_id, code, name, stock_group, unit,
                        tracks_lot, minimum_quantity, active, unit_set_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.organization_id(connection), normalized_code,
                        normalized_name, stock_group.strip().upper() or "SARF",
                        unit.strip().upper() or "ADET", 1 if tracks_lot else 0,
                        max(0.0, self._number(minimum_quantity)), 1 if active else 0,
                        int(unit_set_id) if unit_set_id is not None else None,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{normalized_code} kodlu stok kartı zaten var.") from exc
            record_id = int(cursor.lastrowid)
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="STOCK_ITEM", entity_id=record_id,
                record_key=normalized_code,
                after={"name": normalized_name, "stock_group": stock_group, "unit": unit},
            )
            connection.commit()
        return record_id

    def update_stock_item(self, stock_item_id: int, *, username: str, **fields: object) -> None:
        before = self.stock_item(stock_item_id)
        code = str(fields.get("code", before["code"])).strip().upper()
        name = str(fields.get("name", before["name"])).strip()
        if not code or not name:
            raise ValueError("Stok kodu ve stok adı boş bırakılamaz.")
        values = (
            code, name,
            str(fields.get("stock_group", before["stock_group"])).strip().upper() or "SARF",
            str(fields.get("unit", before["unit"])).strip().upper() or "ADET",
            1 if bool(fields.get("tracks_lot", before["tracks_lot"])) else 0,
            max(0.0, self._number(fields.get("minimum_quantity", before["minimum_quantity"]))),
            1 if bool(fields.get("active", before["active"])) else 0,
            int(fields["unit_set_id"]) if fields.get("unit_set_id") is not None else before.get("unit_set_id"),
        )
        with closing(self.connect()) as connection:
            try:
                connection.execute(
                    """
                    UPDATE stock_items
                    SET code = ?, name = ?, stock_group = ?, unit = ?, tracks_lot = ?,
                        minimum_quantity = ?, active = ?, unit_set_id = ?,
                        row_version = row_version + 1
                    WHERE organization_id = ? AND id = ?
                    """,
                    (*values, self.organization_id(connection), int(stock_item_id)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{code} kodlu stok kartı zaten var.") from exc
            self._audit(
                connection, username=username, action="UPDATE",
                entity_type="STOCK_ITEM", entity_id=int(stock_item_id),
                record_key=code, before=before,
                after={"code": code, "name": name, "stock_group": values[2], "unit": values[3]},
            )
            connection.commit()

    def list_suppliers(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, code, name, supplier_type, tax_office, tax_number,
                       contact_name, phone, email, address, city, currency, active
                FROM suppliers
                WHERE organization_id = ? AND (? OR active = 1)
                ORDER BY name, code
                """,
                (self.organization_id(connection), 1 if include_inactive else 0),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_supplier(
        self, code: str, name: str, *, supplier_type: str = "TEDARİKÇİ",
        tax_office: str = "", tax_number: str = "", contact_name: str = "",
        phone: str = "", email: str = "", address: str = "", city: str = "",
        currency: str = "TRY", username: str,
    ) -> int:
        normalized_code = code.strip().upper()
        normalized_name = name.strip()
        if not normalized_code or not normalized_name:
            raise ValueError("Tedarikçi kodu ve ticari unvan zorunludur.")
        with closing(self.connect()) as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO suppliers(
                        organization_id, code, name, supplier_type, tax_office,
                        tax_number, contact_name, phone, email, address, city, currency
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.organization_id(connection), normalized_code, normalized_name,
                        supplier_type.strip().upper() or "TEDARİKÇİ", tax_office.strip(),
                        tax_number.strip(), contact_name.strip(), phone.strip(), email.strip(),
                        address.strip(), city.strip().upper(), currency.strip().upper() or "TRY",
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{normalized_code} kodlu tedarikçi zaten var.") from exc
            record_id = int(cursor.lastrowid)
            self._audit(
                connection, username=username, action="CREATE", entity_type="SUPPLIER",
                entity_id=record_id, record_key=normalized_code,
                after={"name": normalized_name, "supplier_type": supplier_type},
            )
            connection.commit()
        return record_id

    def supplier(self, supplier_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM suppliers WHERE organization_id = ? AND id = ?",
                (self.organization_id(connection), int(supplier_id)),
            ).fetchone()
        if row is None:
            raise ValueError("Tedarikçi kartı bulunamadı.")
        return dict(row)

    def update_supplier(self, supplier_id: int, *, username: str, **fields: object) -> None:
        before = self.supplier(int(supplier_id))
        code = str(fields.get("code", before["code"])).strip().upper()
        name = str(fields.get("name", before["name"])).strip()
        if not code or not name:
            raise ValueError("Tedarikçi kodu ve ticari unvan zorunludur.")
        values = (
            code,
            name,
            str(fields.get("supplier_type", before["supplier_type"])).strip().upper() or "TEDARİKÇİ",
            str(fields.get("tax_office", before["tax_office"])).strip(),
            str(fields.get("tax_number", before["tax_number"])).strip(),
            str(fields.get("contact_name", before["contact_name"])).strip(),
            str(fields.get("phone", before["phone"])).strip(),
            str(fields.get("email", before["email"])).strip(),
            str(fields.get("address", before["address"])).strip(),
            str(fields.get("city", before["city"])).strip().upper(),
            str(fields.get("currency", before["currency"])).strip().upper() or "TRY",
            1 if bool(fields.get("active", before["active"])) else 0,
        )
        with closing(self.connect()) as connection:
            try:
                connection.execute(
                    """
                    UPDATE suppliers
                    SET code = ?, name = ?, supplier_type = ?, tax_office = ?,
                        tax_number = ?, contact_name = ?, phone = ?, email = ?,
                        address = ?, city = ?, currency = ?, active = ?,
                        row_version = row_version + 1
                    WHERE organization_id = ? AND id = ?
                    """,
                    (*values, self.organization_id(connection), int(supplier_id)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{code} kodlu tedarikçi zaten var.") from exc
            self._audit(
                connection, username=username, action="UPDATE", entity_type="SUPPLIER",
                entity_id=int(supplier_id), record_key=code, before=before,
                after={"code": code, "name": name},
            )
            connection.commit()

    def create_purchase_request(
        self, *, request_date: str, lines: Iterable[dict[str, object]],
        username: str, description: str = "",
    ) -> int:
        values = list(lines)
        if not values:
            raise ValueError("Satın alma talebinde en az bir satır olmalıdır.")
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            request_no = self._next_no(connection, "TA")
            cursor = connection.execute(
                """
                INSERT INTO purchase_requests(
                    organization_id, request_no, request_date, requested_by, description
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (organization_id, request_no, request_date, username, description.strip()),
            )
            request_id = int(cursor.lastrowid)
            for index, line in enumerate(values, start=1):
                quantity = self._number(line.get("quantity"))
                if quantity <= 0:
                    raise ValueError(f"{index}. talep satırının miktarı sıfır olamaz.")
                stock_item_id = int(line.get("stock_item_id") or 0)
                stock = connection.execute(
                    "SELECT id FROM stock_items WHERE id = ? AND organization_id = ? AND active = 1",
                    (stock_item_id, organization_id),
                ).fetchone()
                if stock is None:
                    raise ValueError(f"{index}. talep satırının stok kartı geçersiz.")
                warehouse_value = line.get("warehouse_id")
                warehouse_id = (
                    int(warehouse_value) if warehouse_value
                    else self.warehouse_id(connection, str(line.get("warehouse_code") or "HAMMADDE"))
                )
                connection.execute(
                    """
                    INSERT INTO purchase_request_lines(
                        purchase_request_id, line_no, stock_item_id, warehouse_id,
                        required_date, quantity, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id, index, stock_item_id, warehouse_id,
                        str(line.get("required_date") or request_date), quantity,
                        str(line.get("reason") or "").strip(),
                    ),
                )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="PURCHASE_REQUEST", entity_id=request_id,
                record_key=request_no, after={"line_count": len(values)},
            )
            connection.commit()
        return request_id

    def approve_purchase_request(self, request_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            request = connection.execute(
                "SELECT * FROM purchase_requests WHERE id = ? AND organization_id = ?",
                (int(request_id), self.organization_id(connection)),
            ).fetchone()
            if request is None:
                raise ValueError("Satın alma talebi bulunamadı.")
            if str(request["approval_status"]) == "ONAYLANDI":
                return
            now = self._now()
            connection.execute(
                """
                UPDATE purchase_requests
                SET approval_status = 'ONAYLANDI', approved_by = ?, approved_at = ?,
                    row_version = row_version + 1 WHERE id = ?
                """,
                (username, now, int(request_id)),
            )
            connection.execute(
                "UPDATE purchase_request_lines SET approved_quantity = quantity WHERE purchase_request_id = ? AND status = 'AÇIK'",
                (int(request_id),),
            )
            self._audit(
                connection, username=username, action="APPROVE",
                entity_type="PURCHASE_REQUEST", entity_id=int(request_id),
                record_key=str(request["request_no"]),
            )
            connection.commit()

    def create_purchase_order_from_request(
        self, request_id: int, supplier_id: int, *, order_date: str,
        delivery_date: str | None = None, currency: str = "TRY",
        exchange_rate: float = 1, unit_prices: dict[int, float] | None = None,
        supplier_document_no: str = "", note: str = "", username: str,
    ) -> int:
        prices = unit_prices or {}
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            request = connection.execute(
                "SELECT * FROM purchase_requests WHERE id = ? AND organization_id = ?",
                (int(request_id), organization_id),
            ).fetchone()
            if request is None or str(request["approval_status"]) != "ONAYLANDI":
                raise ValueError("Yalnız onaylanmış satın alma talebi siparişe çevrilebilir.")
            supplier = connection.execute(
                "SELECT * FROM suppliers WHERE id = ? AND organization_id = ? AND active = 1",
                (int(supplier_id), organization_id),
            ).fetchone()
            if supplier is None:
                raise ValueError("Tedarikçi kartı bulunamadı.")
            lines = connection.execute(
                """
                SELECT *, MAX(0, approved_quantity - ordered_quantity) AS remaining_quantity
                FROM purchase_request_lines
                WHERE purchase_request_id = ? AND approved_quantity > ordered_quantity + 0.0005
                ORDER BY line_no
                """,
                (int(request_id),),
            ).fetchall()
            if not lines:
                raise ValueError("Talebin siparişe çevrilecek kalan miktarı yok.")
            order_no = self._next_no(connection, "SA")
            cursor = connection.execute(
                """
                INSERT INTO purchase_orders(
                    organization_id, supplier_id, purchase_request_id,
                    purchase_order_no, supplier_document_no, order_date,
                    delivery_date, currency, exchange_rate, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id, int(supplier_id), int(request_id), order_no,
                    supplier_document_no.strip(), order_date, delivery_date,
                    currency.strip().upper() or str(supplier["currency"]),
                    max(0.0001, self._number(exchange_rate)), note.strip(), username,
                ),
            )
            order_id = int(cursor.lastrowid)
            for index, line in enumerate(lines, start=1):
                quantity = float(line["remaining_quantity"])
                connection.execute(
                    """
                    INSERT INTO purchase_order_lines(
                        purchase_order_id, purchase_request_line_id, line_no,
                        stock_item_id, warehouse_id, quantity, unit_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id, int(line["id"]), index, int(line["stock_item_id"]),
                        int(line["warehouse_id"]), quantity,
                        max(0.0, self._number(prices.get(int(line["id"]), 0))),
                    ),
                )
                connection.execute(
                    """
                    UPDATE purchase_request_lines
                    SET ordered_quantity = ordered_quantity + ?, status = 'SİPARİŞE DÖNÜŞTÜ'
                    WHERE id = ?
                    """,
                    (quantity, int(line["id"])),
                )
            connection.execute(
                "UPDATE purchase_requests SET status = 'SİPARİŞE DÖNÜŞTÜ', row_version = row_version + 1 WHERE id = ?",
                (int(request_id),),
            )
            self._audit(
                connection, username=username, action="CONVERT_TO_ORDER",
                entity_type="PURCHASE_ORDER", entity_id=order_id,
                record_key=order_no, after={"request_id": int(request_id)},
            )
            connection.commit()
        return order_id

    def receive_purchase_order(
        self, purchase_order_id: int, *, receipt_date: str, username: str,
        dispatch_note_no: str = "", lot_no: str = "", note: str = "",
        quantities: dict[int, float] | None = None,
    ) -> int:
        requested = quantities or {}
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            order = connection.execute(
                "SELECT * FROM purchase_orders WHERE id = ? AND organization_id = ?",
                (int(purchase_order_id), organization_id),
            ).fetchone()
            if order is None or str(order["status"]) == "TAMAMLANDI":
                raise ValueError("Mal kabul yapılabilecek açık satın alma siparişi bulunamadı.")
            lines = connection.execute(
                """
                SELECT * FROM purchase_order_lines
                WHERE purchase_order_id = ? AND received_quantity < quantity - 0.0005
                ORDER BY line_no
                """,
                (int(purchase_order_id),),
            ).fetchall()
            if not lines:
                raise ValueError("Siparişin teslim alınacak kalan miktarı yok.")
            receipt_no = self._next_no(connection, "MG")
            cursor = connection.execute(
                """
                INSERT INTO goods_receipts(
                    organization_id, purchase_order_id, receipt_no,
                    dispatch_note_no, receipt_date, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id, int(purchase_order_id), receipt_no,
                    dispatch_note_no.strip(), receipt_date, note.strip(), username,
                ),
            )
            receipt_id = int(cursor.lastrowid)
            accepted = 0
            for line in lines:
                remaining = float(line["quantity"]) - float(line["received_quantity"])
                quantity = self._number(requested.get(int(line["id"]), remaining))
                if quantity <= 0:
                    continue
                if quantity > remaining + 0.0005:
                    raise ValueError(
                        f"{line['line_no']}. satır kabul miktarı kalan {remaining:.3f} miktarı aşamaz."
                    )
                accepted += 1
                connection.execute(
                    "INSERT INTO goods_receipt_lines(goods_receipt_id, purchase_order_line_id, quantity, lot_no) VALUES (?, ?, ?, ?)",
                    (receipt_id, int(line["id"]), quantity, lot_no.strip()),
                )
                connection.execute(
                    """
                    UPDATE purchase_order_lines
                    SET received_quantity = received_quantity + ?,
                        status = CASE WHEN received_quantity + ? >= quantity - 0.0005
                                      THEN 'TAMAMLANDI' ELSE 'KISMİ' END
                    WHERE id = ?
                    """,
                    (quantity, quantity, int(line["id"])),
                )
                connection.execute(
                    """
                    INSERT INTO stock_movements(
                        organization_id, stock_item_id, warehouse_id,
                        movement_type, direction, quantity, lot_no,
                        document_no, created_by
                    ) VALUES (?, ?, ?, 'SATIN ALMA MAL KABUL', 1, ?, ?, ?, ?)
                    """,
                    (
                        organization_id, int(line["stock_item_id"]),
                        int(line["warehouse_id"]), quantity, lot_no.strip(),
                        receipt_no, username,
                    ),
                )
            if accepted == 0:
                raise ValueError("En az bir mal kabul miktarı sıfırdan büyük olmalıdır.")
            open_count = connection.execute(
                "SELECT COUNT(*) FROM purchase_order_lines WHERE purchase_order_id = ? AND status <> 'TAMAMLANDI'",
                (int(purchase_order_id),),
            ).fetchone()[0]
            connection.execute(
                "UPDATE purchase_orders SET status = ?, row_version = row_version + 1 WHERE id = ?",
                ("TAMAMLANDI" if int(open_count) == 0 else "KISMİ TESLİM", int(purchase_order_id)),
            )
            self._audit(
                connection, username=username, action="GOODS_RECEIPT",
                entity_type="GOODS_RECEIPT", entity_id=receipt_id,
                record_key=receipt_no, after={"purchase_order_id": int(purchase_order_id)},
            )
            connection.commit()
        return receipt_id

    @staticmethod
    def _approval_display(value: object) -> str:
        status = str(value or "").strip().upper()
        if status in {"ONAYLANDI", "KABUL", "AÇIK", "TAMAMLANDI"}:
            return "KABUL"
        if status in {"BEKLİYOR", "ONAY BEKLİYOR", "TASLAK"}:
            return "BEKLİYOR"
        return status or "BEKLİYOR"

    def list_purchase_requests(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pr.id, pr.request_no, pr.request_date, pr.requested_by,
                       pr.description, pr.approval_status, pr.status,
                       COUNT(prl.id) AS line_count,
                       COALESCE(SUM(prl.quantity), 0) AS requested_quantity,
                       COALESCE(SUM(prl.approved_quantity), 0) AS approved_quantity,
                       COALESCE(SUM(prl.ordered_quantity), 0) AS ordered_quantity,
                       COALESCE(SUM(prl.quantity - prl.ordered_quantity), 0) AS pending_quantity
                FROM purchase_requests pr
                LEFT JOIN purchase_request_lines prl ON prl.purchase_request_id = pr.id
                WHERE pr.organization_id = ?
                GROUP BY pr.id ORDER BY pr.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            values["approval_display"] = self._approval_display(values.get("approval_status"))
            result.append(values)
        return result

    def list_purchase_request_lines(self, request_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT prl.id, prl.line_no, prl.required_date, prl.quantity,
                       prl.approved_quantity, prl.ordered_quantity, prl.reason,
                       prl.status, si.code AS stock_code, si.name AS stock_name,
                       si.unit, w.code AS warehouse_code, w.name AS warehouse_name
                FROM purchase_request_lines prl
                JOIN stock_items si ON si.id = prl.stock_item_id
                JOIN warehouses w ON w.id = prl.warehouse_id
                WHERE prl.purchase_request_id = ? ORDER BY prl.line_no
                """,
                (int(request_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_purchase_orders(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT po.id, po.purchase_order_no, po.supplier_document_no,
                       po.order_date, po.delivery_date, po.currency, po.exchange_rate,
                       po.status, po.created_by, s.code AS supplier_code,
                       s.name AS supplier_name, pr.request_no,
                       COUNT(pol.id) AS line_count,
                       COALESCE(SUM(pol.quantity), 0) AS ordered_quantity,
                       COALESCE(SUM(pol.received_quantity), 0) AS received_quantity,
                       COALESCE(SUM(pol.quantity - pol.received_quantity), 0) AS pending_quantity,
                       COALESCE(SUM(pol.quantity * pol.unit_price), 0) AS total_amount
                FROM purchase_orders po
                JOIN suppliers s ON s.id = po.supplier_id
                LEFT JOIN purchase_requests pr ON pr.id = po.purchase_request_id
                LEFT JOIN purchase_order_lines pol ON pol.purchase_order_id = po.id
                WHERE po.organization_id = ?
                GROUP BY po.id ORDER BY po.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            currency = str(values.get("currency") or "TRY").upper()
            values["currency_display"] = "TL" if currency == "TRY" else currency
            result.append(values)
        return result

    def list_purchase_order_lines(self, purchase_order_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pol.id, pol.line_no, pol.quantity, pol.received_quantity,
                       pol.unit_price, pol.status, si.code AS stock_code,
                       si.name AS stock_name, si.unit,
                       w.code AS warehouse_code, w.name AS warehouse_name
                FROM purchase_order_lines pol
                JOIN stock_items si ON si.id = pol.stock_item_id
                JOIN warehouses w ON w.id = pol.warehouse_id
                WHERE pol.purchase_order_id = ? ORDER BY pol.line_no
                """,
                (int(purchase_order_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_goods_receipts(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT gr.id, gr.receipt_no, gr.dispatch_note_no, gr.receipt_date,
                       gr.created_by, po.purchase_order_no, s.name AS supplier_name,
                       COUNT(grl.id) AS line_count,
                       COALESCE(SUM(grl.quantity), 0) AS received_quantity
                FROM goods_receipts gr
                JOIN purchase_orders po ON po.id = gr.purchase_order_id
                JOIN suppliers s ON s.id = po.supplier_id
                LEFT JOIN goods_receipt_lines grl ON grl.goods_receipt_id = gr.id
                WHERE gr.organization_id = ?
                GROUP BY gr.id ORDER BY gr.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _next_no(self, connection: sqlite3.Connection, prefix: str) -> str:
        connection.execute(
            "INSERT OR IGNORE INTO local_sequences(prefix, last_value) VALUES (?, 0)",
            (prefix,),
        )
        connection.execute(
            "UPDATE local_sequences SET last_value = last_value + 1 WHERE prefix = ?",
            (prefix,),
        )
        value = int(
            connection.execute(
                "SELECT last_value FROM local_sequences WHERE prefix = ?",
                (prefix,),
            ).fetchone()[0]
        )
        return self._format_sequence_no(prefix, value)

    def _audit(
        self,
        connection: sqlite3.Connection,
        *,
        username: str,
        action: str,
        entity_type: str,
        entity_id: int | None,
        record_key: str = "",
        before: object = None,
        after: object = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_log(
                organization_id, username, action, entity_type, entity_id,
                record_key, before_json, after_json, machine_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.organization_id(connection),
                username.strip() or "sistem",
                action,
                entity_type,
                entity_id,
                record_key,
                json.dumps(before, ensure_ascii=False) if before is not None else None,
                json.dumps(after, ensure_ascii=False) if after is not None else None,
                socket.gethostname(),
            ),
        )

    def _upsert_attachment(
        self,
        connection: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: int,
        document_type: str,
        file_path: str,
        username: str,
        source_system: str = "",
    ) -> int | None:
        path = Path(str(file_path or "").strip())
        if not str(file_path or "").strip():
            return None
        sha256 = ""
        size_bytes = 0
        if path.is_file():
            size_bytes = path.stat().st_size
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            sha256 = digest.hexdigest()
        content_type = mimetypes.guess_type(path.name)[0] or ""
        connection.execute(
            """
            INSERT INTO attachments(
                organization_id, entity_type, entity_id, document_type,
                file_name, file_path, content_type, sha256, size_bytes,
                source_system, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id, file_path) DO UPDATE SET
                document_type = excluded.document_type,
                file_name = excluded.file_name,
                content_type = excluded.content_type,
                sha256 = excluded.sha256,
                size_bytes = excluded.size_bytes,
                source_system = excluded.source_system,
                active = 1
            """,
            (
                self.organization_id(connection),
                entity_type.strip().upper(),
                int(entity_id),
                document_type.strip().upper(),
                path.name or "belge",
                str(path),
                content_type,
                sha256,
                size_bytes,
                source_system.strip().upper(),
                username.strip() or "sistem",
            ),
        )
        row = connection.execute(
            "SELECT id FROM attachments WHERE entity_type = ? AND entity_id = ? AND file_path = ?",
            (entity_type.strip().upper(), int(entity_id), str(path)),
        ).fetchone()
        return int(row[0]) if row else None

    def add_attachment(
        self,
        *,
        entity_type: str,
        entity_id: int,
        document_type: str,
        file_path: str,
        username: str,
    ) -> int | None:
        with closing(self.connect()) as connection:
            attachment_id = self._upsert_attachment(
                connection,
                entity_type=entity_type,
                entity_id=entity_id,
                document_type=document_type,
                file_path=file_path,
                username=username,
            )
            if attachment_id is not None:
                self._audit(
                    connection,
                    username=username,
                    action="ATTACH",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    record_key=str(attachment_id),
                    after={"document_type": document_type, "file_path": file_path},
                )
            connection.commit()
            return attachment_id

    def list_attachments(self, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, document_type, file_name, file_path, content_type,
                       sha256, size_bytes, source_system, created_at
                FROM attachments
                WHERE organization_id = ? AND entity_type = ?
                  AND entity_id = ? AND active = 1
                ORDER BY document_type, file_name
                """,
                (
                    self.organization_id(connection),
                    entity_type.strip().upper(),
                    int(entity_id),
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_customer(
        self,
        code: str,
        name: str,
        *,
        tax_office: str = "",
        tax_number: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        city: str = "",
        country: str = "TÜRKİYE",
        sales_representative: str = "",
        currency: str = "TRY",
        short_name: str = "",
        sector: str = "",
        district: str = "",
        postal_code: str = "",
        phone2: str = "",
        fax: str = "",
        email2: str = "",
        accounting_code: str = "",
        bank_name: str = "",
        notes: str = "",
        order_note: str = "",
        production_note: str = "",
        general_warning: str = "",
        is_supplier: bool = False,
        is_subcontractor: bool = False,
        contacts: Iterable[dict[str, object]] | None = None,
        addresses: Iterable[dict[str, object]] | None = None,
        username: str,
    ) -> int:
        code = code.strip().upper()
        name = name.strip()
        if not code or not name:
            raise ValueError("Müşteri kodu ve adı boş bırakılamaz.")
        with closing(self.connect()) as connection:
            duplicate = connection.execute(
                "SELECT 1 FROM customers WHERE organization_id = ? AND code = ?",
                (self.organization_id(connection), code),
            ).fetchone()
            if duplicate is not None:
                raise ValueError(f"{code} kodlu müşteri kartı zaten var.")
            values = {
                "code": code,
                "name": name,
                "tax_office": tax_office.strip(),
                "tax_number": tax_number.strip(),
                "phone": phone.strip(),
                "email": email.strip(),
                "address": address.strip(),
                "city": city.strip(),
                "country": country.strip() or "TÜRKİYE",
                "sales_representative": sales_representative.strip(),
                "currency": currency.strip().upper() or "TRY",
                "short_name": short_name.strip(),
                "sector": sector.strip(),
                "district": district.strip(),
                "postal_code": postal_code.strip(),
                "phone2": phone2.strip(),
                "fax": fax.strip(),
                "email2": email2.strip(),
                "accounting_code": accounting_code.strip(),
                "bank_name": bank_name.strip(),
                "notes": notes.strip(),
                "order_note": order_note.strip(),
                "production_note": production_note.strip(),
                "general_warning": general_warning.strip(),
                "is_supplier": 1 if is_supplier else 0,
                "is_subcontractor": 1 if is_subcontractor else 0,
            }
            cursor = connection.execute(
                """
                INSERT INTO customers(
                    organization_id, code, name, tax_office, tax_number, phone,
                    email, address, city, country, sales_representative, currency,
                    short_name, sector, district, postal_code, phone2, fax, email2,
                    accounting_code, bank_name, notes, order_note, production_note,
                    general_warning, is_supplier, is_subcontractor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.organization_id(connection), *values.values()),
            )
            record_id = int(cursor.lastrowid)
            self._replace_customer_contacts(
                connection, record_id, contacts or (), username=username
            )
            self._replace_customer_addresses(connection, record_id, addresses or ())
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="CUSTOMER",
                entity_id=record_id,
                record_key=code,
                after=values,
            )
            connection.commit()
            return record_id

    def customer(self, customer_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE organization_id = ? AND id = ?",
                (self.organization_id(connection), int(customer_id)),
            ).fetchone()
        if row is None:
            raise ValueError("Müşteri kartı bulunamadı.")
        return dict(row)

    def list_customer_contacts(self, customer_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, name, role, phone1, phone2, email, active
                FROM customer_contacts
                WHERE organization_id = ? AND customer_id = ? AND active = 1
                ORDER BY name, id
                """,
                (self.organization_id(connection), int(customer_id)),
            ).fetchall()
        return [dict(row) for row in rows]

    def _replace_customer_contacts(
        self, connection: sqlite3.Connection, customer_id: int,
        contacts: Iterable[dict[str, object]], *, username: str,
    ) -> None:
        connection.execute(
            "DELETE FROM customer_contacts WHERE organization_id = ? AND customer_id = ?",
            (self.organization_id(connection), int(customer_id)),
        )
        for contact in contacts:
            name = str(contact.get("name") or "").strip()
            if not name:
                continue
            connection.execute(
                """
                INSERT INTO customer_contacts(
                    organization_id, customer_id, name, role, phone1, phone2,
                    email, active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    self.organization_id(connection), int(customer_id), name,
                    str(contact.get("role") or "").strip(),
                    str(contact.get("phone1") or "").strip(),
                    str(contact.get("phone2") or "").strip(),
                    str(contact.get("email") or "").strip(),
                    username.strip() or "sistem",
                ),
            )

    def list_customer_addresses(self, customer_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, name, country, city, district, address, postal_code,
                       tax_office, tax_number, active
                FROM customer_addresses
                WHERE organization_id = ? AND customer_id = ? AND active = 1
                ORDER BY name, id
                """,
                (self.organization_id(connection), int(customer_id)),
            ).fetchall()
        return [dict(row) for row in rows]

    def _replace_customer_addresses(
        self,
        connection: sqlite3.Connection,
        customer_id: int,
        addresses: Iterable[dict[str, object]],
    ) -> None:
        connection.execute(
            "DELETE FROM customer_addresses WHERE organization_id = ? AND customer_id = ?",
            (self.organization_id(connection), int(customer_id)),
        )
        for values in addresses:
            name = str(values.get("name") or "MERKEZ").strip().upper() or "MERKEZ"
            address = str(values.get("address") or "").strip()
            if not address:
                continue
            connection.execute(
                """
                INSERT INTO customer_addresses(
                    organization_id, customer_id, name, country, city, district,
                    address, postal_code, tax_office, tax_number, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    self.organization_id(connection), int(customer_id), name,
                    str(values.get("country") or "TÜRKİYE").strip().upper(),
                    str(values.get("city") or "").strip().upper(),
                    str(values.get("district") or "").strip().upper(),
                    address,
                    str(values.get("postal_code") or "").strip(),
                    str(values.get("tax_office") or "").strip(),
                    str(values.get("tax_number") or "").strip(),
                ),
            )

    def update_customer(self, customer_id: int, *, username: str, **fields: object) -> None:
        before = self.customer(customer_id)
        code = str(fields.get("code", before["code"])).strip().upper()
        name = str(fields.get("name", before["name"])).strip()
        if not code or not name:
            raise ValueError("Müşteri kodu ve adı boş bırakılamaz.")
        values = {
            "code": code,
            "name": name,
            "tax_office": str(fields.get("tax_office", before["tax_office"])).strip(),
            "tax_number": str(fields.get("tax_number", before["tax_number"])).strip(),
            "phone": str(fields.get("phone", before["phone"])).strip(),
            "email": str(fields.get("email", before["email"])).strip(),
            "address": str(fields.get("address", before["address"])).strip(),
            "city": str(fields.get("city", before["city"])).strip(),
            "country": str(fields.get("country", before["country"])).strip() or "TÜRKİYE",
            "sales_representative": str(
                fields.get("sales_representative", before["sales_representative"])
            ).strip(),
            "currency": str(fields.get("currency", before["currency"])).strip().upper() or "TRY",
        }
        for key in (
            "short_name", "sector", "district", "postal_code", "phone2", "fax",
            "email2", "accounting_code", "bank_name", "notes", "order_note",
            "production_note", "general_warning",
        ):
            values[key] = str(fields.get(key, before[key]) or "").strip()
        values["is_supplier"] = 1 if fields.get("is_supplier", before["is_supplier"]) else 0
        values["is_subcontractor"] = (
            1 if fields.get("is_subcontractor", before["is_subcontractor"]) else 0
        )
        with closing(self.connect()) as connection:
            duplicate = connection.execute(
                """
                SELECT 1 FROM customers
                WHERE organization_id = ? AND code = ? AND id <> ?
                """,
                (self.organization_id(connection), code, int(customer_id)),
            ).fetchone()
            if duplicate is not None:
                raise ValueError(f"{code} kodlu başka bir müşteri kartı zaten var.")
            connection.execute(
                """
                UPDATE customers SET
                    code = ?, name = ?, tax_office = ?, tax_number = ?, phone = ?,
                    email = ?, address = ?, city = ?, country = ?,
                    sales_representative = ?, currency = ?, short_name = ?, sector = ?,
                    district = ?, postal_code = ?, phone2 = ?, fax = ?, email2 = ?,
                    accounting_code = ?, bank_name = ?, notes = ?, order_note = ?,
                    production_note = ?, general_warning = ?, is_supplier = ?,
                    is_subcontractor = ?, updated_at = CURRENT_TIMESTAMP,
                    row_version = row_version + 1
                WHERE organization_id = ? AND id = ?
                """,
                (*values.values(), self.organization_id(connection), int(customer_id)),
            )
            if "contacts" in fields:
                self._replace_customer_contacts(
                    connection, int(customer_id), fields.get("contacts") or (),
                    username=username,
                )
            if "addresses" in fields:
                self._replace_customer_addresses(
                    connection, int(customer_id), fields.get("addresses") or ()
                )
            self._audit(
                connection, username=username, action="UPDATE", entity_type="CUSTOMER",
                entity_id=int(customer_id), record_key=code, before=before, after=values,
            )
            connection.commit()

    def set_customer_active(self, customer_id: int, active: bool, *, username: str) -> None:
        before = self.customer(customer_id)
        with closing(self.connect()) as connection:
            connection.execute(
                """
                UPDATE customers SET active = ?, updated_at = CURRENT_TIMESTAMP,
                    row_version = row_version + 1
                WHERE organization_id = ? AND id = ?
                """,
                (1 if active else 0, self.organization_id(connection), int(customer_id)),
            )
            self._audit(
                connection, username=username,
                action="ACTIVATE" if active else "DEACTIVATE",
                entity_type="CUSTOMER", entity_id=int(customer_id),
                record_key=str(before["code"]), before={"active": before["active"]},
                after={"active": 1 if active else 0},
            )
            connection.commit()

    def delete_customer(self, customer_id: int, *, username: str) -> None:
        """Müşteri kartını kalıcı siler; bağlı sipariş varsa engeller."""
        before = self.customer(customer_id)
        with closing(self.connect()) as connection:
            org_id = self.organization_id(connection)
            cid = int(customer_id)
            blockers: list[str] = []
            order_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM sales_orders
                    WHERE organization_id = ? AND customer_id = ?
                    """,
                    (org_id, cid),
                ).fetchone()[0]
            )
            if order_count:
                blockers.append(f"{order_count} satış siparişi")
            quote_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM sales_quotes
                    WHERE organization_id = ? AND customer_id = ?
                    """,
                    (org_id, cid),
                ).fetchone()[0]
            ) if self._table_exists(connection, "sales_quotes") else 0
            if quote_count:
                blockers.append(f"{quote_count} satış teklifi")
            complaint_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM customer_complaints
                    WHERE organization_id = ? AND customer_id = ?
                    """,
                    (org_id, cid),
                ).fetchone()[0]
            ) if self._table_exists(connection, "customer_complaints") else 0
            if complaint_count:
                blockers.append(f"{complaint_count} şikayet kaydı")
            if blockers:
                raise ValueError(
                    f"{before['code']} — {before['name']} silinemez; bağlı kayıtlar var: "
                    + ", ".join(blockers)
                    + ". Önce bağlı kayıtları kaldırın veya kartı pasife alın."
                )
            connection.execute(
                "DELETE FROM customer_contacts WHERE organization_id = ? AND customer_id = ?",
                (org_id, cid),
            )
            connection.execute(
                "DELETE FROM customer_addresses WHERE organization_id = ? AND customer_id = ?",
                (org_id, cid),
            )
            connection.execute(
                "DELETE FROM customers WHERE organization_id = ? AND id = ?",
                (org_id, cid),
            )
            self._audit(
                connection,
                username=username,
                action="DELETE",
                entity_type="CUSTOMER",
                entity_id=cid,
                record_key=str(before["code"]),
                before=before,
            )
            connection.commit()

    def create_profile(
        self,
        profile_code: str,
        profile_name: str,
        *,
        unit_weight_kg_m: float,
        customer_id: int | None = None,
        alloy: str = "6060B",
        temper: str = "T5",
        username: str,
    ) -> int:
        profile_code = profile_code.strip().upper()
        profile_name = profile_name.strip()
        if not profile_code or not profile_name:
            raise ValueError("Profil kodu ve adı boş bırakılamaz.")
        if self._number(unit_weight_kg_m) <= 0:
            raise ValueError("Profil birim ağırlığı sıfırdan büyük olmalıdır.")
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO profiles(
                    organization_id, customer_id, profile_code, profile_name,
                    unit_weight_kg_m, alloy, temper
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    customer_id,
                    profile_code,
                    profile_name,
                    self._number(unit_weight_kg_m),
                    alloy.strip().upper(),
                    temper.strip().upper(),
                ),
            )
            profile_id = int(cursor.lastrowid)
            stock_cursor = connection.execute(
                """
                INSERT INTO stock_items(
                    organization_id, profile_id, code, name, stock_group, unit
                ) VALUES (?, ?, ?, ?, 'PROFİL', 'KG')
                """,
                (
                    self.organization_id(connection),
                    profile_id,
                    profile_code,
                    profile_name,
                ),
            )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="PROFILE",
                entity_id=profile_id,
                record_key=profile_code,
                after={
                    "profile_name": profile_name,
                    "unit_weight_kg_m": self._number(unit_weight_kg_m),
                    "stock_item_id": int(stock_cursor.lastrowid),
                },
            )
            connection.commit()
            return profile_id

    def profile(self, profile_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT p.*, org.name AS organization_name
                FROM profiles p
                JOIN organizations org ON org.id = p.organization_id
                WHERE p.id = ? AND p.organization_id = ?
                """,
                (int(profile_id), self.organization_id(connection)),
            ).fetchone()
            if row is None:
                raise ValueError("Profil kartı bulunamadı.")
        return dict(row)

    def update_profile(
        self,
        profile_id: int,
        *,
        profile_name: str,
        unit_weight_kg_m: float,
        alloy: str,
        temper: str,
        username: str,
    ) -> None:
        name = profile_name.strip()
        if not name:
            raise ValueError("Profil adı boş bırakılamaz.")
        weight = self._number(unit_weight_kg_m)
        if weight <= 0:
            raise ValueError("Teorik ağırlık sıfırdan büyük olmalıdır.")
        with closing(self.connect()) as connection:
            profile = connection.execute(
                "SELECT * FROM profiles WHERE id = ? AND organization_id = ?",
                (int(profile_id), self.organization_id(connection)),
            ).fetchone()
            if profile is None:
                raise ValueError("Profil kartı bulunamadı.")
            connection.execute(
                """
                UPDATE profiles
                SET profile_name = ?, unit_weight_kg_m = ?, alloy = ?, temper = ?,
                    updated_at = CURRENT_TIMESTAMP, row_version = row_version + 1
                WHERE id = ?
                """,
                (
                    name, weight, alloy.strip().upper(), temper.strip().upper(),
                    int(profile_id),
                ),
            )
            connection.execute(
                """
                UPDATE stock_items
                SET name = ?, row_version = row_version + 1
                WHERE profile_id = ? AND organization_id = ?
                """,
                (name, int(profile_id), self.organization_id(connection)),
            )
            self._audit(
                connection, username=username, action="UPDATE",
                entity_type="PROFILE", entity_id=int(profile_id),
                record_key=str(profile["profile_code"]),
            )
            connection.commit()

    def deactivate_profile(self, profile_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            profile = connection.execute(
                "SELECT * FROM profiles WHERE id = ? AND organization_id = ?",
                (int(profile_id), self.organization_id(connection)),
            ).fetchone()
            if profile is None:
                raise ValueError("Profil kartı bulunamadı.")
            open_orders = connection.execute(
                """
                SELECT 1 FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                WHERE l.profile_id = ? AND o.status NOT IN ('KAPALI', 'İPTAL', 'SEVK EDİLDİ')
                LIMIT 1
                """,
                (int(profile_id),),
            ).fetchone()
            if open_orders is not None:
                raise ValueError("Açık siparişi olan profil pasife alınamaz.")
            connection.execute(
                """
                UPDATE profiles SET active = 0, updated_at = CURRENT_TIMESTAMP,
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (int(profile_id),),
            )
            connection.execute(
                """
                UPDATE stock_items SET active = 0, row_version = row_version + 1
                WHERE profile_id = ? AND organization_id = ?
                """,
                (int(profile_id), self.organization_id(connection)),
            )
            self._audit(
                connection, username=username, action="DEACTIVATE",
                entity_type="PROFILE", entity_id=int(profile_id),
                record_key=str(profile["profile_code"]),
            )
            connection.commit()

    def die(self, die_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT d.*, p.profile_code, p.profile_name
                FROM dies d
                JOIN profiles p ON p.id = d.profile_id
                WHERE d.id = ? AND d.organization_id = ?
                """,
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
        return dict(row)

    def update_die(
        self,
        die_id: int,
        *,
        life_limit_kg: float,
        tenefer_no: str,
        tenefer_type: str,
        tenefer_limit_m: float,
        location: str,
        note: str,
        username: str,
        figure_count: int | None = None,
        supplier_name: str = "",
    ) -> None:
        with closing(self.connect()) as connection:
            die_row = connection.execute(
                "SELECT * FROM dies WHERE id = ? AND organization_id = ?",
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if die_row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            no = tenefer_no.strip().upper()
            limit_m = self._number(tenefer_limit_m)
            if limit_m <= 0 and no:
                limit_m = self._tenefer_standard_limit_m(connection, no) or float(
                    die_row["tenefer_limit_m"] or 0
                )
            figure = (
                max(1, int(figure_count))
                if figure_count is not None
                else max(1, int(die_row["figure_count"] or 1))
            )
            connection.execute(
                """
                UPDATE dies
                SET life_limit_kg = ?, tenefer_no = ?, tenefer_type = ?,
                    tenefer_limit_m = ?, location = ?, note = ?,
                    figure_count = ?, supplier_name = ?,
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (
                    self._number(life_limit_kg),
                    no,
                    tenefer_type.strip().upper(),
                    limit_m,
                    location.strip().upper(),
                    note.strip(),
                    figure,
                    supplier_name.strip().upper()
                    or str(die_row["supplier_name"] or ""),
                    int(die_id),
                ),
            )
            if no.isdigit() and limit_m > 0:
                connection.execute(
                    """
                    INSERT INTO tenefer_life_limits(
                        organization_id, profile_id, die_id, tenefer_no,
                        operator_no, limit_m
                    ) VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(die_id, tenefer_no, operator_no) DO UPDATE SET
                        limit_m = excluded.limit_m
                    """,
                    (
                        int(die_row["organization_id"]),
                        int(die_row["profile_id"]),
                        int(die_id),
                        int(no),
                        limit_m,
                    ),
                )
            self._audit(
                connection, username=username, action="UPDATE",
                entity_type="DIE", entity_id=int(die_id),
                record_key=str(die_row["die_code"]),
            )
            connection.commit()

    def scrap_die(self, die_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            die_row = connection.execute(
                "SELECT * FROM dies WHERE id = ? AND organization_id = ?",
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if die_row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            active = connection.execute(
                """
                SELECT 1 FROM sales_order_lines
                WHERE die_id = ? AND status NOT IN ('HAZIR', 'KAPALI', 'İPTAL')
                LIMIT 1
                """,
                (int(die_id),),
            ).fetchone()
            if active is not None:
                raise ValueError("Aktif sipariş satırına bağlı kalıp hurdaya ayrılamaz.")
            connection.execute(
                """
                UPDATE dies SET status = 'HURDA', location = 'HURDA',
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (int(die_id),),
            )
            self._audit(
                connection, username=username, action="SCRAP",
                entity_type="DIE", entity_id=int(die_id),
                record_key=str(die_row["die_code"]),
            )
            connection.commit()

    def delete_die(self, die_id: int, *, username: str) -> None:
        """Kalıp kartını kalıcı siler; bağlı sipariş/hareket varsa engeller."""
        with closing(self.connect()) as connection:
            die_row = connection.execute(
                "SELECT * FROM dies WHERE id = ? AND organization_id = ?",
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if die_row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            blockers: list[str] = []
            line_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM sales_order_lines WHERE die_id = ?",
                    (int(die_id),),
                ).fetchone()[0]
            )
            if line_count:
                blockers.append(f"{line_count} sipariş satırı")
            move_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM die_movements WHERE die_id = ?",
                    (int(die_id),),
                ).fetchone()[0]
            ) if self._table_exists(connection, "die_movements") else 0
            if move_count:
                blockers.append(f"{move_count} kalıp hareketi")
            if blockers:
                raise ValueError(
                    f"{die_row['die_code']} kalıbı silinemez; bağlı kayıtlar var: "
                    + ", ".join(blockers)
                    + ". Silmek yerine hurdaya ayırın."
                )
            if self._table_exists(connection, "tenefer_life_limits"):
                connection.execute(
                    "DELETE FROM tenefer_life_limits WHERE die_id = ?",
                    (int(die_id),),
                )
            if self._table_exists(connection, "die_station_compatibility"):
                connection.execute(
                    "DELETE FROM die_station_compatibility WHERE die_id = ?",
                    (int(die_id),),
                )
            connection.execute("DELETE FROM dies WHERE id = ?", (int(die_id),))
            self._audit(
                connection,
                username=username,
                action="DELETE",
                entity_type="DIE",
                entity_id=int(die_id),
                record_key=str(die_row["die_code"]),
                before=dict(die_row),
            )
            connection.commit()


    def apply_price_list_to_order(
        self, order_id: int, price_list_id: int, *, username: str
    ) -> int:
        with closing(self.connect()) as connection:
            self._assert_sales_order_editable(connection, int(order_id))
            price_list = connection.execute(
                """
                SELECT * FROM sales_price_lists
                WHERE id = ? AND organization_id = ?
                """,
                (int(price_list_id), self.organization_id(connection)),
            ).fetchone()
            if price_list is None:
                raise ValueError("Fiyat listesi bulunamadı.")
            lines = connection.execute(
                """
                SELECT l.id, l.profile_id, l.surface, l.alloy, l.temper, l.unit_price
                FROM sales_order_lines l
                WHERE l.sales_order_id = ?
                ORDER BY l.line_no
                """,
                (int(order_id),),
            ).fetchall()
            updated = 0
            for line in lines:
                match = connection.execute(
                    """
                    SELECT unit_price FROM sales_price_list_lines
                    WHERE price_list_id = ? AND profile_id = ?
                      AND (surface = '' OR surface = ?)
                      AND (alloy = '' OR alloy = ?)
                      AND (temper = '' OR temper = ?)
                    ORDER BY
                        CASE WHEN surface <> '' THEN 0 ELSE 1 END,
                        CASE WHEN alloy <> '' THEN 0 ELSE 1 END,
                        CASE WHEN temper <> '' THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (
                        int(price_list_id), int(line["profile_id"]),
                        str(line["surface"] or ""), str(line["alloy"] or ""),
                        str(line["temper"] or ""),
                    ),
                ).fetchone()
                if match is None:
                    continue
                new_price = float(match["unit_price"])
                if abs(new_price - float(line["unit_price"] or 0)) < 0.000001:
                    continue
                connection.execute(
                    """
                    UPDATE sales_order_lines
                    SET unit_price = ?, row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (new_price, int(line["id"])),
                )
                updated += 1
            if updated == 0:
                raise ValueError("Fiyat listesinde eşleşen satır bulunamadı.")
            self._audit(
                connection, username=username, action="PRICE_LIST_APPLY",
                entity_type="SALES_ORDER", entity_id=int(order_id),
                record_key=str(price_list["list_code"]),
                after={"updated_lines": updated, "price_list_id": int(price_list_id)},
            )
            connection.commit()
        return updated

    def apply_maturity_pricing_to_order(
        self,
        order_id: int,
        *,
        annual_rate_pct: float = 12.0,
        username: str,
    ) -> int:
        """Vadeli siparişlerde birim fiyatı vade gününe göre günceller."""
        with closing(self.connect()) as connection:
            self._assert_sales_order_editable(connection, int(order_id))
            order = connection.execute(
                "SELECT * FROM sales_orders WHERE id = ?", (int(order_id),)
            ).fetchone()
            if order is None:
                raise ValueError("Satış siparişi bulunamadı.")
            payment = str(order["payment_method"] or "").upper()
            days = int(order["maturity_days"] or 0)
            if payment not in {"VADELİ", "ÇEK", "SENET"} or days <= 0:
                raise ValueError("Vade farkı yalnızca vadeli/çek/senet siparişlerde uygulanır.")
            factor = 1.0 + (days / 365.0) * (float(annual_rate_pct) / 100.0)
            lines = connection.execute(
                "SELECT id, unit_price FROM sales_order_lines WHERE sales_order_id = ?",
                (int(order_id),),
            ).fetchall()
            updated = 0
            for line in lines:
                old_price = float(line["unit_price"] or 0)
                if old_price <= 0:
                    continue
                new_price = round(old_price * factor, 4)
                connection.execute(
                    """
                    UPDATE sales_order_lines
                    SET unit_price = ?, row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (new_price, int(line["id"])),
                )
                updated += 1
            if updated == 0:
                raise ValueError("Güncellenecek fiyatlı satır bulunamadı.")
            self._audit(
                connection, username=username, action="MATURITY_PRICING",
                entity_type="SALES_ORDER", entity_id=int(order_id),
                record_key=str(order["order_no"]),
                after={"days": days, "rate_pct": annual_rate_pct, "lines": updated},
            )
            connection.commit()
        return updated

    def create_purchase_request_from_sales_order(
        self, order_id: int, *, username: str
    ) -> int:
        """Karşı sipariş — satış siparişi satırlarından satın alma talebi."""
        progress = self.order_progress(int(order_id))
        order = progress["order"]
        lines: list[dict[str, object]] = []
        with closing(self.connect()) as connection:
            org_id = self.organization_id(connection)
            for row in progress["lines"]:
                stock = connection.execute(
                    "SELECT id FROM stock_items WHERE profile_id = ? AND organization_id = ? AND active = 1 LIMIT 1",
                    (int(row["profile_id"]), org_id),
                ).fetchone()
                if stock is None:
                    raise ValueError(
                        f"{row.get('profile_code')} için stok kartı bulunamadı."
                    )
                qty = float(row["ordered_kg"] or row["ordered_quantity"] or 0)
                if qty <= 0:
                    continue
                lines.append({
                    "stock_item_id": int(stock["id"]),
                    "quantity": qty,
                    "warehouse_code": "HAMMADDE",
                    "reason": f"Karşı talep — {order['order_no']} satır {row['line_no']}",
                })
        if not lines:
            raise ValueError("Talep satırı oluşturulacak miktar yok.")
        return self.create_purchase_request(
            request_date=str(order["order_date"]),
            description=f"Satış siparişi {order['order_no']} karşı talebi",
            lines=lines,
            username=username,
        )

    def create_purchase_request_from_recipe_materials(
        self, order_id: int, *, username: str
    ) -> int:
        """Alt malzeme siparişi — reçete hammaddelerinden satın alma talebi."""
        progress = self.order_progress(int(order_id))
        order = progress["order"]
        materials: dict[int, float] = {}
        with closing(self.connect()) as connection:
            org_id = self.organization_id(connection)
            for row in progress["lines"]:
                profile_id = int(row["profile_id"])
                routes = self.list_routes(profile_id)
                if not routes:
                    continue
                recipe = connection.execute(
                    """
                    SELECT r.id, r.raw_material_stock_external_id
                    FROM recipes r
                    WHERE r.profile_id = ? AND r.active = 1
                    ORDER BY r.id DESC LIMIT 1
                    """,
                    (profile_id,),
                ).fetchone()
                if recipe is None:
                    continue
                raw_code = str(recipe["raw_material_stock_external_id"] or "AL-BILLET").strip().upper()
                stock = connection.execute(
                    """
                    SELECT id FROM stock_items
                    WHERE organization_id = ? AND UPPER(code) = ? AND active = 1
                    """,
                    (org_id, raw_code),
                ).fetchone()
                if stock is None:
                    continue
                need_kg = float(row["ordered_kg"] or 0)
                if need_kg <= 0:
                    continue
                sid = int(stock["id"])
                materials[sid] = materials.get(sid, 0.0) + need_kg
            if not materials:
                raise ValueError("Reçeteden çıkarılacak hammadde bulunamadı.")
            lines = [
                {
                    "stock_item_id": sid,
                    "quantity": qty,
                    "warehouse_code": "HAMMADDE",
                    "reason": f"Alt malzeme — {order['order_no']}",
                }
                for sid, qty in materials.items()
            ]
        return self.create_purchase_request(
            request_date=str(order["order_date"]),
            description=f"Satış siparişi {order['order_no']} alt malzeme talebi",
            lines=lines,
            username=username,
        )

    def create_die(
        self,
        profile_id: int,
        die_code: str,
        *,
        spare_no: int = 0,
        figure_count: int = 1,
        life_limit_kg: float = 0,
        tenefer_no: str = "",
        tenefer_type: str = "",
        tenefer_limit_m: float = 0,
        compatible_stations: Iterable[str] | None = None,
        supplier_name: str = "",
        note: str = "",
        username: str,
    ) -> int:
        die_code = die_code.strip().upper()
        if not die_code:
            raise ValueError("Kalıp kodu boş bırakılamaz.")
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO dies(
                    organization_id, profile_id, die_code, spare_no,
                    figure_count, life_limit_kg, tenefer_no, tenefer_type,
                    tenefer_limit_m, supplier_name, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(profile_id),
                    die_code,
                    int(spare_no),
                    max(1, int(figure_count)),
                    self._number(life_limit_kg),
                    tenefer_no.strip().upper(),
                    tenefer_type.strip().upper(),
                    self._number(tenefer_limit_m),
                    supplier_name.strip().upper(),
                    note.strip(),
                ),
            )
            die_id = int(cursor.lastrowid)
            # Varsayılan durum: ARŞİVDE
            connection.execute(
                "UPDATE dies SET status = 'ARŞİVDE' WHERE id = ?",
                (die_id,),
            )
            no = tenefer_no.strip()
            limit_m = self._number(tenefer_limit_m)
            if no and limit_m <= 0:
                self._sync_die_tenefer_limit(connection, die_id)
            elif no and no.isdigit() and limit_m > 0:
                connection.execute(
                    """
                    INSERT INTO tenefer_life_limits(
                        organization_id, profile_id, die_id, tenefer_no,
                        operator_no, limit_m
                    ) VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(die_id, tenefer_no, operator_no) DO UPDATE SET
                        limit_m = excluded.limit_m
                    """,
                    (
                        self.organization_id(connection),
                        int(profile_id),
                        die_id,
                        int(no),
                        limit_m,
                    ),
                )
            for station_name in compatible_stations or ():
                cleaned_station = str(station_name or "").strip().upper()
                if not cleaned_station:
                    continue
                station_id = self._ensure_operation_station(
                    connection,
                    operation_name="PRES ÜRETİM",
                    station_name=cleaned_station,
                )
                connection.execute(
                    """
                    INSERT INTO die_station_compatibility(
                        die_id, station_id, station_external_id,
                        external_source, external_id, active
                    ) VALUES (?, ?, ?, 'RIGEL', ?, 1)
                    ON CONFLICT(die_id, station_external_id) DO UPDATE SET
                        station_id = excluded.station_id, active = 1
                    """,
                    (die_id, station_id, cleaned_station, f"{die_id}:{cleaned_station}"),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="DIE",
                entity_id=die_id,
                record_key=f"{die_code}/{spare_no}",
            )
            connection.commit()
            return die_id

    def _tenefer_standard_limit_m(
        self,
        connection: sqlite3.Connection,
        tenefer_no: str,
        *,
        operator_no: int = 1,
    ) -> float:
        cleaned = str(tenefer_no or "").strip()
        if not cleaned.isdigit():
            return 0.0
        row = connection.execute(
            """
            SELECT limit_m FROM tenefer_life_standards
            WHERE tenefer_no = ? AND operator_no = ?
            """,
            (int(cleaned), int(operator_no)),
        ).fetchone()
        return float(row["limit_m"]) if row is not None else 0.0

    def _sync_die_tenefer_limit(
        self,
        connection: sqlite3.Connection,
        die_id: int,
        *,
        tenefer_no: str | None = None,
    ) -> None:
        die = connection.execute("SELECT * FROM dies WHERE id = ?", (int(die_id),)).fetchone()
        if die is None:
            return
        no = str(tenefer_no if tenefer_no is not None else die["tenefer_no"] or "").strip()
        if not no.isdigit():
            return
        limit_m = self._tenefer_standard_limit_m(connection, no)
        if limit_m <= 0:
            return
        connection.execute(
            """
            UPDATE dies
            SET tenefer_limit_m = ?, row_version = row_version + 1
            WHERE id = ?
            """,
            (limit_m, int(die_id)),
        )
        connection.execute(
            """
            INSERT INTO tenefer_life_limits(
                organization_id, profile_id, die_id, tenefer_no, operator_no, limit_m
            ) VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(die_id, tenefer_no, operator_no) DO UPDATE SET
                limit_m = excluded.limit_m
            """,
            (
                int(die["organization_id"]),
                int(die["profile_id"]),
                int(die_id),
                int(no),
                limit_m,
            ),
        )

    def _enrich_die_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        values = dict(row)
        limit_kg = float(values.get("life_limit_kg") or 0)
        used_kg = float(values.get("used_kg") or 0)
        limit_m = float(values.get("tenefer_limit_m") or 0)
        used_m = float(values.get("tenefer_used_m") or 0)
        values["remaining_kg"] = max(0.0, limit_kg - used_kg)
        values["tenefer_remaining_m"] = max(0.0, limit_m - used_m)
        values["usage_pct"] = round(used_kg / limit_kg * 100.0, 1) if limit_kg > 0 else 0.0
        values["tenefer_usage_pct"] = (
            round(used_m / limit_m * 100.0, 1) if limit_m > 0 else 0.0
        )
        if int(values.get("is_external") or 0):
            values["external_label"] = str(values.get("external_company") or "DIŞARIDA")
        else:
            values["external_label"] = str(values.get("location") or "FABRİKA")
        return values

    def _die_tenefer_metre_delta(
        self,
        die_row: sqlite3.Row | dict[str, Any],
        *,
        metre: float,
        quantity: float,
        length_mm: float,
    ) -> float:
        figure = max(
            1,
            int(
                die_row["figure_count"]
                if isinstance(die_row, sqlite3.Row)
                else die_row.get("figure_count") or 1
            ),
        )
        net_metre = self._number(metre)
        if net_metre <= 0 and quantity > 0 and length_mm > 0:
            net_metre = quantity * (length_mm / 1000.0)
        return net_metre * figure

    def _record_die_production_usage(
        self,
        connection: sqlite3.Connection,
        *,
        die_id: int,
        net_kg: float,
        tenefer_delta_m: float,
        production_entry_id: int,
        username: str,
        work_order_no: str = "",
    ) -> None:
        die = connection.execute("SELECT * FROM dies WHERE id = ?", (int(die_id),)).fetchone()
        if die is None:
            return
        status = str(die["status"] or "").upper()
        if status in {"HURDA", "DIŞARIDA", "TEDARİK BEKLİYOR"}:
            raise ValueError(
                f"Kalıp {die['die_code']} durumu '{die['status']}' — üretim girilemez."
            )
        if int(die["is_external"] or 0):
            raise ValueError(
                f"Kalıp {die['die_code']} tenefer/firma dışında — üretim girilemez."
            )
        # Tenefer yaklaşma ayrı ekran filtresidir; durum değişmez.
        # Yalnız kg ömrü tükenince BAKIMDA.
        connection.execute(
            """
            UPDATE dies
            SET used_kg = used_kg + ?, tenefer_used_m = tenefer_used_m + ?,
                status = CASE
                    WHEN life_limit_kg > 0 AND used_kg + ? >= life_limit_kg
                        THEN 'BAKIMDA'
                    ELSE status
                END,
                row_version = row_version + 1
            WHERE id = ?
            """,
            (net_kg, tenefer_delta_m, net_kg, int(die_id)),
        )
        connection.execute(
            """
            INSERT INTO die_movements(
                organization_id, die_id, movement_type, company, quantity, unit,
                location_from, location_to, note, created_by,
                production_entry_id, net_kg, metre, tenefer_no
            ) VALUES (?, ?, 'ÜRETİM', '', ?, 'KG', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(die["organization_id"]),
                int(die_id),
                net_kg,
                str(die["location"] or "PRES"),
                str(die["location"] or "PRES"),
                f"Pres fişi #{production_entry_id} / {work_order_no}".strip(" /"),
                username,
                int(production_entry_id),
                net_kg,
                tenefer_delta_m,
                str(die["tenefer_no"] or ""),
            ),
        )

    def send_die_to_tenefer(
        self,
        die_id: int,
        *,
        company: str,
        username: str,
        note: str = "",
    ) -> int:
        firm = company.strip().upper()
        if not firm:
            raise ValueError("Tenefer firması belirtilmelidir.")
        with closing(self.connect()) as connection:
            die = connection.execute(
                "SELECT * FROM dies WHERE id = ? AND organization_id = ?",
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if die is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            if int(die["is_external"] or 0):
                raise ValueError("Kalıp zaten dışarıda görünüyor.")
            doc_no = self._next_no(connection, "TN")
            cursor = connection.execute(
                """
                INSERT INTO tenefer_documents(
                    organization_id, document_no, company_name, direction,
                    document_date, total_kg, total_count, note, created_by
                ) VALUES (?, ?, ?, 'GİDEN', ?, ?, 1, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    doc_no,
                    firm,
                    self._now()[:10],
                    float(die["used_kg"] or 0),
                    note.strip(),
                    username,
                ),
            )
            doc_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO tenefer_document_lines(
                    tenefer_document_id, die_id, profile_id,
                    tenefer_no, tenefer_type, direction
                ) VALUES (?, ?, ?, ?, ?, 'GİDEN')
                """,
                (
                    doc_id,
                    int(die_id),
                    int(die["profile_id"]),
                    str(die["tenefer_no"] or ""),
                    str(die["tenefer_type"] or ""),
                ),
            )
            connection.execute(
                """
                INSERT INTO die_movements(
                    organization_id, die_id, movement_type, company, quantity, unit,
                    location_from, location_to, note, created_by, tenefer_no
                ) VALUES (?, ?, 'TENEFER GİTTİ', ?, 1, 'ADET', ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(die_id),
                    firm,
                    str(die["location"] or "ARŞİVDE"),
                    firm,
                    note.strip() or f"Tenefer belgesi {doc_no}",
                    username,
                    str(die["tenefer_no"] or ""),
                ),
            )
            connection.execute(
                """
                UPDATE dies
                SET is_external = 1, external_company = ?, location = ?,
                    status = 'DIŞARIDA', row_version = row_version + 1
                WHERE id = ?
                """,
                (firm, firm, int(die_id)),
            )
            self._audit(
                connection,
                username=username,
                action="TENEFER_SEND",
                entity_type="DIE",
                entity_id=int(die_id),
                record_key=str(die["die_code"]),
                after={"company": firm, "document_no": doc_no},
            )
            connection.commit()
            return doc_id

    def receive_die_from_tenefer(
        self,
        die_id: int,
        *,
        company: str,
        new_tenefer_no: str,
        username: str,
        note: str = "",
    ) -> int:
        firm = company.strip().upper()
        tenefer_no = str(new_tenefer_no or "").strip().upper()
        if not firm:
            raise ValueError("Tenefer firması belirtilmelidir.")
        if not tenefer_no.isdigit():
            raise ValueError("Yeni tenefer numarası sayısal olmalıdır.")
        with closing(self.connect()) as connection:
            die = connection.execute(
                "SELECT * FROM dies WHERE id = ? AND organization_id = ?",
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if die is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            doc_no = self._next_no(connection, "TN")
            cursor = connection.execute(
                """
                INSERT INTO tenefer_documents(
                    organization_id, document_no, company_name, direction,
                    document_date, total_kg, total_count, note, created_by
                ) VALUES (?, ?, ?, 'GELEN', ?, ?, 1, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    doc_no,
                    firm,
                    self._now()[:10],
                    float(die["used_kg"] or 0),
                    note.strip(),
                    username,
                ),
            )
            doc_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO tenefer_document_lines(
                    tenefer_document_id, die_id, profile_id,
                    tenefer_no, tenefer_type, direction
                ) VALUES (?, ?, ?, ?, ?, 'GELEN')
                """,
                (
                    doc_id,
                    int(die_id),
                    int(die["profile_id"]),
                    tenefer_no,
                    str(die["tenefer_type"] or ""),
                ),
            )
            connection.execute(
                """
                INSERT INTO die_movements(
                    organization_id, die_id, movement_type, company, quantity, unit,
                    location_from, location_to, note, created_by, tenefer_no
                ) VALUES (?, ?, 'TENEFER GELDİ', ?, 1, 'ADET', ?, 'ARŞİVDE', ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(die_id),
                    firm,
                    firm,
                    note.strip() or f"Tenefer {tenefer_no} ile döndü ({doc_no})",
                    username,
                    tenefer_no,
                ),
            )
            # Tenefer geldikten sonra kullanım sıfırlanır, durum ARŞİVDE
            connection.execute(
                """
                UPDATE dies
                SET is_external = 0, external_company = '', location = 'ARŞİVDE',
                    tenefer_no = ?, tenefer_used_m = 0, status = 'ARŞİVDE',
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (tenefer_no, int(die_id)),
            )
            self._sync_die_tenefer_limit(connection, int(die_id), tenefer_no=tenefer_no)
            self._audit(
                connection,
                username=username,
                action="TENEFER_RECEIVE",
                entity_type="DIE",
                entity_id=int(die_id),
                record_key=str(die["die_code"]),
                after={"company": firm, "tenefer_no": tenefer_no, "document_no": doc_no},
            )
            connection.commit()
            return doc_id

    def list_tenefer_documents(self, die_id: int | None = None) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            org_id = self.organization_id(connection)
            if die_id is not None:
                rows = connection.execute(
                    """
                    SELECT td.id, td.document_no, td.company_name, td.direction,
                           td.document_date AS record_date, td.total_kg,
                           td.total_count, td.note, td.created_by,
                           d.die_code, tl.tenefer_no
                    FROM tenefer_documents td
                    JOIN tenefer_document_lines tl ON tl.tenefer_document_id = td.id
                    JOIN dies d ON d.id = tl.die_id
                    WHERE td.organization_id = ? AND tl.die_id = ?
                    ORDER BY td.id DESC
                    """,
                    (org_id, int(die_id)),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT td.id, td.document_no, td.company_name, td.direction,
                           td.document_date AS record_date, td.total_kg,
                           td.total_count, td.note, td.created_by,
                           GROUP_CONCAT(DISTINCT d.die_code) AS die_codes
                    FROM tenefer_documents td
                    LEFT JOIN tenefer_document_lines tl ON tl.tenefer_document_id = td.id
                    LEFT JOIN dies d ON d.id = tl.die_id
                    WHERE td.organization_id = ?
                    GROUP BY td.id
                    ORDER BY td.id DESC
                    """,
                    (org_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def _ensure_operation_station(
        self,
        connection: sqlite3.Connection,
        *,
        operation_name: str,
        station_name: str,
    ) -> int:
        organization_id = self.organization_id(connection)
        operation = operation_name.strip().upper()
        station = station_name.strip().upper()
        if not operation or not station:
            raise ValueError("Operasyon ve istasyon adı boş bırakılamaz.")
        operation_code = "_".join(operation.split())[:60]
        station_code = "_".join(station.split())[:60]
        connection.execute(
            """
            INSERT INTO operations(
                organization_id, external_source, external_id, code, name
            )
            VALUES (?, 'RIGEL', ?, ?, ?)
            ON CONFLICT(organization_id, code) DO UPDATE SET
                name = excluded.name, active = 1
            """,
            (organization_id, operation_code, operation_code, operation),
        )
        operation_id = int(
            connection.execute(
                "SELECT id FROM operations WHERE organization_id = ? AND code = ?",
                (organization_id, operation_code),
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO stations(
                organization_id, operation_id, external_source, external_id,
                code, name
            )
            VALUES (?, ?, 'RIGEL', ?, ?, ?)
            ON CONFLICT(organization_id, code) DO UPDATE SET
                operation_id = excluded.operation_id, name = excluded.name, active = 1
            """,
            (organization_id, operation_id, station_code, station_code, station),
        )
        return int(
            connection.execute(
                "SELECT id FROM stations WHERE organization_id = ? AND code = ?",
                (organization_id, station_code),
            ).fetchone()[0]
        )

    def set_die_station_compatibility(
        self,
        die_id: int,
        station_names: Iterable[str],
        *,
        username: str,
    ) -> None:
        prepared = sorted(
            {
                str(value or "").strip().upper()
                for value in station_names
                if str(value or "").strip()
            }
        )
        if not prepared:
            raise ValueError("Kalıp için en az bir uyumlu pres istasyonu seçilmelidir.")
        with closing(self.connect()) as connection:
            die = connection.execute(
                "SELECT id, die_code, spare_no FROM dies WHERE id = ?",
                (int(die_id),),
            ).fetchone()
            if die is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            connection.execute(
                "UPDATE die_station_compatibility SET active = 0 WHERE die_id = ?",
                (int(die_id),),
            )
            for station_name in prepared:
                station_id = self._ensure_operation_station(
                    connection,
                    operation_name="PRES ÜRETİM",
                    station_name=station_name,
                )
                connection.execute(
                    """
                    INSERT INTO die_station_compatibility(
                        die_id, station_id, station_external_id,
                        external_source, external_id, active
                    ) VALUES (?, ?, ?, 'RIGEL', ?, 1)
                    ON CONFLICT(die_id, station_external_id) DO UPDATE SET
                        station_id = excluded.station_id, active = 1
                    """,
                    (
                        int(die_id), station_id, station_name,
                        f"{int(die_id)}:{station_name}",
                    ),
                )
            self._audit(
                connection,
                username=username,
                action="SET_STATIONS",
                entity_type="DIE",
                entity_id=int(die_id),
                record_key=f"{die['die_code']}/{die['spare_no']}",
                after={"compatible_stations": prepared},
            )
            connection.commit()

    def create_route(
        self,
        profile_id: int,
        code: str,
        name: str,
        steps: Iterable[dict[str, object]],
        *,
        username: str,
        recipe_name: str = "",
        production_length_mm: int = 0,
        surface: str = "",
        color: str = "",
        alloy: str = "",
        temper: str = "",
        mechanical: str = "",
    ) -> int:
        prepared = list(steps)
        if not prepared:
            raise ValueError("Üretim rotasında en az bir operasyon bulunmalıdır.")
        route_code = code.strip().upper()
        route_name = name.strip()
        if not route_code or not route_name:
            raise ValueError("Üretim rotası kodu ve adı boş bırakılamaz.")
        for step in prepared:
            operation = str(step.get("operation") or "").strip()
            station = str(step.get("station") or "").strip()
            if not operation or not station:
                raise ValueError("Her rota adımında operasyon ve istasyon seçilmelidir.")
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO routes(
                    organization_id, profile_id, code, name, recipe_name,
                    production_length_mm, surface, color, alloy, temper, mechanical
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(profile_id),
                    route_code,
                    route_name,
                    recipe_name.strip(),
                    max(0, int(production_length_mm)),
                    surface.strip().upper(),
                    color.strip().upper(),
                    alloy.strip().upper(),
                    temper.strip().upper(),
                    mechanical.strip().upper(),
                ),
            )
            route_id = int(cursor.lastrowid)
            for sequence, step in enumerate(prepared, start=1):
                input_code = str(step.get("input_warehouse") or "").strip().upper()
                output_code = str(step.get("output_warehouse") or "").strip().upper()
                connection.execute(
                    """
                    INSERT INTO route_steps(
                        route_id, sequence_no, operation, default_station,
                        input_warehouse_id, output_warehouse_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        route_id,
                        sequence,
                        str(step.get("operation") or "").strip().upper(),
                        str(step.get("station") or "").strip().upper(),
                        self.warehouse_id(connection, input_code) if input_code else None,
                        self.warehouse_id(connection, output_code) if output_code else None,
                    ),
                )
                self._ensure_operation_station(
                    connection,
                    operation_name=str(step.get("operation") or ""),
                    station_name=str(step.get("station") or ""),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="ROUTE",
                entity_id=route_id,
                record_key=route_code,
                after={"steps": prepared},
            )
            connection.commit()
            return route_id

    def create_recipe(
        self,
        profile_id: int,
        route_id: int,
        recipe_code: str,
        recipe_name: str,
        lines: Iterable[dict[str, object]],
        *,
        username: str,
        production_length_mm: float = 0,
        saw_allowance_mm: float = 0,
        hanger_allowance_mm: float = 0,
        raw_material_stock_code: str = "",
    ) -> int:
        code = recipe_code.strip().upper()
        name = recipe_name.strip()
        prepared = list(lines)
        if not code or not name:
            raise ValueError("Reçete kodu ve adı boş bırakılamaz.")
        if not prepared:
            raise ValueError("Reçetede en az bir operasyon satırı olmalıdır.")
        with closing(self.connect()) as connection:
            route = connection.execute(
                """
                SELECT id FROM routes
                WHERE id = ? AND profile_id = ? AND organization_id = ? AND active = 1
                """,
                (int(route_id), int(profile_id), self.organization_id(connection)),
            ).fetchone()
            if route is None:
                raise ValueError("Profil ile üretim rotası eşleşmiyor.")
            raw_material_code = str(raw_material_stock_code or "").strip().upper()
            cursor = connection.execute(
                """
                INSERT INTO recipes(
                    organization_id, profile_id, route_id, external_source,
                    external_id, recipe_code, recipe_name, production_length_mm,
                    saw_allowance_mm, hanger_allowance_mm,
                    raw_material_stock_external_id
                ) VALUES (?, ?, ?, 'RIGEL', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection), int(profile_id), int(route_id),
                    code, code, name, self._number(production_length_mm),
                    self._number(saw_allowance_mm), self._number(hanger_allowance_mm),
                    raw_material_code,
                ),
            )
            recipe_id = int(cursor.lastrowid)
            for sequence_no, values in enumerate(prepared, start=1):
                operation = str(values.get("operation") or "").strip().upper()
                station = str(values.get("station") or "").strip().upper()
                if not operation or not station:
                    raise ValueError("Her reçete satırında operasyon ve istasyon olmalıdır.")
                route_sequence_no = int(
                    self._number(values.get("route_sequence_no") or sequence_no)
                )
                numerator = self._number(values.get("numerator"))
                denominator = self._number(values.get("denominator"))
                if (numerator > 0) != (denominator > 0):
                    raise ValueError("Reçete oranında pay ve payda birlikte girilmelidir.")
                self._ensure_operation_station(
                    connection, operation_name=operation, station_name=station
                )
                connection.execute(
                    """
                    INSERT INTO recipe_lines(
                        recipe_id, external_source, external_id, process_type,
                        sequence_no, route_sequence_no, quantity, main_quantity,
                        numerator, denominator, description, external_unit_weight,
                        external_kg, external_quantity, external_metre,
                        operation_name, station_name, stock_code, unit_code,
                        warehouse_code
                    ) VALUES (?, 'RIGEL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id, f"{code}:{sequence_no}",
                        str(values.get("process_type") or operation).strip().upper(),
                        sequence_no, route_sequence_no,
                        self._number(values.get("quantity")),
                        self._number(values.get("main_quantity")),
                        numerator, denominator,
                        str(values.get("description") or "").strip(),
                        self._number(values.get("unit_weight")),
                        self._number(values.get("kg")),
                        self._number(values.get("external_quantity")),
                        self._number(values.get("metre")),
                        operation, station,
                        str(values.get("stock_code") or "").strip().upper(),
                        str(values.get("unit_code") or "").strip().upper(),
                        str(values.get("warehouse_code") or "").strip().upper(),
                    ),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="RECIPE",
                entity_id=recipe_id,
                record_key=code,
                after={"route_id": int(route_id), "line_count": len(prepared)},
            )
            connection.commit()
            return recipe_id

    def _route_has_production(self, connection, route_id: int) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM production_orders
            WHERE route_id = ? AND status <> 'İPTAL'
            LIMIT 1
            """,
            (int(route_id),),
        ).fetchone()
        return row is not None

    def _recipe_has_production(self, connection, recipe_id: int) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM production_orders
            WHERE recipe_id = ? AND status <> 'İPTAL'
            LIMIT 1
            """,
            (int(recipe_id),),
        ).fetchone()
        return row is not None

    def get_recipe(self, recipe_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT rc.*, p.profile_code, p.profile_name,
                       r.code AS route_code, r.name AS route_name
                FROM recipes rc
                JOIN profiles p ON p.id = rc.profile_id
                LEFT JOIN routes r ON r.id = rc.route_id
                WHERE rc.id = ? AND rc.organization_id = ?
                """,
                (int(recipe_id), self.organization_id(connection)),
            ).fetchone()
            if row is None:
                raise ValueError("Reçete bulunamadı.")
        return dict(row)

    def update_route(
        self,
        route_id: int,
        *,
        name: str,
        steps: Iterable[dict[str, object]] | None,
        username: str,
        recipe_name: str = "",
        production_length_mm: int = 0,
        surface: str = "",
        color: str = "",
        alloy: str = "",
        temper: str = "",
        mechanical: str = "",
    ) -> None:
        route_name = name.strip()
        if not route_name:
            raise ValueError("Üretim rotası adı boş bırakılamaz.")
        prepared = list(steps) if steps is not None else None
        if prepared is not None and not prepared:
            raise ValueError("Üretim rotasında en az bir operasyon bulunmalıdır.")
        if prepared is not None:
            for step in prepared:
                operation = str(step.get("operation") or "").strip()
                station = str(step.get("station") or "").strip()
                if not operation or not station:
                    raise ValueError("Her rota adımında operasyon ve istasyon seçilmelidir.")
        with closing(self.connect()) as connection:
            route = connection.execute(
                """
                SELECT * FROM routes
                WHERE id = ? AND organization_id = ? AND active = 1
                """,
                (int(route_id), self.organization_id(connection)),
            ).fetchone()
            if route is None:
                raise ValueError("Üretim rotası bulunamadı.")
            if prepared is not None and self._route_has_production(connection, int(route_id)):
                raise ValueError(
                    "Bu rotayı kullanan üretim emri olduğu için operasyon adımları "
                    "değiştirilemez. Yalnızca rota adı ve koşul bilgileri güncellenebilir."
                )
            connection.execute(
                """
                UPDATE routes
                SET name = ?, recipe_name = ?, production_length_mm = ?,
                    surface = ?, color = ?, alloy = ?, temper = ?, mechanical = ?
                WHERE id = ?
                """,
                (
                    route_name,
                    recipe_name.strip(),
                    max(0, int(production_length_mm)),
                    surface.strip().upper(),
                    color.strip().upper(),
                    alloy.strip().upper(),
                    temper.strip().upper(),
                    mechanical.strip().upper(),
                    int(route_id),
                ),
            )
            if prepared is not None:
                connection.execute(
                    "DELETE FROM route_steps WHERE route_id = ?",
                    (int(route_id),),
                )
                for sequence, step in enumerate(prepared, start=1):
                    input_code = str(step.get("input_warehouse") or "").strip().upper()
                    output_code = str(step.get("output_warehouse") or "").strip().upper()
                    connection.execute(
                        """
                        INSERT INTO route_steps(
                            route_id, sequence_no, operation, default_station,
                            input_warehouse_id, output_warehouse_id
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(route_id),
                            sequence,
                            str(step.get("operation") or "").strip().upper(),
                            str(step.get("station") or "").strip().upper(),
                            self.warehouse_id(connection, input_code) if input_code else None,
                            self.warehouse_id(connection, output_code) if output_code else None,
                        ),
                    )
                    self._ensure_operation_station(
                        connection,
                        operation_name=str(step.get("operation") or ""),
                        station_name=str(step.get("station") or ""),
                    )
            self._audit(
                connection,
                username=username,
                action="UPDATE",
                entity_type="ROUTE",
                entity_id=int(route_id),
                record_key=str(route["code"]),
                after={"name": route_name, "step_count": len(prepared) if prepared else None},
            )
            connection.commit()

    def update_recipe(
        self,
        recipe_id: int,
        *,
        recipe_name: str,
        lines: Iterable[dict[str, object]] | None,
        username: str,
        production_length_mm: float = 0,
        saw_allowance_mm: float = 0,
        hanger_allowance_mm: float = 0,
        raw_material_stock_code: str = "",
    ) -> None:
        name = recipe_name.strip()
        if not name:
            raise ValueError("Reçete adı boş bırakılamaz.")
        prepared = list(lines) if lines is not None else None
        if prepared is not None and not prepared:
            raise ValueError("Reçetede en az bir operasyon satırı olmalıdır.")
        with closing(self.connect()) as connection:
            recipe = connection.execute(
                """
                SELECT * FROM recipes
                WHERE id = ? AND organization_id = ? AND active = 1
                """,
                (int(recipe_id), self.organization_id(connection)),
            ).fetchone()
            if recipe is None:
                raise ValueError("Reçete bulunamadı.")
            if prepared is not None and self._recipe_has_production(connection, int(recipe_id)):
                raise ValueError(
                    "Bu reçeteyi kullanan üretim emri olduğu için operasyon satırları "
                    "değiştirilemez. Yalnızca reçete adı ve pay bilgileri güncellenebilir."
                )
            raw_material_code = str(raw_material_stock_code or "").strip().upper()
            connection.execute(
                """
                UPDATE recipes
                SET recipe_name = ?, production_length_mm = ?,
                    saw_allowance_mm = ?, hanger_allowance_mm = ?,
                    raw_material_stock_external_id = ?
                WHERE id = ?
                """,
                (
                    name,
                    self._number(production_length_mm),
                    self._number(saw_allowance_mm),
                    self._number(hanger_allowance_mm),
                    raw_material_code or str(recipe["raw_material_stock_external_id"] or ""),
                    int(recipe_id),
                ),
            )
            if prepared is not None:
                code = str(recipe["recipe_code"])
                connection.execute(
                    "DELETE FROM recipe_lines WHERE recipe_id = ?",
                    (int(recipe_id),),
                )
                for sequence_no, values in enumerate(prepared, start=1):
                    operation = str(values.get("operation") or "").strip().upper()
                    station = str(values.get("station") or "").strip().upper()
                    if not operation or not station:
                        raise ValueError("Her reçete satırında operasyon ve istasyon olmalıdır.")
                    route_sequence_no = int(
                        self._number(values.get("route_sequence_no") or sequence_no)
                    )
                    numerator = self._number(values.get("numerator"))
                    denominator = self._number(values.get("denominator"))
                    if (numerator > 0) != (denominator > 0):
                        raise ValueError("Reçete oranında pay ve payda birlikte girilmelidir.")
                    self._ensure_operation_station(
                        connection, operation_name=operation, station_name=station
                    )
                    connection.execute(
                        """
                        INSERT INTO recipe_lines(
                            recipe_id, external_source, external_id, process_type,
                            sequence_no, route_sequence_no, quantity, main_quantity,
                            numerator, denominator, description, external_unit_weight,
                            external_kg, external_quantity, external_metre,
                            operation_name, station_name, stock_code, unit_code,
                            warehouse_code
                        ) VALUES (?, 'RIGEL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(recipe_id), f"{code}:{sequence_no}",
                            str(values.get("process_type") or operation).strip().upper(),
                            sequence_no, route_sequence_no,
                            self._number(values.get("quantity")),
                            self._number(values.get("main_quantity")),
                            numerator, denominator,
                            str(values.get("description") or "").strip(),
                            self._number(values.get("unit_weight")),
                            self._number(values.get("kg")),
                            self._number(values.get("external_quantity")),
                            self._number(values.get("metre")),
                            operation, station,
                            str(values.get("stock_code") or "").strip().upper(),
                            str(values.get("unit_code") or "").strip().upper(),
                            str(values.get("warehouse_code") or "").strip().upper(),
                        ),
                    )
            self._audit(
                connection,
                username=username,
                action="UPDATE",
                entity_type="RECIPE",
                entity_id=int(recipe_id),
                record_key=str(recipe["recipe_code"]),
                after={"line_count": len(prepared) if prepared else None},
            )
            connection.commit()

    def create_sales_order(
        self,
        customer_id: int,
        *,
        order_date: str,
        delivery_date: str,
        lines: Iterable[dict[str, object]],
        username: str,
        customer_document_no: str = "",
        msp: str = "",
        currency: str = "TRY",
        delivery_address_id: int | None = None,
        payment_method: str = "",
        maturity_days: int = 0,
        contact_name: str = "",
        representative: str = "",
        note: str = "",
        usd_rate: float = 0,
        eur_rate: float = 0,
        lme_usd_ton: float = 0,
        premium_usd_ton: float = 0,
        branch_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> int:
        prepared = list(lines)
        if not prepared:
            raise ValueError("Siparişte en az bir profil satırı olmalıdır.")
        with closing(self.connect()) as connection:
            if delivery_address_id is not None:
                valid_address = connection.execute(
                    """
                    SELECT 1 FROM customer_addresses
                    WHERE id = ? AND customer_id = ? AND organization_id = ? AND active = 1
                    """,
                    (
                        int(delivery_address_id), int(customer_id),
                        self.organization_id(connection),
                    ),
                ).fetchone()
                if valid_address is None:
                    raise ValueError("Seçilen teslim adresi bu müşteri kartına bağlı değil.")
            order_no = self._next_no(connection, "R")
            cursor = connection.execute(
                """
                INSERT INTO sales_orders(
                    organization_id, customer_id, order_no, customer_document_no,
                    msp, order_date, delivery_date, currency, delivery_address_id,
                    payment_method, maturity_days, contact_name, representative, note,
                    usd_rate, eur_rate, lme_usd_ton, premium_usd_ton,
                    branch_id, warehouse_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(customer_id),
                    order_no,
                    customer_document_no.strip(),
                    msp.strip(),
                    order_date,
                    delivery_date,
                    currency.strip().upper(),
                    int(delivery_address_id) if delivery_address_id is not None else None,
                    payment_method.strip(),
                    int(maturity_days),
                    contact_name.strip(),
                    representative.strip(),
                    note.strip(),
                    self._number(usd_rate),
                    self._number(eur_rate),
                    self._number(lme_usd_ton),
                    self._number(premium_usd_ton),
                    int(branch_id) if branch_id is not None else None,
                    int(warehouse_id) if warehouse_id is not None else None,
                    username,
                ),
            )
            order_id = int(cursor.lastrowid)
            self._insert_sales_order_lines(connection, order_id, prepared)
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="SALES_ORDER",
                entity_id=order_id,
                record_key=order_no,
                after={"line_count": len(prepared)},
            )
            connection.commit()
            return order_id

    def _assert_sales_order_editable(
        self, connection: sqlite3.Connection, order_id: int
    ) -> sqlite3.Row:
        order = connection.execute(
            "SELECT * FROM sales_orders WHERE id = ?",
            (int(order_id),),
        ).fetchone()
        if order is None:
            raise ValueError("Satış siparişi bulunamadı.")
        if str(order["status"] or "").upper() in {"KAPALI", "İPTAL"}:
            raise ValueError("Kapalı veya iptal sipariş değiştirilemez.")
        if str(order["production_approval"] or "").upper() == "ONAYLANDI":
            raise ValueError("Üretime onaylanmış sipariş değiştirilemez.")
        produced = connection.execute(
            """
            SELECT COALESCE(SUM(produced_kg), 0) AS total
            FROM sales_order_lines WHERE sales_order_id = ?
            """,
            (int(order_id),),
        ).fetchone()
        if float(produced["total"] or 0) > 0:
            raise ValueError("Üretim başlamış sipariş değiştirilemez.")
        planned = connection.execute(
            """
            SELECT 1
            FROM production_orders po
            JOIN sales_order_lines l ON l.id = po.sales_order_line_id
            WHERE l.sales_order_id = ?
            LIMIT 1
            """,
            (int(order_id),),
        ).fetchone()
        if planned is not None:
            raise ValueError("Planlanmış üretim emri olan sipariş değiştirilemez.")
        return order

    def _insert_sales_order_lines(
        self,
        connection: sqlite3.Connection,
        order_id: int,
        lines: Iterable[dict[str, object]],
    ) -> None:
        for line_no, values in enumerate(lines, start=1):
            profile_id = int(values["profile_id"])
            profile = connection.execute(
                "SELECT alloy, temper FROM profiles WHERE id = ? AND active = 1",
                (profile_id,),
            ).fetchone()
            if profile is None:
                raise ValueError("Sipariş satırındaki profil kartı bulunamadı.")
            quantity = self._number(values.get("quantity"))
            kg = self._number(values.get("kg"))
            if quantity <= 0 and kg <= 0:
                raise ValueError("Sipariş adedi veya kilogramı sıfırdan büyük olmalıdır.")
            if self._number(values.get("length_mm")) <= 0:
                raise ValueError("Sipariş profil boyu sıfırdan büyük olmalıdır.")
            connection.execute(
                """
                INSERT INTO sales_order_lines(
                    sales_order_id, line_no, profile_id, die_id,
                    stock_length_mm, production_length_mm, surface, color,
                    alloy, temper, mechanical, ordered_quantity, ordered_kg,
                    unit_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(order_id),
                    line_no,
                    profile_id,
                    values.get("die_id"),
                    int(self._number(values.get("length_mm"))),
                    int(self._number(values.get("production_length_mm") or values.get("length_mm"))),
                    str(values.get("surface") or "PRES").strip().upper(),
                    str(values.get("color") or "*").strip().upper(),
                    str(values.get("alloy") or profile["alloy"]).strip().upper(),
                    str(values.get("temper") or profile["temper"]).strip().upper(),
                    str(values.get("mechanical") or "").strip().upper(),
                    quantity,
                    kg,
                    self._number(values.get("unit_price")),
                ),
            )

    def update_sales_order(
        self,
        order_id: int,
        customer_id: int,
        *,
        order_date: str,
        delivery_date: str,
        lines: Iterable[dict[str, object]],
        username: str,
        customer_document_no: str = "",
        msp: str = "",
        currency: str = "TRY",
        delivery_address_id: int | None = None,
        payment_method: str = "",
        maturity_days: int = 0,
        contact_name: str = "",
        representative: str = "",
        note: str = "",
        usd_rate: float = 0,
        eur_rate: float = 0,
        lme_usd_ton: float = 0,
        premium_usd_ton: float = 0,
        branch_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> None:
        prepared = list(lines)
        if not prepared:
            raise ValueError("Siparişte en az bir profil satırı olmalıdır.")
        with closing(self.connect()) as connection:
            order = self._assert_sales_order_editable(connection, int(order_id))
            if delivery_address_id is not None:
                valid_address = connection.execute(
                    """
                    SELECT 1 FROM customer_addresses
                    WHERE id = ? AND customer_id = ? AND organization_id = ? AND active = 1
                    """,
                    (
                        int(delivery_address_id), int(customer_id),
                        self.organization_id(connection),
                    ),
                ).fetchone()
                if valid_address is None:
                    raise ValueError("Seçilen teslim adresi bu müşteri kartına bağlı değil.")
            connection.execute(
                """
                UPDATE sales_orders
                SET customer_id = ?, customer_document_no = ?, msp = ?,
                    order_date = ?, delivery_date = ?, currency = ?,
                    delivery_address_id = ?, payment_method = ?, maturity_days = ?,
                    contact_name = ?, representative = ?, note = ?,
                    usd_rate = ?, eur_rate = ?, lme_usd_ton = ?, premium_usd_ton = ?,
                    branch_id = ?, warehouse_id = ?,
                    updated_at = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (
                    int(customer_id),
                    customer_document_no.strip(),
                    msp.strip(),
                    order_date,
                    delivery_date,
                    currency.strip().upper(),
                    int(delivery_address_id) if delivery_address_id is not None else None,
                    payment_method.strip(),
                    int(maturity_days),
                    contact_name.strip(),
                    representative.strip(),
                    note.strip(),
                    self._number(usd_rate),
                    self._number(eur_rate),
                    self._number(lme_usd_ton),
                    self._number(premium_usd_ton),
                    int(branch_id) if branch_id is not None else None,
                    int(warehouse_id) if warehouse_id is not None else None,
                    self._now(),
                    int(order_id),
                ),
            )
            connection.execute(
                "DELETE FROM sales_order_lines WHERE sales_order_id = ?",
                (int(order_id),),
            )
            self._insert_sales_order_lines(connection, int(order_id), prepared)
            self._audit(
                connection,
                username=username,
                action="UPDATE",
                entity_type="SALES_ORDER",
                entity_id=int(order_id),
                record_key=str(order["order_no"]),
                after={"line_count": len(prepared)},
            )
            connection.commit()

    def delete_sales_order(self, order_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            order = self._assert_sales_order_editable(connection, int(order_id))
            shipped = connection.execute(
                """
                SELECT COALESCE(SUM(shipped_kg), 0) AS total
                FROM sales_order_lines WHERE sales_order_id = ?
                """,
                (int(order_id),),
            ).fetchone()
            if float(shipped["total"] or 0) > 0:
                raise ValueError("Sevk edilmiş sipariş silinemez.")
            connection.execute(
                "DELETE FROM sales_order_lines WHERE sales_order_id = ?",
                (int(order_id),),
            )
            connection.execute(
                "DELETE FROM sales_orders WHERE id = ?",
                (int(order_id),),
            )
            self._audit(
                connection,
                username=username,
                action="DELETE",
                entity_type="SALES_ORDER",
                entity_id=int(order_id),
                record_key=str(order["order_no"]),
            )
            connection.commit()

    def copy_sales_order(self, order_id: int, *, username: str) -> int:
        progress = self.order_progress(int(order_id))
        order = progress["order"]
        line_payloads: list[dict[str, object]] = []
        for row in progress["lines"]:
            line_payloads.append(
                {
                    "profile_id": int(row["profile_id"]),
                    "die_id": row.get("die_id"),
                    "length_mm": int(row["stock_length_mm"]),
                    "production_length_mm": int(row["production_length_mm"]),
                    "surface": row["surface"],
                    "color": row.get("color") or "*",
                    "alloy": row.get("alloy"),
                    "temper": row.get("temper"),
                    "mechanical": row.get("mechanical") or "",
                    "quantity": float(row["ordered_quantity"]),
                    "kg": float(row["ordered_kg"]),
                    "unit_price": float(row["unit_price"]),
                }
            )
        return self.create_sales_order(
            int(order["customer_id"]),
            order_date=str(order["order_date"]),
            delivery_date=str(order["delivery_date"]),
            lines=line_payloads,
            username=username,
            customer_document_no=str(order.get("customer_document_no") or ""),
            msp=str(order.get("msp") or ""),
            currency=str(order.get("currency") or "TRY"),
            delivery_address_id=order.get("delivery_address_id"),
            payment_method=str(order.get("payment_method") or ""),
            maturity_days=int(order.get("maturity_days") or 0),
            contact_name=str(order.get("contact_name") or ""),
            representative=str(order.get("representative") or ""),
            note=str(order.get("note") or ""),
            usd_rate=float(order.get("usd_rate") or 0),
            eur_rate=float(order.get("eur_rate") or 0),
            lme_usd_ton=float(order.get("lme_usd_ton") or 0),
            premium_usd_ton=float(order.get("premium_usd_ton") or 0),
            branch_id=order.get("branch_id"),
            warehouse_id=order.get("warehouse_id"),
        )

    def confirm_sales_order(self, order_id: int, *, username: str) -> None:
        """Sipariş Onay: ticari onay, üretim onayından ayrı."""
        with closing(self.connect()) as connection:
            order = connection.execute(
                "SELECT * FROM sales_orders WHERE id = ?",
                (int(order_id),),
            ).fetchone()
            if order is None:
                raise ValueError("Satış siparişi bulunamadı.")
            status = str(order["status"] or "").upper()
            if status in {"KAPALI", "İPTAL"}:
                raise ValueError("Kapalı veya iptal sipariş onaylanamaz.")
            if status not in {"ONAY BEKLİYOR", "TASLAK"}:
                raise ValueError("Sipariş zaten onaylı.")
            line_count = connection.execute(
                "SELECT COUNT(*) AS total FROM sales_order_lines WHERE sales_order_id = ?",
                (int(order_id),),
            ).fetchone()
            if int(line_count["total"] or 0) <= 0:
                raise ValueError("Satırı olmayan sipariş onaylanamaz.")
            connection.execute(
                """
                UPDATE sales_orders
                SET status = 'AÇIK', updated_at = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (self._now(), int(order_id)),
            )
            self._audit(
                connection,
                username=username,
                action="CONFIRM",
                entity_type="SALES_ORDER",
                entity_id=int(order_id),
                record_key=str(order["order_no"]),
            )
            connection.commit()

    def close_sales_order(self, order_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            order = connection.execute(
                "SELECT * FROM sales_orders WHERE id = ?",
                (int(order_id),),
            ).fetchone()
            if order is None:
                raise ValueError("Satış siparişi bulunamadı.")
            if str(order["status"] or "").upper() in {"KAPALI", "İPTAL"}:
                raise ValueError("Sipariş zaten kapalı.")
            connection.execute(
                """
                UPDATE sales_order_lines
                SET status = 'KAPALI', row_version = row_version + 1
                WHERE sales_order_id = ? AND status NOT IN ('SEVK EDİLDİ', 'İPTAL', 'KAPALI')
                """,
                (int(order_id),),
            )
            connection.execute(
                """
                UPDATE sales_orders
                SET status = 'KAPALI', updated_at = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (self._now(), int(order_id)),
            )
            self._audit(
                connection,
                username=username,
                action="CLOSE",
                entity_type="SALES_ORDER",
                entity_id=int(order_id),
                record_key=str(order["order_no"]),
            )
            connection.commit()

    @staticmethod
    def _route_score(route: sqlite3.Row, line: sqlite3.Row) -> int | None:
        score = 0
        checks = (
            ("production_length_mm", int(line["production_length_mm"] or 0), 20),
            ("surface", str(line["surface"] or "").strip().upper(), 10),
            ("color", str(line["color"] or "").strip().upper(), 5),
            ("alloy", str(line["alloy"] or "").strip().upper(), 8),
            ("temper", str(line["temper"] or "").strip().upper(), 8),
            ("mechanical", str(line["mechanical"] or "").strip().upper(), 3),
        )
        for key, line_value, weight in checks:
            route_value = route[key]
            if key == "production_length_mm":
                route_value = int(route_value or 0)
                if route_value and line_value and route_value != line_value:
                    return None
            else:
                route_value = str(route_value or "").strip().upper()
                if route_value not in {"", "*"} and line_value not in {"", "*"}:
                    if route_value != line_value:
                        return None
            if route_value not in {"", "*", 0} and route_value == line_value:
                score += weight
        return score

    @staticmethod
    def _line_value_for_route_property(line: sqlite3.Row, property_external_id: str) -> str:
        token = str(property_external_id or "").strip().upper()
        mapping = {
            "YUZEY": "surface",
            "OZ-YUZEY": "surface",
            "SURFACE": "surface",
            "RENK": "color",
            "OZ-RENK": "color",
            "COLOR": "color",
            "ALASIM": "alloy",
            "ALLOY": "alloy",
            "SERTLIK": "temper",
            "TEMPER": "temper",
            "MEKANIK": "mechanical",
            "MECHANICAL": "mechanical",
            "BOY": "production_length_mm",
            "UBOY": "production_length_mm",
            "PRODUCTION_LENGTH_MM": "production_length_mm",
        }
        field = mapping.get(token)
        if field is None:
            for suffix, mapped in mapping.items():
                if token.endswith(suffix):
                    field = mapped
                    break
        if field is None:
            return ""
        if field == "production_length_mm":
            return str(int(line["production_length_mm"] or 0))
        return str(line[field] or "").strip().upper()

    @staticmethod
    def _route_condition_value_matches(
        actual: str, operator: str, expected: str,
    ) -> bool:
        left = str(actual or "").strip().upper()
        right = str(expected or "").strip().upper()
        op = str(operator or "=").strip().upper()
        if op in {"=", "==", "EQ"}:
            return left == right
        if op in {"<>", "!=", "NE"}:
            return left != right
        if op in {">", "GT"}:
            try:
                return float(left) > float(right)
            except ValueError:
                return left > right
        if op in {"<", "LT"}:
            try:
                return float(left) < float(right)
            except ValueError:
                return left < right
        if op in {">=", "GE"}:
            try:
                return float(left) >= float(right)
            except ValueError:
                return left >= right
        if op in {"<=", "LE"}:
            try:
                return float(left) <= float(right)
            except ValueError:
                return left <= right
        return left == right

    def _route_ids_from_active_conditions(
        self,
        connection: sqlite3.Connection,
        organization_id: int,
        profile_id: int,
        line: sqlite3.Row,
    ) -> set[int]:
        conditions = connection.execute(
            """
            SELECT rc.id, rc.priority
            FROM route_conditions rc
            JOIN route_condition_routes rcr ON rcr.route_condition_id = rc.id
            JOIN routes r ON r.id = rcr.route_id
            WHERE rc.organization_id = ? AND rc.active = 1
              AND r.profile_id = ? AND r.active = 1
            GROUP BY rc.id
            ORDER BY rc.priority DESC, rc.id DESC
            """,
            (organization_id, int(profile_id)),
        ).fetchall()
        if not conditions:
            return set()
        matched_route_ids: set[int] = set()
        for condition in conditions:
            values = connection.execute(
                """
                SELECT property_external_id, operator, value_text
                FROM route_condition_values
                WHERE route_condition_id = ?
                ORDER BY id
                """,
                (int(condition["id"]),),
            ).fetchall()
            if values and not all(
                self._route_condition_value_matches(
                    self._line_value_for_route_property(
                        line, str(row["property_external_id"]),
                    ),
                    str(row["operator"]),
                    str(row["value_text"]),
                )
                for row in values
            ):
                continue
            route_rows = connection.execute(
                """
                SELECT route_id
                FROM route_condition_routes
                WHERE route_condition_id = ? AND route_id IS NOT NULL
                ORDER BY sequence_no, id
                """,
                (int(condition["id"]),),
            ).fetchall()
            matched_route_ids.update(int(row["route_id"]) for row in route_rows)
        return matched_route_ids

    def _eligible_routes_for_line(
        self,
        connection: sqlite3.Connection,
        organization_id: int,
        line: sqlite3.Row,
        *,
        route_id: int | None = None,
    ) -> list[tuple[int, sqlite3.Row, sqlite3.Row | None]]:
        query = """
            SELECT * FROM routes
            WHERE organization_id = ? AND profile_id = ? AND active = 1
        """
        params: list[object] = [organization_id, int(line["profile_id"])]
        if route_id is not None:
            query += " AND id = ?"
            params.append(int(route_id))
        candidates = connection.execute(query + " ORDER BY id DESC", params).fetchall()
        condition_route_ids = self._route_ids_from_active_conditions(
            connection, organization_id, int(line["profile_id"]), line,
        )
        if condition_route_ids:
            candidates = [
                route for route in candidates
                if int(route["id"]) in condition_route_ids
            ]
        scored: list[tuple[int, sqlite3.Row, sqlite3.Row | None]] = []
        for route in candidates:
            score = self._route_score(route, line)
            if score is None:
                continue
            recipe = self._select_recipe_for_route(
                connection, organization_id, route, line,
            )
            scored.append((score, route, recipe))
        scored.sort(key=lambda item: (-item[0], -int(item[1]["id"])))
        return scored

    def list_eligible_routes_for_line(self, sales_order_line_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            line = connection.execute(
                "SELECT * FROM sales_order_lines WHERE id = ?",
                (int(sales_order_line_id),),
            ).fetchone()
            if line is None:
                raise ValueError("Sipariş satırı bulunamadı.")
            order = connection.execute(
                "SELECT organization_id FROM sales_orders WHERE id = ?",
                (int(line["sales_order_id"]),),
            ).fetchone()
            if order is None:
                raise ValueError("Sipariş başlığı bulunamadı.")
            eligible = self._eligible_routes_for_line(
                connection,
                int(order["organization_id"]),
                line,
            )
        return [
            {
                "id": int(route["id"]),
                "code": route["code"],
                "name": route["name"],
                "score": score,
                "surface": route["surface"],
                "production_length_mm": route["production_length_mm"],
                "recipe_id": int(recipe["id"]) if recipe is not None else None,
                "recipe_code": str(recipe["code"]) if recipe is not None else "",
                "recipe_name": str(recipe["name"]) if recipe is not None else "",
                "raw_material_code": (
                    str(recipe["raw_material_stock_external_id"] or "").strip().upper()
                    if recipe is not None
                    else ""
                ),
            }
            for score, route, recipe in eligible
        ]

    def _select_route_for_line(
        self,
        connection: sqlite3.Connection,
        organization_id: int,
        line: sqlite3.Row,
        route_id: int | None = None,
    ) -> sqlite3.Row | None:
        eligible = self._eligible_routes_for_line(
            connection, organization_id, line, route_id=route_id,
        )
        if not eligible:
            return None
        return eligible[0][1]

    @staticmethod
    def _recipe_line_factor(recipe_line: sqlite3.Row | None) -> float:
        if recipe_line is None:
            return 1.0
        numerator = float(recipe_line["numerator"] or 0)
        denominator = float(recipe_line["denominator"] or 0)
        if numerator > 0 and denominator > 0:
            return numerator / denominator
        quantity = float(recipe_line["quantity"] or 0)
        main_quantity = float(recipe_line["main_quantity"] or 0)
        if quantity > 0 and main_quantity > 0:
            return quantity / main_quantity
        return 1.0

    @staticmethod
    def _normalize_unit_code(unit: object) -> str:
        token = str(unit or "").strip().upper()
        aliases = {
            "KG": "KG",
            "KILOGRAM": "KG",
            "ADET": "ADET",
            "ADT": "ADET",
            "PCS": "ADET",
            "METRE": "METRE",
            "M": "METRE",
            "MT": "METRE",
            "TON": "TON",
        }
        return aliases.get(token, token or "KG")

    def _production_base_quantities(
        self,
        *,
        quantity: float,
        kg: float,
        metre: float,
        profile: sqlite3.Row | None,
        line: sqlite3.Row | None,
    ) -> dict[str, float]:
        qty = self._number(quantity)
        net_kg = self._number(kg)
        net_metre = self._number(metre)
        length_mm = float(line["production_length_mm"] or 0) if line is not None else 0.0
        unit_weight = float(profile["unit_weight_kg_m"] or 0) if profile is not None else 0.0
        if net_metre <= 0 and qty > 0 and length_mm > 0:
            net_metre = qty * length_mm / 1000.0
        if net_kg <= 0 and net_metre > 0 and unit_weight > 0:
            net_kg = net_metre * unit_weight
        if qty <= 0 and net_kg > 0 and length_mm > 0 and unit_weight > 0:
            qty = net_kg / (length_mm / 1000.0 * unit_weight)
        return {
            "KG": net_kg,
            "ADET": qty,
            "METRE": net_metre,
            "TON": net_kg / 1000.0 if net_kg > 0 else 0.0,
        }

    def _quantity_in_unit(
        self,
        bases: dict[str, float],
        unit: object,
        *,
        unit_set_id: int | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> float:
        target = self._normalize_unit_code(unit)
        if target in bases:
            return self._number(bases[target])
        if unit_set_id is not None and connection is not None:
            row = connection.execute(
                """
                SELECT us.base_unit, usl.factor
                FROM unit_set_lines usl
                JOIN unit_sets us ON us.id = usl.unit_set_id
                WHERE usl.unit_set_id = ? AND UPPER(usl.unit_code) = ?
                """,
                (int(unit_set_id), target),
            ).fetchone()
            if row is not None:
                base_unit = self._normalize_unit_code(row["base_unit"])
                base_qty = self._number(bases.get(base_unit, 0))
                return base_qty * float(row["factor"] or 1)
        return self._number(bases.get("KG", 0))

    def _resolve_stock_item_for_recipe_line(
        self,
        connection: sqlite3.Connection,
        organization_id: int,
        recipe_line: sqlite3.Row | None,
        profile: sqlite3.Row | None,
        *,
        for_output: bool,
    ) -> sqlite3.Row | None:
        if recipe_line is not None:
            stock_code = str(recipe_line["stock_code"] or "").strip().upper()
            if stock_code:
                row = connection.execute(
                    """
                    SELECT * FROM stock_items
                    WHERE organization_id = ? AND UPPER(code) = ? AND active = 1
                    """,
                    (organization_id, stock_code),
                ).fetchone()
                if row is not None:
                    return row
        if for_output and profile is not None:
            return connection.execute(
                "SELECT * FROM stock_items WHERE profile_id = ? AND active = 1",
                (int(profile["id"]),),
            ).fetchone()
        return None

    def create_unit_set(
        self,
        code: str,
        name: str,
        *,
        base_unit: str = "KG",
        lines: Iterable[dict[str, object]] | None = None,
        username: str,
    ) -> int:
        normalized_code = code.strip().upper()
        if not normalized_code:
            raise ValueError("Birim seti kodu boş bırakılamaz.")
        prepared = list(lines or [])
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            cursor = connection.execute(
                """
                INSERT INTO unit_sets(
                    organization_id, code, name, base_unit, active
                ) VALUES (?, ?, ?, ?, 1)
                """,
                (
                    organization_id,
                    normalized_code,
                    name.strip(),
                    self._normalize_unit_code(base_unit),
                ),
            )
            unit_set_id = int(cursor.lastrowid)
            for values in prepared:
                unit_code = self._normalize_unit_code(values.get("unit_code"))
                factor = self._number(values.get("factor"))
                if factor <= 0:
                    raise ValueError(f"{unit_code} birimi için çarpan sıfırdan büyük olmalıdır.")
                connection.execute(
                    """
                    INSERT INTO unit_set_lines(
                        unit_set_id, unit_code, factor, description
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        unit_set_id,
                        unit_code,
                        factor,
                        str(values.get("description") or "").strip(),
                    ),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="UNIT_SET",
                entity_id=unit_set_id,
                record_key=normalized_code,
                after={"line_count": len(prepared)},
            )
            connection.commit()
            return unit_set_id

    def list_unit_sets(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT us.id, us.code, us.name, us.base_unit, us.active,
                       COUNT(usl.id) AS line_count
                FROM unit_sets us
                LEFT JOIN unit_set_lines usl ON usl.unit_set_id = us.id
                WHERE us.organization_id = ?
                GROUP BY us.id, us.code, us.name, us.base_unit, us.active
                ORDER BY us.code
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_unit_set_lines(self, unit_set_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, unit_code, factor, description
                FROM unit_set_lines
                WHERE unit_set_id = ?
                ORDER BY unit_code
                """,
                (int(unit_set_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _select_recipe_for_route(
        self,
        connection: sqlite3.Connection,
        organization_id: int,
        route: sqlite3.Row,
        line: sqlite3.Row,
    ) -> sqlite3.Row | None:
        rows = connection.execute(
            """
            SELECT * FROM recipes
            WHERE organization_id = ? AND profile_id = ? AND active = 1
              AND (route_id = ? OR route_id IS NULL)
            ORDER BY CASE WHEN route_id = ? THEN 0 ELSE 1 END, id DESC
            """,
            (
                organization_id,
                int(line["profile_id"]),
                int(route["id"]),
                int(route["id"]),
            ),
        ).fetchall()
        production_length = float(line["production_length_mm"] or 0)
        for row in rows:
            recipe_length = float(row["production_length_mm"] or 0)
            if recipe_length <= 0 or production_length <= 0:
                return row
            if abs(recipe_length - production_length) < 0.001:
                return row
        return None

    @staticmethod
    def _recipe_line_for_step(
        recipe_lines: list[sqlite3.Row], sequence_no: int,
    ) -> sqlite3.Row | None:
        exact = [
            row for row in recipe_lines
            if int(row["route_sequence_no"] or 0) == sequence_no
        ]
        if exact:
            return sorted(exact, key=lambda row: (int(row["sequence_no"] or 0), int(row["id"])))[0]
        fallback = [
            row for row in recipe_lines
            if int(row["sequence_no"] or 0) == sequence_no
        ]
        return fallback[0] if fallback else None

    def _validate_die_station_compatibility(
        self,
        connection: sqlite3.Connection,
        line: sqlite3.Row,
        first_step: sqlite3.Row,
    ) -> None:
        die_id = line["die_id"]
        if die_id is None:
            return
        compatibility_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM die_station_compatibility WHERE die_id = ?",
                (int(die_id),),
            ).fetchone()[0]
        )
        station_name = str(first_step["default_station"] or "").strip().upper()
        if compatibility_count == 0 and station_name:
            station_id = self._ensure_operation_station(
                connection,
                operation_name=str(first_step["operation"] or "PRES ÜRETİM"),
                station_name=station_name,
            )
            connection.execute(
                """
                INSERT INTO die_station_compatibility(
                    die_id, station_id, station_external_id,
                    external_source, external_id, active
                ) VALUES (?, ?, ?, 'RIGEL', ?, 1)
                ON CONFLICT(die_id, station_external_id) DO UPDATE SET active = 1
                """,
                (int(die_id), station_id, station_name, f"{die_id}:{station_name}"),
            )
            compatibility_count = 1
        if compatibility_count == 0:
            return
        compatible = connection.execute(
            """
            SELECT 1
            FROM die_station_compatibility dsc
            LEFT JOIN stations s ON s.id = dsc.station_id
            WHERE dsc.die_id = ? AND dsc.active = 1
              AND (
                    UPPER(COALESCE(s.code, '')) = ?
                 OR UPPER(COALESCE(s.name, '')) = ?
                 OR UPPER(COALESCE(dsc.station_external_id, '')) = ?
              )
            LIMIT 1
            """,
            (int(die_id), station_name, station_name, station_name),
        ).fetchone()
        if compatible is None:
            die = connection.execute(
                "SELECT die_code, spare_no FROM dies WHERE id = ?",
                (int(die_id),),
            ).fetchone()
            die_label = (
                f"{die['die_code']}/{die['spare_no']}" if die is not None else str(die_id)
            )
            raise ValueError(
                f"{die_label} kalıbı {station_name} istasyonunda çalışmaya tanımlı değil. "
                "Kalıp–istasyon uyumluluk kartını kontrol edin."
            )

    def _plan_sales_order_line(
        self,
        connection: sqlite3.Connection,
        line: sqlite3.Row,
        *,
        planned_quantity: float,
        planned_kg: float,
        route_id: int | None,
        planned_start: str | None,
        username: str,
    ) -> int:
        order = connection.execute(
            "SELECT * FROM sales_orders WHERE id = ?",
            (int(line["sales_order_id"]),),
        ).fetchone()
        if order is None:
            raise ValueError("Sipariş başlığı bulunamadı.")
        organization_id = int(order["organization_id"])
        allocated = connection.execute(
            """
            SELECT COALESCE(SUM(planned_quantity), 0) AS quantity,
                   COALESCE(SUM(planned_kg), 0) AS kg
            FROM production_orders
            WHERE sales_order_line_id = ? AND status <> 'İPTAL'
            """,
            (int(line["id"]),),
        ).fetchone()
        remaining_quantity = max(
            0.0, float(line["ordered_quantity"] or 0) - float(allocated["quantity"] or 0)
        )
        remaining_kg = max(
            0.0, float(line["ordered_kg"] or 0) - float(allocated["kg"] or 0)
        )
        quantity = self._number(planned_quantity)
        kg = self._number(planned_kg)
        if quantity <= 0 and kg <= 0:
            raise ValueError("Plan adedi veya kilogramı sıfırdan büyük olmalıdır.")
        if remaining_quantity > 0 and quantity > remaining_quantity + 0.001:
            raise ValueError(
                f"Plan adedi kalan {remaining_quantity:.3f} adet miktarı aşamaz."
            )
        if remaining_kg > 0 and kg > remaining_kg + 0.001:
            raise ValueError(f"Plan kilogramı kalan {remaining_kg:.3f} kg miktarı aşamaz.")
        route = self._select_route_for_line(connection, organization_id, line, route_id)
        if route is None:
            raise ValueError(
                f"{line['line_no']}. sipariş satırının profil/boy/yüzey/alaşım/"
                "sertlik bilgilerine uygun aktif reçete/rota yok."
            )
        if route_id is not None and int(route["id"]) != int(route_id):
            raise ValueError(
                "Seçilen rota sipariş satırının boy, yüzey ve koşul bilgileriyle "
                "uyumlu değil."
            )
        steps = connection.execute(
            "SELECT * FROM route_steps WHERE route_id = ? ORDER BY sequence_no",
            (int(route["id"]),),
        ).fetchall()
        if not steps:
            raise ValueError("Seçilen üretim rotasının operasyon adımı yok.")
        self._validate_die_station_compatibility(connection, line, steps[0])
        recipe = self._select_recipe_for_route(connection, organization_id, route, line)
        if recipe is None:
            raise ValueError(
                f"{line['line_no']}. satır için {route['code']} rotasına bağlı "
                "uygun aktif reçete bulunamadı. Üretim → Reçeteler ekranından "
                "reçeteyi tanımlayın."
            )
        recipe_lines = connection.execute(
            "SELECT * FROM recipe_lines WHERE recipe_id = ? ORDER BY route_sequence_no, sequence_no, id",
            (int(recipe["id"]),),
        ).fetchall()
        batch_no = int(
            connection.execute(
                "SELECT COALESCE(MAX(batch_no), 0) + 1 FROM production_orders WHERE sales_order_line_id = ?",
                (int(line["id"]),),
            ).fetchone()[0]
        )
        production_no = self._next_no(connection, "UE")
        cursor = connection.execute(
            """
            INSERT INTO production_orders(
                organization_id, sales_order_line_id, route_id, recipe_id,
                batch_no, production_order_no, planned_quantity, planned_kg,
                planned_start, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                int(line["id"]),
                int(route["id"]),
                int(recipe["id"]),
                batch_no,
                production_no,
                quantity,
                kg,
                planned_start or None,
                username,
            ),
        )
        production_id = int(cursor.lastrowid)
        length_mm = float(line["production_length_mm"] or 0)
        for step in steps:
            sequence_no = int(step["sequence_no"])
            recipe_line = self._recipe_line_for_step(recipe_lines, sequence_no)
            factor = self._recipe_line_factor(recipe_line)
            work_no = self._next_no(connection, "IE")
            connection.execute(
                """
                INSERT INTO work_orders(
                    production_order_id, route_step_id, recipe_line_id,
                    work_order_no, sequence_no, operation, station,
                    planned_quantity, planned_kg, planned_metre,
                    quantity_factor, status, production_length_mm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    production_id,
                    int(step["id"]),
                    int(recipe_line["id"]) if recipe_line is not None else None,
                    work_no,
                    sequence_no,
                    str(step["operation"]),
                    str(step["default_station"]),
                    quantity * factor,
                    kg * factor,
                    quantity * (length_mm / 1000.0) * factor,
                    factor,
                    "HAZIR" if sequence_no == int(steps[0]["sequence_no"]) else "BEKLİYOR",
                    max(0.0, length_mm),
                ),
            )
        connection.execute(
            """
            UPDATE sales_order_lines
            SET status = 'ÜRETİMDE', row_version = row_version + 1
            WHERE id = ?
            """,
            (int(line["id"]),),
        )
        self._audit(
            connection,
            username=username,
            action="PLAN",
            entity_type="PRODUCTION_ORDER",
            entity_id=production_id,
            record_key=production_no,
            after={
                "sales_order_line_id": int(line["id"]),
                "route_id": int(route["id"]),
                "recipe_id": int(recipe["id"]),
                "batch_no": batch_no,
                "planned_quantity": quantity,
                "planned_kg": kg,
            },
        )
        return production_id

    def plan_sales_order_line(
        self,
        sales_order_line_id: int,
        *,
        planned_quantity: float,
        planned_kg: float,
        username: str,
        route_id: int | None = None,
        planned_start: str | None = None,
    ) -> int:
        with closing(self.connect()) as connection:
            line = connection.execute(
                "SELECT * FROM sales_order_lines WHERE id = ?",
                (int(sales_order_line_id),),
            ).fetchone()
            if line is None:
                raise ValueError("Sipariş satırı bulunamadı.")
            production_id = self._plan_sales_order_line(
                connection,
                line,
                planned_quantity=planned_quantity,
                planned_kg=planned_kg,
                route_id=route_id,
                planned_start=planned_start,
                username=username,
            )
            connection.execute(
                """
                UPDATE sales_orders
                SET production_approval = 'ONAYLANDI', status = 'ÜRETİMDE',
                    updated_at = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (self._now(), int(line["sales_order_id"])),
            )
            recalculate_order_line_status(
                connection, sales_order_line_id=int(line["id"])
            )
            connection.commit()
            return production_id

    def approve_sales_order(self, order_id: int, *, username: str) -> list[int]:
        """Üretim onayı planlama adımından ayrıdır."""
        approved_line_ids: list[int] = []
        with closing(self.connect()) as connection:
            order = connection.execute(
                "SELECT * FROM sales_orders WHERE id = ?",
                (int(order_id),),
            ).fetchone()
            if order is None:
                raise ValueError("Satış siparişi bulunamadı.")
            lines = connection.execute(
                "SELECT * FROM sales_order_lines WHERE sales_order_id = ? ORDER BY line_no",
                (int(order_id),),
            ).fetchall()
            if not lines:
                raise ValueError("Üretime onaylanacak sipariş satırı bulunmuyor.")
            for line in lines:
                if str(line["status"] or "").upper() in {"İPTAL", "SEVK EDİLDİ", "KAPALI"}:
                    continue
                connection.execute(
                    """
                    UPDATE sales_order_lines
                    SET status = 'ONAYLANDI', row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (int(line["id"]),),
                )
                approved_line_ids.append(int(line["id"]))
            connection.execute(
                """
                UPDATE sales_orders
                SET production_approval = 'ONAYLANDI',
                    status = CASE
                        WHEN status IN ('TASLAK', 'AÇIK') THEN 'ONAYLANDI'
                        ELSE status
                    END,
                    updated_at = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (self._now(), int(order_id)),
            )
            self._audit(
                connection,
                username=username,
                action="APPROVE",
                entity_type="SALES_ORDER",
                entity_id=int(order_id),
                record_key=str(order["order_no"]),
                after={"approved_line_ids": approved_line_ids},
            )
            connection.commit()
        return approved_line_ids

    def work_orders_for_production(self, production_order_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM work_orders WHERE production_order_id = ? ORDER BY sequence_no",
                (int(production_order_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _validate_press_slip_lines(
        self,
        *,
        gross: float,
        net: float,
        quantity: float,
        billets: Sequence[dict[str, Any]],
        baskets: Sequence[dict[str, Any]],
        scraps: Sequence[dict[str, Any]],
    ) -> None:
        """Fişin kendi içinde tutarlı olmasını zorunlu kılar.

        Brüt billetten, net sepetten gelir; fire ikisinin farkıdır ve hurda
        kırılımıyla birebir örtüşmelidir. Aksi hâlde fire kaçağı görünmez olur.
        """
        billet_gross = sum(self._number(row.get("gross_kg")) for row in billets)
        if abs(billet_gross - gross) > max(0.05, gross * 0.001):
            raise ValueError(
                "Billet brüt kilogram toplamı fiş brüt değerine eşit olmalıdır. "
                f"Billet toplamı {billet_gross:.2f}, fiş brütü {gross:.2f}."
            )
        if baskets:
            basket_kg = sum(self._number(row.get("net_kg")) for row in baskets)
            basket_qty = sum(self._number(row.get("quantity")) for row in baskets)
            if abs(basket_kg - net) > max(0.05, net * 0.001):
                raise ValueError(
                    "Sepet net kilogram toplamı fiş net değerine eşit olmalıdır. "
                    f"Sepet toplamı {basket_kg:.2f}, fiş neti {net:.2f}."
                )
            if abs(basket_qty - quantity) > 0.5:
                raise ValueError(
                    "Sepet adet toplamı net adede eşit olmalıdır. "
                    f"Sepet toplamı {basket_qty:.0f}, net adet {quantity:.0f}."
                )
        if scraps:
            scrap_kg = sum(self._number(row.get("kg")) for row in scraps)
            expected = max(0.0, gross - net)
            if abs(scrap_kg - expected) > max(0.05, expected * 0.001):
                raise ValueError(
                    "Hurda kırılımı fire kilogramına eşit olmalıdır. "
                    f"Hurda toplamı {scrap_kg:.2f}, fire {expected:.2f}."
                )

    def _save_press_slip_lines(
        self,
        connection: sqlite3.Connection,
        entry_id: int,
        *,
        billets: Iterable[dict[str, Any]] | None,
        baskets: Iterable[dict[str, Any]] | None,
        scraps: Iterable[dict[str, Any]] | None,
    ) -> None:
        """Pres fişinin billet, sepet ve hurda dökümünü yazar."""
        for sequence, row in enumerate(billets or [], start=1):
            connection.execute(
                """
                INSERT INTO production_entry_billets(
                    production_entry_id, sequence_no, billet_length_mm, billet_count,
                    length_count, total_length_count, gross_kg, raw_material_stock,
                    lot_no, dummy_length_mm, press_speed_m_s, container_temp_c,
                    die_temp_c, billet_temp_c, exit_temp_c, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    sequence,
                    self._number(row.get("billet_length_mm")),
                    self._number(row.get("billet_count")),
                    self._number(row.get("length_count")),
                    self._number(row.get("total_length_count")),
                    self._number(row.get("gross_kg")),
                    str(row.get("raw_material_stock") or "").strip(),
                    str(row.get("lot_no") or "").strip(),
                    self._number(row.get("dummy_length_mm")),
                    self._number(row.get("press_speed_m_s")),
                    self._number(row.get("container_temp_c")),
                    self._number(row.get("die_temp_c")),
                    self._number(row.get("billet_temp_c")),
                    self._number(row.get("exit_temp_c")),
                    str(row.get("note") or "").strip(),
                ),
            )
        for sequence, row in enumerate(baskets or [], start=1):
            connection.execute(
                """
                INSERT INTO production_entry_baskets(
                    production_entry_id, sequence_no, basket_no, length_mm,
                    quantity, net_kg, work_order_no, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    sequence,
                    str(row.get("basket_no") or "").strip().upper(),
                    self._number(row.get("length_mm")),
                    self._number(row.get("quantity")),
                    self._number(row.get("net_kg")),
                    str(row.get("work_order_no") or "").strip(),
                    str(row.get("note") or "").strip(),
                ),
            )
        for sequence, row in enumerate(scraps or [], start=1):
            connection.execute(
                """
                INSERT INTO production_entry_scraps(
                    production_entry_id, sequence_no, scrap_reason, quantity, kg
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    sequence,
                    str(row.get("scrap_reason") or "HURDA").strip().upper(),
                    self._number(row.get("quantity")),
                    self._number(row.get("kg")),
                ),
            )

    def press_entry_context(self, work_order_id: int) -> dict[str, Any]:
        """Pres fişi ekranının başlık ve yan panelde gösterdiği bağlamı toplar."""
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT wo.work_order_no, wo.operation, wo.station,
                       wo.planned_quantity, wo.planned_kg, wo.production_length_mm,
                       po.production_order_no,
                       o.order_no, l.line_no, l.surface,
                       l.ordered_quantity, l.ordered_kg, l.die_id,
                       c.name AS customer_name,
                       p.profile_code, p.profile_name, p.unit_weight_kg_m, p.alloy,
                       d.die_code, d.spare_no, d.figure_count, d.tenefer_no,
                       d.tenefer_limit_m, d.tenefer_used_m
                FROM work_orders wo
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = l.die_id
                WHERE wo.id = ?
                """,
                (int(work_order_id),),
            ).fetchone()
            if row is None:
                raise ValueError("İş emri bulunamadı.")
            raw_material = connection.execute(
                """
                SELECT name FROM stock_items WHERE code = 'AL-BILLET' LIMIT 1
                """
            ).fetchone()
        context = dict(row)
        context["order_line_ref"] = (
            f"{context.get('order_no')}-{context.get('line_no')}"
            if context.get("line_no")
            else context.get("order_no")
        )
        context["tenefer_remaining_m"] = max(
            0.0,
            float(context.get("tenefer_limit_m") or 0)
            - float(context.get("tenefer_used_m") or 0),
        )
        context["raw_material_stock"] = (
            str(raw_material["name"]) if raw_material else "AL. BİLLET"
        )
        return context

    def press_slip_document(self, production_entry_id: int) -> dict[str, Any]:
        """PRES ÜRETİM FİŞİ çıktısı için başlık ve tüm alt dökümleri toplar."""
        with closing(self.connect()) as connection:
            header = connection.execute(
                """
                SELECT pe.*, wo.work_order_no, wo.operation, wo.station,
                       wo.planned_quantity, wo.planned_kg,
                       po.production_order_no,
                       o.order_no, o.order_date, o.delivery_date,
                       o.customer_document_no, o.representative,
                       l.line_no, l.surface, l.color, l.temper, l.mechanical,
                       l.ordered_quantity, l.ordered_kg,
                       l.stock_length_mm, l.production_length_mm AS line_length_mm,
                       c.name AS customer_name,
                       p.profile_code, p.profile_name, p.unit_weight_kg_m,
                       p.alloy, p.profile_group,
                       d.die_code, d.tenefer_limit_m, d.tenefer_used_m,
                       d.life_limit_kg, d.used_kg
                FROM production_entries pe
                JOIN work_orders wo ON wo.id = pe.work_order_id
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = COALESCE(pe.die_id, l.die_id)
                WHERE pe.id = ?
                """,
                (int(production_entry_id),),
            ).fetchone()
            if header is None:
                raise ValueError("Pres üretim fişi bulunamadı.")
            billets = connection.execute(
                """
                SELECT * FROM production_entry_billets
                WHERE production_entry_id = ? ORDER BY sequence_no
                """,
                (int(production_entry_id),),
            ).fetchall()
            baskets = connection.execute(
                """
                SELECT * FROM production_entry_baskets
                WHERE production_entry_id = ? ORDER BY sequence_no
                """,
                (int(production_entry_id),),
            ).fetchall()
            scraps = connection.execute(
                """
                SELECT * FROM production_entry_scraps
                WHERE production_entry_id = ? ORDER BY sequence_no
                """,
                (int(production_entry_id),),
            ).fetchall()
        return {
            "header": dict(header),
            "billets": [dict(row) for row in billets],
            "baskets": [dict(row) for row in baskets],
            "scraps": [dict(row) for row in scraps],
        }

    def record_work_order_output(
        self,
        work_order_id: int,
        *,
        quantity: float,
        gross_kg: float,
        net_kg: float,
        metre: float = 0,
        die_id: int | None = None,
        lot_no: str = "",
        shift: str = "",
        username: str,
        complete: bool = True,
        production_type: str = "PLANLI ÜRETİM",
        press_status: str = "",
        saw_status: str = "",
        real_weight_kg_m: float = 0,
        theoretical_weight_kg_m: float = 0,
        billet_count: int = 0,
        billet_length_mm: float = 0,
        billet_diameter_mm: float = 0,
        billet_density_kg_m3: float = 0,
        billet_weight_kg_m: float = 0,
        theoretical_net_kg: float = 0,
        theoretical_billet_kg: float = 0,
        press_fire_pct: float = 0,
        basket_count: int = 0,
        result_length_mm: float = 0,
        preparation_min: float = 0,
        duration_min: float = 0,
        missing_quantity: float = 0,
        missing_reason: str = "",
        note: str = "",
        qc_username: str = "",
        test_result: str = "",
        die_problem: str = "",
        die_problem_note: str = "",
        spare_no: int = 0,
        figure_count: int = 0,
        tenefer_no: str = "",
        raw_material_stock: str = "",
        remaining_quantity: float = 0,
        started_at: str = "",
        ended_at: str = "",
        billets: Iterable[dict[str, Any]] | None = None,
        baskets: Iterable[dict[str, Any]] | None = None,
        scraps: Iterable[dict[str, Any]] | None = None,
    ) -> int:
        gross = self._number(gross_kg)
        net = self._number(net_kg)
        produced_quantity = self._number(quantity)
        if gross < 0 or net <= 0 or net > gross:
            raise ValueError("Üretim brüt/net kilogram değerleri geçersiz.")
        billet_rows = list(billets or [])
        basket_rows = list(baskets or [])
        scrap_rows = list(scraps or [])
        if billet_rows:
            self._validate_press_slip_lines(
                gross=gross,
                net=net,
                quantity=produced_quantity,
                billets=billet_rows,
                baskets=basket_rows,
                scraps=scrap_rows,
            )
        with closing(self.connect()) as connection:
            work = connection.execute(
                "SELECT * FROM work_orders WHERE id = ?",
                (int(work_order_id),),
            ).fetchone()
            if work is None:
                raise ValueError("İş emri bulunamadı.")
            if work["status"] not in {"HAZIR", "ÜRETİLİYOR"}:
                raise ValueError("Bu iş emri henüz üretime hazır değil.")
            production = connection.execute(
                "SELECT * FROM production_orders WHERE id = ?",
                (int(work["production_order_id"]),),
            ).fetchone()
            line = connection.execute(
                "SELECT * FROM sales_order_lines WHERE id = ?",
                (int(production["sales_order_line_id"]),),
            ).fetchone()
            is_press = str(work["operation"] or "").upper().startswith("PRES")
            # Gerçek billet dökümü girildiyse tartılan değerler esastır; teorik
            # eşitlik kontrolü yalnız döküm yokken uygulanır.
            if is_press and int(billet_count or 0) > 0 and not billet_rows:
                theory = self.calculate_press_theory(
                    quantity=produced_quantity,
                    result_length_mm=self._number(result_length_mm),
                    profile_weight_kg_m=self._number(theoretical_weight_kg_m),
                    billet_count=int(billet_count),
                    billet_diameter_mm=self._number(billet_diameter_mm),
                    billet_density_kg_m3=self._number(billet_density_kg_m3),
                    fire_pct=self._number(press_fire_pct),
                )
                required = {
                    "Çıkan boy": self._number(result_length_mm),
                    "Teorik profil gramajı": self._number(theoretical_weight_kg_m),
                    "Billet çapı": self._number(billet_diameter_mm),
                    "Billet yoğunluğu": self._number(billet_density_kg_m3),
                }
                missing = [name for name, value in required.items() if value <= 0]
                if produced_quantity <= 0:
                    missing.append("Üretilen adet")
                if missing:
                    raise ValueError(
                        "Pres üretim fişi kaydedilemez. Zorunlu teorik alanlar: "
                        + ", ".join(missing)
                    )

                checks = (
                    ("Net metre", self._number(metre), theory["net_metre"], 0.01),
                    ("Net KG", net, theory["theoretical_net_kg"], 0.01),
                    ("Brüt billet KG", gross, theory["theoretical_billet_kg"], 0.01),
                    ("Billet boyu", self._number(billet_length_mm), theory["billet_length_mm"], 0.01),
                )
                for label, entered, expected, ratio in checks:
                    tolerance = max(0.05, abs(expected) * ratio)
                    if abs(entered - expected) > tolerance:
                        raise ValueError(
                            f"{label} teorik hesapla uyuşmuyor. "
                            f"Beklenen {expected:.3f}, girilen {entered:.3f}."
                        )
                billet_weight_kg_m = theory["billet_weight_kg_m"]
                theoretical_net_kg = theory["theoretical_net_kg"]
                theoretical_billet_kg = theory["theoretical_billet_kg"]
            if int(work["sequence_no"]) > 1:
                previous = connection.execute(
                    """
                    SELECT produced_kg FROM work_orders
                    WHERE production_order_id = ? AND sequence_no < ?
                    ORDER BY sequence_no DESC LIMIT 1
                    """,
                    (int(work["production_order_id"]), int(work["sequence_no"])),
                ).fetchone()
                already_consumed = float(
                    connection.execute(
                        "SELECT COALESCE(SUM(gross_kg), 0) FROM production_entries WHERE work_order_id = ?",
                        (int(work_order_id),),
                    ).fetchone()[0]
                )
                available = float(previous["produced_kg"] if previous else 0) - already_consumed
                if gross > available + 0.001:
                    raise ValueError(
                        "Bu operasyona girilen brüt miktar önceki istasyondan çıkan "
                        f"kullanılabilir {max(0.0, available):.3f} kg miktarı aşamaz."
                    )
            now = self._now()
            scrap = max(0.0, gross - net)
            slip_no = self._next_no(connection, "PF")
            die_row = (
                connection.execute("SELECT * FROM dies WHERE id = ?", (int(die_id),)).fetchone()
                if die_id
                else None
            )
            cursor = connection.execute(
                """
                INSERT INTO production_entries(
                    work_order_id, entry_type, operator_username, shift, die_id,
                    lot_no, gross_kg, net_kg, scrap_kg, quantity, metre,
                    started_at, ended_at, note, production_type, press_status,
                    saw_status, real_weight_kg_m, theoretical_weight_kg_m,
                    billet_count, billet_length_mm, billet_diameter_mm,
                    billet_density_kg_m3, billet_weight_kg_m,
                    theoretical_net_kg, theoretical_billet_kg, press_fire_pct,
                    basket_count,
                    result_length_mm, preparation_min, duration_min,
                    missing_quantity, missing_reason,
                    slip_no, qc_username, test_result, die_problem,
                    die_problem_note, spare_no, figure_count, tenefer_no,
                    raw_material_stock, remaining_quantity, fire_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(work_order_id),
                    work["operation"],
                    username,
                    shift,
                    die_id,
                    lot_no,
                    gross,
                    net,
                    scrap,
                    produced_quantity,
                    self._number(metre),
                    started_at.strip() or now,
                    (ended_at.strip() or now) if complete else (ended_at.strip() or None),
                    note.strip(),
                    production_type.strip().upper() or "PLANLI ÜRETİM",
                    press_status.strip().upper(),
                    saw_status.strip().upper(),
                    self._number(real_weight_kg_m),
                    self._number(theoretical_weight_kg_m),
                    max(0, int(billet_count)),
                    self._number(billet_length_mm),
                    self._number(billet_diameter_mm),
                    self._number(billet_density_kg_m3),
                    self._number(billet_weight_kg_m),
                    self._number(theoretical_net_kg),
                    self._number(theoretical_billet_kg),
                    self._number(press_fire_pct),
                    max(0, int(basket_count)),
                    self._number(result_length_mm),
                    self._number(preparation_min),
                    self._number(duration_min),
                    self._number(missing_quantity),
                    missing_reason.strip(),
                    slip_no,
                    qc_username.strip(),
                    test_result.strip().upper(),
                    die_problem.strip().upper(),
                    die_problem_note.strip(),
                    int(spare_no or (die_row["spare_no"] if die_row else 0) or 0),
                    int(figure_count or (die_row["figure_count"] if die_row else 0) or 0),
                    (tenefer_no.strip() or str(die_row["tenefer_no"] or "") if die_row else tenefer_no.strip()),
                    raw_material_stock.strip(),
                    self._number(remaining_quantity),
                    round(scrap / gross * 100, 2) if gross > 0 else 0.0,
                ),
            )
            entry_id = int(cursor.lastrowid)
            self._save_press_slip_lines(
                connection, entry_id, billets=billets, baskets=baskets, scraps=scraps
            )
            new_status = "TAMAMLANDI" if complete else "ÜRETİLİYOR"
            completed_quantity = float(work["produced_quantity"]) + produced_quantity
            completed_net_kg = float(work["produced_kg"]) + net
            connection.execute(
                """
                UPDATE work_orders
                SET produced_quantity = produced_quantity + ?,
                    produced_kg = produced_kg + ?, scrap_kg = scrap_kg + ?,
                    status = ?, actual_start = COALESCE(actual_start, ?),
                    actual_end = ?, row_version = row_version + 1
                WHERE id = ?
                """,
                (
                    produced_quantity,
                    net,
                    max(0.0, gross - net),
                    new_status,
                    now,
                    now if complete else None,
                    int(work_order_id),
                ),
            )
            if die_id:
                die_row = connection.execute(
                    "SELECT * FROM dies WHERE id = ?",
                    (int(die_id),),
                ).fetchone()
                if die_row is not None:
                    length_mm = float(
                        work["production_length_mm"]
                        if work["production_length_mm"]
                        else line["production_length_mm"]
                        if line["production_length_mm"]
                        else line["length_mm"]
                        or 0
                    )
                    tenefer_delta = self._die_tenefer_metre_delta(
                        die_row,
                        metre=self._number(metre),
                        quantity=produced_quantity,
                        length_mm=length_mm,
                    )
                    self._record_die_production_usage(
                        connection,
                        die_id=int(die_id),
                        net_kg=net,
                        tenefer_delta_m=tenefer_delta,
                        production_entry_id=entry_id,
                        username=username,
                        work_order_no=str(work["work_order_no"]),
                    )
            route_step = connection.execute(
                "SELECT * FROM route_steps WHERE id = ?",
                (int(work["route_step_id"]),),
            ).fetchone()
            organization_id = self.organization_id(connection)
            profile = connection.execute(
                "SELECT * FROM profiles WHERE id = ?",
                (int(line["profile_id"]),),
            ).fetchone()
            recipe_line = None
            if work["recipe_line_id"] is not None:
                recipe_line = connection.execute(
                    "SELECT * FROM recipe_lines WHERE id = ?",
                    (int(work["recipe_line_id"]),),
                ).fetchone()
            production_bases = self._production_base_quantities(
                quantity=produced_quantity,
                kg=net,
                metre=self._number(metre),
                profile=profile,
                line=line,
            )
            if route_step is not None:
                input_stock = self._resolve_stock_item_for_recipe_line(
                    connection,
                    organization_id,
                    recipe_line,
                    profile,
                    for_output=False,
                )
                output_stock = self._resolve_stock_item_for_recipe_line(
                    connection,
                    organization_id,
                    recipe_line,
                    profile,
                    for_output=True,
                )
                if int(work["sequence_no"]) == 1 and (
                    recipe_line is None
                    or not str(recipe_line["stock_code"] or "").strip()
                ):
                    raw_material_code = ""
                    if production is not None and production["recipe_id"] is not None:
                        recipe_header = connection.execute(
                            """
                            SELECT raw_material_stock_external_id
                            FROM recipes WHERE id = ?
                            """,
                            (int(production["recipe_id"]),),
                        ).fetchone()
                        if recipe_header is not None:
                            raw_material_code = str(
                                recipe_header["raw_material_stock_external_id"] or ""
                            ).strip().upper()
                    if not raw_material_code:
                        raw_material_code = "AL-BILLET"
                    input_stock = connection.execute(
                        """
                        SELECT * FROM stock_items
                        WHERE organization_id = ? AND UPPER(code) = ? AND active = 1
                        """,
                        (organization_id, raw_material_code),
                    ).fetchone()
                    if input_stock is None:
                        input_stock = connection.execute(
                            """
                            SELECT * FROM stock_items
                            WHERE organization_id = ? AND code = 'AL-BILLET' AND active = 1
                            """,
                            (organization_id,),
                        ).fetchone()
                elif input_stock is None and int(work["sequence_no"]) > 1 and profile is not None:
                    input_stock = connection.execute(
                        "SELECT * FROM stock_items WHERE profile_id = ? AND active = 1",
                        (int(profile["id"]),),
                    ).fetchone()
                input_unit = (
                    recipe_line["unit_code"] if recipe_line is not None else "KG"
                )
                output_unit = input_unit or "KG"
                input_qty = self._quantity_in_unit(
                    production_bases,
                    input_unit,
                    unit_set_id=int(input_stock["unit_set_id"] or 0)
                    if input_stock is not None and input_stock["unit_set_id"] is not None
                    else None,
                    connection=connection,
                )
                if input_qty <= 0:
                    input_qty = gross
                if (
                    int(work["sequence_no"]) == 1
                    and input_stock is not None
                    and str(input_stock["code"] or "").upper() == "AL-BILLET"
                    and self._normalize_unit_code(input_unit) == "KG"
                ):
                    input_qty = gross
                output_qty = self._quantity_in_unit(
                    production_bases,
                    output_unit,
                    unit_set_id=int(output_stock["unit_set_id"] or 0)
                    if output_stock is not None and output_stock["unit_set_id"] is not None
                    else None,
                    connection=connection,
                )
                if output_qty <= 0:
                    output_qty = net
                if (
                    route_step["input_warehouse_id"] is not None
                    and input_stock is not None
                    and input_qty > 0
                ):
                    connection.execute(
                        """
                        INSERT INTO stock_movements(
                            organization_id, stock_item_id, warehouse_id,
                            movement_type, direction, quantity, lot_no,
                            sales_order_line_id, work_order_id, document_no,
                            created_by
                        ) VALUES (?, ?, ?, ?, -1, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            organization_id,
                            int(input_stock["id"]),
                            int(route_step["input_warehouse_id"]),
                            f"{work['operation']} ÇIKIŞ",
                            input_qty,
                            lot_no,
                            int(line["id"]),
                            int(work_order_id),
                            str(work["work_order_no"]),
                            username,
                        ),
                    )
                if (
                    route_step["output_warehouse_id"] is not None
                    and output_stock is not None
                    and output_qty > 0
                ):
                    connection.execute(
                        """
                        INSERT INTO stock_movements(
                            organization_id, stock_item_id, warehouse_id,
                            movement_type, direction, quantity, lot_no,
                            sales_order_line_id, work_order_id, document_no,
                            created_by
                        ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            organization_id,
                            int(output_stock["id"]),
                            int(route_step["output_warehouse_id"]),
                            f"{work['operation']} GİRİŞ",
                            output_qty,
                            lot_no,
                            int(line["id"]),
                            int(work_order_id),
                            str(work["work_order_no"]),
                            username,
                        ),
                    )
            if complete:
                next_work = connection.execute(
                    """
                    SELECT id FROM work_orders
                    WHERE production_order_id = ? AND sequence_no > ?
                    ORDER BY sequence_no LIMIT 1
                    """,
                    (int(work["production_order_id"]), int(work["sequence_no"])),
                ).fetchone()
                if next_work is not None:
                    connection.execute(
                        "UPDATE work_orders SET status = 'HAZIR', row_version = row_version + 1 WHERE id = ?",
                        (int(next_work["id"]),),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE production_orders
                        SET produced_quantity = produced_quantity + ?,
                            produced_kg = produced_kg + ?, status = 'TAMAMLANDI',
                            row_version = row_version + 1
                        WHERE id = ?
                        """,
                        (completed_quantity, completed_net_kg, int(production["id"])),
                    )
                    produced_totals = connection.execute(
                        """
                        SELECT COALESCE(SUM(produced_quantity), 0) AS quantity,
                               COALESCE(SUM(produced_kg), 0) AS kg
                        FROM production_orders
                        WHERE sales_order_line_id = ? AND status <> 'İPTAL'
                        """,
                        (int(line["id"]),),
                    ).fetchone()
                    total_quantity = float(produced_totals["quantity"] or 0)
                    total_kg = float(produced_totals["kg"] or 0)
                    ordered_quantity = float(line["ordered_quantity"] or 0)
                    ordered_kg = float(line["ordered_kg"] or 0)
                    quantity_ready = (
                        ordered_quantity <= 0.001
                        or total_quantity + 0.001 >= ordered_quantity
                    )
                    kg_ready = ordered_kg <= 0.001 or total_kg + 0.001 >= ordered_kg
                    line_status = "HAZIR" if quantity_ready and kg_ready else "ÜRETİMDE"
                    connection.execute(
                        """
                        UPDATE sales_order_lines
                        SET produced_quantity = ?, produced_kg = ?, status = ?,
                            row_version = row_version + 1
                        WHERE id = ?
                        """,
                        (total_quantity, total_kg, line_status, int(line["id"])),
                    )
                    order_id = int(line["sales_order_id"])
                    remaining = connection.execute(
                        """
                        SELECT COUNT(*) FROM sales_order_lines
                        WHERE sales_order_id = ? AND status <> 'HAZIR'
                        """,
                        (order_id,),
                    ).fetchone()[0]
                    if int(remaining) == 0:
                        connection.execute(
                            "UPDATE sales_orders SET status = 'HAZIR', updated_at = ?, row_version = row_version + 1 WHERE id = ?",
                            (now, order_id),
                        )
            if (
                complete
                and is_press
                and self._number(result_length_mm) > 0
            ):
                self._handle_length_deviation(
                    connection,
                    work=dict(work),
                    line=dict(line),
                    production=dict(production),
                    result_length_mm=self._number(result_length_mm),
                    produced_quantity=produced_quantity,
                    username=username,
                )
            self._audit(
                connection,
                username=username,
                action="PRODUCTION_ENTRY",
                entity_type="WORK_ORDER",
                entity_id=int(work_order_id),
                record_key=str(work["work_order_no"]),
                after={
                    "gross_kg": gross, "net_kg": net, "complete": complete,
                    "production_type": production_type,
                    "press_status": press_status, "saw_status": saw_status,
                    "billet_count": billet_count, "basket_count": basket_count,
                },
            )
            recalculate_order_line_status(
                connection, sales_order_line_id=int(line["id"])
            )
            connection.commit()
            return entry_id

    def create_package(
        self,
        sales_order_line_id: int,
        *,
        quantity: float,
        net_kg: float,
        gross_kg: float,
        username: str,
        lot_no: str = "",
    ) -> int:
        net = self._number(net_kg)
        gross = self._number(gross_kg)
        if net <= 0 or gross < net:
            raise ValueError("Paket net/brüt kilogram değerleri geçersiz.")
        with closing(self.connect()) as connection:
            line = connection.execute(
                """
                SELECT l.*, o.customer_id
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                WHERE l.id = ?
                """,
                (int(sales_order_line_id),),
            ).fetchone()
            if line is None:
                raise ValueError("Sipariş satırı bulunamadı.")
            already_packed = connection.execute(
                "SELECT COALESCE(SUM(net_kg), 0) FROM package_lines WHERE sales_order_line_id = ?",
                (int(sales_order_line_id),),
            ).fetchone()[0]
            if float(already_packed) + net > float(line["produced_kg"]) + 0.001:
                raise ValueError("Paket miktarı üretilmiş miktarı aşamaz.")
            package_no = self._next_no(connection, "PK")
            # Kasalama/paketleme bittiğinde ürün doğrudan "Sevk Hazır" olmaz.
            # Önce SEVK ÖN'de bekler; çeki listesine alınınca
            # SEVK HAZIR'a aktarılır.
            warehouse = self.warehouse_id(connection, "SEVK_ON")
            cursor = connection.execute(
                """
                INSERT INTO packages(
                    organization_id, package_no, customer_id, warehouse_id,
                    net_kg, gross_kg, status, packed_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'SEVK ÖN', ?)
                """,
                (
                    self.organization_id(connection),
                    package_no,
                    int(line["customer_id"]),
                    warehouse,
                    net,
                    gross,
                    username,
                ),
            )
            package_id = int(cursor.lastrowid)
            stock = connection.execute(
                "SELECT id FROM stock_items WHERE profile_id = ?",
                (int(line["profile_id"]),),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO package_lines(
                    package_id, sales_order_line_id, stock_item_id, lot_no,
                    quantity, net_kg, gross_kg
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package_id,
                    int(sales_order_line_id),
                    int(stock["id"]),
                    lot_no,
                    self._number(quantity),
                    net,
                    gross,
                ),
            )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="PACKAGE",
                entity_id=package_id,
                record_key=package_no,
                after={"net_kg": net, "gross_kg": gross},
            )
            recalculate_order_line_status(
                connection, sales_order_line_id=int(sales_order_line_id)
            )
            connection.commit()
            return package_id

    def create_weighing_list(
        self,
        package_ids: Iterable[int],
        *,
        username: str,
        note: str = "",
    ) -> int:
        """SEVK ÖN'deki kasaları çeki listesine bağlayıp SEVK HAZIR'a taşır."""
        selected = list(dict.fromkeys(int(value) for value in package_ids))
        if not selected:
            raise ValueError("Çeki listesi için en az bir SEVK ÖN paketi seçilmelidir.")
        with closing(self.connect()) as connection:
            placeholders = ",".join("?" for _ in selected)
            packages = connection.execute(
                f"SELECT * FROM packages WHERE id IN ({placeholders}) ORDER BY id",
                selected,
            ).fetchall()
            if len(packages) != len(selected):
                raise ValueError("Seçilen paketlerden biri bulunamadı.")
            customer_ids = {int(row["customer_id"]) for row in packages}
            if len(customer_ids) != 1:
                raise ValueError("Tek çeki listesinde yalnız aynı müşterinin paketleri bulunabilir.")
            if any(str(row["status"]) != "SEVK ÖN" for row in packages):
                raise ValueError("Yalnız SEVK ÖN durumundaki paketler çeki listesine alınabilir.")

            weighing_list_no = self._next_no(connection, "CL")
            cursor = connection.execute(
                """
                INSERT INTO weighing_lists(
                    organization_id, weighing_list_no, customer_id, note, created_by
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    weighing_list_no,
                    next(iter(customer_ids)),
                    note.strip(),
                    username,
                ),
            )
            weighing_list_id = int(cursor.lastrowid)
            ready_warehouse = self.warehouse_id(connection, "SEVK_HAZIR")
            for package in packages:
                connection.execute(
                    """
                    INSERT INTO weighing_list_packages(
                        weighing_list_id, package_id, net_kg, gross_kg
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        weighing_list_id,
                        int(package["id"]),
                        float(package["net_kg"]),
                        float(package["gross_kg"]),
                    ),
                )
                lines = connection.execute(
                    "SELECT * FROM package_lines WHERE package_id = ?",
                    (int(package["id"]),),
                ).fetchall()
                for line in lines:
                    for warehouse_id, direction, movement_type in (
                        (int(package["warehouse_id"]), -1, "ÇEKİ LİSTESİ ÇIKIŞ"),
                        (ready_warehouse, 1, "ÇEKİ LİSTESİ GİRİŞ"),
                    ):
                        connection.execute(
                            """
                            INSERT INTO stock_movements(
                                organization_id, stock_item_id, warehouse_id,
                                movement_type, direction, quantity, lot_no,
                                sales_order_line_id, document_no, created_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                self.organization_id(connection),
                                int(line["stock_item_id"]),
                                warehouse_id,
                                movement_type,
                                direction,
                                float(line["net_kg"]),
                                line["lot_no"],
                                int(line["sales_order_line_id"]),
                                weighing_list_no,
                                username,
                            ),
                        )
                connection.execute(
                    """
                    UPDATE packages
                    SET warehouse_id = ?, status = 'SEVK HAZIR',
                        row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (ready_warehouse, int(package["id"])),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="WEIGHING_LIST",
                entity_id=weighing_list_id,
                record_key=weighing_list_no,
                after={"packages": selected},
            )
            connection.commit()
            return weighing_list_id

    def create_shipment(
        self,
        package_ids: Iterable[int],
        *,
        shipment_date: str,
        username: str,
        vehicle_plate: str = "",
        weighing_list_id: int | None = None,
        dispatch_note_no: str = "",
    ) -> int:
        """SEVK HAZIR paketlerden irsaliye keser; stoku Sevk Hazır'dan düşer.

        ``shipments.weighing_list_id`` tekildir. Kısmi sevkte bağ kurulmaz;
        son paket çıkınca bağlanır. Çeki listesi durumu her sevkte güncellenir
        (KISMİ SEVK / SEVK EDİLDİ).
        """
        selected = [int(value) for value in package_ids]
        if not selected:
            raise ValueError("Sevkiyat için en az bir hazır paket seçilmelidir.")
        with closing(self.connect()) as connection:
            ready_warehouse = self.warehouse_id(connection, "SEVK_HAZIR")
            requested_weighing_list_id = (
                int(weighing_list_id) if weighing_list_id is not None else None
            )
            if requested_weighing_list_id is not None:
                weighing_list = connection.execute(
                    "SELECT id, status FROM weighing_lists WHERE id = ?",
                    (requested_weighing_list_id,),
                ).fetchone()
                if weighing_list is None:
                    raise ValueError("Çeki listesi bulunamadı.")
                if str(weighing_list["status"]) == "SEVK EDİLDİ":
                    raise ValueError("Bu çeki listesi daha önce sevk edilmiş.")
            placeholders = ",".join("?" for _ in selected)
            packages = connection.execute(
                f"SELECT * FROM packages WHERE id IN ({placeholders}) ORDER BY id",
                selected,
            ).fetchall()
            if len(packages) != len(selected):
                raise ValueError("Seçilen paketlerden biri bulunamadı.")
            customer_ids = {int(row["customer_id"]) for row in packages}
            if len(customer_ids) != 1:
                raise ValueError("Tek sevkiyatta yalnız aynı müşterinin paketleri bulunabilir.")
            if any(row["status"] != "SEVK HAZIR" for row in packages):
                raise ValueError(
                    "Yalnız çeki listesine alınmış SEVK HAZIR paketleri sevk edilebilir."
                )
            for package in packages:
                if int(package["warehouse_id"]) != ready_warehouse:
                    raise ValueError(
                        "Sevk edilecek paketler Sevk Hazır ambarında olmalıdır."
                    )
            if requested_weighing_list_id is not None:
                linked_to_list = {
                    int(row["package_id"])
                    for row in connection.execute(
                        f"""
                        SELECT package_id
                        FROM weighing_list_packages
                        WHERE weighing_list_id = ?
                          AND package_id IN ({placeholders})
                        """,
                        (requested_weighing_list_id, *selected),
                    ).fetchall()
                }
                if linked_to_list != set(selected):
                    raise ValueError(
                        "Seçilen paketlerin tümü bu çeki listesine ait olmalıdır."
                    )

            # Paketlerin bağlı olduğu çeki listelerini bul (durum güncellemesi için).
            linked_lists = {
                int(row["weighing_list_id"])
                for row in connection.execute(
                    f"""
                    SELECT DISTINCT weighing_list_id
                    FROM weighing_list_packages
                    WHERE package_id IN ({placeholders})
                    """,
                    selected,
                ).fetchall()
            }
            if requested_weighing_list_id is not None:
                linked_lists.add(requested_weighing_list_id)

            # UNIQUE(weighing_list_id): yalnız listenin son paketi sevk edilirken bağla.
            shipment_weighing_list_id: int | None = None
            candidate = requested_weighing_list_id
            if candidate is None and len(linked_lists) == 1:
                candidate = next(iter(linked_lists))
            if candidate is not None:
                remaining = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM weighing_list_packages
                        WHERE weighing_list_id = ?
                          AND package_id NOT IN ({placeholders})
                          AND package_id NOT IN (
                              SELECT package_id FROM shipment_lines
                          )
                        """,
                        (candidate, *selected),
                    ).fetchone()[0]
                )
                if remaining == 0:
                    shipment_weighing_list_id = candidate
            shipment_no = self._next_no(connection, "SV")
            dispatch_no = dispatch_note_no.strip().upper() or shipment_no
            cursor = connection.execute(
                """
                INSERT INTO shipments(
                    organization_id, shipment_no, customer_id, shipment_date,
                    vehicle_plate, created_by, weighing_list_id, dispatch_note_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    shipment_no,
                    next(iter(customer_ids)),
                    shipment_date,
                    vehicle_plate.strip().upper(),
                    username,
                    shipment_weighing_list_id,
                    dispatch_no,
                ),
            )
            shipment_id = int(cursor.lastrowid)
            affected_orders: set[int] = set()
            for package in packages:
                connection.execute(
                    "INSERT INTO shipment_lines(shipment_id, package_id, net_kg, gross_kg) VALUES (?, ?, ?, ?)",
                    (
                        shipment_id,
                        int(package["id"]),
                        float(package["net_kg"]),
                        float(package["gross_kg"]),
                    ),
                )
                lines = connection.execute(
                    "SELECT * FROM package_lines WHERE package_id = ?",
                    (int(package["id"]),),
                ).fetchall()
                for line in lines:
                    connection.execute(
                        """
                        UPDATE sales_order_lines
                        SET shipped_quantity = shipped_quantity + ?,
                            shipped_kg = shipped_kg + ?,
                            status = CASE
                                WHEN shipped_kg + ? >= ordered_kg - 0.001
                                THEN 'SEVK EDİLDİ' ELSE 'KISMİ SEVK'
                            END,
                            row_version = row_version + 1
                        WHERE id = ?
                        """,
                        (
                            float(line["quantity"]),
                            float(line["net_kg"]),
                            float(line["net_kg"]),
                            int(line["sales_order_line_id"]),
                        ),
                    )
                    order_id = connection.execute(
                        "SELECT sales_order_id FROM sales_order_lines WHERE id = ?",
                        (int(line["sales_order_line_id"]),),
                    ).fetchone()[0]
                    affected_orders.add(int(order_id))
                    # İrsaliye anında stok Sevk Hazır ambarından çıkar.
                    connection.execute(
                        """
                        INSERT INTO stock_movements(
                            organization_id, stock_item_id, warehouse_id,
                            movement_type, direction, quantity, lot_no,
                            sales_order_line_id, document_no, created_by
                        ) VALUES (?, ?, ?, 'SEVKİYAT ÇIKIŞ', -1, ?, ?, ?, ?, ?)
                        """,
                        (
                            self.organization_id(connection),
                            int(line["stock_item_id"]),
                            ready_warehouse,
                            float(line["net_kg"]),
                            line["lot_no"],
                            int(line["sales_order_line_id"]),
                            shipment_no,
                            username,
                        ),
                    )
                connection.execute(
                    """
                    UPDATE packages
                    SET status = 'SEVK EDİLDİ',
                        warehouse_id = ?,
                        row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (ready_warehouse, int(package["id"])),
                )
            for order_id in affected_orders:
                open_lines = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM sales_order_lines
                        WHERE sales_order_id = ? AND status <> 'SEVK EDİLDİ'
                        """,
                        (order_id,),
                    ).fetchone()[0]
                )
                connection.execute(
                    "UPDATE sales_orders SET status = ?, updated_at = ?, row_version = row_version + 1 WHERE id = ?",
                    (
                        "SEVK EDİLDİ" if open_lines == 0 else "KISMİ SEVK",
                        self._now(),
                        order_id,
                    ),
                )
            # Çeki listesi: kısmi veya tam kapanış (UNIQUE yüzünden shipment FK
            # yalnızca son sevkte dolu olsa da liste durumu her sevkte güncellenir).
            for list_id in linked_lists:
                pending = int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM weighing_list_packages wlp
                        WHERE wlp.weighing_list_id = ?
                          AND wlp.package_id NOT IN (
                              SELECT package_id FROM shipment_lines
                          )
                        """,
                        (int(list_id),),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    UPDATE weighing_lists
                    SET status = ?, row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (
                        "SEVK EDİLDİ" if pending == 0 else "KISMİ SEVK",
                        int(list_id),
                    ),
                )
            self._audit(
                connection,
                username=username,
                action="SHIP",
                entity_type="SHIPMENT",
                entity_id=shipment_id,
                record_key=shipment_no,
                after={
                    "packages": selected,
                    "weighing_list_id": shipment_weighing_list_id,
                    "dispatch_note_no": dispatch_no,
                },
            )
            for package in packages:
                for line in connection.execute(
                    "SELECT sales_order_line_id FROM package_lines WHERE package_id = ?",
                    (int(package["id"]),),
                ).fetchall():
                    recalculate_order_line_status(
                        connection,
                        sales_order_line_id=int(line["sales_order_line_id"]),
                    )
            connection.commit()
            return shipment_id

    def packages_for_weighing_list(self, weighing_list_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pk.id, pk.package_no, pk.net_kg, pk.gross_kg,
                       pk.package_count, pk.status, pk.packed_at, pk.packed_by,
                       c.name AS customer_name, w.name AS warehouse_name,
                       GROUP_CONCAT(DISTINCT o.order_no) AS order_nos,
                       GROUP_CONCAT(DISTINCT p.profile_code) AS profile_codes
                FROM weighing_list_packages wlp
                JOIN packages pk ON pk.id = wlp.package_id
                JOIN customers c ON c.id = pk.customer_id
                JOIN warehouses w ON w.id = pk.warehouse_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                WHERE wlp.weighing_list_id = ?
                GROUP BY pk.id
                ORDER BY pk.id
                """,
                (int(weighing_list_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def packages_for_shipment(self, shipment_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pk.id, pk.package_no, sl.net_kg, sl.gross_kg,
                       pk.package_count, pk.status,
                       c.name AS customer_name, w.name AS warehouse_name,
                       GROUP_CONCAT(DISTINCT o.order_no) AS order_nos,
                       GROUP_CONCAT(DISTINCT p.profile_code) AS profile_codes
                FROM shipment_lines sl
                JOIN packages pk ON pk.id = sl.package_id
                JOIN customers c ON c.id = pk.customer_id
                JOIN warehouses w ON w.id = pk.warehouse_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                WHERE sl.shipment_id = ?
                GROUP BY pk.id
                ORDER BY pk.id
                """,
                (int(shipment_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_package_lines(self, package_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pl.id, pl.lot_no, pl.quantity, pl.net_kg, pl.gross_kg,
                       si.code AS stock_code, si.name AS stock_name, si.unit,
                       p.profile_code, p.profile_name,
                       o.order_no, l.line_no, l.production_length_mm
                FROM package_lines pl
                JOIN stock_items si ON si.id = pl.stock_item_id
                JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN profiles p ON p.id = l.profile_id
                WHERE pl.package_id = ?
                ORDER BY pl.id
                """,
                (int(package_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_goods_receipt_lines(self, goods_receipt_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT grl.id, grl.quantity, grl.lot_no,
                       pol.line_no, pol.unit_price, pol.quantity AS ordered_quantity,
                       si.code AS stock_code, si.name AS stock_name, si.unit,
                       w.name AS warehouse_name
                FROM goods_receipt_lines grl
                JOIN purchase_order_lines pol ON pol.id = grl.purchase_order_line_id
                JOIN stock_items si ON si.id = pol.stock_item_id
                JOIN warehouses w ON w.id = pol.warehouse_id
                WHERE grl.goods_receipt_id = ?
                ORDER BY pol.line_no
                """,
                (int(goods_receipt_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def production_orders_for_line(self, sales_order_line_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT po.id, po.production_order_no, po.planned_quantity,
                       po.planned_kg, po.status, r.code AS route_code,
                       (SELECT COUNT(*) FROM work_orders wo
                        WHERE wo.production_order_id = po.id) AS work_order_count,
                       (SELECT COUNT(*) FROM work_orders wo
                        WHERE wo.production_order_id = po.id
                          AND wo.status = 'TAMAMLANDI') AS completed_work_orders
                FROM production_orders po
                LEFT JOIN routes r ON r.id = po.route_id
                WHERE po.sales_order_line_id = ?
                ORDER BY po.id
                """,
                (int(sales_order_line_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_sales_invoice(
        self,
        shipment_id: int,
        *,
        invoice_date: str,
        currency: str,
        exchange_rate: float,
        lme_usd_ton: float,
        premium_usd_ton: float,
        pricing_mode: str,
        username: str,
    ) -> int:
        mode = pricing_mode.strip().upper()
        if mode not in {"BİRİM FİYAT", "LME + PRİM"}:
            raise ValueError("Fatura fiyatlandırma yöntemi geçersiz.")
        with closing(self.connect()) as connection:
            shipment = connection.execute(
                "SELECT id FROM shipments WHERE id = ?",
                (int(shipment_id),),
            ).fetchone()
            if shipment is None:
                raise ValueError("Satış irsaliyesi bulunamadı.")
            if connection.execute(
                "SELECT 1 FROM sales_invoices WHERE shipment_id = ?",
                (int(shipment_id),),
            ).fetchone() is not None:
                raise ValueError("Bu irsaliye daha önce faturalanmış.")
            totals = connection.execute(
                """
                SELECT COALESCE(SUM(pl.net_kg), 0) AS net_kg,
                       COALESCE(SUM(pl.net_kg * sol.unit_price), 0) AS unit_total
                FROM shipment_lines sl
                JOIN package_lines pl ON pl.package_id = sl.package_id
                JOIN sales_order_lines sol ON sol.id = pl.sales_order_line_id
                WHERE sl.shipment_id = ?
                """,
                (int(shipment_id),),
            ).fetchone()
            net_kg = float(totals["net_kg"] or 0)
            rate = max(0.0, self._number(exchange_rate))
            if mode == "LME + PRİM":
                total_usd = net_kg / 1000.0 * (
                    self._number(lme_usd_ton) + self._number(premium_usd_ton)
                )
                total = total_usd if currency.strip().upper() == "USD" else total_usd * rate
            else:
                total = float(totals["unit_total"] or 0)
            invoice_no = self._next_no(connection, "FAT")
            cursor = connection.execute(
                """
                INSERT INTO sales_invoices(
                    organization_id, shipment_id, invoice_no, invoice_date,
                    currency, exchange_rate, lme_usd_ton, premium_usd_ton,
                    pricing_mode, total_amount, status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'TASLAK', ?)
                """,
                (
                    self.organization_id(connection), int(shipment_id), invoice_no,
                    invoice_date, currency.strip().upper(), rate,
                    self._number(lme_usd_ton), self._number(premium_usd_ton),
                    mode, total, username,
                ),
            )
            invoice_id = int(cursor.lastrowid)
            self._audit(
                connection,
                username=username,
                action="INVOICE",
                entity_type="SHIPMENT",
                entity_id=int(shipment_id),
                record_key=invoice_no,
                after={"invoice_id": invoice_id, "pricing_mode": mode, "total": total},
            )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="INVOICE",
                entity_id=invoice_id,
                record_key=invoice_no,
                after={
                    "shipment_id": int(shipment_id),
                    "pricing_mode": mode,
                    "total": total,
                },
            )
            connection.commit()
            return invoice_id

    def update_work_order_priority(
        self,
        work_order_ids: Iterable[int],
        priority: int,
        *,
        username: str,
    ) -> None:
        selected = list(dict.fromkeys(int(value) for value in work_order_ids))
        if not selected:
            raise ValueError("Önceliği değiştirilecek iş emri seçilmedi.")
        normalized = max(1, min(999, int(priority)))
        with closing(self.connect()) as connection:
            placeholders = ",".join("?" for _ in selected)
            connection.execute(
                f"UPDATE work_orders SET priority = ?, row_version = row_version + 1 WHERE id IN ({placeholders})",
                (normalized, *selected),
            )
            for work_order_id in selected:
                self._audit(
                    connection,
                    username=username,
                    action="PRIORITY",
                    entity_type="WORK_ORDER",
                    entity_id=work_order_id,
                    after={"priority": normalized},
                )
            connection.commit()

    def list_production_entries(self, work_order_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pe.*, wo.work_order_no, wo.operation, wo.station
                FROM production_entries pe
                JOIN work_orders wo ON wo.id = pe.work_order_id
                WHERE pe.work_order_id = ?
                ORDER BY pe.id DESC
                """,
                (int(work_order_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_stock_movements(
        self,
        *,
        sales_order_line_id: int | None = None,
        work_order_id: int | None = None,
        movement_types: Iterable[str] | None = None,
        stock_item_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["sm.organization_id = ?"]
        parameters: list[object] = []
        with closing(self.connect()) as connection:
            parameters.append(self.organization_id(connection))
            if sales_order_line_id is not None:
                conditions.append("sm.sales_order_line_id = ?")
                parameters.append(int(sales_order_line_id))
            if work_order_id is not None:
                conditions.append("sm.work_order_id = ?")
                parameters.append(int(work_order_id))
            if stock_item_id is not None:
                conditions.append("sm.stock_item_id = ?")
                parameters.append(int(stock_item_id))
            if movement_types is not None:
                types = [str(value).strip().upper() for value in movement_types if str(value).strip()]
                if types:
                    placeholders = ", ".join("?" for _ in types)
                    conditions.append(f"UPPER(sm.movement_type) IN ({placeholders})")
                    parameters.extend(types)
            rows = connection.execute(
                f"""
                SELECT sm.id, sm.movement_at, sm.movement_type, sm.direction,
                       sm.quantity, sm.lot_no, sm.document_no, sm.created_by,
                       si.code AS stock_code, si.name AS stock_name, si.unit,
                       w.code AS warehouse_code, w.name AS warehouse_name,
                       o.order_no, wo.work_order_no
                FROM stock_movements sm
                JOIN stock_items si ON si.id = sm.stock_item_id
                JOIN warehouses w ON w.id = sm.warehouse_id
                LEFT JOIN sales_order_lines sol ON sol.id = sm.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = sol.sales_order_id
                LEFT JOIN work_orders wo ON wo.id = sm.work_order_id
                WHERE {' AND '.join(conditions)}
                ORDER BY sm.id DESC
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_warehouse_balances(self) -> list[dict[str, Any]]:
        """Return the live lot balance produced by the immutable movement ledger.

        ``Ambar Yükleri`` screen is a balance view, not a second stock
        table.  Keeping the same rule here prevents package, weighing-list and
        shipment screens from drifting away from the movement history.
        """
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                WITH balances AS (
                    SELECT MIN(sm.id) AS id,
                           w.code AS warehouse_code, w.name AS warehouse_name,
                           w.warehouse_type,
                           si.code AS stock_code, si.name AS stock_name,
                           si.stock_group, si.unit, si.minimum_quantity,
                           COALESCE(p.profile_code, '') AS profile_code,
                           COALESCE(p.profile_group, '') AS sub_group,
                           COALESCE(p.unit_weight_kg_m, 0) AS real_weight_kg_m,
                           COALESCE(l.production_length_mm, 0) AS production_length_mm,
                           COALESCE(l.stock_length_mm, 0) AS stock_length_mm,
                           COALESCE(l.surface, '') AS surface,
                           COALESCE(l.color, '') AS color,
                           COALESCE(l.temper, p.temper, '') AS temper,
                           COALESCE(l.alloy, p.alloy, '') AS alloy,
                           COALESCE(o.order_no, '') AS order_no,
                           COALESCE(l.line_no, 0) AS order_line_no,
                           COALESCE(c.name, '') AS customer_name,
                           sm.lot_no,
                           SUM(sm.direction * sm.quantity) AS balance,
                           MAX(sm.movement_at) AS last_movement_at,
                           COUNT(*) AS movement_count
                    FROM stock_movements sm
                    JOIN warehouses w ON w.id = sm.warehouse_id
                    JOIN stock_items si ON si.id = sm.stock_item_id
                    LEFT JOIN profiles p ON p.id = si.profile_id
                    LEFT JOIN sales_order_lines l ON l.id = sm.sales_order_line_id
                    LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                    LEFT JOIN customers c ON c.id = o.customer_id
                    WHERE sm.organization_id = ?
                    GROUP BY w.id, w.code, w.name, w.warehouse_type,
                             si.id, si.code, si.name, si.stock_group, si.unit,
                             si.minimum_quantity, p.profile_code, p.profile_group,
                             p.unit_weight_kg_m, p.temper, p.alloy,
                             l.id, l.production_length_mm, l.stock_length_mm,
                             l.surface, l.color, l.temper, l.alloy,
                             o.order_no, l.line_no, c.name, sm.lot_no
                    HAVING ABS(SUM(sm.direction * sm.quantity)) > 0.0005
                )
                SELECT balances.*,
                       '' AS selected, '' AS image_path,
                       CASE
                         WHEN unit = 'ADET' THEN balance
                         WHEN real_weight_kg_m > 0 AND production_length_mm > 0
                           THEN balance / real_weight_kg_m / (production_length_mm / 1000.0)
                         ELSE 0
                       END AS quantity,
                       CASE
                         WHEN unit IN ('M', 'METRE') THEN balance
                         WHEN real_weight_kg_m > 0 THEN balance / real_weight_kg_m
                         ELSE 0
                       END AS metre,
                       CASE WHEN order_no <> ''
                         THEN printf('%s-%d', order_no, order_line_no)
                         ELSE '' END AS order_ref,
                       CASE WHEN order_no <> ''
                         THEN printf('%s / %s', order_no, stock_code)
                         ELSE '' END AS order_stock,
                       CAST(MAX(0, julianday('now') - julianday(last_movement_at)) AS INTEGER)
                         AS days_since_last_movement
                FROM balances
                ORDER BY warehouse_name, stock_code, lot_no, order_ref
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_die_movement(
        self,
        die_id: int,
        *,
        movement_type: str,
        username: str,
        company: str = "",
        quantity: float = 0,
        unit: str = "ADET",
        location_to: str = "",
        note: str = "",
    ) -> int:
        movement = movement_type.strip().upper()
        if not movement:
            raise ValueError("Kalıp hareket tipi boş bırakılamaz.")
        # Eski menü etiketlerini standart adına çevir
        aliases = {
            "TENEFERE GÖNDER": "TENEFER GİTTİ",
            "TENEFERDEN GELDİ": "TENEFER GELDİ",
        }
        movement = aliases.get(movement, movement)
        if movement == "TENEFER GİTTİ":
            return self.send_die_to_tenefer(
                die_id, company=company or location_to, username=username, note=note,
            )
        if movement == "TENEFER GELDİ":
            raise ValueError(
                "Tenefer gelişi için yeni tenefer numarası gerekir. "
                "Kalıp kartından 'TENEFER GELDİ' menüsünü kullanın."
            )
        with closing(self.connect()) as connection:
            die = connection.execute(
                "SELECT id, location, status FROM dies WHERE id = ?",
                (int(die_id),),
            ).fetchone()
            if die is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            target = location_to.strip().upper() or str(die["location"])
            cursor = connection.execute(
                """
                INSERT INTO die_movements(
                    organization_id, die_id, movement_type, company, quantity,
                    unit, location_from, location_to, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection), int(die_id), movement,
                    company.strip(), self._number(quantity), unit.strip().upper(),
                    str(die["location"]), target, note.strip(), username,
                ),
            )
            new_status = None
            if movement in {"BAKIMA GÖNDER", "REVİZYON"}:
                new_status = "BAKIMDA" if movement.startswith("BAKIM") else "REVİZYON"
            elif movement in {"BAKIMDAN GELDİ", "REVİZYONDAN GELDİ"}:
                new_status = "ARŞİVDE"
            elif movement == "HURDA":
                new_status = "HURDA"
            elif movement == "İMALATA VER":
                new_status = "İMALATTA"
            sets = ["location = ?", "row_version = row_version + 1"]
            params: list[object] = [target]
            if new_status:
                sets.append("status = ?")
                params.append(new_status)
            params.append(int(die_id))
            connection.execute(
                f"UPDATE dies SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            movement_id = int(cursor.lastrowid)
            self._audit(
                connection,
                username=username,
                action="MOVEMENT",
                entity_type="DIE",
                entity_id=int(die_id),
                record_key=str(movement_id),
                after={"movement_type": movement, "location_to": target},
            )
            connection.commit()
            return movement_id

    def list_die_movements(
        self,
        die_id: int,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        start, end = self._date_bounds(date_from, date_to)
        clauses = ["dm.die_id = ?"]
        params: list[object] = [int(die_id)]
        moved_at = "REPLACE(dm.movement_at, 'T', ' ')"
        if start:
            clauses.append(f"{moved_at} >= ?")
            params.append(start)
        if end:
            clauses.append(f"{moved_at} <= ?")
            params.append(end)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT dm.*, {moved_at} AS record_date, d.die_code, d.spare_no
                FROM die_movements dm
                JOIN dies d ON d.id = dm.die_id
                WHERE {' AND '.join(clauses)}
                ORDER BY dm.id DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def _handle_length_deviation(
        self,
        connection: sqlite3.Connection,
        *,
        work: dict[str, Any],
        line: dict[str, Any],
        production: dict[str, Any],
        result_length_mm: float,
        produced_quantity: float,
        username: str,
    ) -> int | None:
        """Sipariş boyundan farklı pres çıkışında devam iş emri zincirini günceller."""
        ordered_length = float(
            work.get("production_length_mm") or line.get("production_length_mm") or 0
        )
        actual_length = float(result_length_mm or 0)
        if ordered_length <= 0 or actual_length <= 0:
            return None
        if abs(actual_length - ordered_length) <= 1.0:
            return None
        connection.execute(
            """
            UPDATE work_orders
            SET production_length_mm = ?, row_version = row_version + 1
            WHERE id = ?
            """,
            (actual_length, int(work["id"])),
        )
        connection.execute(
            """
            UPDATE production_orders
            SET actual_length_mm = ?, row_version = row_version + 1
            WHERE id = ?
            """,
            (actual_length, int(production["id"])),
        )
        length_ratio = actual_length / ordered_length
        subsequent = connection.execute(
            """
            SELECT id, planned_quantity, planned_kg, planned_metre, sequence_no,
                   operation, status
            FROM work_orders
            WHERE production_order_id = ? AND sequence_no > ?
              AND status IN ('BEKLİYOR', 'HAZIR')
            ORDER BY sequence_no
            """,
            (int(work["production_order_id"]), int(work["sequence_no"])),
        ).fetchall()
        continuation_id: int | None = None
        for row in subsequent:
            new_metre = float(row["planned_metre"] or 0) * length_ratio
            new_kg = float(row["planned_kg"] or 0) * length_ratio
            connection.execute(
                """
                UPDATE work_orders
                SET production_length_mm = ?,
                    planned_metre = ?,
                    planned_kg = ?,
                    parent_work_order_id = COALESCE(parent_work_order_id, ?),
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (
                    actual_length,
                    new_metre,
                    new_kg,
                    int(work["id"]),
                    int(row["id"]),
                ),
            )
            continuation_id = int(row["id"])
        remaining_qty = max(
            0.0,
            float(work["planned_quantity"] or 0) - float(produced_quantity or 0),
        )
        if remaining_qty > 0.001 and continuation_id is None:
            continuation_id = self._create_length_continuation_batch(
                connection,
                work=work,
                line=line,
                production=production,
                actual_length_mm=actual_length,
                remaining_quantity=remaining_qty,
                username=username,
            )
        self._audit(
            connection,
            username=username,
            action="LENGTH_CONTINUATION",
            entity_type="WORK_ORDER",
            entity_id=int(work["id"]),
            record_key=str(work["work_order_no"]),
            after={
                "ordered_length_mm": ordered_length,
                "actual_length_mm": actual_length,
                "continuation_work_order_id": continuation_id,
                "updated_downstream": len(subsequent),
            },
        )
        return continuation_id

    def _create_length_continuation_batch(
        self,
        connection: sqlite3.Connection,
        *,
        work: dict[str, Any],
        line: dict[str, Any],
        production: dict[str, Any],
        actual_length_mm: float,
        remaining_quantity: float,
        username: str,
    ) -> int | None:
        """Kısmi pres üretiminde farklı boy için devam üretim partisi açar."""
        steps = connection.execute(
            """
            SELECT wo.* FROM work_orders wo
            WHERE wo.production_order_id = ? AND wo.sequence_no >= ?
            ORDER BY wo.sequence_no
            """,
            (int(work["production_order_id"]), int(work["sequence_no"])),
        ).fetchall()
        if not steps:
            return None
        batch_no = int(
            connection.execute(
                """
                SELECT COALESCE(MAX(batch_no), 0) + 1
                FROM production_orders WHERE sales_order_line_id = ?
                """,
                (int(line["id"]),),
            ).fetchone()[0]
        )
        production_no = self._next_no(connection, "UE")
        remaining_kg = remaining_quantity * (
            float(line["ordered_kg"] or 0)
            / max(1.0, float(line["ordered_quantity"] or 1))
        )
        cursor = connection.execute(
            """
            INSERT INTO production_orders(
                organization_id, sales_order_line_id, route_id, recipe_id,
                batch_no, production_order_no, planned_quantity, planned_kg,
                actual_length_mm, parent_production_order_id, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(production["organization_id"]),
                int(line["id"]),
                int(production["route_id"]),
                int(production["recipe_id"]),
                batch_no,
                production_no,
                remaining_quantity,
                remaining_kg,
                actual_length_mm,
                int(production["id"]),
                username,
            ),
        )
        new_production_id = int(cursor.lastrowid)
        first_continuation: int | None = None
        for index, step in enumerate(steps):
            factor = float(step["quantity_factor"] or 1)
            work_no = self._next_no(connection, "IE")
            cursor = connection.execute(
                """
                INSERT INTO work_orders(
                    production_order_id, route_step_id, recipe_line_id,
                    work_order_no, sequence_no, operation, station,
                    planned_quantity, planned_kg, planned_metre,
                    quantity_factor, status, production_length_mm,
                    parent_work_order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_production_id,
                    int(step["route_step_id"]),
                    step["recipe_line_id"],
                    work_no,
                    int(step["sequence_no"]),
                    str(step["operation"]),
                    str(step["station"]),
                    remaining_quantity * factor,
                    remaining_kg * factor,
                    remaining_quantity * (actual_length_mm / 1000.0) * factor,
                    factor,
                    "HAZIR" if index == 0 else "BEKLİYOR",
                    actual_length_mm,
                    int(work["id"]),
                ),
            )
            if index == 0:
                first_continuation = int(cursor.lastrowid)
        return first_continuation

    def list_all_die_movements(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT dm.id, dm.movement_at AS record_date, dm.movement_type,
                       dm.company, dm.quantity, dm.unit,
                       dm.location_from, dm.location_to, dm.note,
                       dm.created_by, d.die_code, d.spare_no, p.profile_code,
                       d.status
                FROM die_movements dm
                JOIN dies d ON d.id = dm.die_id
                JOIN profiles p ON p.id = d.profile_id
                WHERE dm.organization_id = ?
                ORDER BY dm.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ---- KALIP KART veri kümesi ---------------------------------------
    #
    # Kalıp kartının alt sekmeleri tek bir kalıp kimliği etrafında bağlıdır:
    # kalıp → pres fişleri → iş emri → sipariş satırı → müşteri ve stok
    # hareketi. Aşağıdaki sorgular bu zinciri kartın her sekmesi için aynı
    # kalıp kimliğinden kurar.

    TENEFER_OPERATOR_LABELS = {1: "EŞİTTİR", 2: "BÜYÜKTÜR", 3: "KÜÇÜKTÜR"}

    # Fişin başlangıç saati ISO ('2026-08-11T09:30') ya da boş gelebilir; metin
    # karşılaştırması yapılacağı için ayraç boşluğa çevrilir ve boş değer
    # kayıt zamanına düşer.
    _ENTRY_DATE = (
        "COALESCE(NULLIF(REPLACE(pe.started_at, 'T', ' '), ''), pe.created_at)"
    )

    @staticmethod
    def _date_bounds(
        date_from: str | None, date_to: str | None
    ) -> tuple[str | None, str | None]:
        """Gün bazlı aralığı saat içeren metin damgalarıyla karşılaştırılır kılar."""
        start = f"{date_from} 00:00:00" if date_from else None
        end = f"{date_to} 23:59:59" if date_to else None
        return start, end

    def die_card_header(self, die_id: int) -> dict[str, Any]:
        """Kalıp kartı başlığı: profil, kalıp ömrü ve üretim toplamları."""
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT d.*, p.profile_code, p.profile_name, p.profile_group,
                       p.unit_weight_kg_m, p.perimeter_mm, p.area_mm2,
                       p.alloy, p.temper, p.created_at AS profile_created_at,
                       c.name AS owner_customer_name
                FROM dies d
                JOIN profiles p ON p.id = d.profile_id
                LEFT JOIN customers c ON c.id = p.customer_id
                WHERE d.id = ? AND d.organization_id = ?
                """,
                (int(die_id), self.organization_id(connection)),
            ).fetchone()
            if row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            totals = connection.execute(
                """
                SELECT COALESCE(SUM(gross_kg), 0) AS total_gross_kg,
                       COALESCE(SUM(net_kg), 0) AS total_net_kg,
                       COALESCE(SUM(metre), 0) AS total_metre,
                       COUNT(*) AS total_usage,
                       COALESCE(SUM(
                           CASE WHEN entry_type LIKE '%TEST%'
                                  OR production_type LIKE '%TEST%'
                                THEN 1 ELSE 0 END
                       ), 0) AS test_count,
                       COALESCE(SUM(
                           CASE WHEN test_result = 'BAŞARILI' THEN 1 ELSE 0 END
                       ), 0) AS test_pass_count,
                       COALESCE(SUM(
                           CASE WHEN test_result = 'BAŞARISIZ' THEN 1 ELSE 0 END
                       ), 0) AS test_fail_count
                FROM production_entries
                WHERE die_id = ?
                """,
                (int(die_id),),
            ).fetchone()
        values = self._enrich_die_dict(dict(row))
        values.update(dict(totals))
        values["is_customer_specific"] = 1 if values.get("owner_customer_name") else 0
        # Kart, limiti aşan teneferi eksi kalanla gösterir; listelerde kullanılan
        # sıfıra kırpılmış değer olduğu gibi kalır.
        values["tenefer_remaining_signed_m"] = (
            float(values.get("tenefer_limit_m") or 0)
            - float(values.get("tenefer_used_m") or 0)
        )
        return values

    def list_die_press_entries(
        self,
        die_id: int,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Kalıbın pres üretim fişleri — sipariş ve müşteriye kadar bağlı."""
        start, end = self._date_bounds(date_from, date_to)
        clauses = ["pe.die_id = ?"]
        params: list[object] = [int(die_id)]
        if start:
            clauses.append(f"{self._ENTRY_DATE} >= ?")
            params.append(start)
        if end:
            clauses.append(f"{self._ENTRY_DATE} <= ?")
            params.append(end)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT pe.id, pe.slip_no,
                       {self._ENTRY_DATE} AS record_date,
                       pe.entry_type, pe.production_type,
                       COALESCE(NULLIF(pe.press_status, ''), wo.status)
                           AS press_status,
                       COALESCE(NULLIF(pe.saw_status, ''), wo.status)
                           AS saw_status,
                       pe.operator_username, pe.shift,
                       pe.quantity, pe.gross_kg, pe.net_kg, pe.scrap_kg,
                       pe.metre, pe.fire_pct, pe.lot_no, pe.tenefer_no,
                       pe.test_result, pe.die_problem, pe.die_problem_note,
                       pe.spare_no, pe.figure_count, pe.result_length_mm,
                       pe.duration_min, pe.preparation_min, pe.qc_username,
                       wo.work_order_no, wo.station, wo.operation,
                       po.production_order_no,
                       printf('%s-%d', o.order_no, l.line_no) AS order_ref,
                       o.order_no, l.line_no, l.surface,
                       c.name AS customer_name, p.profile_code, p.profile_name
                FROM production_entries pe
                JOIN work_orders wo ON wo.id = pe.work_order_id
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                WHERE {' AND '.join(clauses)}
                ORDER BY pe.id DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def is_test_press_entry(entry: dict[str, Any]) -> bool:
        """Test üretimi alt sekmesi fiş tipi ya da üretim tipinden ayrışır."""
        haystack = " ".join(
            str(entry.get(key) or "")
            for key in ("entry_type", "production_type", "test_result")
        ).upper()
        return "TEST" in haystack

    def die_card_tenefer_life(self, die_id: int) -> dict[str, list[dict[str, Any]]]:
        """Tenefer sekmesinin iki gridi: ömür tanımları ve güncel kullanım."""
        with closing(self.connect()) as connection:
            die = connection.execute(
                "SELECT * FROM dies WHERE id = ?", (int(die_id),)
            ).fetchone()
            if die is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            standards = connection.execute(
                """
                SELECT tenefer_no, operator_no, limit_m
                FROM tenefer_life_standards
                ORDER BY tenefer_no, operator_no
                """
            ).fetchall()
            overrides = connection.execute(
                """
                SELECT tenefer_no, operator_no, limit_m
                FROM tenefer_life_limits
                WHERE die_id = ?
                ORDER BY tenefer_no, operator_no
                """,
                (int(die_id),),
            ).fetchall()
        definitions: dict[tuple[int, int], dict[str, Any]] = {}
        for source, is_override in ((standards, False), (overrides, True)):
            for row in source:
                key = (int(row["tenefer_no"]), int(row["operator_no"]))
                definitions[key] = {
                    "tenefer_no": int(row["tenefer_no"]),
                    "operator_no": int(row["operator_no"]),
                    "operator_label": self.TENEFER_OPERATOR_LABELS.get(
                        int(row["operator_no"]), str(row["operator_no"])
                    ),
                    "limit_m": float(row["limit_m"]),
                    "source": "KALIP" if is_override else "STANDART",
                }
        die_values = dict(die)
        limit_m = float(die_values.get("tenefer_limit_m") or 0)
        used_m = float(die_values.get("tenefer_used_m") or 0)
        usage = [
            {
                "tenefer_no": str(die_values.get("tenefer_no") or ""),
                "tenefer_type": str(die_values.get("tenefer_type") or ""),
                "limit_m": limit_m,
                "used_m": used_m,
                "remaining_m": limit_m - used_m,
                "usage_pct": round(used_m / limit_m * 100.0, 1) if limit_m > 0 else 0.0,
            }
        ] if str(die_values.get("tenefer_no") or "").strip() else []
        return {
            "definitions": [
                definitions[key] for key in sorted(definitions)
            ],
            "usage": usage,
        }

    def list_die_problems(
        self,
        die_id: int,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Kalıp problemleri — problem kartları ve pres fişindeki bildirimler."""
        start, end = self._date_bounds(date_from, date_to)
        with closing(self.connect()) as connection:
            card_rows = connection.execute(
                """
                SELECT problem_no, record_date, problem_type, description,
                       status, created_by
                FROM die_tooling_problems
                WHERE die_id = ? AND organization_id = ?
                ORDER BY id DESC
                """,
                (int(die_id), self.organization_id(connection)),
            ).fetchall()
            slip_rows = connection.execute(
                f"""
                SELECT pe.slip_no,
                       {self._ENTRY_DATE} AS record_date,
                       pe.die_problem, pe.die_problem_note, pe.operator_username,
                       pe.test_result, wo.station, wo.work_order_no
                FROM production_entries pe
                JOIN work_orders wo ON wo.id = pe.work_order_id
                WHERE pe.die_id = ? AND TRIM(pe.die_problem) <> ''
                ORDER BY pe.id DESC
                """,
                (int(die_id),),
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in card_rows:
            records.append({
                "problem_no": str(row["problem_no"] or ""),
                "record_date": str(row["record_date"] or ""),
                "problem_type": str(row["problem_type"] or ""),
                "description": str(row["description"] or ""),
                "status": str(row["status"] or ""),
                "source": "PROBLEM KARTI",
                "slip_no": "",
                "station": "",
                "operator_username": "",
                "created_by": str(row["created_by"] or ""),
            })
        for row in slip_rows:
            records.append({
                "problem_no": "",
                "record_date": str(row["record_date"] or ""),
                "problem_type": str(row["die_problem"] or ""),
                "description": str(row["die_problem_note"] or ""),
                "status": (
                    "TEST BAŞARISIZ" if str(row["test_result"] or "") == "BAŞARISIZ"
                    else "PRES BİLDİRİMİ"
                ),
                "source": "PRES FİŞİ",
                "slip_no": str(row["slip_no"] or ""),
                "station": str(row["station"] or ""),
                "operator_username": str(row["operator_username"] or ""),
                "created_by": str(row["operator_username"] or ""),
            })
        if start or end:
            records = [
                row for row in records
                if (not start or str(row["record_date"]) >= start)
                and (not end or str(row["record_date"]) <= end)
            ]
        records.sort(key=lambda row: str(row.get("record_date") or ""), reverse=True)
        return records

    def list_die_order_lines(self, die_id: int) -> list[dict[str, Any]]:
        """Kalıbın bağlı olduğu sipariş satırları — sipariş hareketleri gridi."""
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT l.id, o.order_no, l.line_no,
                       printf('%s-%d', o.order_no, l.line_no) AS order_ref,
                       o.order_date AS record_date, o.delivery_date,
                       o.status AS order_status, c.name AS customer_name,
                       p.profile_code, p.profile_name, l.surface, l.color,
                       l.alloy, l.temper, l.production_length_mm,
                       l.ordered_quantity, l.ordered_kg, l.produced_quantity,
                       l.produced_kg, l.shipped_quantity, l.shipped_kg,
                       l.status
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                WHERE l.die_id = ?
                ORDER BY o.id DESC, l.line_no
                """,
                (int(die_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_die_stock_movements(
        self,
        die_id: int,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Kalıpla üretilen iş emirlerinden doğan stok hareketleri."""
        start, end = self._date_bounds(date_from, date_to)
        clauses = ["l.die_id = ?"]
        params: list[object] = [int(die_id)]
        moved_at = "REPLACE(sm.movement_at, 'T', ' ')"
        if start:
            clauses.append(f"{moved_at} >= ?")
            params.append(start)
        if end:
            clauses.append(f"{moved_at} <= ?")
            params.append(end)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT sm.id, {moved_at} AS record_date, sm.movement_type,
                       sm.direction, sm.quantity, sm.lot_no, sm.document_no,
                       sm.created_by, si.code AS stock_code, si.name AS stock_name,
                       si.unit, w.code AS warehouse_code, w.name AS warehouse_name,
                       wo.work_order_no, wo.station,
                       printf('%s-%d', o.order_no, l.line_no) AS order_ref,
                       c.name AS customer_name
                FROM stock_movements sm
                JOIN stock_items si ON si.id = sm.stock_item_id
                JOIN warehouses w ON w.id = sm.warehouse_id
                LEFT JOIN work_orders wo ON wo.id = sm.work_order_id
                LEFT JOIN sales_order_lines l ON l.id = COALESCE(
                    sm.sales_order_line_id,
                    (SELECT po.sales_order_line_id FROM production_orders po
                     WHERE po.id = wo.production_order_id)
                )
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN customers c ON c.id = o.customer_id
                WHERE {' AND '.join(clauses)}
                ORDER BY sm.id DESC
                """,
                params,
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            values["direction_label"] = (
                "GİRİŞ" if int(values.get("direction") or 0) > 0 else "ÇIKIŞ"
            )
            records.append(values)
        return records

    def list_die_siblings(self, die_id: int) -> list[dict[str, Any]]:
        """Aynı profile bağlı kalıplar — kartta yedek/figür karşılaştırması."""
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT profile_id FROM dies WHERE id = ?", (int(die_id),)
            ).fetchone()
            if row is None:
                raise ValueError("Kalıp kartı bulunamadı.")
            rows = connection.execute(
                """
                SELECT d.id, d.die_code, d.spare_no, d.figure_count, d.status,
                       d.location, d.tenefer_no, d.tenefer_type,
                       d.tenefer_limit_m, d.tenefer_used_m, d.life_limit_kg,
                       d.used_kg, d.supplier_name, d.external_company,
                       d.is_external, p.profile_code, p.profile_name
                FROM dies d
                JOIN profiles p ON p.id = d.profile_id
                WHERE d.profile_id = ?
                ORDER BY d.die_code, d.spare_no
                """,
                (int(row["profile_id"]),),
            ).fetchall()
        return [self._enrich_die_dict(dict(item)) for item in rows]

    def list_dies_filtered(
        self,
        *,
        status: str | None = None,
        tenefer_near_limit: bool = False,
        scrap_only: bool = False,
    ) -> list[dict[str, Any]]:
        if scrap_only:
            with closing(self.connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT d.id, d.profile_id, d.die_code, d.spare_no,
                           d.figure_count, d.life_limit_kg, d.used_kg,
                           d.tenefer_no, d.tenefer_type, d.tenefer_limit_m,
                           d.tenefer_used_m, d.status, d.location, d.active,
                           d.external_company, d.is_external, d.supplier_name,
                           p.profile_code, p.profile_name, p.unit_weight_kg_m,
                           COALESCE((
                               SELECT dm.movement_type FROM die_movements dm
                               WHERE dm.die_id = d.id
                               ORDER BY dm.id DESC LIMIT 1
                           ), '') AS last_movement,
                           COALESCE(d.external_company, '') AS last_tenefer_company,
                           (SELECT COUNT(*) FROM attachments a
                            WHERE a.entity_type = 'DIE' AND a.entity_id = d.id
                              AND a.active = 1) AS attachment_count
                    FROM dies d
                    JOIN profiles p ON p.id = d.profile_id
                    WHERE d.organization_id = ? AND d.status = 'HURDA'
                    ORDER BY d.die_code, d.spare_no
                    """,
                    (self.organization_id(connection),),
                ).fetchall()
            return [self._enrich_die_dict(dict(row)) for row in rows]
        records = self.list_dies()
        if status:
            target = status.strip().upper()
            records = [
                row for row in records
                if str(row.get("status") or "").upper() == target
            ]
        if tenefer_near_limit:
            # "Teneferi Yaklaşanlar": kalan ömür düşük olanlar
            warning_m = 500.0
            try:
                from models.factory_config import factory_config

                warning_m = float(factory_config().tenefer_uyari_metre or 500)
            except Exception:
                warning_m = 500.0
            filtered: list[dict[str, Any]] = []
            for row in records:
                limit_m = float(row.get("tenefer_limit_m") or 0)
                remain = float(row.get("tenefer_remaining_m") or 0)
                if limit_m <= 0:
                    continue
                if remain <= warning_m or remain <= limit_m * 0.15:
                    filtered.append(dict(row))
            return filtered
        return records

    def list_all_production_entries(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pe.id, pe.slip_no, pe.created_at AS record_date, pe.entry_type,
                       pe.operator_username, pe.shift, pe.gross_kg, pe.net_kg,
                       pe.scrap_kg, pe.quantity, pe.metre, pe.lot_no,
                       pe.fire_pct, pe.tenefer_no, pe.die_problem, pe.test_result,
                       pe.production_type, pe.press_status, pe.saw_status,
                       pe.result_length_mm, pe.preparation_min, pe.duration_min,
                       pe.started_at, pe.ended_at, pe.note,
                       pe.real_weight_kg_m, pe.theoretical_weight_kg_m,
                       pe.spare_no, pe.figure_count, pe.raw_material_stock,
                       pe.die_problem_note,
                       COALESCE((
                         SELECT SUM(peb.billet_count)
                         FROM production_entry_billets peb
                         WHERE peb.production_entry_id = pe.id
                       ), pe.billet_count, 0) AS billet_count,
                       COALESCE((
                         SELECT AVG(NULLIF(peb.billet_length_mm, 0))
                         FROM production_entry_billets peb
                         WHERE peb.production_entry_id = pe.id
                       ), pe.billet_length_mm, 0) AS average_billet_length_mm,
                       COALESCE((
                         SELECT MAX(NULLIF(peb.billet_length_mm, 0))
                         FROM production_entry_billets peb
                         WHERE peb.production_entry_id = pe.id
                       ), pe.billet_length_mm, 0) AS max_billet_length_mm,
                       COALESCE((
                         SELECT MIN(NULLIF(peb.billet_length_mm, 0))
                         FROM production_entry_billets peb
                         WHERE peb.production_entry_id = pe.id
                       ), pe.billet_length_mm, 0) AS min_billet_length_mm,
                       wo.work_order_no, wo.operation, wo.station, po.production_order_no,
                       printf('%s-%d', o.order_no, l.line_no) AS order_ref,
                       c.name AS customer_name, p.profile_code,
                       l.surface, l.color,
                       COALESCE(NULLIF(c.city, ''), NULLIF(c.district, ''), '')
                           AS customer_region,
                       COALESCE(NULLIF(s.name, ''), NULLIF(d.supplier_name, ''), '')
                           AS die_supplier
                FROM production_entries pe
                JOIN work_orders wo ON wo.id = pe.work_order_id
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = COALESCE(pe.die_id, l.die_id)
                LEFT JOIN suppliers s ON s.id = d.supplier_id
                ORDER BY pe.id DESC
                """
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            net = float(values.get("net_kg") or 0)
            duration = float(values.get("duration_min") or 0)
            prep = float(values.get("preparation_min") or 0)
            effective = max(0.0, duration - prep)
            values["kg_hour"] = round(
                (net / (effective / 60.0)) if effective > 0 else 0.0, 2
            )
            values["figure_gross_metre"] = round(
                float(values.get("metre") or 0)
                * max(1, int(values.get("figure_count") or 1)),
                3,
            )
            result.append(values)
        return result

    def list_eloksal_slips(self, *, tracking_only: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            where = "WHERE es.organization_id = ?"
            params: list[object] = [self.organization_id(connection)]
            if tracking_only:
                where += " AND (es.eloksal_finished = 0 OR es.stripping_finished = 0)"
            rows = connection.execute(
                f"""
                SELECT es.id, es.slip_no, es.hanger_no, es.hanging_date AS record_date,
                       es.color_group, es.customer_name, es.profile_code,
                       es.order_color, es.eloksal_finished, es.eloksal_finished_at,
                       es.stripping_finished, es.stripping_finished_at,
                       es.hanging_quantity, es.hanging_kg, es.stripping_quantity,
                       es.stripping_kg, es.scrap_quantity, es.scrap_kg,
                       wo.work_order_no, wo.station,
                       printf('%s-%d', o.order_no, l.line_no) AS order_ref
                FROM eloksal_slips es
                LEFT JOIN work_orders wo ON wo.id = es.work_order_id
                LEFT JOIN sales_order_lines l ON l.id = es.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                {where}
                ORDER BY es.id DESC
                """,
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            values["eloksal_status"] = (
                "TAMAMLANDI" if values.get("eloksal_finished") else "BEKLİYOR"
            )
            values["stripping_status"] = (
                "TAMAMLANDI" if values.get("stripping_finished") else "BEKLİYOR"
            )
            result.append(values)
        return result

    def create_eloksal_slip(
        self,
        *,
        work_order_id: int,
        hanger_no: str = "",
        color_group: str = "",
        hanging_quantity: float = 0,
        hanging_kg: float = 0,
        username: str,
    ) -> int:
        with closing(self.connect()) as connection:
            work = connection.execute(
                """
                SELECT wo.*, l.id AS sales_order_line_id, l.surface,
                       p.profile_code, c.name AS customer_name, o.order_no, l.line_no
                FROM work_orders wo
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                WHERE wo.id = ?
                """,
                (int(work_order_id),),
            ).fetchone()
            if work is None:
                raise ValueError("İş emri bulunamadı.")
            if "ELOKSAL" not in str(work["operation"] or "").upper():
                raise ValueError("Eloksal fişi yalnız eloksal iş emirleri için açılabilir.")
            slip_no = self._next_no(connection, "ELF")
            cursor = connection.execute(
                """
                INSERT INTO eloksal_slips(
                    organization_id, slip_no, hanger_no, hanging_date,
                    color_group, work_order_id, sales_order_line_id,
                    customer_name, profile_code, order_color,
                    hanging_quantity, hanging_kg, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    slip_no,
                    hanger_no.strip(),
                    self._now()[:10],
                    color_group.strip(),
                    int(work_order_id),
                    int(work["sales_order_line_id"]),
                    str(work["customer_name"]),
                    str(work["profile_code"]),
                    str(work["surface"] or ""),
                    self._number(hanging_quantity),
                    self._number(hanging_kg),
                    username,
                ),
            )
            slip_id = int(cursor.lastrowid)
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="ELOKSAL_SLIP",
                entity_id=slip_id,
                record_key=slip_no,
                after={"work_order_id": work_order_id},
            )
            connection.commit()
            return slip_id

    def complete_eloksal_step(
        self,
        slip_id: int,
        *,
        step: str,
        quantity: float = 0,
        kg: float = 0,
        scrap_quantity: float = 0,
        scrap_kg: float = 0,
        username: str,
    ) -> None:
        step_key = step.strip().upper()
        if step_key not in {"ELOKSAL", "SÖKME", "SOKME"}:
            raise ValueError("Adım ELOKSAL veya SÖKME olmalıdır.")
        with closing(self.connect()) as connection:
            slip = connection.execute(
                "SELECT * FROM eloksal_slips WHERE id = ?",
                (int(slip_id),),
            ).fetchone()
            if slip is None:
                raise ValueError("Eloksal fişi bulunamadı.")
            now = self._now()
            if step_key == "ELOKSAL":
                connection.execute(
                    """
                    UPDATE eloksal_slips
                    SET eloksal_finished = 1, eloksal_finished_at = ?,
                        hanging_quantity = CASE WHEN ? > 0 THEN ? ELSE hanging_quantity END,
                        hanging_kg = CASE WHEN ? > 0 THEN ? ELSE hanging_kg END,
                        row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (
                        now,
                        self._number(quantity), self._number(quantity),
                        self._number(kg), self._number(kg),
                        int(slip_id),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE eloksal_slips
                    SET stripping_finished = 1, stripping_finished_at = ?,
                        stripping_quantity = ?, stripping_kg = ?,
                        scrap_quantity = ?, scrap_kg = ?,
                        row_version = row_version + 1
                    WHERE id = ?
                    """,
                    (
                        now,
                        self._number(quantity),
                        self._number(kg),
                        self._number(scrap_quantity),
                        self._number(scrap_kg),
                        int(slip_id),
                    ),
                )
            connection.commit()

    def list_downtime_events(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, reason, sub_reason, started_at AS record_date,
                       ended_at, duration_min, operation, station,
                       station_section, status, has_downtime, note, created_by
                FROM downtime_events
                WHERE organization_id = ?
                ORDER BY id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_downtime_event(
        self,
        *,
        reason: str,
        sub_reason: str = "",
        operation: str = "",
        station: str = "",
        station_section: str = "",
        note: str = "",
        username: str,
    ) -> int:
        if not reason.strip():
            raise ValueError("Duruş sebebi zorunludur.")
        with closing(self.connect()) as connection:
            now = self._now()
            cursor = connection.execute(
                """
                INSERT INTO downtime_events(
                    organization_id, reason, sub_reason, started_at,
                    operation, station, station_section, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    reason.strip(),
                    sub_reason.strip(),
                    now,
                    operation.strip().upper(),
                    station.strip().upper(),
                    station_section.strip(),
                    note.strip(),
                    username,
                ),
            )
            event_id = int(cursor.lastrowid)
            connection.commit()
            return event_id

    def close_downtime_event(self, event_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM downtime_events WHERE id = ?",
                (int(event_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Duruş kaydı bulunamadı.")
            if row["ended_at"]:
                raise ValueError("Duruş kaydı zaten kapatılmış.")
            ended = self._now()
            started = datetime.fromisoformat(str(row["started_at"]))
            ended_dt = datetime.fromisoformat(ended)
            duration = max(0.0, (ended_dt - started).total_seconds() / 60.0)
            connection.execute(
                """
                UPDATE downtime_events
                SET ended_at = ?, duration_min = ?, status = 'KAPALI',
                    row_version = row_version + 1
                WHERE id = ?
                """,
                (ended, duration, int(event_id)),
            )
            connection.commit()

    def list_maintenance_orders(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            where = "WHERE mo.organization_id = ?"
            params: list[object] = [self.organization_id(connection)]
            if pending_only:
                where += " AND mo.status IN ('BEKLİYOR', 'PLANLANDI', 'AÇIK')"
            rows = connection.execute(
                f"""
                SELECT mo.id, mo.order_no, mo.order_type, mo.name,
                       mo.description, mo.status, mo.operation, mo.station,
                       mo.station_section, mo.order_date AS record_date,
                       mo.downtime_note, mo.planned_start, mo.planned_end,
                       mo.actual_start, mo.actual_end, mo.compliance_pct,
                       mo.created_by
                FROM maintenance_orders mo
                {where}
                ORDER BY mo.id DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def create_maintenance_order(
        self,
        *,
        order_type: str,
        name: str,
        operation: str = "",
        station: str = "",
        station_section: str = "",
        description: str = "",
        planned_start: str = "",
        planned_end: str = "",
        username: str,
    ) -> int:
        if not name.strip():
            raise ValueError("Bakım adı zorunludur.")
        with closing(self.connect()) as connection:
            order_no = self._next_no(connection, "BKM")
            cursor = connection.execute(
                """
                INSERT INTO maintenance_orders(
                    organization_id, order_no, order_type, name, description,
                    operation, station, station_section, order_date,
                    planned_start, planned_end, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    order_no,
                    order_type.strip().upper(),
                    name.strip(),
                    description.strip(),
                    operation.strip().upper(),
                    station.strip().upper(),
                    station_section.strip(),
                    self._now()[:10],
                    planned_start or None,
                    planned_end or None,
                    username,
                ),
            )
            order_id = int(cursor.lastrowid)
            connection.commit()
            return order_id

    def list_maintenance_instructions(
        self, *, include_inactive: bool = True
    ) -> list[dict[str, Any]]:
        clause = "" if include_inactive else " AND active = 1"
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, instruction_no, instruction_type, name, description,
                       operation, station, period_days, active, created_by,
                       created_at AS record_date
                FROM maintenance_instructions
                WHERE organization_id = ?{clause}
                ORDER BY id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def maintenance_instruction(self, instruction_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT id, instruction_no, instruction_type, name, description,
                       operation, station, period_days, active, created_by,
                       created_at AS record_date
                FROM maintenance_instructions
                WHERE id = ? AND organization_id = ?
                """,
                (int(instruction_id), self.organization_id(connection)),
            ).fetchone()
        if row is None:
            raise ValueError("Bakım talimatı bulunamadı.")
        return dict(row)

    MAINTENANCE_INSTRUCTION_TYPES = ("PERİYODİK", "ÖNLEYİCİ", "KESTİRİMCİ", "ARİZİ")

    def _validated_instruction_fields(
        self,
        *,
        instruction_type: str,
        name: str,
        period_days: int,
    ) -> tuple[str, str, int]:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Bakım talimatı adı zorunludur.")
        kind = instruction_type.strip().upper()
        if kind not in self.MAINTENANCE_INSTRUCTION_TYPES:
            allowed = ", ".join(self.MAINTENANCE_INSTRUCTION_TYPES)
            raise ValueError(f"Bakım talimatı tipi şunlardan biri olmalıdır: {allowed}.")
        period = int(period_days)
        if period < 0:
            raise ValueError("Bakım periyodu negatif olamaz.")
        if kind == "PERİYODİK" and period <= 0:
            raise ValueError("Periyodik talimatlarda gün cinsinden periyot zorunludur.")
        return kind, normalized_name, period

    def create_maintenance_instruction(
        self,
        *,
        instruction_type: str,
        name: str,
        description: str = "",
        operation: str = "",
        station: str = "",
        period_days: int = 0,
        active: bool = True,
        username: str,
    ) -> int:
        kind, normalized_name, period = self._validated_instruction_fields(
            instruction_type=instruction_type, name=name, period_days=period_days
        )
        with closing(self.connect()) as connection:
            instruction_no = self._next_no(connection, "BT")
            cursor = connection.execute(
                """
                INSERT INTO maintenance_instructions(
                    organization_id, instruction_no, instruction_type, name,
                    description, operation, station, period_days, active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    instruction_no,
                    kind,
                    normalized_name,
                    description.strip(),
                    operation.strip().upper(),
                    station.strip().upper(),
                    period,
                    1 if active else 0,
                    username,
                ),
            )
            instruction_id = int(cursor.lastrowid)
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="maintenance_instruction", entity_id=instruction_id,
                record_key=instruction_no,
                after={"name": normalized_name, "type": kind, "period_days": period},
            )
            connection.commit()
        return instruction_id

    def update_maintenance_instruction(
        self,
        instruction_id: int,
        *,
        instruction_type: str,
        name: str,
        description: str = "",
        operation: str = "",
        station: str = "",
        period_days: int = 0,
        active: bool = True,
        username: str,
    ) -> None:
        kind, normalized_name, period = self._validated_instruction_fields(
            instruction_type=instruction_type, name=name, period_days=period_days
        )
        before = self.maintenance_instruction(int(instruction_id))
        with closing(self.connect()) as connection:
            connection.execute(
                """
                UPDATE maintenance_instructions
                SET instruction_type = ?, name = ?, description = ?,
                    operation = ?, station = ?, period_days = ?, active = ?,
                    row_version = row_version + 1
                WHERE id = ? AND organization_id = ?
                """,
                (
                    kind,
                    normalized_name,
                    description.strip(),
                    operation.strip().upper(),
                    station.strip().upper(),
                    period,
                    1 if active else 0,
                    int(instruction_id),
                    self.organization_id(connection),
                ),
            )
            self._audit(
                connection, username=username, action="UPDATE",
                entity_type="maintenance_instruction", entity_id=int(instruction_id),
                record_key=str(before.get("instruction_no") or ""),
                before={
                    "name": before.get("name"),
                    "type": before.get("instruction_type"),
                    "period_days": before.get("period_days"),
                    "active": before.get("active"),
                },
                after={
                    "name": normalized_name, "type": kind,
                    "period_days": period, "active": 1 if active else 0,
                },
            )
            connection.commit()

    def set_maintenance_instruction_active(
        self, instruction_id: int, active: bool, *, username: str
    ) -> None:
        before = self.maintenance_instruction(int(instruction_id))
        with closing(self.connect()) as connection:
            connection.execute(
                """
                UPDATE maintenance_instructions
                SET active = ?, row_version = row_version + 1
                WHERE id = ? AND organization_id = ?
                """,
                (
                    1 if active else 0,
                    int(instruction_id),
                    self.organization_id(connection),
                ),
            )
            self._audit(
                connection, username=username,
                action="ACTIVATE" if active else "DEACTIVATE",
                entity_type="maintenance_instruction", entity_id=int(instruction_id),
                record_key=str(before.get("instruction_no") or ""),
                before={"active": before.get("active")},
                after={"active": 1 if active else 0},
            )
            connection.commit()

    def create_maintenance_order_from_instruction(
        self, instruction_id: int, *, planned_start: str = "", username: str
    ) -> int:
        """Talimatı iş listesine alır: periyoda göre bakım emri açar."""
        instruction = self.maintenance_instruction(int(instruction_id))
        if not int(instruction.get("active") or 0):
            raise ValueError("Pasif bakım talimatından bakım emri açılamaz.")
        start = planned_start.strip() or self._now()[:10]
        period = int(instruction.get("period_days") or 0)
        planned_end = ""
        if period > 0:
            planned_end = (
                datetime.fromisoformat(start) + timedelta(days=period)
            ).date().isoformat()
        return self.create_maintenance_order(
            order_type=str(instruction.get("instruction_type") or "PERİYODİK"),
            name=str(instruction.get("name") or ""),
            description=str(instruction.get("description") or ""),
            operation=str(instruction.get("operation") or ""),
            station=str(instruction.get("station") or ""),
            planned_start=start,
            planned_end=planned_end,
            username=username,
        )

    def list_purchase_invoices(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pi.id, pi.invoice_no, pi.invoice_date AS record_date,
                       pi.due_date, pi.subtotal, pi.tax_amount, pi.total_amount,
                       pi.currency, pi.exchange_rate, pi.status, pi.note,
                       s.name AS supplier_name,
                       po.purchase_order_no, gr.receipt_no AS goods_receipt_no
                FROM purchase_invoices pi
                JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN purchase_orders po ON po.id = pi.purchase_order_id
                LEFT JOIN goods_receipts gr ON gr.id = pi.goods_receipt_id
                WHERE pi.organization_id = ?
                ORDER BY pi.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_purchase_invoice_from_receipt(
        self,
        goods_receipt_id: int,
        *,
        username: str,
    ) -> int:
        with closing(self.connect()) as connection:
            receipt = connection.execute(
                """
                SELECT gr.*, po.id AS purchase_order_id, po.supplier_id,
                       po.currency
                FROM goods_receipts gr
                JOIN purchase_orders po ON po.id = gr.purchase_order_id
                WHERE gr.id = ?
                """,
                (int(goods_receipt_id),),
            ).fetchone()
            if receipt is None:
                raise ValueError("Mal kabul fişi bulunamadı.")
            existing = connection.execute(
                "SELECT id FROM purchase_invoices WHERE goods_receipt_id = ?",
                (int(goods_receipt_id),),
            ).fetchone()
            if existing is not None:
                raise ValueError("Bu mal kabul fişi için fatura zaten oluşturulmuş.")
            # Fatura yalnız bu mal kabulünde teslim alınan miktarlar üzerinden kesilir.
            subtotal = float(
                connection.execute(
                    """
                    SELECT COALESCE(SUM(grl.quantity * pol.unit_price), 0)
                    FROM goods_receipt_lines grl
                    JOIN purchase_order_lines pol
                      ON pol.id = grl.purchase_order_line_id
                    WHERE grl.goods_receipt_id = ?
                    """,
                    (int(goods_receipt_id),),
                ).fetchone()[0]
                or 0
            )
            tax = subtotal * 0.20
            invoice_no = self._next_no(connection, "SAF")
            cursor = connection.execute(
                """
                INSERT INTO purchase_invoices(
                    organization_id, invoice_no, goods_receipt_id,
                    purchase_order_id, supplier_id, invoice_date,
                    subtotal, tax_amount, total_amount, currency, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    invoice_no,
                    int(goods_receipt_id),
                    int(receipt["purchase_order_id"]),
                    int(receipt["supplier_id"]),
                    self._now()[:10],
                    subtotal,
                    tax,
                    subtotal + tax,
                    str(receipt["currency"] or "TRY"),
                    username,
                ),
            )
            invoice_id = int(cursor.lastrowid)
            connection.commit()
            return invoice_id

    def list_purchase_quotes(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT pq.id, pq.quote_no, pq.quote_date AS record_date,
                       pq.delivery_date, pq.unit_price, pq.quantity,
                       pq.total_amount, pq.currency, pq.selected, pq.note,
                       s.name AS supplier_name, pr.request_no
                FROM purchase_quotes pq
                JOIN suppliers s ON s.id = pq.supplier_id
                LEFT JOIN purchase_requests pr ON pr.id = pq.request_id
                WHERE pq.organization_id = ?
                ORDER BY pq.request_id, pq.selected DESC, pq.total_amount
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_purchase_quote(
        self,
        *,
        request_id: int,
        supplier_id: int,
        unit_price: float,
        quantity: float,
        currency: str = "TRY",
        delivery_date: str = "",
        note: str = "",
        username: str,
    ) -> int:
        with closing(self.connect()) as connection:
            quote_no = self._next_no(connection, "TEK")
            total = self._number(unit_price) * self._number(quantity)
            cursor = connection.execute(
                """
                INSERT INTO purchase_quotes(
                    organization_id, request_id, supplier_id, quote_no,
                    quote_date, delivery_date, unit_price, quantity,
                    total_amount, currency, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.organization_id(connection),
                    int(request_id),
                    int(supplier_id),
                    quote_no,
                    self._now()[:10],
                    delivery_date or None,
                    self._number(unit_price),
                    self._number(quantity),
                    total,
                    currency.strip().upper(),
                    note.strip(),
                    username,
                ),
            )
            quote_id = int(cursor.lastrowid)
            connection.commit()
            return quote_id

    def select_purchase_quote(self, quote_id: int, *, username: str) -> None:
        with closing(self.connect()) as connection:
            quote = connection.execute(
                "SELECT * FROM purchase_quotes WHERE id = ?",
                (int(quote_id),),
            ).fetchone()
            if quote is None:
                raise ValueError("Teklif bulunamadı.")
            connection.execute(
                "UPDATE purchase_quotes SET selected = 0 WHERE request_id = ?",
                (int(quote["request_id"]),),
            )
            connection.execute(
                """
                UPDATE purchase_quotes
                SET selected = 1, row_version = row_version + 1
                WHERE id = ?
                """,
                (int(quote_id),),
            )
            connection.commit()

    def create_sales_quote(
        self,
        customer_id: int,
        *,
        quote_date: str,
        valid_until: str,
        lines: Iterable[dict[str, object]],
        username: str,
        currency: str = "EUR",
        exchange_rate: float = 1,
        note: str = "",
    ) -> int:
        prepared = list(lines)
        if not prepared:
            raise ValueError("Teklifte en az bir profil satırı olmalıdır.")
        with closing(self.connect()) as connection:
            quote_no = self._next_no(connection, "ST")
            total = 0.0
            for row in prepared:
                qty = self._number(row.get("quantity"))
                kg = self._number(row.get("kg"))
                unit_price = self._number(row.get("unit_price"))
                basis = kg if kg > 0 else qty
                total += basis * unit_price
            cursor = connection.execute(
                """
                INSERT INTO sales_quotes(
                    organization_id, quote_no, customer_id, quote_date,
                    valid_until, currency, exchange_rate, total_amount,
                    status, note, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TASLAK', ?, ?)
                """,
                (
                    self.organization_id(connection),
                    quote_no,
                    int(customer_id),
                    quote_date,
                    valid_until or None,
                    currency.strip().upper(),
                    self._number(exchange_rate) or 1.0,
                    total,
                    note.strip(),
                    username,
                ),
            )
            quote_id = int(cursor.lastrowid)
            for line_no, row in enumerate(prepared, start=1):
                profile_id = int(row["profile_id"])
                die_id = row.get("die_id")
                qty = self._number(row.get("quantity"))
                kg = self._number(row.get("kg"))
                unit_price = self._number(row.get("unit_price"))
                basis = kg if kg > 0 else qty
                line_amount = basis * unit_price
                connection.execute(
                    """
                    INSERT INTO sales_quote_lines(
                        sales_quote_id, line_no, profile_id, die_id,
                        length_mm, quantity, kg, unit_price, line_amount,
                        surface, alloy, temper, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        quote_id,
                        line_no,
                        profile_id,
                        int(die_id) if die_id else None,
                        self._number(row.get("length_mm")),
                        qty,
                        kg,
                        unit_price,
                        line_amount,
                        str(row.get("surface") or "").strip().upper(),
                        str(row.get("alloy") or "").strip().upper(),
                        str(row.get("temper") or "").strip().upper(),
                        str(row.get("note") or "").strip(),
                    ),
                )
            self._audit(
                connection,
                username=username,
                action="CREATE",
                entity_type="SALES_QUOTE",
                entity_id=quote_id,
                record_key=quote_no,
                after={"line_count": len(prepared), "total_amount": total},
            )
            connection.commit()
            return quote_id

    def list_sales_quote_lines(self, quote_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT l.*, p.profile_code, p.profile_name,
                       d.die_code, d.spare_no
                FROM sales_quote_lines l
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = l.die_id
                WHERE l.sales_quote_id = ?
                ORDER BY l.line_no
                """,
                (int(quote_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def convert_sales_quote_to_order(
        self,
        quote_id: int,
        *,
        order_date: str,
        delivery_date: str,
        username: str,
    ) -> int:
        with closing(self.connect()) as connection:
            quote = connection.execute(
                """
                SELECT * FROM sales_quotes
                WHERE id = ? AND organization_id = ?
                """,
                (int(quote_id), self.organization_id(connection)),
            ).fetchone()
            if quote is None:
                raise ValueError("Satış teklifi bulunamadı.")
            if str(quote["status"]).upper() in {"SİPARİŞE DÖNÜŞTÜ", "KAPALI", "İPTAL"}:
                raise ValueError("Bu teklif zaten siparişe dönüştürülmüş veya kapalı.")
            lines = connection.execute(
                """
                SELECT * FROM sales_quote_lines
                WHERE sales_quote_id = ?
                ORDER BY line_no
                """,
                (int(quote_id),),
            ).fetchall()
            if not lines:
                raise ValueError("Teklif satırı bulunmuyor.")
        order_lines = [
            {
                "profile_id": int(row["profile_id"]),
                "die_id": int(row["die_id"]) if row["die_id"] else None,
                "length_mm": float(row["length_mm"] or 0),
                "quantity": float(row["quantity"] or 0),
                "kg": float(row["kg"] or 0),
                "unit_price": float(row["unit_price"] or 0),
                "surface": str(row["surface"] or ""),
                "alloy": str(row["alloy"] or ""),
                "temper": str(row["temper"] or ""),
            }
            for row in lines
        ]
        order_id = self.create_sales_order(
            int(quote["customer_id"]),
            order_date=order_date,
            delivery_date=delivery_date,
            lines=order_lines,
            username=username,
            currency=str(quote["currency"] or "TRY"),
            note=str(quote["note"] or ""),
        )
        with closing(self.connect()) as connection:
            connection.execute(
                """
                UPDATE sales_quotes
                SET status = 'SİPARİŞE DÖNÜŞTÜ', row_version = row_version + 1
                WHERE id = ?
                """,
                (int(quote_id),),
            )
            self._audit(
                connection,
                username=username,
                action="CONVERT",
                entity_type="SALES_QUOTE",
                entity_id=int(quote_id),
                record_key=str(quote["quote_no"]),
                after={"order_id": order_id},
            )
            connection.commit()
        return order_id

    def list_sales_quotes(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT sq.id, sq.quote_no, sq.quote_date AS record_date,
                       sq.valid_until, sq.currency, sq.exchange_rate,
                       sq.total_amount, sq.status, sq.note,
                       c.name AS customer_name, c.code AS customer_code,
                       COUNT(sql.id) AS line_count
                FROM sales_quotes sq
                JOIN customers c ON c.id = sq.customer_id
                LEFT JOIN sales_quote_lines sql ON sql.sales_quote_id = sq.id
                WHERE sq.organization_id = ?
                GROUP BY sq.id
                ORDER BY sq.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def audit_history(self, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, username, action, record_key, before_json,
                       after_json, machine_name, created_at
                FROM audit_log
                WHERE organization_id = ? AND entity_type = ? AND entity_id = ?
                ORDER BY id DESC
                """,
                (
                    self.organization_id(connection),
                    entity_type.strip().upper(),
                    int(entity_id),
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def order_progress(self, order_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            order = connection.execute(
                """
                SELECT o.*, c.code AS customer_code, c.name AS customer_name
                FROM sales_orders o JOIN customers c ON c.id = o.customer_id
                WHERE o.id = ?
                """,
                (int(order_id),),
            ).fetchone()
            if order is None:
                raise ValueError("Satış siparişi bulunamadı.")
            rows = connection.execute(
                """
                SELECT l.*, p.profile_code, p.profile_name
                FROM sales_order_lines l JOIN profiles p ON p.id = l.profile_id
                WHERE l.sales_order_id = ? ORDER BY l.line_no
                """,
                (int(order_id),),
            ).fetchall()
        lines = []
        for row in rows:
            values = dict(row)
            ordered_kg = float(row["ordered_kg"] or 0)
            shipped_kg = float(row["shipped_kg"] or 0)
            values["production_remaining_kg"] = max(
                0.0,
                ordered_kg - float(row["produced_kg"] or 0),
            )
            values["shipping_remaining_kg"] = max(
                0.0,
                ordered_kg - shipped_kg,
            )
            values["progress_pct"] = (
                round(shipped_kg * 100 / ordered_kg) if ordered_kg > 0 else 0
            )
            lines.append(values)
        return {"order": dict(order), "lines": lines}

    def list_customers(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM customers
                WHERE organization_id = ? AND (? = 1 OR active = 1)
                ORDER BY name, code
                """,
                (self.organization_id(connection), 1 if include_inactive else 0),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_profiles(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT p.id, p.profile_code, p.profile_name,
                       p.unit_weight_kg_m, p.alloy, p.temper, p.active,
                       org.code AS organization_code,
                       org.name AS organization_name,
                       org.name AS customer_name,
                       EXISTS(
                           SELECT 1 FROM routes r
                           WHERE r.profile_id = p.id AND r.active = 1
                       ) AS has_route,
                       (SELECT COUNT(*) FROM attachments a
                        WHERE a.entity_type = 'PROFILE' AND a.entity_id = p.id
                          AND a.active = 1) AS attachment_count
                FROM profiles p
                JOIN organizations org ON org.id = p.organization_id
                WHERE p.organization_id = ? AND p.active = 1
                ORDER BY p.profile_code
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_dies(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        params: list[object] = []
        where = "WHERE d.organization_id = ? AND d.status <> 'HURDA'"
        with closing(self.connect()) as connection:
            params.append(self.organization_id(connection))
            if profile_id is not None:
                where += " AND d.profile_id = ?"
                params.append(int(profile_id))
            rows = connection.execute(
                f"""
                SELECT d.id, d.profile_id, d.die_code, d.spare_no,
                       d.figure_count, d.life_limit_kg, d.used_kg,
                       d.tenefer_no, d.tenefer_type, d.tenefer_limit_m,
                       d.tenefer_used_m, d.status, d.location, d.active,
                       d.external_company, d.is_external, d.supplier_name,
                       p.profile_code, p.profile_name, p.unit_weight_kg_m,
                       COALESCE((
                           SELECT dm.movement_type FROM die_movements dm
                           WHERE dm.die_id = d.id
                           ORDER BY dm.id DESC LIMIT 1
                       ), '') AS last_movement,
                       COALESCE((
                           SELECT dm.company FROM die_movements dm
                           WHERE dm.die_id = d.id
                             AND dm.movement_type IN ('TENEFER GİTTİ', 'TENEFER GELDİ',
                                                      'TENEFERE GÖNDER', 'TENEFERDEN GELDİ')
                           ORDER BY dm.id DESC LIMIT 1
                       ), d.external_company) AS last_tenefer_company,
                       (SELECT COUNT(*) FROM attachments a
                        WHERE a.entity_type = 'DIE' AND a.entity_id = d.id
                          AND a.active = 1) AS attachment_count
                FROM dies d
                JOIN profiles p ON p.id = d.profile_id
                {where}
                ORDER BY d.die_code, d.spare_no
                """,
                params,
            ).fetchall()
        return [self._enrich_die_dict(dict(row)) for row in rows]

    def list_routes(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        params: list[object] = [self.organization_code]
        profile_filter = ""
        if profile_id is not None:
            profile_filter = " AND r.profile_id = ?"
            params.append(int(profile_id))
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT r.id, r.profile_id, r.code, r.name, r.recipe_name,
                       r.production_length_mm, r.surface, r.color, r.alloy,
                       r.temper, r.mechanical, r.active,
                       p.profile_code, p.profile_name,
                       COUNT(rs.id) AS step_count,
                       GROUP_CONCAT(rs.operation || ' / ' || rs.default_station, ' → ')
                           AS route_summary
                FROM routes r
                JOIN organizations o ON o.id = r.organization_id
                JOIN profiles p ON p.id = r.profile_id
                LEFT JOIN route_steps rs ON rs.route_id = r.id
                WHERE o.code = ? AND r.active = 1 {profile_filter}
                GROUP BY r.id
                ORDER BY p.profile_code, r.code
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_route_steps(self, route_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT rs.id, rs.sequence_no, rs.operation, rs.default_station,
                       wi.code AS input_warehouse_code,
                       wi.name AS input_warehouse_name,
                       wo.code AS output_warehouse_code,
                       wo.name AS output_warehouse_name
                FROM route_steps rs
                LEFT JOIN warehouses wi ON wi.id = rs.input_warehouse_id
                LEFT JOIN warehouses wo ON wo.id = rs.output_warehouse_id
                WHERE rs.route_id = ?
                ORDER BY rs.sequence_no
                """,
                (int(route_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recipes(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        params: list[object] = [self.organization_code]
        profile_filter = ""
        if profile_id is not None:
            profile_filter = " AND rc.profile_id = ?"
            params.append(int(profile_id))
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT rc.id, rc.profile_id, rc.route_id, rc.recipe_code,
                       rc.recipe_name, rc.production_length_mm,
                       rc.saw_allowance_mm, rc.hanger_allowance_mm, rc.active,
                       rc.raw_material_stock_external_id AS raw_material_code,
                       p.profile_code, p.profile_name,
                       r.code AS route_code, r.name AS route_name,
                       COUNT(rl.id) AS line_count
                FROM recipes rc
                JOIN organizations o ON o.id = rc.organization_id
                JOIN profiles p ON p.id = rc.profile_id
                LEFT JOIN routes r ON r.id = rc.route_id
                LEFT JOIN recipe_lines rl ON rl.recipe_id = rc.id
                WHERE o.code = ? AND rc.active = 1 {profile_filter}
                GROUP BY rc.id
                ORDER BY p.profile_code, rc.recipe_code
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recipe_lines(self, recipe_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, sequence_no, route_sequence_no, process_type,
                       operation_name, station_name, stock_code, unit_code,
                       warehouse_code, quantity, main_quantity, numerator,
                       denominator, external_unit_weight, external_kg,
                       external_quantity, external_metre, description
                FROM recipe_lines
                WHERE recipe_id = ?
                ORDER BY route_sequence_no, sequence_no, id
                """,
                (int(recipe_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_stations(self, operation: str = "") -> list[dict[str, Any]]:
        term = operation.strip().upper()
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.code, s.name, s.active,
                       COALESCE(o.code, '') AS operation_code,
                       COALESCE(o.name, '') AS operation_name
                FROM stations s
                LEFT JOIN operations o ON o.id = s.operation_id
                WHERE s.organization_id = ? AND s.active = 1
                  AND (? = '' OR UPPER(COALESCE(o.name, '')) LIKE '%' || ? || '%'
                       OR UPPER(COALESCE(o.code, '')) LIKE '%' || ? || '%')
                ORDER BY o.name, s.name
                """,
                (self.organization_id(connection), term, term, term),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_die_station_compatibility(self, die_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT dsc.id, dsc.active,
                       COALESCE(s.code, dsc.station_external_id) AS station_code,
                       COALESCE(s.name, dsc.station_external_id) AS station_name
                FROM die_station_compatibility dsc
                LEFT JOIN stations s ON s.id = dsc.station_id
                WHERE dsc.die_id = ? AND dsc.active = 1
                ORDER BY station_name
                """,
                (int(die_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sales_order_lines_detail(self) -> list[dict[str, Any]]:
        """Sipariş Detay (Satış) — satır bazlı durum grid."""
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            missing_status = connection.execute(
                """
                SELECT COUNT(*)
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN sales_order_line_status st ON st.sales_order_line_id = l.id
                WHERE o.organization_id = ? AND o.status <> 'İPTAL'
                  AND st.sales_order_line_id IS NULL
                """,
                (organization_id,),
            ).fetchone()[0]
            if int(missing_status or 0) > 0:
                recalculate_order_line_status(connection)
                connection.commit()
            rows = connection.execute(
                """
                SELECT l.id, l.sales_order_id, l.line_no,
                       l.production_length_mm, l.surface, l.color,
                       l.alloy, l.temper, l.mechanical,
                       l.ordered_quantity, l.ordered_kg,
                       l.produced_quantity, l.produced_kg,
                       l.shipped_quantity, l.shipped_kg,
                       l.unit_price, l.status AS line_status,
                       o.order_no, o.revision_no, o.customer_document_no,
                       o.order_date, o.delivery_date, o.status AS order_status,
                       o.production_approval, o.msp,
                       c.code AS customer_code, c.name AS customer_name,
                       c.city AS customer_region,
                       p.profile_code, p.profile_name,
                       d.die_code, d.spare_no,
                       st.fulfillment_status, st.progress_pct,
                       st.planned_quantity, st.planned_kg,
                       st.pending_production_quantity, st.pending_production_kg,
                       st.field_quantity, st.field_kg,
                       st.ready_package_quantity, st.ready_package_kg,
                       st.pending_shipment_quantity, st.pending_shipment_kg,
                       st.warehouse_summary, st.plan_summary,
                       st.last_shipment_date
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = l.die_id
                LEFT JOIN sales_order_line_status st ON st.sales_order_line_id = l.id
                WHERE o.organization_id = ? AND o.status <> 'İPTAL'
                ORDER BY o.order_date DESC, o.id DESC, l.line_no
                """,
                (organization_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            delivery = str(values.get("delivery_date") or "")[:10]
            if delivery:
                delivery_date = date.fromisoformat(delivery)
                values["line_delivery_week"] = delivery_date.isocalendar()[1]
            else:
                values["line_delivery_week"] = ""
            values["record_date"] = str(values.get("order_date") or "")[:10]
            order_status = str(values.get("order_status") or "").upper()
            production = str(values.get("production_approval") or "").upper()
            line_status = str(values.get("line_status") or "AÇIK").upper()
            values["status_display"] = line_status
            values["order_approval"] = (
                "KABUL" if order_status not in {"ONAY BEKLİYOR", "TASLAK"} else "BEKLİYOR"
            )
            values["production_approval_display"] = (
                "KABUL" if production == "ONAYLANDI" else "BEKLİYOR"
            )
            values["fulfillment_status"] = str(
                values.get("fulfillment_status") or "ÜRETİLECEK"
            ).upper()
            values["production_quantity"] = float(values.get("produced_quantity") or 0)
            values["production_kg"] = float(values.get("produced_kg") or 0)
            values["pending_production_quantity"] = float(
                values.get("pending_production_quantity") or 0
            )
            values["pending_production_kg"] = float(
                values.get("pending_production_kg") or 0
            )
            values["field_quantity"] = float(values.get("field_quantity") or 0)
            values["field_kg"] = float(values.get("field_kg") or 0)
            values["ready_shipment_quantity"] = float(
                values.get("ready_package_quantity") or 0
            )
            values["ready_shipment_kg"] = float(values.get("ready_package_kg") or 0)
            values["pending_shipment_quantity"] = float(
                values.get("pending_shipment_quantity") or 0
            )
            values["pending_shipment_kg"] = float(values.get("pending_shipment_kg") or 0)
            values["progress_pct"] = float(values.get("progress_pct") or 0)
            values["warehouses"] = values.get("warehouse_summary") or ""
            values["plans"] = values.get("plan_summary") or ""
            values["product_code"] = values.get("customer_document_no") or values.get("msp") or ""
            values["merged_flag"] = "false"
            values["order_ref"] = f"{values.get('order_no')}-{values.get('line_no')}"
            values["line_amount"] = (
                float(values.get("ordered_kg") or 0) * float(values.get("unit_price") or 0)
            )
            result.append(values)
        return result

    def list_order_lines_for_planning(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT l.id, l.sales_order_id, l.line_no, l.profile_id,
                       l.die_id, l.ordered_quantity, l.ordered_kg,
                       l.production_length_mm, l.surface, l.color, l.alloy,
                       l.temper, l.mechanical, l.status,
                       o.order_no, o.order_date, o.delivery_date,
                       c.name AS customer_name,
                       p.profile_code, p.profile_name,
                       d.die_code,
                       COALESCE(SUM(CASE WHEN po.status <> 'İPTAL'
                           THEN po.planned_quantity ELSE 0 END), 0) AS planned_quantity,
                       COALESCE(SUM(CASE WHEN po.status <> 'İPTAL'
                           THEN po.planned_kg ELSE 0 END), 0) AS planned_kg,
                       MAX(0, l.ordered_quantity - COALESCE(SUM(CASE WHEN po.status <> 'İPTAL'
                           THEN po.planned_quantity ELSE 0 END), 0)) AS remaining_quantity,
                       MAX(0, l.ordered_kg - COALESCE(SUM(CASE WHEN po.status <> 'İPTAL'
                           THEN po.planned_kg ELSE 0 END), 0)) AS remaining_kg,
                       COUNT(po.id) AS production_order_count
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = l.die_id
                LEFT JOIN production_orders po ON po.sales_order_line_id = l.id
                WHERE o.organization_id = ? AND o.status <> 'İPTAL'
                GROUP BY l.id
                ORDER BY o.delivery_date, o.id, l.line_no
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sales_orders(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT o.id, o.order_no, o.revision_no, o.customer_document_no,
                       o.msp, o.order_date, o.delivery_date, o.currency,
                       o.status, o.production_approval, o.created_by,
                       o.representative, o.usd_rate, o.eur_rate,
                       c.code AS customer_code, c.name AS customer_name,
                       COALESCE(b.name, '') AS branch_name,
                       COALESCE(w.name, '') AS warehouse_name,
                       COUNT(l.id) AS line_count,
                       COALESCE(SUM(l.ordered_quantity), 0) AS ordered_quantity,
                       COALESCE(SUM(l.ordered_kg), 0) AS ordered_kg,
                       COALESCE(SUM(l.produced_kg), 0) AS produced_kg,
                       COALESCE(SUM(l.shipped_kg), 0) AS shipped_kg,
                       COALESCE(SUM(l.ordered_kg), 0) - COALESCE(SUM(l.shipped_kg), 0)
                           AS pending_kg,
                       COALESCE(SUM(l.ordered_kg * l.unit_price), 0) AS total_amount,
                       CASE
                           WHEN COALESCE(SUM(l.ordered_kg), 0) <= 0 THEN 0
                           ELSE CAST(
                               ROUND(
                                   COALESCE(SUM(l.shipped_kg), 0) * 100.0
                                   / COALESCE(SUM(l.ordered_kg), 0),
                                   0
                               ) AS INTEGER
                           )
                       END AS progress_pct,
                       printf('%02d', o.revision_no) AS revision_display
                FROM sales_orders o
                JOIN customers c ON c.id = o.customer_id
                LEFT JOIN branches b ON b.id = o.branch_id
                LEFT JOIN warehouses w ON w.id = o.warehouse_id
                LEFT JOIN sales_order_lines l ON l.sales_order_id = o.id
                WHERE o.organization_id = ?
                  AND (? = '%%' OR o.order_no LIKE ? OR c.name LIKE ?
                       OR o.customer_document_no LIKE ? OR o.status LIKE ?)
                GROUP BY o.id
                ORDER BY o.order_date DESC, o.id DESC
                """,
                (
                    self.organization_id(connection),
                    term,
                    term,
                    term,
                    term,
                    term,
                ),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            delivery = str(values.get("delivery_date") or "")[:10]
            if delivery:
                delivery_date = date.fromisoformat(delivery)
                values["delivery_week"] = delivery_date.isocalendar()[1]
                values["delivery_year"] = delivery_date.year
            else:
                values["delivery_week"] = ""
                values["delivery_year"] = ""
            currency = str(values.get("currency") or "TRY").upper()
            values["currency_display"] = "TL" if currency == "TRY" else currency
            total_amount = float(values.get("total_amount") or 0)
            usd_rate = float(values.get("usd_rate") or 0)
            values["foreign_total"] = total_amount if currency not in {"TRY", "TL"} else 0.0
            if currency == "USD":
                values["usd_total"] = total_amount
            elif currency == "TRY" and usd_rate > 0:
                values["usd_total"] = round(total_amount / usd_rate, 2)
            else:
                values["usd_total"] = 0.0
            status = str(values.get("status") or "").upper()
            production = str(values.get("production_approval") or "").upper()
            values["order_approval"] = (
                "KABUL" if status not in {"ONAY BEKLİYOR", "TASLAK"} else "BEKLİYOR"
            )
            values["production_approval_display"] = (
                "KABUL" if production == "ONAYLANDI" else "BEKLİYOR"
            )
            values["close_status"] = "KAPALI" if status == "KAPALI" else "AÇIK"
            values["order_status"] = (
                "" if status in {"AÇIK", "KAPALI", "ONAYLANDI", "ONAY BEKLİYOR", "TASLAK"}
                else status
            )
            values["approval_note"] = ""
            result.append(values)
        return result

    def list_production_orders(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT po.id, po.production_order_no, po.planned_quantity,
                       po.planned_kg, po.produced_quantity, po.produced_kg,
                       po.status, o.order_no, o.delivery_date,
                       c.name AS customer_name, p.profile_code, p.profile_name,
                       r.code AS route_code,
                       COUNT(wo.id) AS work_order_count,
                       SUM(CASE WHEN wo.status = 'TAMAMLANDI' THEN 1 ELSE 0 END)
                           AS completed_work_orders
                FROM production_orders po
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                JOIN routes r ON r.id = po.route_id
                LEFT JOIN work_orders wo ON wo.production_order_id = po.id
                WHERE po.organization_id = ?
                GROUP BY po.id
                ORDER BY po.id DESC
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_work_orders(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT wo.id, wo.work_order_no, wo.production_order_id,
                       wo.sequence_no, wo.priority, wo.operation, wo.station,
                       wo.planned_quantity, wo.planned_kg,
                       wo.produced_quantity, wo.produced_kg, wo.scrap_kg,
                       wo.status, wo.actual_start, wo.actual_end,
                       po.production_order_no, o.order_no, o.order_date,
                       o.delivery_date, o.revision_no,
                       l.line_no,
                       printf('%s-%d %02d', o.order_no, l.line_no, o.revision_no)
                           AS order_line_ref,
                       CASE
                           WHEN wo.planned_kg > 0 THEN CAST(
                               ROUND(wo.produced_kg * 100.0 / wo.planned_kg, 0) AS INTEGER
                           )
                           ELSE 0
                       END AS production_pct,
                       COALESCE(wo.actual_start, o.order_date) AS record_date,
                       c.name AS customer_name,
                       c.production_note,
                       p.profile_code, p.profile_name, p.unit_weight_kg_m,
                       COALESCE(NULLIF(wo.production_length_mm, 0), l.production_length_mm)
                           AS production_length_mm,
                       l.stock_length_mm, l.surface, l.surface AS order_surface,
                       l.color, l.color AS order_color,
                       l.ordered_quantity, l.ordered_kg,
                       l.die_id, d.die_code,
                       wi.code AS input_warehouse_code,
                       wi.name AS input_warehouse_name,
                       wo2.code AS output_warehouse_code,
                       wo2.name AS output_warehouse_name,
                       wi.code AS raw_material_stock,
                       MAX(0, wo.planned_quantity - wo.produced_quantity)
                           AS remaining_quantity,
                       MAX(0, wo.planned_kg - wo.produced_kg) AS remaining_kg,
                       CASE WHEN p.unit_weight_kg_m > 0
                         THEN MAX(0, wo.planned_kg - wo.produced_kg) / p.unit_weight_kg_m
                         ELSE 0 END AS remaining_metre,
                       COALESCE((
                         SELECT SUM(sm.direction * sm.quantity)
                         FROM stock_movements sm
                         WHERE sm.sales_order_line_id = l.id
                           AND sm.warehouse_id = rs.output_warehouse_id
                       ), 0) AS warehouse_kg,
                       CASE WHEN p.unit_weight_kg_m > 0
                              AND COALESCE(NULLIF(wo.production_length_mm, 0), l.production_length_mm) > 0
                         THEN COALESCE((
                           SELECT SUM(sm2.direction * sm2.quantity)
                           FROM stock_movements sm2
                           WHERE sm2.sales_order_line_id = l.id
                             AND sm2.warehouse_id = rs.output_warehouse_id
                         ), 0) / p.unit_weight_kg_m /
                           (COALESCE(NULLIF(wo.production_length_mm, 0), l.production_length_mm) / 1000.0)
                         ELSE 0 END AS warehouse_quantity,
                       COALESCE((
                         SELECT prev.station FROM work_orders prev
                         WHERE prev.production_order_id = wo.production_order_id
                           AND prev.sequence_no = wo.sequence_no - 1
                       ), '') AS previous_station,
                       COALESCE((
                         SELECT nxt.station FROM work_orders nxt
                         WHERE nxt.production_order_id = wo.production_order_id
                           AND nxt.sequence_no = wo.sequence_no + 1
                       ), '') AS next_station
                FROM work_orders wo
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                JOIN route_steps rs ON rs.id = wo.route_step_id
                LEFT JOIN warehouses wi ON wi.id = rs.input_warehouse_id
                LEFT JOIN warehouses wo2 ON wo2.id = rs.output_warehouse_id
                LEFT JOIN dies d ON d.id = l.die_id
                ORDER BY
                    CASE wo.status
                        WHEN 'HAZIR' THEN 0 WHEN 'ÜRETİLİYOR' THEN 1
                        WHEN 'BEKLİYOR' THEN 2 ELSE 3 END,
                    o.delivery_date, wo.production_order_id, wo.sequence_no
                """
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            values = dict(row)
            values["selected"] = ""
            values["image_path"] = ""
            result.append(values)
        return result

    def list_packable_lines(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT l.id, o.order_no, c.name AS customer_name,
                       p.profile_code, p.profile_name,
                       l.produced_quantity, l.produced_kg,
                       COALESCE(SUM(pl.quantity), 0) AS packed_quantity,
                       COALESCE(SUM(pl.net_kg), 0) AS packed_kg,
                       l.produced_quantity - COALESCE(SUM(pl.quantity), 0)
                           AS remaining_quantity,
                       l.produced_kg - COALESCE(SUM(pl.net_kg), 0)
                           AS remaining_kg
                FROM sales_order_lines l
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN package_lines pl ON pl.sales_order_line_id = l.id
                GROUP BY l.id
                HAVING remaining_kg > 0.001
                ORDER BY o.delivery_date, o.id, l.line_no
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def weighing_list_document(self, weighing_list_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            header = connection.execute(
                """
                SELECT wl.*, c.name AS customer_name, c.code AS customer_code
                FROM weighing_lists wl
                JOIN customers c ON c.id = wl.customer_id
                WHERE wl.id = ?
                """,
                (int(weighing_list_id),),
            ).fetchone()
            if header is None:
                raise ValueError("Çeki listesi bulunamadı.")
            lines = connection.execute(
                """
                SELECT pk.package_no, pk.net_kg, pk.gross_kg,
                       wlp.net_kg AS list_net_kg, wlp.gross_kg AS list_gross_kg,
                       pl.quantity, pl.lot_no,
                       o.order_no, p.profile_code, p.profile_name
                FROM weighing_list_packages wlp
                JOIN packages pk ON pk.id = wlp.package_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                WHERE wlp.weighing_list_id = ?
                ORDER BY pk.package_no, pl.id
                """,
                (int(weighing_list_id),),
            ).fetchall()
        result_lines: list[dict[str, Any]] = []
        for row in lines:
            values = dict(row)
            values["net_kg"] = float(values.get("list_net_kg") or values.get("net_kg") or 0)
            values["gross_kg"] = float(values.get("list_gross_kg") or values.get("gross_kg") or 0)
            result_lines.append(values)
        return {"header": dict(header), "lines": result_lines}

    def shipment_document(self, shipment_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            header = connection.execute(
                """
                SELECT s.*, c.name AS customer_name, c.code AS customer_code,
                       wl.weighing_list_no
                FROM shipments s
                JOIN customers c ON c.id = s.customer_id
                LEFT JOIN weighing_lists wl ON wl.id = s.weighing_list_id
                WHERE s.id = ?
                """,
                (int(shipment_id),),
            ).fetchone()
            if header is None:
                raise ValueError("Sevkiyat bulunamadı.")
            lines = connection.execute(
                """
                SELECT pk.package_no, sl.net_kg, sl.gross_kg,
                       pl.quantity, pl.lot_no,
                       o.order_no, p.profile_code, p.profile_name
                FROM shipment_lines sl
                JOIN packages pk ON pk.id = sl.package_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                WHERE sl.shipment_id = ?
                ORDER BY pk.package_no, pl.id
                """,
                (int(shipment_id),),
            ).fetchall()
        return {"header": dict(header), "lines": [dict(row) for row in lines]}

    def package_label_document(self, package_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            header = connection.execute(
                """
                SELECT pk.*, c.name AS customer_name,
                       w.name AS warehouse_name, w.code AS warehouse_code,
                       GROUP_CONCAT(DISTINCT o.order_no) AS order_nos,
                       GROUP_CONCAT(DISTINCT p.profile_code) AS profile_codes
                FROM packages pk
                JOIN customers c ON c.id = pk.customer_id
                JOIN warehouses w ON w.id = pk.warehouse_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                WHERE pk.id = ?
                GROUP BY pk.id
                """,
                (int(package_id),),
            ).fetchone()
            if header is None:
                raise ValueError("Paket bulunamadı.")
            lines = connection.execute(
                """
                SELECT pl.quantity, pl.lot_no, pl.net_kg, pl.gross_kg,
                       o.order_no, p.profile_code, p.profile_name
                FROM package_lines pl
                JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN profiles p ON p.id = l.profile_id
                WHERE pl.package_id = ?
                ORDER BY pl.id
                """,
                (int(package_id),),
            ).fetchall()
        return {"header": dict(header), "lines": [dict(row) for row in lines]}

    def work_order_document(self, work_order_id: int) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT wo.*, po.production_order_no,
                       o.order_no, o.order_date, o.delivery_date,
                       l.line_no, l.surface, l.production_length_mm,
                       c.name AS customer_name,
                       p.profile_code, p.profile_name,
                       d.die_code,
                       wi.name AS input_warehouse_name,
                       wo2.name AS output_warehouse_name
                FROM work_orders wo
                JOIN production_orders po ON po.id = wo.production_order_id
                JOIN sales_order_lines l ON l.id = po.sales_order_line_id
                JOIN sales_orders o ON o.id = l.sales_order_id
                JOIN customers c ON c.id = o.customer_id
                JOIN profiles p ON p.id = l.profile_id
                LEFT JOIN dies d ON d.id = l.die_id
                LEFT JOIN route_steps rs ON rs.id = wo.route_step_id
                LEFT JOIN warehouses wi ON wi.id = rs.input_warehouse_id
                LEFT JOIN warehouses wo2 ON wo2.id = rs.output_warehouse_id
                WHERE wo.id = ?
                """,
                (int(work_order_id),),
            ).fetchone()
            if row is None:
                raise ValueError("İş emri bulunamadı.")
        return dict(row)

    def list_packages(
        self, statuses: Sequence[str] | None = None
    ) -> list[dict[str, Any]]:
        params: list[object] = []
        where = ""
        if statuses:
            status_values = [str(value) for value in statuses]
            placeholders = ",".join("?" for _ in status_values)
            where = f"WHERE pk.status IN ({placeholders})"
            params.extend(status_values)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT pk.id, pk.package_no, pk.net_kg, pk.gross_kg,
                       pk.package_count, pk.status, pk.packed_at, pk.packed_by,
                       c.name AS customer_name, w.code AS warehouse_code,
                       w.name AS warehouse_name,
                       GROUP_CONCAT(DISTINCT o.order_no) AS order_nos,
                       GROUP_CONCAT(DISTINCT p.profile_code) AS profile_codes
                FROM packages pk
                JOIN customers c ON c.id = pk.customer_id
                JOIN warehouses w ON w.id = pk.warehouse_id
                LEFT JOIN package_lines pl ON pl.package_id = pk.id
                LEFT JOIN sales_order_lines l ON l.id = pl.sales_order_line_id
                LEFT JOIN sales_orders o ON o.id = l.sales_order_id
                LEFT JOIN profiles p ON p.id = l.profile_id
                {where}
                GROUP BY pk.id
                ORDER BY pk.id DESC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_weighing_lists(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT wl.id, wl.weighing_list_no, wl.status, wl.note,
                       wl.created_by, wl.created_at, c.name AS customer_name,
                       COUNT(wlp.id) AS package_count,
                       COALESCE(SUM(wlp.net_kg), 0) AS net_kg,
                       COALESCE(SUM(wlp.gross_kg), 0) AS gross_kg
                FROM weighing_lists wl
                JOIN customers c ON c.id = wl.customer_id
                LEFT JOIN weighing_list_packages wlp
                    ON wlp.weighing_list_id = wl.id
                GROUP BY wl.id
                ORDER BY wl.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_shipments(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.shipment_no, s.dispatch_note_no,
                       s.shipment_date, s.vehicle_plate,
                       s.status, s.created_by, c.name AS customer_name,
                       wl.weighing_list_no,
                       COUNT(sl.id) AS package_count,
                       COALESCE(SUM(sl.net_kg), 0) AS net_kg,
                       COALESCE(SUM(sl.gross_kg), 0) AS gross_kg
                FROM shipments s
                JOIN customers c ON c.id = s.customer_id
                LEFT JOIN weighing_lists wl ON wl.id = s.weighing_list_id
                LEFT JOIN shipment_lines sl ON sl.shipment_id = s.id
                GROUP BY s.id
                ORDER BY s.shipment_date DESC, s.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sales_invoices(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT i.id, i.invoice_no, i.invoice_date, i.currency,
                       i.exchange_rate, i.lme_usd_ton, i.premium_usd_ton,
                       i.pricing_mode, i.total_amount, i.status, i.created_by,
                       i.shipment_id, s.shipment_no, s.dispatch_note_no,
                       c.name AS customer_name
                FROM sales_invoices i
                JOIN shipments s ON s.id = i.shipment_id
                JOIN customers c ON c.id = s.customer_id
                ORDER BY i.invoice_date DESC, i.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _imported_route_steps(recipe: dict[str, object]) -> list[dict[str, str]]:
        structured = recipe.get("route_steps")
        if isinstance(structured, list) and structured:
            prepared: list[dict[str, str]] = []
            previous = "HAMMADDE"
            for index, raw_step in enumerate(structured, start=1):
                if not isinstance(raw_step, dict):
                    continue
                operation_id = str(
                    raw_step.get("operation_external_id") or ""
                ).strip()
                station_id = str(raw_step.get("station_external_id") or "").strip()
                operation = str(
                    raw_step.get("operation")
                    or raw_step.get("station")
                    or (f"OPERASYON {operation_id}" if operation_id else f"OPERASYON {index}")
                ).strip().upper()
                station = str(
                    raw_step.get("station")
                    or (f"İSTASYON {station_id}" if station_id else operation)
                ).strip().upper()
                label = f"{operation} {station}"
                if "PRES" in label:
                    output = "PRES"
                elif "TERM" in label:
                    output = "TERMIK"
                elif "ELOK" in label or "BOYA" in label or "YÜZEY" in label:
                    output = "YUZEY"
                elif "PAKET" in label or "KASA" in label:
                    output = "SEVK_ON"
                else:
                    output = previous
                prepared.append(
                    {
                        "operation": operation,
                        "station": station,
                        "input_warehouse": previous,
                        "output_warehouse": output,
                    }
                )
                previous = output
            # Gerçek SQL rotası geldiyse eksik adım uydurulmaz; özellikle
            # PAKETLEME otomatik eklenmez.
            return prepared

        note = str(recipe.get("note") or "")
        route_text = note.split(":", 1)[1].strip() if ":" in note else note.strip()
        tokens = [token.strip().upper() for token in route_text.split("-") if token.strip()]
        steps: list[dict[str, str]] = []
        previous = "HAMMADDE"
        cfg = factory_config()
        pres_token = str(cfg.pres_ad or "PRES").strip().upper()

        def add(operation: str, station: str, output: str) -> None:
            nonlocal previous
            if any(step["operation"] == operation for step in steps):
                return
            steps.append(
                {
                    "operation": operation,
                    "station": station,
                    "input_warehouse": previous,
                    "output_warehouse": output,
                }
            )
            previous = output

        if not any(pres_token in token or "PRES" in token for token in tokens):
            add(f"{pres_token} ÜRETİM", f"{pres_token} 1", "PRES")
        for token in tokens:
            if pres_token in token or "PRES" in token:
                station = token if any(ch.isdigit() for ch in token) else f"{pres_token} 1"
                add(f"{pres_token} ÜRETİM", station, "PRES")
            elif "TERM" in token:
                add("TERMİK ÇIKIŞ", token if any(ch.isdigit() for ch in token) else "TERMİK 1", "TERMIK")
            elif "ELOK" in token:
                add("ELOKSAL", token, "YUZEY")
            elif "BOYA" in token:
                add("BOYA", token, "YUZEY")
        surface = str(recipe.get("surface") or "").strip().upper()
        if "ELOKSAL" in surface:
            add("ELOKSAL", "ELOKSAL 1", "YUZEY")
        elif "BOYA" in surface:
            add("BOYA", "BOYA 1", "YUZEY")
        add("PAKETLEME", "PAKETLEME 1", "SEVK_ON")
        return steps

    def import_master_cards(
        self,
        *,
        customers: Iterable[dict[str, object]],
        profiles: Iterable[dict[str, object]],
        dies: Iterable[dict[str, object]],
        recipes: Iterable[dict[str, object]],
        username: str = "ilk_aktarim",
    ) -> dict[str, int]:
        """İlk aktarım kartlarını aynı ilişkisel yerel şemaya tekrar çalışabilir taşır."""
        counts = {
            "customers": 0, "profiles": 0, "dies": 0,
            "routes": 0, "recipes": 0, "recipe_lines": 0,
            "route_conditions": 0, "attachments": 0,
        }
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            for values in customers:
                code = str(values.get("code") or "").strip().upper()
                name = str(values.get("name") or "").strip()
                if not code or not name:
                    continue
                connection.execute(
                    """
                    INSERT INTO customers(
                        organization_id, code, name, tax_office, tax_number,
                        phone, email, address, city, country, currency, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, code) DO UPDATE SET
                        name = excluded.name, tax_office = excluded.tax_office,
                        tax_number = excluded.tax_number, phone = excluded.phone,
                        email = excluded.email, address = excluded.address,
                        city = excluded.city, country = excluded.country,
                        currency = excluded.currency, active = excluded.active,
                        updated_at = CURRENT_TIMESTAMP, row_version = row_version + 1
                    """,
                    (
                        organization_id,
                        code,
                        name,
                        str(values.get("tax_office") or ""),
                        str(values.get("tax_no") or values.get("tax_number") or ""),
                        str(values.get("phone") or ""),
                        str(values.get("email") or ""),
                        str(values.get("address") or ""),
                        str(values.get("city") or ""),
                        str(values.get("country") or "TÜRKİYE"),
                        str(values.get("currency") or "TRY").upper(),
                        1 if values.get("active", True) else 0,
                    ),
                )
                counts["customers"] += 1

            customer_rows = connection.execute(
                "SELECT id, code, name FROM customers WHERE organization_id = ?",
                (organization_id,),
            ).fetchall()
            customer_lookup: dict[str, int] = {}
            for row in customer_rows:
                customer_lookup[str(row["code"]).strip().casefold()] = int(row["id"])
                customer_lookup[str(row["name"]).strip().casefold()] = int(row["id"])

            for values in profiles:
                code = str(values.get("profile_code") or "").strip().upper()
                name = str(values.get("profile_name") or "").strip()
                if not code or not name:
                    continue
                company = str(values.get("company") or "").strip().casefold()
                customer_id = customer_lookup.get(company)
                connection.execute(
                    """
                    INSERT INTO profiles(
                        organization_id, customer_id, profile_code, profile_name,
                        unit_weight_kg_m, perimeter_mm, alloy, temper, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, profile_code) DO UPDATE SET
                        customer_id = COALESCE(excluded.customer_id, profiles.customer_id),
                        profile_name = excluded.profile_name,
                        unit_weight_kg_m = excluded.unit_weight_kg_m,
                        perimeter_mm = excluded.perimeter_mm,
                        alloy = excluded.alloy, temper = excluded.temper,
                        active = excluded.active, updated_at = CURRENT_TIMESTAMP,
                        row_version = row_version + 1
                    """,
                    (
                        organization_id,
                        customer_id,
                        code,
                        name,
                        max(0.0, self._number(values.get("unit_weight"))),
                        max(0.0, self._number(values.get("perimeter"))),
                        str(values.get("alloy") or "6060B").upper(),
                        str(values.get("temper") or "T5").upper(),
                        1 if values.get("active", True) else 0,
                    ),
                )
                profile_id = int(
                    connection.execute(
                        "SELECT id FROM profiles WHERE organization_id = ? AND profile_code = ?",
                        (organization_id, code),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO stock_items(
                        organization_id, profile_id, code, name, stock_group, unit
                    ) VALUES (?, ?, ?, ?, 'PROFİL', 'KG')
                    ON CONFLICT(organization_id, code) DO UPDATE SET
                        profile_id = excluded.profile_id, name = excluded.name,
                        active = 1, row_version = row_version + 1
                    """,
                    (organization_id, profile_id, code, name),
                )
                for document_type, key in (
                    ("PROFİL PDF", "drawing_path"),
                    ("PROFİL GÖRSELİ", "image_path"),
                ):
                    if self._upsert_attachment(
                        connection,
                        entity_type="PROFILE",
                        entity_id=profile_id,
                        document_type=document_type,
                        file_path=str(values.get(key) or ""),
                        username=username,
                        source_system="LEGACY",
                    ) is not None:
                        counts["attachments"] += 1
                counts["profiles"] += 1

            profile_lookup = {
                str(row["profile_code"]).strip().upper(): int(row["id"])
                for row in connection.execute(
                    "SELECT id, profile_code FROM profiles WHERE organization_id = ?",
                    (organization_id,),
                )
            }
            for values in dies:
                profile_id = profile_lookup.get(
                    str(values.get("profile_code") or "").strip().upper()
                )
                die_code = str(values.get("die_code") or "").strip().upper()
                if profile_id is None or not die_code:
                    continue
                spare_no = int(self._number(values.get("spare_no")))
                connection.execute(
                    """
                    INSERT INTO dies(
                        organization_id, profile_id, die_code, spare_no,
                        figure_count, life_limit_kg, used_kg,
                        tenefer_used_m, status, location, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, die_code, spare_no) DO UPDATE SET
                        profile_id = excluded.profile_id,
                        figure_count = excluded.figure_count,
                        life_limit_kg = excluded.life_limit_kg,
                        used_kg = excluded.used_kg,
                        tenefer_used_m = excluded.tenefer_used_m,
                        status = excluded.status, location = excluded.location,
                        note = excluded.note, row_version = row_version + 1
                    """,
                    (
                        organization_id,
                        profile_id,
                        die_code,
                        spare_no,
                        max(1, int(self._number(values.get("figure")))),
                        max(0.0, self._number(values.get("life_limit_kg"))),
                        max(0.0, self._number(values.get("used_kg"))),
                        max(0.0, self._number(values.get("tenefer_used_m"))),
                        str(values.get("status") or "AKTİF").upper(),
                        str(values.get("location") or ""),
                        str(values.get("note") or ""),
                    ),
                )
                die_id = int(
                    connection.execute(
                        """
                        SELECT id FROM dies
                        WHERE organization_id = ? AND die_code = ? AND spare_no = ?
                        """,
                        (organization_id, die_code, spare_no),
                    ).fetchone()[0]
                )
                for document_type, key in (
                    ("KALIP PDF", "pdf_path"),
                    ("KALIP GÖRSELİ", "image_path"),
                ):
                    if self._upsert_attachment(
                        connection,
                        entity_type="DIE",
                        entity_id=die_id,
                        document_type=document_type,
                        file_path=str(values.get(key) or ""),
                        username=username,
                        source_system="LEGACY",
                    ) is not None:
                        counts["attachments"] += 1
                counts["dies"] += 1

            for values in recipes:
                profile_id = profile_lookup.get(
                    str(values.get("profile_code") or "").strip().upper()
                )
                recipe_code = str(
                    values.get("order_ref") or values.get("recipe_code") or ""
                ).strip().upper()
                if profile_id is None or not recipe_code:
                    continue
                route_code = f"IMP-{recipe_code}"[:60]
                route_name = str(values.get("stock_name") or f"Reçete {recipe_code}")
                connection.execute(
                    """
                    INSERT INTO routes(
                        organization_id, profile_id, code, name, recipe_name,
                        production_length_mm, surface, color, alloy, temper,
                        mechanical, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, code) DO UPDATE SET
                        profile_id = excluded.profile_id, name = excluded.name,
                        recipe_name = excluded.recipe_name,
                        production_length_mm = excluded.production_length_mm,
                        surface = excluded.surface, color = excluded.color,
                        alloy = excluded.alloy, temper = excluded.temper,
                        mechanical = excluded.mechanical, active = excluded.active
                    """,
                    (
                        organization_id,
                        profile_id,
                        route_code,
                        route_name,
                        route_name,
                        max(0, int(self._number(values.get("production_length_mm")))),
                        str(values.get("surface") or "").upper(),
                        str(values.get("color") or "").upper(),
                        str(values.get("alloy") or "").upper(),
                        str(values.get("temper") or "").upper(),
                        str(values.get("mechanical") or "").upper(),
                        0 if str(values.get("status") or "").upper() == "KAPALI" else 1,
                    ),
                )
                route_id = int(
                    connection.execute(
                        "SELECT id FROM routes WHERE organization_id = ? AND code = ?",
                        (organization_id, route_code),
                    ).fetchone()[0]
                )
                connection.execute("DELETE FROM route_steps WHERE route_id = ?", (route_id,))
                preserved_steps = self._imported_route_steps(values)
                structured_steps = values.get("route_steps")
                if isinstance(structured_steps, list):
                    for raw_step in structured_steps:
                        if not isinstance(raw_step, dict):
                            continue
                        operation_external_id = str(
                            raw_step.get("operation_external_id") or ""
                        ).strip()
                        station_external_id = str(
                            raw_step.get("station_external_id") or ""
                        ).strip()
                        operation_name = str(
                            raw_step.get("operation")
                            or (f"Operasyon {operation_external_id}" if operation_external_id else "")
                        ).strip()
                        station_name = str(
                            raw_step.get("station")
                            or (f"İstasyon {station_external_id}" if station_external_id else "")
                        ).strip()
                        operation_id = None
                        if operation_external_id:
                            operation_code = f"ALU-OP-{operation_external_id}"[:80]
                            connection.execute(
                                """
                                INSERT INTO operations(
                                    organization_id, external_source, external_id,
                                    code, name, active
                                ) VALUES (?, 'LEGACY', ?, ?, ?, 1)
                                ON CONFLICT(organization_id, code) DO UPDATE SET
                                    external_source = excluded.external_source,
                                    external_id = excluded.external_id,
                                    name = excluded.name, active = 1
                                """,
                                (
                                    organization_id,
                                    operation_external_id,
                                    operation_code,
                                    operation_name or operation_code,
                                ),
                            )
                            operation_id = int(
                                connection.execute(
                                    "SELECT id FROM operations WHERE organization_id = ? AND code = ?",
                                    (organization_id, operation_code),
                                ).fetchone()[0]
                            )
                        if station_external_id:
                            station_code = f"ALU-ST-{station_external_id}"[:80]
                            connection.execute(
                                """
                                INSERT INTO stations(
                                    organization_id, operation_id, external_source,
                                    external_id, code, name, active
                                ) VALUES (?, ?, 'LEGACY', ?, ?, ?, 1)
                                ON CONFLICT(organization_id, code) DO UPDATE SET
                                    operation_id = COALESCE(excluded.operation_id, stations.operation_id),
                                    external_source = excluded.external_source,
                                    external_id = excluded.external_id,
                                    name = excluded.name, active = 1
                                """,
                                (
                                    organization_id,
                                    operation_id,
                                    station_external_id,
                                    station_code,
                                    station_name or station_code,
                                ),
                            )
                for sequence, step in enumerate(preserved_steps, start=1):
                    connection.execute(
                        """
                        INSERT INTO route_steps(
                            route_id, sequence_no, operation, default_station,
                            input_warehouse_id, output_warehouse_id
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            route_id,
                            sequence,
                            step["operation"],
                            step["station"],
                            self.warehouse_id(connection, step["input_warehouse"]),
                            self.warehouse_id(connection, step["output_warehouse"]),
                        ),
                    )

                recipe_external_id = str(
                    values.get("external_id") or recipe_code
                ).strip()
                connection.execute(
                    """
                    INSERT INTO recipes(
                        organization_id, profile_id, route_id, external_source,
                        external_id, recipe_code, recipe_name,
                        main_stock_external_id, raw_material_stock_external_id,
                        production_length_mm, saw_allowance_mm, hanger_allowance_mm,
                        active, raw_payload_json
                    ) VALUES (?, ?, ?, 'LEGACY', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_id, recipe_code) DO UPDATE SET
                        profile_id = excluded.profile_id,
                        route_id = excluded.route_id,
                        external_source = excluded.external_source,
                        external_id = excluded.external_id,
                        recipe_name = excluded.recipe_name,
                        main_stock_external_id = excluded.main_stock_external_id,
                        raw_material_stock_external_id = excluded.raw_material_stock_external_id,
                        production_length_mm = excluded.production_length_mm,
                        saw_allowance_mm = excluded.saw_allowance_mm,
                        hanger_allowance_mm = excluded.hanger_allowance_mm,
                        active = excluded.active,
                        raw_payload_json = excluded.raw_payload_json
                    """,
                    (
                        organization_id,
                        profile_id,
                        route_id,
                        recipe_external_id,
                        recipe_code,
                        route_name,
                        str(values.get("main_stock_external_id") or ""),
                        str(values.get("raw_material_stock_external_id") or ""),
                        max(0.0, self._number(values.get("production_length_mm"))),
                        max(0.0, self._number(values.get("saw_allowance_mm"))),
                        max(0.0, self._number(values.get("hanger_allowance_mm"))),
                        0 if str(values.get("status") or "").upper() == "KAPALI" else 1,
                        json.dumps(
                            values.get("raw_payload") or {},
                            ensure_ascii=False,
                            default=str,
                        ),
                    ),
                )
                recipe_id = int(
                    connection.execute(
                        "SELECT id FROM recipes WHERE organization_id = ? AND recipe_code = ?",
                        (organization_id, recipe_code),
                    ).fetchone()[0]
                )
                connection.execute("DELETE FROM recipe_lines WHERE recipe_id = ?", (recipe_id,))
                detail_lines = values.get("detail_lines")
                if isinstance(detail_lines, list):
                    for line_index, line in enumerate(detail_lines, start=1):
                        if not isinstance(line, dict):
                            continue
                        line_external_id = str(
                            line.get("external_id") or f"{recipe_external_id}-{line_index}"
                        ).strip()
                        connection.execute(
                            """
                            INSERT INTO recipe_lines(
                                recipe_id, external_source, external_id,
                                parent_recipe_external_id, operation_external_id,
                                station_external_id, process_type, sequence_no,
                                route_sequence_no, stock_external_id, quantity,
                                unit_external_id, main_unit_external_id, main_quantity,
                                numerator, denominator, description,
                                warehouse_external_id, external_unit_weight,
                                external_kg, external_quantity, external_metre,
                                raw_payload_json
                            ) VALUES (
                                ?, 'LEGACY', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                            """,
                            (
                                recipe_id,
                                line_external_id,
                                str(line.get("parent_recipe_external_id") or ""),
                                str(line.get("operation_external_id") or ""),
                                str(line.get("station_external_id") or ""),
                                str(line.get("process_type") or ""),
                                int(self._number(line.get("sequence_no"))),
                                int(self._number(line.get("route_sequence_no"))),
                                str(line.get("stock_external_id") or ""),
                                self._number(line.get("quantity")),
                                str(line.get("unit_external_id") or ""),
                                str(line.get("main_unit_external_id") or ""),
                                self._number(line.get("main_quantity")),
                                self._number(line.get("numerator")),
                                self._number(line.get("denominator")),
                                str(line.get("description") or ""),
                                str(line.get("warehouse_external_id") or ""),
                                self._number(line.get("external_unit_weight")),
                                self._number(line.get("external_kg")),
                                self._number(line.get("external_quantity")),
                                self._number(line.get("external_metre")),
                                json.dumps(
                                    line.get("raw_payload") or {},
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            ),
                        )
                        counts["recipe_lines"] += 1
                conditions = values.get("route_conditions")
                if isinstance(conditions, list):
                    for condition_index, condition in enumerate(conditions, start=1):
                        if not isinstance(condition, dict):
                            continue
                        condition_external_id = str(
                            condition.get("external_id")
                            or f"{recipe_external_id}-K-{condition_index}"
                        ).strip()
                        connection.execute(
                            """
                            INSERT INTO route_conditions(
                                organization_id, external_source, external_id,
                                code, name, priority, active, raw_payload_json
                            ) VALUES (?, 'LEGACY', ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(organization_id, external_source, external_id)
                            DO UPDATE SET code = excluded.code, name = excluded.name,
                                priority = excluded.priority, active = excluded.active,
                                raw_payload_json = excluded.raw_payload_json
                            """,
                            (
                                organization_id,
                                condition_external_id,
                                str(condition.get("code") or ""),
                                str(condition.get("name") or ""),
                                int(self._number(condition.get("priority"))),
                                1 if condition.get("active", True) else 0,
                                json.dumps(
                                    condition.get("raw_payload") or {},
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            ),
                        )
                        condition_id = int(
                            connection.execute(
                                """
                                SELECT id FROM route_conditions
                                WHERE organization_id = ? AND external_source = 'LEGACY'
                                  AND external_id = ?
                                """,
                                (organization_id, condition_external_id),
                            ).fetchone()[0]
                        )
                        connection.execute(
                            "DELETE FROM route_condition_values WHERE route_condition_id = ?",
                            (condition_id,),
                        )
                        for value_index, condition_value in enumerate(
                            condition.get("values") or [], start=1
                        ):
                            if not isinstance(condition_value, dict):
                                continue
                            value_external_id = str(
                                condition_value.get("external_id")
                                or f"{condition_external_id}-V-{value_index}"
                            ).strip()
                            connection.execute(
                                """
                                INSERT INTO route_condition_values(
                                    route_condition_id, external_source, external_id,
                                    property_external_id, operator, value_text,
                                    raw_payload_json
                                ) VALUES (?, 'LEGACY', ?, ?, ?, ?, ?)
                                """,
                                (
                                    condition_id,
                                    value_external_id,
                                    str(condition_value.get("property_external_id") or ""),
                                    str(condition_value.get("operator") or "="),
                                    str(condition_value.get("value") or ""),
                                    json.dumps(
                                        condition_value.get("raw_payload") or {},
                                        ensure_ascii=False,
                                        default=str,
                                    ),
                                ),
                            )
                        route_external_id = str(
                            values.get("route_external_id") or route_code
                        ).strip()
                        connection.execute(
                            """
                            INSERT INTO route_condition_routes(
                                route_condition_id, route_id, route_external_id,
                                sequence_no, raw_payload_json
                            ) VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(route_condition_id, route_external_id)
                            DO UPDATE SET route_id = excluded.route_id,
                                sequence_no = excluded.sequence_no,
                                raw_payload_json = excluded.raw_payload_json
                            """,
                            (
                                condition_id,
                                route_id,
                                route_external_id,
                                int(self._number(condition.get("route_sequence_no"))),
                                json.dumps(
                                    condition.get("route_link_raw_payload") or {},
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            ),
                        )
                        counts["route_conditions"] += 1
                counts["recipes"] += 1
                counts["routes"] += 1
            self._audit(
                connection,
                username=username,
                action="IMPORT",
                entity_type="MASTER_DATA",
                entity_id=None,
                record_key="LEGACY",
                after=counts,
            )
            connection.commit()
        return counts

    def create_request_reason(
        self, *, code: str, name: str, description: str = "", username: str = ""
    ) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            row_id = master_data_service.create_request_reason(
                connection, organization_id,
                code=code, name=name, description=description,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="request_reason", entity_id=row_id, record_key=code,
            )
            connection.commit()
        return row_id

    def create_customer_complaint(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            complaint_no = self._next_no(connection, "SK")
            row_id = master_data_service.create_customer_complaint(
                connection, organization_id,
                complaint_no=complaint_no, username=username, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="customer_complaint", entity_id=row_id,
                record_key=complaint_no,
            )
            connection.commit()
        return row_id

    def create_sales_price_list(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            if not str(fields.get("list_code") or "").strip():
                fields = dict(fields)
                fields["list_code"] = self._next_no(connection, "FL")
            row_id = master_data_service.create_sales_price_list(
                connection, organization_id, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="sales_price_list", entity_id=row_id,
                record_key=str(fields.get("list_code") or ""),
            )
            connection.commit()
        return row_id

    def create_die_tooling_request(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            request_no = self._next_no(connection, "KT")
            row_id = master_data_service.create_die_tooling_request(
                connection, organization_id,
                request_no=request_no, username=username, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="die_tooling_request", entity_id=row_id,
                record_key=request_no,
            )
            connection.commit()
        return row_id

    def create_die_tooling_work_order(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            work_order_no = self._next_no(connection, "KIE")
            row_id = master_data_service.create_die_tooling_work_order(
                connection, organization_id,
                work_order_no=work_order_no, username=username, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="die_tooling_work_order", entity_id=row_id,
                record_key=work_order_no,
            )
            connection.commit()
        return row_id

    def create_die_tooling_slip(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            slip_no = self._next_no(connection, "KFS")
            row_id = master_data_service.create_die_tooling_slip(
                connection, organization_id,
                slip_no=slip_no, username=username, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="die_tooling_slip", entity_id=row_id, record_key=slip_no,
            )
            connection.commit()
        return row_id

    def create_die_tooling_problem(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            problem_no = self._next_no(connection, "KPR")
            row_id = master_data_service.create_die_tooling_problem(
                connection, organization_id,
                problem_no=problem_no, username=username, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="die_tooling_problem", entity_id=row_id,
                record_key=problem_no,
            )
            connection.commit()
        return row_id

    def create_service_item_master(
        self, *, code: str, name: str, unit: str = "KG",
        description: str = "", username: str = "",
    ) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            row_id = master_data_service.create_service_item(
                connection, organization_id,
                code=code, name=name, unit=unit, description=description,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="service_item", entity_id=row_id, record_key=code,
            )
            connection.commit()
        return row_id

    def create_party_product_code(self, *, username: str, **fields: Any) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            row_id = master_data_service.create_party_product_code(
                connection, organization_id, **fields,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="party_product_code", entity_id=row_id,
                record_key=str(fields.get("external_code") or ""),
            )
            connection.commit()
        return row_id

    def create_property_set_master(
        self, *, code: str, name: str, property_kind: str = "YÜZEY", username: str = "",
    ) -> int:
        with closing(self.connect()) as connection:
            organization_id = self.organization_id(connection)
            row_id = master_data_service.create_property_set(
                connection, organization_id,
                code=code, name=name, property_kind=property_kind,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="property_set", entity_id=row_id, record_key=code,
            )
            connection.commit()
        return row_id

    def create_property_set_value(
        self, *, property_set_id: int, code: str, name: str,
        sort_order: int = 0, username: str = "",
    ) -> int:
        with closing(self.connect()) as connection:
            row_id = master_data_service.create_property_set_value(
                connection,
                property_set_id=int(property_set_id),
                code=code, name=name, sort_order=sort_order,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="property_set_value", entity_id=row_id, record_key=code,
            )
            connection.commit()
        return row_id

    def create_sales_price_list_line(
        self, *, price_list_id: int, profile_id: int, unit_price: float,
        surface: str = "", alloy: str = "", temper: str = "",
        currency: str = "USD", username: str = "",
    ) -> int:
        with closing(self.connect()) as connection:
            row_id = master_data_service.create_sales_price_list_line(
                connection,
                price_list_id=int(price_list_id), profile_id=int(profile_id),
                unit_price=unit_price, surface=surface, alloy=alloy,
                temper=temper, currency=currency,
            )
            self._audit(
                connection, username=username, action="CREATE",
                entity_type="sales_price_list_line", entity_id=row_id,
                record_key=str(price_list_id),
            )
            connection.commit()
        return row_id

    def list_sales_price_list_lines(self, price_list_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_sales_price_list_lines(
                connection, int(price_list_id),
            )

    def create_subcontractor(
        self, code: str, name: str, *, username: str, **fields: Any
    ) -> int:
        return self.create_supplier(
            code, name, supplier_type="FASONCU", username=username, **fields,
        )

    def recalculate_all_order_line_status(self) -> int:
        with closing(self.connect()) as connection:
            count = recalculate_order_line_status(connection)
            connection.commit()
        return count

    def list_request_reasons(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_request_reasons(
                connection, self.organization_id(connection)
            )

    def list_customer_product_codes(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_party_product_codes(
                connection, self.organization_id(connection), party_type="CUSTOMER"
            )

    def list_supplier_product_codes(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_party_product_codes(
                connection, self.organization_id(connection), party_type="SUPPLIER"
            )

    def list_service_items_master(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_service_items(
                connection, self.organization_id(connection)
            )

    def list_property_sets(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_property_sets(
                connection, self.organization_id(connection)
            )

    def list_property_values(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_property_values(
                connection, self.organization_id(connection)
            )

    def list_sales_price_lists(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_sales_price_lists(
                connection, self.organization_id(connection)
            )

    def list_customer_complaints(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_customer_complaints(
                connection, self.organization_id(connection)
            )

    def list_die_tooling_requests(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_die_tooling_requests(
                connection, self.organization_id(connection)
            )

    def list_die_tooling_work_orders(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_die_tooling_work_orders(
                connection, self.organization_id(connection), pending_only=pending_only
            )

    def list_die_tooling_slips(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_die_tooling_slips(
                connection, self.organization_id(connection)
            )

    def list_die_tooling_problems(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_die_tooling_problems(
                connection, self.organization_id(connection)
            )

    def list_profiles_missing_die(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return master_data_service.list_profiles_without_die_on_open_orders(
                connection, self.organization_id(connection)
            )

    def factory_config_path(self) -> str:
        from models.factory_config import DEFAULT_RIGEL_CONFIG

        return str(DEFAULT_RIGEL_CONFIG)

    def list_subcontractors(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, code, name, supplier_type, phone, city, active
                FROM suppliers
                WHERE organization_id = ?
                  AND UPPER(supplier_type) IN ('FASON', 'FASONCU', 'FASONCİ')
                ORDER BY name
                """,
                (self.organization_id(connection),),
            ).fetchall()
        return [dict(row) for row in rows]

    def table_count(self, table: str) -> int:
        allowed = {
            "customers", "profiles", "dies", "sales_orders", "sales_order_lines",
            "production_orders", "work_orders", "production_entries",
            "stock_movements", "packages", "shipments", "audit_log",
            "attachments", "recipes", "recipe_lines", "route_conditions",
            "weighing_lists", "weighing_list_packages",
        }
        if table not in allowed:
            raise ValueError("Geçersiz tablo adı.")
        with closing(self.connect()) as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
