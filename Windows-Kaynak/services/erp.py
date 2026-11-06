from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from models.erp_definitions import ModuleSpec, get_module_spec


class ErpService:
    """İşletme modüllerini maliyet verisinden ayrı SQLite dosyasında tutar."""

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
            return Path(override) / "erp.db"
        location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        return Path(location or Path.home() / ".rigelcost") / "erp.db"

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
                CREATE TABLE IF NOT EXISTS erp_sequences (
                    prefix TEXT PRIMARY KEY,
                    last_value INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS erp_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT NOT NULL,
                    module TEXT NOT NULL,
                    record_no TEXT NOT NULL,
                    parent_id INTEGER,
                    source_ref TEXT NOT NULL DEFAULT '',
                    source_system TEXT NOT NULL DEFAULT '',
                    external_key TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    search_text TEXT NOT NULL DEFAULT '',
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(department, module, record_no),
                    FOREIGN KEY(parent_id) REFERENCES erp_records(id)
                        ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_erp_records_module
                    ON erp_records(department, module, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_erp_records_parent
                    ON erp_records(parent_id);
                CREATE INDEX IF NOT EXISTS idx_erp_records_status
                    ON erp_records(status);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(erp_records)")
            }
            if "source_system" not in columns:
                connection.execute(
                    "ALTER TABLE erp_records ADD COLUMN source_system TEXT NOT NULL DEFAULT ''"
                )
            if "external_key" not in columns:
                connection.execute(
                    "ALTER TABLE erp_records ADD COLUMN external_key TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_records_external
                ON erp_records(source_system, department, module, external_key)
                WHERE source_system <> '' AND external_key <> ''
                """
            )
            connection.commit()

    @staticmethod
    def number(value: object) -> float:
        if value is None or value == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(" ", "")
        if not text:
            return 0.0
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def parse_datetime(value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        for candidate in (text, text.replace(" ", "T")):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        for pattern in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
        return None

    def calculate_data(
        self,
        spec: ModuleSpec,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        data = dict(values)
        field_keys = spec.field_map

        if "total" in field_keys:
            amount_basis = self.number(data.get("quantity"))
            if "kg" in field_keys and self.number(data.get("kg")) > 0:
                amount_basis = self.number(data.get("kg"))
            data["total"] = round(
                amount_basis * self.number(data.get("unit_price")),
                4,
            )

        if spec.name in {
            "Teklifler",
            "Satış Siparişleri",
            "Bekleyen Siparişler",
            "Bekleyen Siparişler Pivot",
            "Sipariş Detay (Satış)",
            "Sipariş Detay (Numune)",
            "Profil Fiyat Listeleri",
            "Üretim Siparişleri",
            "Üretim Siparişleri (Detay)",
            "Üretim Onayı Bekleyen Siparişler",
            "Üretim Planlama",
            "Üretim Emirleri",
            "Reçeteler",
        }:
            quantity = self.number(data.get("quantity"))
            length_m = self.number(
                data.get("production_length_mm")
                or data.get("stock_length_mm")
                or data.get("length_mm")
            ) / 1000.0
            unit_weight = self.number(data.get("unit_weight"))
            if quantity > 0 and length_m > 0 and unit_weight > 0:
                data["kg"] = round(quantity * length_m * unit_weight, 3)
                if "total" in field_keys:
                    data["total"] = round(
                        data["kg"] * self.number(data.get("unit_price")), 4
                    )

        if spec.name in {
            "İş Emirleri",
            "İş Emri Miktarları",
            "İstasyon Yükleri",
            "Planlama Takvimi",
        }:
            data["remaining_quantity"] = max(
                0.0,
                self.number(data.get("quantity"))
                - self.number(data.get("produced_quantity")),
            )
            data["remaining_kg"] = round(
                max(
                    0.0,
                    self.number(data.get("kg"))
                    - self.number(data.get("produced_kg")),
                ),
                3,
            )

        if spec.department == "Kalıphane" and "life_limit_kg" in field_keys:
            life = self.number(data.get("life_limit_kg"))
            used = self.number(data.get("used_kg"))
            data["remaining_kg"] = round(max(0.0, life - used), 3)
            data["usage_pct"] = round((used / life * 100.0) if life > 0 else 0.0, 2)
            if life > 0 and used >= life and data.get("status") == "AKTİF":
                data["status"] = "BAKIMDA"

        if "gross_kg" in field_keys and "net_kg" in field_keys and "fire_kg" in field_keys:
            gross = self.number(data.get("gross_kg"))
            net = self.number(data.get("net_kg"))
            metre = self.number(data.get("metre"))
            duration_min = self.number(data.get("duration_min"))
            theoretical_weight = self.number(data.get("theoretical_weight"))
            real_weight = self.number(data.get("real_weight"))
            fire = max(0.0, gross - net)
            data["fire_kg"] = round(fire, 3)
            data["fire_pct"] = round((fire / gross * 100.0) if gross > 0 else 0.0, 2)
            effective_minutes = max(
                0.0,
                duration_min - self.number(data.get("die_setup_min")),
            )
            data["kg_hour"] = round(
                (net / (effective_minutes / 60.0)) if effective_minutes > 0 else 0.0,
                2,
            )
            data["theoretical_net_kg"] = round(metre * theoretical_weight, 3)
            data["weight_diff_pct"] = round(
                ((real_weight - theoretical_weight) / theoretical_weight * 100.0)
                if theoretical_weight > 0
                else 0.0,
                2,
            )
            figure = max(1.0, self.number(data.get("figure")))
            data["tenefer_m"] = round(metre * figure, 3)

        if spec.department == "Bakım" or spec.name == "Duruşlar":
            planned_start = self.parse_datetime(data.get("planned_start"))
            planned_end = self.parse_datetime(data.get("planned_end"))
            actual_start = self.parse_datetime(data.get("actual_start"))
            actual_end = self.parse_datetime(data.get("actual_end"))
            if actual_start and actual_end and actual_end >= actual_start:
                actual_min = (actual_end - actual_start).total_seconds() / 60.0
                data["downtime_min"] = round(actual_min, 2)
            else:
                actual_min = self.number(data.get("downtime_min"))
            if planned_start and planned_end and planned_end >= planned_start:
                planned_min = (planned_end - planned_start).total_seconds() / 60.0
                if planned_min > 0 and actual_min > 0:
                    variance = abs(actual_min - planned_min) / planned_min
                    data["compliance_pct"] = round(max(0.0, 100.0 - variance * 100.0), 2)
            if actual_end and data.get("status") != "İPTAL":
                data["status"] = "TAMAMLANDI"

        return data

    def _next_record_no(
        self,
        connection: sqlite3.Connection,
        prefix: str,
    ) -> str:
        connection.execute(
            "INSERT OR IGNORE INTO erp_sequences(prefix, last_value) VALUES (?, 0)",
            (prefix,),
        )
        connection.execute(
            "UPDATE erp_sequences SET last_value = last_value + 1 WHERE prefix = ?",
            (prefix,),
        )
        value = connection.execute(
            "SELECT last_value FROM erp_sequences WHERE prefix = ?",
            (prefix,),
        ).fetchone()[0]
        return f"{prefix}-{date.today():%y%m}-{int(value):06d}"

    @staticmethod
    def _search_text(record_no: str, data: dict[str, Any]) -> str:
        return " ".join(
            [record_no, *(str(value) for value in data.values() if value is not None)]
        ).casefold()

    def create_record(
        self,
        department: str,
        module_name: str,
        values: dict[str, Any],
        *,
        parent_id: int | None = None,
        source_ref: str = "",
    ) -> int:
        spec = get_module_spec(department, module_name)
        data = self.calculate_data(spec, values)
        for field in spec.fields:
            if field.required and not str(data.get(field.key, "")).strip():
                raise ValueError(f"{field.label} boş bırakılamaz.")
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            record_no = self._next_record_no(connection, spec.prefix)
            cursor = connection.execute(
                """
                INSERT INTO erp_records (
                    department, module, record_no, parent_id, source_ref,
                    source_system, external_key, status, search_text, data_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?)
                """,
                (
                    department,
                    module_name,
                    record_no,
                    parent_id,
                    source_ref,
                    str(data.get("status") or ""),
                    self._search_text(record_no, data),
                    json.dumps(data, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def upsert_external_records(
        self,
        department: str,
        module_name: str,
        rows: list[tuple[str, dict[str, Any]]],
        *,
        source_system: str = "LEGACY",
    ) -> dict[str, int]:
        """Dış sistem kayıtlarını kimliğine göre tekrar oluşturmadan aktarır."""
        spec = get_module_spec(department, module_name)
        source_system = source_system.strip().upper()
        if not source_system:
            raise ValueError("Kaynak sistem adı boş olamaz.")
        now = datetime.now().isoformat(timespec="seconds")
        result = {"inserted": 0, "updated": 0, "skipped": 0}
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for external_key, raw_values in rows:
                external_key = str(external_key or "").strip()
                if not external_key:
                    result["skipped"] += 1
                    continue
                data = self.calculate_data(spec, raw_values)
                if any(
                    field.required and not str(data.get(field.key, "")).strip()
                    for field in spec.fields
                ):
                    result["skipped"] += 1
                    continue
                existing = connection.execute(
                    """
                    SELECT id, record_no FROM erp_records
                    WHERE source_system = ? AND department = ?
                      AND module = ? AND external_key = ?
                    """,
                    (source_system, department, module_name, external_key),
                ).fetchone()
                if existing is None:
                    record_no = self._next_record_no(connection, spec.prefix)
                    connection.execute(
                        """
                        INSERT INTO erp_records (
                            department, module, record_no, parent_id, source_ref,
                            source_system, external_key, status, search_text,
                            data_json, created_at, updated_at
                        ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            department,
                            module_name,
                            record_no,
                            external_key,
                            source_system,
                            external_key,
                            str(data.get("status") or ""),
                            self._search_text(record_no, data),
                            json.dumps(data, ensure_ascii=False),
                            now,
                            now,
                        ),
                    )
                    result["inserted"] += 1
                else:
                    connection.execute(
                        """
                        UPDATE erp_records
                        SET source_ref = ?, status = ?, search_text = ?,
                            data_json = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            external_key,
                            str(data.get("status") or ""),
                            self._search_text(str(existing["record_no"]), data),
                            json.dumps(data, ensure_ascii=False),
                            now,
                            int(existing["id"]),
                        ),
                    )
                    result["updated"] += 1
            connection.commit()
        return result

    def update_record(self, record_id: int, values: dict[str, Any]) -> None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT department, module, record_no FROM erp_records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Kayıt bulunamadı.")
            spec = get_module_spec(row["department"], row["module"])
            data = self.calculate_data(spec, values)
            for field in spec.fields:
                if field.required and not str(data.get(field.key, "")).strip():
                    raise ValueError(f"{field.label} boş bırakılamaz.")
            connection.execute(
                """
                UPDATE erp_records
                SET status = ?, search_text = ?, data_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(data.get("status") or ""),
                    self._search_text(row["record_no"], data),
                    json.dumps(data, ensure_ascii=False),
                    datetime.now().isoformat(timespec="seconds"),
                    int(record_id),
                ),
            )
            connection.commit()

    def delete_record(self, record_id: int) -> None:
        with closing(self.connect()) as connection:
            child_count = connection.execute(
                "SELECT COUNT(*) FROM erp_records WHERE parent_id = ?",
                (int(record_id),),
            ).fetchone()[0]
            if child_count:
                raise ValueError(
                    "Bu kayıt başka bir iş akışı kaydının kaynağıdır; önce bağlı kayıtları silin."
                )
            connection.execute("DELETE FROM erp_records WHERE id = ?", (int(record_id),))
            connection.commit()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            data = json.loads(result.pop("data_json"))
        except (json.JSONDecodeError, TypeError):
            data = {}
        result["data"] = data
        return result

    def get_record(self, record_id: int) -> dict[str, Any] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM erp_records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
        return self._decode(row) if row is not None else None

    def list_records(
        self,
        department: str,
        module_name: str,
        *,
        search: str = "",
        limit: int = 2_000,
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = [department, module_name]
        condition = ""
        if search.strip():
            condition = "AND search_text LIKE ?"
            parameters.append(f"%{search.strip().casefold()}%")
        parameters.append(max(1, min(int(limit), 10_000)))
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM erp_records
                WHERE department = ? AND module = ? {condition}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._decode(row) for row in rows]

    def summary(self, department: str, module_name: str) -> dict[str, float]:
        records = self.list_records(department, module_name, limit=10_000)
        open_count = 0
        total_kg = 0.0
        total_amount = 0.0
        for record in records:
            data = record["data"]
            closed_statuses = {"TAMAMLANDI", "KAPALI", "SEVK EDİLDİ", "İPTAL"}
            status = str(data.get("status") or record.get("status") or "").upper()
            if "press_status" in data:
                press_status = str(data.get("press_status") or "").upper()
                saw_status = str(data.get("saw_status") or "").upper()
                is_open = press_status not in closed_statuses or (
                    bool(saw_status) and saw_status not in closed_statuses
                )
            else:
                is_open = status not in closed_statuses
            if is_open:
                open_count += 1
            kg_value = data.get("net_kg") or data.get("kg")
            if not kg_value and str(data.get("unit") or "").upper() == "KG":
                kg_value = data.get("quantity")
            total_kg += self.number(kg_value)
            total_amount += self.number(data.get("total"))
        return {
            "record_count": float(len(records)),
            "open_count": float(open_count),
            "total_kg": total_kg,
            "total_amount": total_amount,
        }

    def create_linked_record(self, source_id: int) -> int:
        source = self.get_record(source_id)
        if source is None:
            raise ValueError("Kaynak kayıt bulunamadı.")
        source_spec = get_module_spec(source["department"], source["module"])
        if source_spec.next_step is None:
            raise ValueError("Bu kayıt için tanımlı bir sonraki aşama yok.")
        target_department, target_module = source_spec.next_step
        target_spec = get_module_spec(target_department, target_module)
        source_data = source["data"]
        values: dict[str, Any] = {}
        for field in target_spec.fields:
            if field.key in source_data:
                values[field.key] = source_data[field.key]
            else:
                values[field.key] = field.default

        source_no = str(source["record_no"])
        values["source_ref"] = source_no
        if "order_ref" in target_spec.field_map and not values.get("order_ref"):
            values["order_ref"] = source_data.get("order_ref") or source_no
        if "company" in target_spec.field_map and not values.get("company"):
            values["company"] = source_data.get("customer") or "FİRMA BELİRTİLMEDİ"
        if "profile_code" in target_spec.field_map and not values.get("profile_code"):
            values["profile_code"] = (
                source_data.get("stock_code")
                or source_data.get("stock_name")
                or "PROFİL BELİRTİLMEDİ"
            )
        if "production_order_ref" in target_spec.field_map:
            values["production_order_ref"] = source_no
        if "work_order_ref" in target_spec.field_map and not values.get("work_order_ref"):
            values["work_order_ref"] = source_no
        if "package_no" in target_spec.field_map and not values.get("package_no"):
            values["package_no"] = source_no
        if "stock_name" in target_spec.field_map and not values.get("stock_name"):
            values["stock_name"] = (
                source_data.get("profile_code")
                or source_data.get("stock_code")
                or "PROFİL"
            )
        if "status" in target_spec.field_map:
            values["status"] = target_spec.field_map["status"].default

        return self.create_record(
            target_department,
            target_module,
            values,
            parent_id=int(source["id"]),
            source_ref=source_no,
        )

    def linked_records(self, record_id: int) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM erp_records WHERE parent_id = ? ORDER BY id",
                (int(record_id),),
            ).fetchall()
        return [self._decode(row) for row in rows]
