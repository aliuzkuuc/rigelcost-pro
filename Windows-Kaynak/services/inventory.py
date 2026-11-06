from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


class InventoryService:
    """Stok kartlarını ve hareketlerini yerel SQLite veritabanında tutar."""

    CATEGORIES = (
        "Billet",
        "Profil / Mamul",
        "Hurda / Fire",
        "Ambalaj",
        "Sarf Malzemesi",
        "Yedek Parça",
        "Diğer",
    )
    UNITS = ("kg", "ton", "adet", "metre", "m²", "m³", "litre", "paket")
    MOVEMENT_TYPES = ("GİRİŞ", "ÇIKIŞ", "SAYIM")

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
            return Path(override) / "inventory.db"
        location = QStandardPaths.writableLocation(
            QStandardPaths.AppDataLocation
        )
        base = Path(location or Path.home() / ".rigelcost")
        return base / "inventory.db"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS stock_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    min_quantity REAL NOT NULL DEFAULT 0,
                    current_quantity REAL NOT NULL DEFAULT 0,
                    average_cost REAL NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    movement_date TEXT NOT NULL,
                    movement_type TEXT NOT NULL,
                    quantity_delta REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    unit_cost REAL NOT NULL DEFAULT 0,
                    document_no TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES stock_items(id)
                );

                CREATE INDEX IF NOT EXISTS idx_stock_movements_item
                    ON stock_movements(item_id);
                CREATE INDEX IF NOT EXISTS idx_stock_movements_date
                    ON stock_movements(movement_date);
                """
            )
            connection.commit()

    @staticmethod
    def _positive_name(name: str, value: float, *, allow_zero: bool) -> float:
        number = float(value)
        if number < 0 or (not allow_zero and number == 0):
            condition = "negatif olamaz" if allow_zero else "sıfırdan büyük olmalıdır"
            raise ValueError(f"{name} {condition}.")
        return number

    def add_item(
        self,
        code: str,
        name: str,
        category: str,
        unit: str,
        *,
        min_quantity: float = 0,
        opening_quantity: float = 0,
        opening_unit_cost: float = 0,
    ) -> int:
        code = code.strip().upper()
        name = name.strip()
        category = category.strip()
        unit = unit.strip()
        if not code:
            raise ValueError("Stok kodu boş olamaz.")
        if not name:
            raise ValueError("Stok adı boş olamaz.")
        if not category or not unit:
            raise ValueError("Kategori ve birim seçilmelidir.")

        min_quantity = self._positive_name(
            "Minimum stok", min_quantity, allow_zero=True
        )
        opening_quantity = self._positive_name(
            "Açılış miktarı", opening_quantity, allow_zero=True
        )
        opening_unit_cost = self._positive_name(
            "Açılış birim maliyeti", opening_unit_cost, allow_zero=True
        )
        now = datetime.now().isoformat(timespec="seconds")

        try:
            with closing(self.connect()) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO stock_items (
                        code, name, category, unit, min_quantity,
                        current_quantity, average_cost, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code,
                        name,
                        category,
                        unit,
                        min_quantity,
                        opening_quantity,
                        opening_unit_cost,
                        now,
                        now,
                    ),
                )
                item_id = int(cursor.lastrowid)
                if opening_quantity > 0:
                    connection.execute(
                        """
                        INSERT INTO stock_movements (
                            item_id, movement_date, movement_type,
                            quantity_delta, balance_after, unit_cost,
                            document_no, note, created_at
                        ) VALUES (?, ?, 'AÇILIŞ', ?, ?, ?, '', ?, ?)
                        """,
                        (
                            item_id,
                            date.today().isoformat(),
                            opening_quantity,
                            opening_quantity,
                            opening_unit_cost,
                            "İlk stok kartı açılışı",
                            now,
                        ),
                    )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Bu stok kodu zaten kullanılıyor.") from exc
        return item_id

    def record_movement(
        self,
        item_id: int,
        movement_type: str,
        quantity: float,
        *,
        unit_cost: float = 0,
        document_no: str = "",
        note: str = "",
        movement_date: str | None = None,
    ) -> dict[str, float]:
        movement_type = movement_type.strip().upper()
        if movement_type not in self.MOVEMENT_TYPES:
            raise ValueError("Hareket tipi geçersiz.")
        quantity = self._positive_name(
            "Miktar", quantity, allow_zero=False
        )
        unit_cost = self._positive_name(
            "Birim maliyet", unit_cost, allow_zero=True
        )
        movement_date = movement_date or date.today().isoformat()
        try:
            date.fromisoformat(movement_date)
        except ValueError as exc:
            raise ValueError("Hareket tarihi geçersiz.") from exc

        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            item = connection.execute(
                """
                SELECT id, current_quantity, average_cost
                FROM stock_items WHERE id = ? AND active = 1
                """,
                (int(item_id),),
            ).fetchone()
            if item is None:
                raise ValueError("Stok kartı bulunamadı.")

            current = float(item["current_quantity"])
            average = float(item["average_cost"])
            if movement_type == "GİRİŞ":
                delta = quantity
                new_balance = current + quantity
                if unit_cost > 0 and new_balance > 0:
                    average = (
                        current * average + quantity * unit_cost
                    ) / new_balance
            elif movement_type == "ÇIKIŞ":
                delta = -quantity
                new_balance = current - quantity
                if new_balance < -1e-9:
                    raise ValueError(
                        "Çıkış miktarı mevcut stoktan fazla olamaz."
                    )
                new_balance = max(0.0, new_balance)
                unit_cost = average
            else:
                new_balance = quantity
                delta = new_balance - current
                unit_cost = average

            now = datetime.now().isoformat(timespec="seconds")
            connection.execute(
                """
                UPDATE stock_items
                SET current_quantity = ?, average_cost = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_balance, average, now, int(item_id)),
            )
            connection.execute(
                """
                INSERT INTO stock_movements (
                    item_id, movement_date, movement_type, quantity_delta,
                    balance_after, unit_cost, document_no, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(item_id),
                    movement_date,
                    movement_type,
                    delta,
                    new_balance,
                    unit_cost,
                    document_no.strip(),
                    note.strip(),
                    now,
                ),
            )
            connection.commit()

        return {
            "quantity_delta": delta,
            "balance_after": new_balance,
            "average_cost": average,
        }

    def list_items(
        self,
        *,
        search: str = "",
        category: str = "",
    ) -> list[dict[str, Any]]:
        clauses = ["active = 1"]
        parameters: list[Any] = []
        if search.strip():
            clauses.append("(code LIKE ? OR name LIKE ?)")
            term = f"%{search.strip()}%"
            parameters.extend([term, term])
        if category and category != "Tümü":
            clauses.append("category = ?")
            parameters.append(category)

        query = f"""
            SELECT id, code, name, category, unit, min_quantity,
                   current_quantity, average_cost,
                   current_quantity * average_cost AS stock_value,
                   CASE
                       WHEN min_quantity > 0
                            AND current_quantity <= min_quantity THEN 1
                       ELSE 0
                   END AS is_low
            FROM stock_items
            WHERE {' AND '.join(clauses)}
            ORDER BY is_low DESC, category, code
        """
        with closing(self.connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def list_movements(
        self,
        *,
        item_id: int | None = None,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = []
        condition = ""
        if item_id is not None:
            condition = "WHERE m.item_id = ?"
            parameters.append(int(item_id))
        parameters.append(max(1, min(int(limit), 2_000)))

        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT m.id, m.movement_date, m.movement_type,
                       m.quantity_delta, m.balance_after, m.unit_cost,
                       m.document_no, m.note,
                       i.code, i.name, i.unit
                FROM stock_movements AS m
                JOIN stock_items AS i ON i.id = m.item_id
                {condition}
                ORDER BY m.movement_date DESC, m.id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, float]:
        today = date.today().isoformat()
        with closing(self.connect()) as connection:
            item_summary = connection.execute(
                """
                SELECT COUNT(*) AS item_count,
                       SUM(CASE WHEN current_quantity <= min_quantity
                                     AND min_quantity > 0
                                THEN 1 ELSE 0 END) AS low_count,
                       SUM(CASE WHEN unit = 'kg'
                                THEN current_quantity ELSE 0 END) AS kg_stock,
                       SUM(current_quantity * average_cost) AS stock_value
                FROM stock_items WHERE active = 1
                """
            ).fetchone()
            movement_count = connection.execute(
                """
                SELECT COUNT(*) FROM stock_movements
                WHERE movement_date = ?
                """,
                (today,),
            ).fetchone()[0]

        return {
            "item_count": float(item_summary["item_count"] or 0),
            "low_count": float(item_summary["low_count"] or 0),
            "kg_stock": float(item_summary["kg_stock"] or 0),
            "stock_value": float(item_summary["stock_value"] or 0),
            "today_movement_count": float(movement_count or 0),
        }
