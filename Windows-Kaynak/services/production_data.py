from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from PySide6.QtCore import QStandardPaths


MONTHS = (
    "OCAK",
    "ŞUBAT",
    "MART",
    "NİSAN",
    "MAYIS",
    "HAZİRAN",
    "TEMMUZ",
    "AĞUSTOS",
    "EYLÜL",
    "EKİM",
    "KASIM",
    "ARALIK",
)

DEFAULT_PRESS_NAME = "6 İNÇ 1650 UST EKSTRÜZYON PRES"


def parse_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return 0.0
    text = re.sub(r"[^0-9,.-]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return max(0.0, float(text))
    except ValueError:
        return 0.0


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip())
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.upper()
    return re.sub(r"[^A-Z0-9]", "", text)


NORMALIZED_MONTHS = {
    normalize_text(month): index for index, month in enumerate(MONTHS)
}


class ProductionDataStore:
    """Aylık pres üretimini yerel JSON dosyasında güvenli biçimde saklar."""

    def data_path(self) -> Path:
        override = os.environ.get("RIGELCOST_DATA_DIR")
        if override:
            root = Path(override)
        else:
            root = Path(
                QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            )
        return root / "production_dashboard.json"

    @staticmethod
    def default_record() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "year": datetime.now().year,
            "press_name": DEFAULT_PRESS_NAME,
            "monthly_kg": [0.0] * 12,
        }

    def load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.data_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.default_record()
        if not isinstance(payload, dict):
            return self.default_record()
        return self.validate_record(payload)

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        validated = self.validate_record(record)
        path = self.data_path()
        temp_path = path.with_suffix(path.suffix + ".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(validated, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, path)
        return validated

    @classmethod
    def validate_record(cls, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            year = int(payload.get("year") or datetime.now().year)
        except (TypeError, ValueError):
            year = datetime.now().year
        year = min(2100, max(2000, year))
        press_name = str(payload.get("press_name") or DEFAULT_PRESS_NAME).strip()
        raw_values = payload.get("monthly_kg")
        if not isinstance(raw_values, list):
            raw_values = []
        monthly_kg = [
            parse_number(raw_values[index]) if index < len(raw_values) else 0.0
            for index in range(12)
        ]
        return {
            "schema_version": 1,
            "year": year,
            "press_name": press_name or DEFAULT_PRESS_NAME,
            "monthly_kg": monthly_kg,
        }

    @classmethod
    def import_excel(cls, source: str | Path) -> dict[str, Any]:
        path = Path(source)
        if not path.exists():
            raise ValueError("Seçilen Excel dosyası bulunamadı.")
        try:
            workbook = load_workbook(
                path,
                read_only=True,
                data_only=True,
            )
        except Exception as exc:
            raise ValueError(f"Excel dosyası açılamadı: {exc}") from exc

        monthly_kg = [0.0] * 12
        found_months: set[int] = set()
        year_candidates: list[int] = []
        for source_text in (path.stem, *workbook.sheetnames):
            year_candidates.extend(
                int(match) for match in re.findall(r"20\d{2}", source_text)
            )

        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                values = list(row)
                for column, value in enumerate(values):
                    month_index = NORMALIZED_MONTHS.get(normalize_text(value))
                    if month_index is None:
                        continue
                    production = 0.0
                    for candidate in values[column + 1 :]:
                        if isinstance(candidate, (int, float)):
                            production = parse_number(candidate)
                            break
                        parsed = parse_number(candidate)
                        if parsed > 0:
                            production = parsed
                            break
                    monthly_kg[month_index] = production
                    found_months.add(month_index)
        workbook.close()

        if not found_months:
            raise ValueError(
                "Excel içinde OCAK-ARALIK aylık üretim satırları bulunamadı."
            )
        return {
            "schema_version": 1,
            "year": year_candidates[0] if year_candidates else datetime.now().year,
            "press_name": DEFAULT_PRESS_NAME,
            "monthly_kg": monthly_kg,
        }
