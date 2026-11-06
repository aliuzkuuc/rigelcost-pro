from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

from openpyxl import load_workbook

from services.erp import ErpService
from services.local_workflow import LocalWorkflowService


ProgressCallback = Callable[[str, int, int], None]


class EncryptedConnectionStringError(ValueError):
    """Kaynak yapılandırmadaki SQL bağlantısı uygulamaya özel şifreliyse."""


def normalize_label(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().upper()
    text = text.replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
    text = text.replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")
    return re.sub(r"\s+", " ", text)


def first_value(row: dict[str, object], *keys: str) -> object:
    for key in keys:
        normalized = normalize_label(key)
        value = row.get(normalized)
        if value not in (None, ""):
            return value
    return ""


def payload_value(payload: dict[str, object], *keys: str) -> object:
    """SQL sütun adlarındaki alt çizgi/Türkçe farklarını tolere eder."""
    normalized = {
        normalize_label(key).replace("_", " "): value
        for key, value in payload.items()
    }
    for key in keys:
        value = normalized.get(normalize_label(key).replace("_", " "))
        if value not in (None, ""):
            return value
    return ""


def text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def number(value: object) -> float:
    return ErpService.number(value)


def date_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = text(value)
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        return raw


def bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize_label(value)
    if normalized in {"1", "EVET", "TRUE", "AKTIF", "VAR"}:
        return True
    if normalized in {"0", "HAYIR", "FALSE", "PASIF", "YOK"}:
        return False
    return default


def stable_key(prefix: str, *parts: object) -> str:
    cleaned = "|".join(text(part).casefold() for part in parts if text(part))
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


class DataImportService:
    """Eski sistem dışa aktarımlarını Rigel kayıtlarına güvenli biçimde taşır."""

    RAW_TABLES = (
        "FIRMA",
        "PROFIL",
        "KALIP",
        "KALIP_ISTASYON",
        "OPERASYON",
        "ISTASYON",
        "BIRIM",
        "STOK",
        "STOK_EX",
        "STOK_TO_OZELLIK",
        "STOK_OZELLIK",
        "STOK_OZELLIK_DEGER",
        "AMBAR",
        "SIPARIS",
        "SIPARIS_D",
        "RECETE",
        "RECETE_D",
        "ROTA",
        "ROTA_D",
        "ROTA_KOSUL",
        "ROTA_KOSUL_ROTA",
        "ROTA_KOSUL_OZELLIK",
        "URETIM_EMRI",
        "IS_EMRI",
        "IS_EMRI_D",
        "PLANLAMA",
        "STOK_FIS",
        "STOK_HA",
        "PRES_BASLIK",
        "PRES_BILLET",
        "PAKET",
        "PAKET_D",
        "PAKET_BASLIK",
        "KASA_BASLIK",
        "BAKIM_TA",
        "BAKIM_EMIR",
    )

    def __init__(
        self,
        erp_service: ErpService | None = None,
        staging_path: str | Path | None = None,
        workflow_service: LocalWorkflowService | None = None,
    ) -> None:
        self.erp = erp_service or ErpService()
        self.workflow = workflow_service or LocalWorkflowService(
            self.erp.database_path.with_name("rigel_operations.db")
        )
        self.staging_path = (
            Path(staging_path)
            if staging_path is not None
            else self.erp.database_path.with_name("data_import.db")
        )
        self.staging_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_staging()

    def staging_connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.staging_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize_staging(self) -> None:
        with closing(self.staging_connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS import_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    error_text TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS raw_records (
                    source_table TEXT NOT NULL,
                    external_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY(source_table, external_key)
                );

                CREATE TABLE IF NOT EXISTS imported_attachments (
                    source_relative_path TEXT PRIMARY KEY,
                    destination_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    imported_at TEXT NOT NULL
                );
                """
            )
            connection.commit()

    @staticmethod
    def discover_excel_files(root: str | Path) -> list[Path]:
        source = Path(root)
        if source.is_file() and source.suffix.lower() == ".xlsx":
            return [source]
        if not source.exists():
            raise ValueError("Seçilen eski sistem veri klasörü bulunamadı.")
        return sorted(
            path
            for path in source.rglob("*.xlsx")
            if not path.name.startswith("~$")
        )

    @staticmethod
    def workbook_rows(path: Path) -> Iterable[tuple[str, int, dict[str, object]]]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            for worksheet in workbook.worksheets:
                iterator = worksheet.iter_rows(values_only=True)
                try:
                    raw_headers = next(iterator)
                except StopIteration:
                    continue
                headers = [normalize_label(value) for value in raw_headers]
                if not any(headers):
                    continue
                for row_number, values in enumerate(iterator, start=2):
                    row = {
                        header: value
                        for header, value in zip(headers, values)
                        if header
                    }
                    if any(value not in (None, "") for value in row.values()):
                        yield worksheet.title, row_number, row
        finally:
            workbook.close()

    def import_excel_folder(
        self,
        root: str | Path,
        progress: ProgressCallback | None = None,
    ) -> dict[str, object]:
        files = self.discover_excel_files(root)
        if not files:
            raise ValueError("Seçilen yerde aktarılabilir Excel dosyası bulunamadı.")
        source_name = str(Path(root))
        batch_id = self._start_batch("EXCEL", source_name)
        totals = {"inserted": 0, "updated": 0, "skipped": 0}
        modules: dict[str, dict[str, int]] = defaultdict(
            lambda: {"inserted": 0, "updated": 0, "skipped": 0}
        )
        errors: list[str] = []
        customer_rows: dict[str, dict[str, Any]] = {}
        profile_rows: dict[str, dict[str, Any]] = {}
        die_rows: dict[str, dict[str, Any]] = {}

        try:
            for file_index, path in enumerate(files, start=1):
                if progress:
                    progress(path.name, file_index, len(files))
                try:
                    rows = list(self.workbook_rows(path))
                    self._collect_masters(
                        rows,
                        customer_rows,
                        profile_rows,
                        die_rows,
                        source_name=path.stem,
                    )
                    for department, module, mapped in self._map_workbook(path, rows):
                        result = self.erp.upsert_external_records(
                            department,
                            module,
                            mapped,
                            source_system="LEGACY",
                        )
                        key = f"{department} / {module}"
                        self._merge_counts(modules[key], result)
                        self._merge_counts(totals, result)
                except Exception as error:  # one broken export must not abort all files
                    errors.append(f"{path.name}: {error}")

            master_sets = (
                (
                    "Satış",
                    "Müşteriler",
                    [(key, values) for key, values in customer_rows.items()],
                ),
                (
                    "Kalıphane",
                    "Profil Kartları",
                    [(key, values) for key, values in profile_rows.items()],
                ),
                (
                    "Kalıphane",
                    "Kalıp Kartları",
                    [(key, values) for key, values in die_rows.items()],
                ),
            )
            for department, module, mapped in master_sets:
                result = self.erp.upsert_external_records(
                    department,
                    module,
                    mapped,
                    source_system="LEGACY",
                )
                key = f"{department} / {module}"
                self._merge_counts(modules[key], result)
                self._merge_counts(totals, result)

            attachment_summary = self.import_shared_files(root, progress)
            connected_summary = self.sync_connected_workflow()
            self._finish_batch(batch_id, totals, errors)
            return {
                "files": len(files),
                "modules": dict(modules),
                "errors": errors,
                "attachments": attachment_summary,
                "connected_workflow": connected_summary,
                **totals,
            }
        except Exception as error:
            self._fail_batch(batch_id, str(error))
            raise

    @staticmethod
    def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
        for key in ("inserted", "updated", "skipped"):
            target[key] = int(target.get(key, 0)) + int(source.get(key, 0))

    def _collect_masters(
        self,
        rows: list[tuple[str, int, dict[str, object]]],
        customers: dict[str, dict[str, Any]],
        profiles: dict[str, dict[str, Any]],
        dies: dict[str, dict[str, Any]],
        *,
        source_name: str = "",
    ) -> None:
        normalized_source = normalize_label(source_name)
        is_pending_die_export = "URETILECEK KALIPLAR" in normalized_source
        for _sheet, _row_no, row in rows:
            company = text(
                first_value(
                    row,
                    "FİRMA",
                    "FIRMA AD",
                    "FİRMA ADI",
                    "MÜŞTERİ",
                    "PROFİL FİRMA",
                    "SİPARİŞ FİRMASI",
                    "İŞLEM FİRMASI",
                )
            )
            if company and not company.isdigit() and len(company) > 2:
                key = stable_key("FIRMA", company)
                customers[key] = {
                    "code": "ALU-" + key.rsplit(":", 1)[1][:10].upper(),
                    "name": company,
                    "customer": True,
                    "supplier": False,
                    "subcontractor": False,
                    "active": True,
                    "note": "Eski sistem dışa aktarımından alınmıştır.",
                }

            profile_code = text(
                first_value(row, "PROFIL KOD", "PROFİL KOD", "PROFİL KODU")
            )
            if not profile_code:
                continue
            if is_pending_die_export:
                # This file is mapped below as a die-manufacturing work list;
                # it must not overwrite richer profile/die master cards.
                continue
            profile_name = text(
                first_value(
                    row,
                    "PROFİL AD",
                    "PROFİL ADI",
                    "PROFIL AD",
                    "PROFIL ADI",
                )
            )
            stock_name = text(first_value(row, "STOK AD", "STOK ADI", "SİPARİŞ STOK"))
            if not profile_name and not stock_name and not company:
                # Some legacy exports append a numeric summary cell below the
                # table.  It is not a profile card and must not become one.
                continue
            key = f"PROFIL:{profile_code}"
            profiles[key] = {
                "profile_code": profile_code,
                "profile_name": profile_name or stock_name or f"Profil {profile_code}",
                "company": text(
                    first_value(
                        row,
                        "PROFİL FİRMA",
                        "FİRMA ADI",
                        "FİRMA",
                        "MÜŞTERİ",
                    )
                ),
                "customer_code": text(
                    first_value(
                        row,
                        "ÜRÜN KOD",
                        "MÜŞTERİ PROFİL KODU",
                        "FİRMA PROFİL KODU",
                    )
                ),
                "unit_weight": number(
                    first_value(
                        row,
                        "REEL GRJ.",
                        "REEL GRAMAJ (Kg/m)",
                        "BİRİM AĞIRLIK",
                        "BİRİM AĞIRLIK (Kg/m)",
                        "TEORIK BİRİM AĞIRLIK (Kg/m)",
                    )
                ),
                "group": text(first_value(row, "GRUP ADI", "PROFİL GRUP")),
                "alloy": text(first_value(row, "ALAŞIM", "ALASIM")) or "6060B",
                "temper": text(first_value(row, "SERTLİK")) or "T5",
                "active": True,
                "note": text(first_value(row, "AÇIKLAMA"))
                or "Eski sistem dışa aktarımından alınmıştır.",
            }

            supplier_code = text(
                first_value(
                    row,
                    "KALIPÇI KODU",
                    "KALIPÇI KOD",
                    "KALIP KODU",
                    "KALIP KOD",
                )
            )
            spare_no = int(number(first_value(row, "YEDEK NO")))
            supplier = text(
                first_value(
                    row,
                    "TEDARİKÇİ",
                    "TEDARİKÇİ ADI",
                    "KALIPÇI",
                    "TEDARIKCI",
                )
            )
            if not supplier_code and not spare_no and not supplier:
                continue
            die_code = supplier_code or f"{profile_code}-{spare_no:02d}"
            die_key = stable_key("KALIP", profile_code, die_code, spare_no)
            status = text(first_value(row, "DURUM"))
            if not status:
                status = (
                    "AKTİF"
                    if bool_value(first_value(row, "AKTİF"), True)
                    else "HURDA"
                )
            notes = [
                text(first_value(row, "AÇIKLAMA")),
                text(first_value(row, "HURDA AÇIKLAMA")),
                text(first_value(row, "SON HAREKET AÇIKLAMASI")),
            ]
            note = " | ".join(dict.fromkeys(value for value in notes if value))
            dies[die_key] = {
                "die_code": die_code,
                "profile_code": profile_code,
                "profile_name": profile_name or stock_name,
                "group": text(first_value(row, "GRUP ADI", "PROFİL GRUP")),
                "spare_no": spare_no,
                "supplier": supplier,
                "supplier_code": supplier_code,
                "die_type": text(first_value(row, "KALIP CİNS", "KALIP CİNSİ")),
                "figure": int(
                    number(first_value(row, "FİGÜR", "FİGÜR ADET", "FIGUR"))
                )
                or 1,
                "diameter_mm": number(first_value(row, "ÇAP", "KALIP ÇAPI")),
                "length_mm": number(first_value(row, "BOY", "KALIP BOYU")),
                "life_limit_kg": number(first_value(row, "ÖMÜR KG", "ÖMÜR LİMİTİ")),
                "tenefer_limit_m": number(first_value(row, "TENEFER ÖMRÜ M")),
                "used_kg": number(
                    first_value(
                        row,
                        "BASILAN KG",
                        "TOPLAM BASILAN KG",
                        "PRES NET KG",
                    )
                ),
                "tenefer_used_m": number(first_value(row, "TENEFER BASILAN M")),
                "real_weight": number(first_value(row, "GERÇEK GRAMAJ")),
                "location": text(first_value(row, "RAF", "KONUM")),
                "status": status,
                "active": bool_value(first_value(row, "AKTİF"), True),
                "note": note or "Eski sistem dışa aktarımından alınmıştır.",
            }

    def _map_workbook(
        self,
        path: Path,
        rows: list[tuple[str, int, dict[str, object]]],
    ) -> Iterable[tuple[str, str, list[tuple[str, dict[str, Any]]]]]:
        if not rows:
            return []
        headers = set(rows[0][2])
        name = normalize_label(path.stem)
        mapped: list[tuple[str, str, list[tuple[str, dict[str, Any]]]]] = []

        if (
            "URETILECEK KALIPLAR" in name
            and {"PROFIL KODU", "YEDEK NO", "DURUM"}.issubset(headers)
        ):
            records = []
            for _sheet, row_no, row in rows:
                profile_code = text(first_value(row, "PROFİL KODU", "PROFİL KOD"))
                profile_name = text(first_value(row, "PROFİL ADI", "PROFİL AD"))
                customer = text(first_value(row, "MÜŞTERİ", "FİRMA"))
                if not profile_code or (not profile_name and not customer):
                    continue
                spare_no = int(number(first_value(row, "YEDEK NO")))
                records.append(
                    (
                        stable_key("IMALAT_KALIP", profile_code, spare_no, row_no),
                        {
                            "die_code": f"{profile_code}-{spare_no:02d}",
                            "profile_code": profile_code,
                            "profile_name": profile_name,
                            "spare_no": spare_no,
                            "customer": customer,
                            "die_type": text(first_value(row, "KALIP CİNS", "KALIP CİNSİ")),
                            "figure": int(number(first_value(row, "FİGÜR ADET"))) or 1,
                            "status": text(first_value(row, "DURUM")) or "İMALATTA",
                            "work_order_date": date_text(first_value(row, "İŞ EMRİ TARİHİ")),
                            "due_date": date_text(first_value(row, "İMALAT TERMİN")),
                            "last_movement": text(first_value(row, "SON HAREKET")),
                            "last_movement_date": date_text(
                                first_value(row, "SON HAREKET TARİH")
                            ),
                            "last_movement_part": text(
                                first_value(row, "SON HAREKET PARÇA")
                            ),
                            "last_movement_operation_no": text(
                                first_value(row, "SON HAREKET İŞLEM NO")
                            ),
                            "note": text(first_value(row, "SON HAREKET AÇIKLAMA")),
                        },
                    )
                )
            mapped.append(("Kalıphane", "İmalattaki Kalıplar", records))

        if {"FIS NO", "SIPARIS KG", "SEVK KG"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                order_no = text(first_value(row, "FİŞ NO"))
                if not order_no:
                    continue
                records.append(
                    (
                        f"SIPARIS:{order_no}",
                        {
                            "company": text(first_value(row, "FİRMA")) or "FİRMA BELİRTİLMEDİ",
                            "document_no": text(first_value(row, "BELGE NO")),
                            "msp": text(first_value(row, "MSP")),
                            "order_date": date_text(first_value(row, "TARİH")),
                            "delivery_date": date_text(first_value(row, "TESLİM TARİHİ")),
                            "stock_name": "Eski Sistem Satış Siparişi",
                            "kg": number(first_value(row, "SİPARİŞ KG")),
                            "currency": text(first_value(row, "DÖVİZ")) or "TL",
                            "total": number(first_value(row, "TOPLAM")),
                            "status": text(first_value(row, "KAPANMA DURUM")) or "AÇIK",
                            "production_approval": text(first_value(row, "ÜRETİM ONAY")) or "BEKLİYOR",
                            "note": f"Eski sistem fiş no: {order_no}",
                        },
                    )
                )
            mapped.append(("Satış", "Satış Siparişleri", records))

        if "SIPARIS REF" in headers and "SIPARIS KG" in headers and "PROFIL KOD" in headers:
            records = []
            for _sheet, row_no, row in rows:
                order_ref = text(first_value(row, "SIPARIS REF"))
                if not order_ref:
                    order_ref = f"{text(first_value(row, 'FİŞ NO'))}:{row_no}"
                profile_code = text(first_value(row, "PROFIL KOD"))
                records.append(
                    (
                        f"SIPARIS_D:{order_ref}",
                        {
                            "company": text(first_value(row, "FIRMA AD", "FİRMA")) or "FİRMA BELİRTİLMEDİ",
                            "document_no": text(first_value(row, "BELGE NO")),
                            "msp": text(first_value(row, "MSP")),
                            "order_date": date_text(first_value(row, "SİPARİŞ TARİH")),
                            "delivery_date": date_text(first_value(row, "SATIR TESLİM TARİH")),
                            "profile_code": profile_code,
                            "stock_name": text(first_value(row, "ÜRÜN TANIM")) or f"Profil {profile_code}",
                            "length_mm": number(first_value(row, "BOY (mm)")),
                            "surface": text(first_value(row, "YÜZEY")) or "PRES",
                            "color": text(first_value(row, "RENK")) or "*",
                            "alloy": text(first_value(row, "ALAŞIM")) or "6060B",
                            "temper": text(first_value(row, "SERTLİK")) or "T5",
                            "quantity": number(first_value(row, "SİPARİŞ ADET")),
                            "kg": number(first_value(row, "SİPARİŞ KG")),
                            "status": text(first_value(row, "DURUM")) or "AÇIK",
                            "production_approval": text(first_value(row, "ÜRETİM ONAY")) or "BEKLİYOR",
                            "note": "Eski sistem sipariş satırından aktarılmıştır.",
                        },
                    )
                )
            mapped.append(("Satış", "Sipariş Detay (Satış)", records))

        if {"RECETE KOD", "RECETE AD", "ROTA", "PROFIL KOD"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                recipe_code = text(first_value(row, "REÇETE KOD"))
                profile_code = text(first_value(row, "PROFİL KOD"))
                if not recipe_code:
                    continue
                records.append(
                    (
                        f"RECETE:{recipe_code}",
                        {
                            "company": text(first_value(row, "PROFİL FİRMA")) or "FİRMA BELİRTİLMEDİ",
                            "order_ref": recipe_code,
                            "profile_code": profile_code,
                            "stock_name": text(first_value(row, "STOK AD")) or f"Profil {profile_code}",
                            "production_length_mm": number(first_value(row, "U.BOY (mm)")),
                            "surface": text(first_value(row, "YÜZEY")) or "PRES",
                            "color": text(first_value(row, "RENK")) or "*",
                            "alloy": text(first_value(row, "ALAŞIM")) or "6060B",
                            "temper": text(first_value(row, "SERTLİK")) or "T5",
                            "status": "AÇIK" if bool_value(first_value(row, "AKTİF"), True) else "KAPALI",
                            "note": f"Eski sistem rota: {text(first_value(row, 'ROTA'))}",
                        },
                    )
                )
            mapped.append(("Üretim", "Reçeteler", records))

        if {"U.EMRI NO", "IS EMRI NO", "OPERASYON", "ISTASYON"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                work_no = text(first_value(row, "İŞ EMRİ NO"))
                if not work_no:
                    continue
                records.append(
                    (
                        f"IS_EMRI:{work_no}",
                        {
                            "production_order_ref": text(first_value(row, "Ü.EMRİ NO")) or work_no,
                            "work_order_ref": work_no,
                            "order_ref": text(first_value(row, "SİPARİŞ REF")) or work_no,
                            "company": text(first_value(row, "FİRMA")),
                            "operation": text(first_value(row, "OPERASYON")) or "EKSTRÜZYON",
                            "station": text(first_value(row, "ISTASYON")),
                            "profile_code": text(first_value(row, "PROFİL KOD")),
                            "quantity": number(first_value(row, "İŞ EMRİ ADET")),
                            "produced_quantity": number(first_value(row, "ÜRETİLEN ADET")),
                            "kg": number(first_value(row, "İŞ EMRİ KG")),
                            "produced_kg": number(first_value(row, "ÜRETİLEN KG")),
                            "status": "KAPALI" if bool_value(first_value(row, "KAPALI")) else "AÇIK",
                            "note": text(first_value(row, "İŞ EMRİ TİPİ")),
                        },
                    )
                )
            mapped.append(("Üretim", "İş Emirleri", records))

        if {"FIS NO", "HAMMADDE", "SIPARIS REF", "PROFIL KOD"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                production_no = text(first_value(row, "FİŞ NO"))
                if not production_no:
                    continue
                records.append(
                    (
                        f"URETIM_EMRI:{production_no}",
                        {
                            "company": text(first_value(row, "FİRMA")) or "FİRMA BELİRTİLMEDİ",
                            "order_ref": text(first_value(row, "SİPARİŞ REF")) or production_no,
                            "raw_material": text(first_value(row, "HAMMADDE")),
                            "profile_code": text(first_value(row, "PROFİL KOD")),
                            "stock_name": text(first_value(row, "STOK AD")),
                            "stock_length_mm": number(first_value(row, "STOK BOY")),
                            "production_length_mm": number(first_value(row, "ÜRETİM BOY")),
                            "quantity": number(first_value(row, "ADET")),
                            "kg": number(first_value(row, "KG")),
                            "surface": text(first_value(row, "YÜZEY")) or "PRES",
                            "color": text(first_value(row, "RENK")) or "*",
                            "alloy": text(first_value(row, "ALAŞIM")) or "6060B",
                            "temper": text(first_value(row, "SERTLİK")) or "T5",
                            "production_date": date_text(first_value(row, "TARİH")),
                            "status": "KAPALI" if bool_value(first_value(row, "KAPALI")) else "AÇIK",
                        },
                    )
                )
            mapped.append(("Üretim", "Üretim Emirleri", records))

        if {"FIS NO", "PRES DURUM", "TESTERE DURUM", "BRUT KG", "NET KG"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                press_no = text(first_value(row, "FİŞ NO"))
                if not press_no:
                    continue
                records.append(
                    (
                        f"PRES:{press_no}",
                        {
                            "production_type": text(first_value(row, "ÜRETİM TİPİ")) or "PLANLI ÜRETİM",
                            "press_status": text(first_value(row, "PRES DURUM")) or "BEKLİYOR",
                            "saw_status": text(first_value(row, "TESTERE DURUM")) or "BEKLİYOR",
                            "station": text(first_value(row, "İSTASYON")),
                            "operator": text(first_value(row, "OPERATÖR")),
                            "shift": text(first_value(row, "VARDİYA")) or "1.VARDİYA",
                            "order_ref": text(first_value(row, "SİPARİŞ REF")) or press_no,
                            "work_order_ref": text(first_value(row, "İŞ EMRİ NO")) or press_no,
                            "company": text(first_value(row, "MÜŞTERİ")),
                            "profile_code": text(first_value(row, "PROFİL KOD")) or "PROFİL BELİRTİLMEDİ",
                            "spare_no": int(number(first_value(row, "YEDEK NO"))),
                            "figure": int(number(first_value(row, "FİGUR"))) or 1,
                            "real_weight": number(first_value(row, "REEL GRAMAJ (Kg/m)")),
                            "theoretical_weight": number(first_value(row, "TEORIK GRAMAJ (Kg/m)")),
                            "duration_min": number(first_value(row, "ÜRETİM SÜRESİ(dk)")),
                            "die_setup_min": number(first_value(row, "KALIP HAZIRLIK(dk)")),
                            "raw_material": text(first_value(row, "HAMMADDE STOK")),
                            "lot_no": text(first_value(row, "LOT NO")),
                            "billet_count": int(number(first_value(row, "BİLLET ADET"))),
                            "metre": number(first_value(row, "NET M")),
                            "gross_kg": number(first_value(row, "BRÜT KG")),
                            "net_kg": number(first_value(row, "NET KG")),
                            "test_ok": bool_value(first_value(row, "TEST BAŞARILI")),
                            "note": text(first_value(row, "AÇIKLAMA")),
                        },
                    )
                )
            mapped.append(("Üretim", "Pres Üretim Fişleri", records))

        if {"FIS NO", "FIS TIPI", "GC KOD", "STOK ADI"}.issubset(headers):
            records = []
            for sheet, row_no, row in rows:
                movement_no = text(first_value(row, "FİŞ NO"))
                stock_name = text(first_value(row, "STOK ADI"))
                if not movement_no or not stock_name:
                    continue
                external = stable_key(
                    "STOK_HA",
                    movement_no,
                    row_no,
                    stock_name,
                    first_value(row, "LOT NO"),
                )
                records.append(
                    (
                        external,
                        {
                            "stock_code": text(first_value(row, "PROFİL KOD")) or stock_name,
                            "stock_name": stock_name,
                            "stock_group": text(first_value(row, "PROFİL GRUP")),
                            "lot_no": text(first_value(row, "LOT NO")),
                            "warehouse": text(first_value(row, "AMBAR")),
                            "quantity": number(first_value(row, "KG")),
                            "unit": "KG",
                            "profile_code": text(first_value(row, "PROFİL KOD")),
                            "length_mm": number(first_value(row, "BOY (mm)")),
                            "surface": text(first_value(row, "YÜZEY")) or "PRES",
                            "color": text(first_value(row, "RENK")) or "*",
                            "alloy": text(first_value(row, "ALAŞIM")) or "6060B",
                            "temper": text(first_value(row, "SERTLİK")) or "T5",
                            "customer": text(first_value(row, "SİPARİŞ FİRMASI")),
                            "order_ref": text(first_value(row, "SİPARİŞ REF")),
                            "status": "TAMAMLANDI",
                            "note": (
                                f"{text(first_value(row, 'FİŞ TİPİ'))} / "
                                f"{text(first_value(row, 'GÇ KOD'))}"
                            ),
                        },
                    )
                )
            mapped.append(("Üretim", "Stok Hareketleri", records))

        if {"KASA FIS NO", "PAKET NO", "SIPARIS REF", "NET KG"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                case_no = text(first_value(row, "KASA FİŞ NO"))
                package_no = text(first_value(row, "PAKET NO"))
                if not case_no or not package_no:
                    continue
                records.append(
                    (
                        stable_key("KASA_D", case_no, package_no, row_no),
                        self._packing_values(row, package_no),
                    )
                )
            mapped.append(("Sevkiyat", "Kasalama Fişleri (Detay)", records))

        if {"FIS NO", "FIRMA", "NET KG", "BRUT KG", "AMBAR"}.issubset(headers) and "KASALAMA" in name:
            records = []
            for _sheet, row_no, row in rows:
                case_no = text(first_value(row, "FİŞ NO"))
                if not case_no:
                    continue
                values = self._packing_values(row, case_no)
                values["status"] = "HAZIR"
                records.append((f"KASA:{case_no}", values))
            mapped.append(("Sevkiyat", "Kasalama Fişleri", records))

        if {"PAKET NO", "PROFIL KOD", "SIPARIS REF", "KASA FIS NO"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                package_no = text(first_value(row, "PAKET NO"))
                if not package_no:
                    continue
                values = self._packing_values(row, package_no)
                values["status"] = "HAZIR"
                records.append((stable_key("HAZIR_KASA", package_no, row_no), values))
            mapped.append(("Sevkiyat", "Hazır Kasalar", records))

        if {"FIS NO", "SIPARIS NO", "NET KG", "BRUT KG", "KONTEYNER NO"}.issubset(headers):
            records = []
            for _sheet, row_no, row in rows:
                dispatch_no = text(first_value(row, "FİŞ NO"))
                if not dispatch_no:
                    continue
                values = self._packing_values(row, dispatch_no)
                values["order_ref"] = text(first_value(row, "SİPARİŞ NO")) or dispatch_no
                values["status"] = "SEVK EDİLDİ"
                values["note"] = (
                    f"Konteyner: {text(first_value(row, 'KONTEYNER NO'))}; "
                    f"İrsaliye: {text(first_value(row, 'İRSALİYE FİŞ NO'))}"
                )
                records.append((f"CEKI:{dispatch_no}", values))
            mapped.append(("Sevkiyat", "Çeki Listeleri", records))

        return mapped

    def import_shared_files(
        self,
        root: str | Path,
        progress: ProgressCallback | None = None,
    ) -> dict[str, int]:
        """Eski sistem belgelerini ayrı Rigel veri klasörüne kopyalar."""
        source_root = Path(root)
        if not source_root.is_dir():
            return {
                "found": 0,
                "copied": 0,
                "unchanged": 0,
                "linked_profiles": 0,
                "linked_dies": 0,
            }
        allowed = {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tif",
            ".tiff",
            ".dwg",
            ".dxf",
            ".step",
            ".stp",
        }
        files = sorted(
            path
            for path in source_root.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in allowed
            and any(part.casefold().startswith("sharedfiles") for part in path.parts)
        )
        if not files:
            return {
                "found": 0,
                "copied": 0,
                "unchanged": 0,
                "linked_profiles": 0,
                "linked_dies": 0,
            }

        destination_root = self.erp.database_path.parent / "migration_attachments"
        destination_root.mkdir(parents=True, exist_ok=True)
        copied = 0
        unchanged = 0
        imported_paths: list[Path] = []
        with closing(self.staging_connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for index, source in enumerate(files, start=1):
                if progress:
                    progress(f"Belge: {source.name}", index, len(files))
                relative = source.relative_to(source_root)
                destination = destination_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                source_hash = self._file_hash(source)
                existing = connection.execute(
                    """
                    SELECT sha256, destination_path FROM imported_attachments
                    WHERE source_relative_path = ?
                    """,
                    (relative.as_posix(),),
                ).fetchone()
                if (
                    existing is not None
                    and existing["sha256"] == source_hash
                    and Path(existing["destination_path"]).exists()
                ):
                    unchanged += 1
                    imported_paths.append(Path(existing["destination_path"]))
                    continue
                shutil.copy2(source, destination)
                connection.execute(
                    """
                    INSERT INTO imported_attachments(
                        source_relative_path, destination_path, sha256,
                        size_bytes, imported_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_relative_path) DO UPDATE SET
                        destination_path = excluded.destination_path,
                        sha256 = excluded.sha256,
                        size_bytes = excluded.size_bytes,
                        imported_at = excluded.imported_at
                    """,
                    (
                        relative.as_posix(),
                        str(destination),
                        source_hash,
                        source.stat().st_size,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                copied += 1
                imported_paths.append(destination)
            connection.commit()
        linked = self._link_attachments(imported_paths)
        return {
            "found": len(files),
            "copied": copied,
            "unchanged": unchanged,
            **linked,
        }

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _link_attachments(self, paths: list[Path]) -> dict[str, int]:
        if not paths:
            return {"linked_profiles": 0, "linked_dies": 0}
        candidates: list[tuple[str, str, str, Path]] = []
        for path in paths:
            normalized_parts = [normalize_label(part) for part in path.parts]
            category = ""
            source_id = ""
            for candidate_category in ("PROFIL", "KALIP"):
                if candidate_category not in normalized_parts:
                    continue
                position = normalized_parts.index(candidate_category)
                category = candidate_category
                if position + 1 < len(path.parts):
                    source_id = text(path.parts[position + 1])
                break
            candidates.append(
                (
                    normalize_label(path.stem).replace(" ", ""),
                    category,
                    source_id,
                    path,
                )
            )
        image_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
        profile_linked = 0
        for record in self.erp.list_records("Kalıphane", "Profil Kartları"):
            values = dict(record["data"])
            code = normalize_label(values.get("profile_code")).replace(" ", "")
            if len(code) < 3:
                continue
            source_id = text(record.get("external_key")).partition(":")[2]
            matches = [
                path
                for stem, category, folder_id, path in candidates
                if (
                    (category == "PROFIL" and source_id and folder_id == source_id)
                    or (category != "KALIP" and code in stem)
                )
            ]
            changed = False
            if not text(values.get("drawing_path")):
                document = next(
                    (path for path in matches if path.suffix.casefold() not in image_suffixes),
                    None,
                )
                if document is not None:
                    values["drawing_path"] = str(document)
                    changed = True
            if not text(values.get("image_path")):
                image = next(
                    (path for path in matches if path.suffix.casefold() in image_suffixes),
                    None,
                )
                if image is not None:
                    values["image_path"] = str(image)
                    changed = True
            if not changed:
                continue
            self.erp.update_record(int(record["id"]), values)
            profile_linked += 1

        die_linked = 0
        for record in self.erp.list_records("Kalıphane", "Kalıp Kartları"):
            values = dict(record["data"])
            die_code = normalize_label(values.get("die_code")).replace(" ", "")
            profile_code = normalize_label(values.get("profile_code")).replace(" ", "")
            source_id = text(record.get("external_key")).partition(":")[2]
            matches = [
                path
                for stem, category, folder_id, path in candidates
                if (
                    (category == "KALIP" and source_id and folder_id == source_id)
                    or (category != "PROFIL" and len(die_code) >= 3 and die_code in stem)
                    or (
                        category == "KALIP"
                        and len(profile_code) >= 3
                        and profile_code in stem
                    )
                )
            ]
            changed = False
            if not text(values.get("pdf_path")):
                document = next(
                    (path for path in matches if path.suffix.casefold() not in image_suffixes),
                    None,
                )
                if document is not None:
                    values["pdf_path"] = str(document)
                    changed = True
            if not text(values.get("image_path")):
                image = next(
                    (path for path in matches if path.suffix.casefold() in image_suffixes),
                    None,
                )
                if image is not None:
                    values["image_path"] = str(image)
                    changed = True
            if not changed:
                continue
            self.erp.update_record(int(record["id"]), values)
            die_linked += 1
        return {"linked_profiles": profile_linked, "linked_dies": die_linked}

    @staticmethod
    def _packing_values(row: dict[str, object], package_no: str) -> dict[str, Any]:
        order_ref = text(first_value(row, "SİPARİŞ REF", "SİPARİŞ NO"))
        return {
            "company": text(first_value(row, "FIRMA", "MÜŞTERİ")) or "FİRMA BELİRTİLMEDİ",
            "package_no": package_no,
            "profile_code": text(first_value(row, "PROFİL KOD", "PROFIL KOD")),
            "stock_name": text(first_value(row, "STOK AD", "PROFİL AD")) or "PROFİL",
            "order_ref": order_ref or package_no,
            "net_kg": number(first_value(row, "NET KG")),
            "gross_kg": number(first_value(row, "BRUT KG", "BRÜT KG")),
            "package_count": int(number(first_value(row, "PAKET ADET"))) or 1,
            "quantity": number(first_value(row, "ADET")),
            "kg": number(first_value(row, "KG")),
            "delivery_week": int(number(first_value(row, "TESLİM HAFTASI"))),
            "branch": text(first_value(row, "ŞUBE")) or "FABRİKA",
            "warehouse": text(first_value(row, "AMBAR")) or "SEVK ÖN",
            "surface": text(first_value(row, "YÜZEY")) or "PRES",
            "color": text(first_value(row, "RENK")) or "*",
            "alloy": text(first_value(row, "ALAŞIM")) or "6060B",
            "temper": text(first_value(row, "SERTLİK")) or "T5",
            "packing_date": date_text(first_value(row, "KASALAMA TARİH", "TARİH")),
            "status": "KASALANIYOR",
            "note": text(first_value(row, "ACIKLAMA", "AÇIKLAMA")),
        }

    @staticmethod
    def parse_config_connection(config_path: str | Path) -> dict[str, str]:
        root = ET.parse(config_path).getroot()
        raw_values: list[str] = []
        for add in root.findall(".//appSettings/add"):
            if add.attrib.get("key") == "ConnectionString":
                raw_values.append(add.attrib.get("value", ""))
        for add in root.findall(".//connectionStrings/add"):
            raw_values.append(add.attrib.get("connectionString", ""))

        for raw in raw_values:
            pairs: dict[str, str] = {}
            for part in raw.split(";"):
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                pairs[normalize_label(key)] = value.strip()
            if (
                pairs.get("DATA SOURCE") or pairs.get("SERVER")
            ) and (
                pairs.get("INITIAL CATALOG") or pairs.get("DATABASE")
            ):
                return pairs
        if raw_values:
            raise EncryptedConnectionStringError(
                "rigel.config içindeki SQL bağlantısı kaynak programa özel şifreli. "
                "İlk aktarım için bağlantı bilgilerini bir kez girin."
            )
        raise ValueError("rigel.config içinde ConnectionString bulunamadı.")

    @staticmethod
    def infer_server_from_config(config_path: str | Path) -> str:
        """Şifreli bağlantıda paylaşım yolundan SQL sunucu adayını bulur.

        Kaynak bağlantı dizesi şifreli olsa bile PaylasimPath çoğunlukla
        ``\\\\sunucu\\paylasim`` biçiminde açık tutulur. Yalnızca sunucu adı/IP
        okunur; kullanıcı adı veya parola işlenmez.
        """
        candidates = [str(config_path)]
        try:
            root = ET.parse(config_path).getroot()
            for add in root.findall(".//appSettings/add"):
                if normalize_label(add.attrib.get("key", "")) in {
                    "PAYLASIMPATH",
                    "PAYLASIM PATH",
                    "SHAREDPATH",
                    "SHARED PATH",
                }:
                    candidates.append(add.attrib.get("value", ""))
        except (ET.ParseError, OSError):
            pass

        for candidate in candidates:
            match = re.match(r"^\\\\([^\\]+)\\", str(candidate).strip())
            if match:
                return match.group(1).strip()
        return ""

    @classmethod
    def sql_server_odbc_string(
        cls,
        config_path: str | Path,
        connection_values: dict[str, str] | None = None,
    ) -> str:
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "SQL aktarımı için pyodbc bileşeni kurulu değil. Excel aktarımı kullanılabilir."
            ) from exc
        config = (
            {
                normalize_label(key): str(value or "").strip()
                for key, value in connection_values.items()
            }
            if connection_values
            else cls.parse_config_connection(config_path)
        )
        drivers = pyodbc.drivers()
        candidates = (
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server Native Client 10.0",
            "SQL Server",
        )
        preferred = next(
            (
                driver
                for candidate in candidates
                for driver in drivers
                if candidate.casefold() == driver.casefold()
            ),
            next(
                (driver for driver in drivers if "sql server" in driver.casefold()),
                None,
            ),
        )
        if preferred is None:
            raise RuntimeError("Bu bilgisayarda Microsoft SQL Server ODBC sürücüsü bulunamadı.")
        server = config.get("DATA SOURCE") or config.get("SERVER")
        database = config.get("INITIAL CATALOG") or config.get("DATABASE")
        username = config.get("USER ID") or config.get("UID")
        password = config.get("PASSWORD") or config.get("PWD")
        trusted = normalize_label(config.get("TRUSTED CONNECTION", "")) in {
            "YES", "TRUE", "EVET", "1",
        }
        if not server or not database:
            raise ValueError("Eski sistem SQL sunucu veya veritabanı bilgisi eksik.")
        parts = [
            f"DRIVER={{{preferred}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
            "APP=Rigel Cost Pro Salt Okunur Aktarım",
            "Encrypt=no",
        ]
        if username and not trusted:
            parts.extend((f"UID={username}", f"PWD={password or ''}"))
        else:
            parts.append("Trusted_Connection=yes")
        return ";".join(parts)

    def import_sql_server(
        self,
        config_path: str | Path,
        progress: ProgressCallback | None = None,
        connection_values: dict[str, str] | None = None,
    ) -> dict[str, object]:
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:
            raise RuntimeError("SQL aktarımı için pyodbc bileşeni kurulu değil.") from exc
        connection_string = self.sql_server_odbc_string(
            config_path,
            connection_values,
        )
        batch_id = self._start_batch("SQL_SERVER", str(config_path))
        totals = {"inserted": 0, "updated": 0, "skipped": 0}
        table_counts: dict[str, int] = {}
        try:
            source = pyodbc.connect(connection_string, timeout=10, autocommit=False)
            try:
                cursor = source.cursor()
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
                existing_tables = {
                    row[0]
                    for row in cursor.execute(
                        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
                    ).fetchall()
                }
                available = [table for table in self.RAW_TABLES if table in existing_tables]
                for index, table in enumerate(available, start=1):
                    if progress:
                        progress(table, index, len(available))
                    cursor.execute(f"SELECT * FROM [dbo].[{table}]")
                    columns = [description[0] for description in cursor.description]
                    count = 0
                    with closing(self.staging_connect()) as staging:
                        staging.execute("BEGIN IMMEDIATE")
                        while True:
                            batch = cursor.fetchmany(1000)
                            if not batch:
                                break
                            for source_row in batch:
                                payload = {
                                    column: self._json_value(value)
                                    for column, value in zip(columns, source_row)
                                }
                                identifier = payload.get("ID")
                                external_key = text(identifier) or stable_key(table, *source_row)
                                before = staging.total_changes
                                staging.execute(
                                    """
                                    INSERT INTO raw_records (
                                        source_table, external_key, payload_json, imported_at
                                    ) VALUES (?, ?, ?, ?)
                                    ON CONFLICT(source_table, external_key) DO UPDATE SET
                                        payload_json = excluded.payload_json,
                                        imported_at = excluded.imported_at
                                    """,
                                    (
                                        table,
                                        external_key,
                                        json.dumps(payload, ensure_ascii=False),
                                        datetime.now().isoformat(timespec="seconds"),
                                    ),
                                )
                                count += 1
                        staging.commit()
                    table_counts[table] = count
                source.rollback()
            finally:
                source.close()

            master_result = self.materialize_sql_masters()
            self._merge_counts(totals, master_result)
            attachment_summary = self.import_shared_files(
                Path(config_path).resolve().parent,
                progress,
            )
            connected_summary = self.sync_connected_workflow()
            self._finish_batch(batch_id, totals, [])
            return {
                "tables": table_counts,
                "attachments": attachment_summary,
                "connected_workflow": connected_summary,
                **totals,
            }
        except Exception as error:
            self._fail_batch(batch_id, str(error))
            raise

    def materialize_sql_masters(self) -> dict[str, int]:
        """Ham SQL tablolarını Rigel'in ilişkili işletme kartlarına dönüştürür."""
        tables: dict[str, list[tuple[str, dict[str, object]]]] = defaultdict(list)
        with closing(self.staging_connect()) as connection:
            for row in connection.execute(
                "SELECT source_table, external_key, payload_json FROM raw_records"
            ):
                tables[str(row["source_table"])].append(
                    (str(row["external_key"]), json.loads(row["payload_json"]))
                )

        def identity(payload: dict[str, object], fallback: str) -> str:
            return text(payload_value(payload, "ID")) or fallback

        note = "İlk kurulumda fabrika veritabanından salt okunur aktarıldı."
        company_names: dict[str, str] = {}
        profile_data: dict[str, dict[str, Any]] = {}
        stock_data: dict[str, dict[str, Any]] = {}
        order_headers: dict[str, dict[str, object]] = {}
        production_refs: dict[str, str] = {}
        work_refs: dict[str, str] = {}

        customers: list[tuple[str, dict[str, Any]]] = []
        profiles: list[tuple[str, dict[str, Any]]] = []
        dies: list[tuple[str, dict[str, Any]]] = []
        stocks: list[tuple[str, dict[str, Any]]] = []
        stock_movements: list[tuple[str, dict[str, Any]]] = []
        orders: list[tuple[str, dict[str, Any]]] = []
        recipes: list[tuple[str, dict[str, Any]]] = []
        production_orders: list[tuple[str, dict[str, Any]]] = []
        work_orders: list[tuple[str, dict[str, Any]]] = []
        press_records: list[tuple[str, dict[str, Any]]] = []
        packages: list[tuple[str, dict[str, Any]]] = []
        cases: list[tuple[str, dict[str, Any]]] = []
        maintenance: list[tuple[str, dict[str, Any]]] = []

        for external, payload in tables.get("FIRMA", []):
            source_id = identity(payload, external)
            company = text(payload_value(payload, "FIRMA_AD", "UNVAN", "AD"))
            if not company:
                continue
            company_names[source_id] = company
            customers.append(
                (
                    f"FIRMA:{external}",
                    {
                        "code": text(payload_value(payload, "KOD", "FIRMA_KOD"))
                        or f"MIG-{external}",
                        "name": company,
                        "tax_office": text(payload_value(payload, "VERGI_DAIRE")),
                        "tax_no": text(payload_value(payload, "VERGI_NO")),
                        "contact": text(payload_value(payload, "YETKILI")),
                        "phone": text(payload_value(payload, "TELEFON", "TEL")),
                        "email": text(payload_value(payload, "EPOSTA", "EMAIL")),
                        "address": text(payload_value(payload, "ADRES")),
                        "city": text(payload_value(payload, "IL", "SEHIR")),
                        "active": bool_value(payload_value(payload, "AKTIF"), True),
                        "customer": True,
                        "supplier": bool_value(payload_value(payload, "TEDARIKCI")),
                        "subcontractor": bool_value(
                            payload_value(payload, "FASON_IMALATCI", "FASONCU")
                        ),
                        "note": note,
                    },
                )
            )

        for external, payload in tables.get("PROFIL", []):
            source_id = identity(payload, external)
            code = text(payload_value(payload, "KOD", "PROFIL_KOD"))
            if not code:
                continue
            values = {
                "profile_code": code,
                "profile_name": text(payload_value(payload, "AD", "PROFIL_AD"))
                or f"Profil {code}",
                "company": company_names.get(
                    text(payload_value(payload, "FIRMA_ID", "MUSTERI_ID")), ""
                ),
                "customer_code": text(payload_value(payload, "MUSTERI_PROFIL_KOD")),
                "unit_weight": number(
                    payload_value(payload, "BIRIM_AGIRLIK", "TEORIK_AGIRLIK", "GRAMAJ")
                ),
                "perimeter": number(payload_value(payload, "CEVRE")),
                "alloy": text(payload_value(payload, "ALASIM")) or "6060B",
                "temper": text(payload_value(payload, "SERTLIK")) or "T5",
                "active": bool_value(payload_value(payload, "AKTIF"), True),
                "note": note,
            }
            profile_data[source_id] = values
            profiles.append((f"PROFIL:{external}", values))

        for external, payload in tables.get("KALIP", []):
            profile = profile_data.get(
                text(payload_value(payload, "PROFIL_ID")), {}
            )
            profile_code = text(payload_value(payload, "PROFIL_KOD")) or text(
                profile.get("profile_code")
            )
            spare_no = int(number(payload_value(payload, "YEDEK_NO", "YEDEK")))
            supplier_code = text(
                payload_value(payload, "KALIPCI_KOD", "KOD", "KALIP_KOD")
            )
            die_code = supplier_code or (
                f"{profile_code}-{spare_no:02d}" if profile_code else ""
            )
            if not die_code or not profile_code:
                continue
            supplier_id = text(payload_value(payload, "TEDARIKCI_ID", "KALIPCI_ID"))
            dies.append(
                (
                    f"KALIP:{external}",
                    {
                        "die_code": die_code,
                        "profile_code": profile_code,
                        "spare_no": spare_no,
                        "supplier": company_names.get(supplier_id, ""),
                        "supplier_code": supplier_code,
                        "figure": int(number(payload_value(payload, "FIGUR"))) or 1,
                        "diameter_mm": number(payload_value(payload, "CAP")),
                        "length_mm": number(payload_value(payload, "BOY")),
                        "life_limit_kg": number(
                            payload_value(payload, "OMUR_KG", "OMUR_LIMIT_KG")
                        ),
                        "used_kg": number(
                            payload_value(payload, "BASILAN_KG", "TOPLAM_KG")
                        ),
                        "tenefer_used_m": number(
                            payload_value(payload, "TENEFER_BASILAN_M")
                        ),
                        "location": text(payload_value(payload, "RAF", "KONUM")),
                        "status": "AKTİF"
                        if bool_value(payload_value(payload, "AKTIF"), True)
                        else "HURDA",
                        "note": note,
                    },
                )
            )

        operation_names = {
            identity(payload, external): text(
                payload_value(payload, "AD", "OPERASYON_AD", "KOD", "OPERASYON_KOD")
            )
            for external, payload in tables.get("OPERASYON", [])
        }
        station_names = {
            identity(payload, external): text(
                payload_value(payload, "AD", "ISTASYON_AD", "KOD", "ISTASYON_KOD")
            )
            for external, payload in tables.get("ISTASYON", [])
        }
        route_names: dict[str, str] = {}
        route_steps: dict[str, list[dict[str, object]]] = defaultdict(list)
        for external, payload in tables.get("ROTA", []):
            source_id = identity(payload, external)
            route_names[source_id] = text(
                payload_value(payload, "AD", "ROTA_AD", "KOD", "ROTA_KOD")
            )
        for external, payload in tables.get("ROTA_D", []):
            route_id = text(payload_value(payload, "ROTA_ID", "ROTA_BASLIK_ID"))
            if not route_id:
                continue
            sequence = int(number(payload_value(payload, "SIRA", "SIRA_NO")))
            operation_id = text(payload_value(payload, "OPERASYON_ID"))
            station_id = text(payload_value(payload, "ISTASYON_ID"))
            operation_name = text(
                payload_value(payload, "OPERASYON_AD", "OPERASYON")
            ) or operation_names.get(operation_id, "")
            station_name = text(
                payload_value(payload, "ISTASYON_AD", "ISTASYON", "AD")
            ) or station_names.get(station_id, "")
            route_steps[route_id].append(
                {
                    "external_id": identity(payload, external),
                    "sequence_no": sequence,
                    "route_sequence_no": int(
                        number(payload_value(payload, "ROTA_SIRA", "ROTA_SIRA_NO"))
                    ),
                    "operation_external_id": operation_id,
                    "operation": operation_name,
                    "station_external_id": station_id,
                    "station": station_name,
                    "input_warehouse_external_id": text(
                        payload_value(payload, "GIRIS_AMBAR_ID", "AMBAR_ID")
                    ),
                    "output_warehouse_external_id": text(
                        payload_value(payload, "CIKIS_AMBAR_ID")
                    ),
                    "raw_payload": payload,
                }
            )

        condition_headers = {
            identity(payload, external): {
                "external_id": identity(payload, external),
                "code": text(payload_value(payload, "KOD", "KOSUL_KOD")),
                "name": text(payload_value(payload, "AD", "KOSUL_AD")),
                "priority": int(number(payload_value(payload, "ONCELIK", "SIRA"))),
                "active": bool_value(payload_value(payload, "AKTIF"), True),
                "raw_payload": payload,
            }
            for external, payload in tables.get("ROTA_KOSUL", [])
        }
        condition_values: dict[str, list[dict[str, object]]] = defaultdict(list)
        for external, payload in tables.get("ROTA_KOSUL_OZELLIK", []):
            condition_id = text(
                payload_value(payload, "ROTA_KOSUL_ID", "KOSUL_ID")
            )
            if condition_id:
                condition_values[condition_id].append(
                    {
                        "external_id": identity(payload, external),
                        "property_external_id": text(
                            payload_value(payload, "OZELLIK_ID", "STOK_OZELLIK_ID")
                        ),
                        "operator": text(
                            payload_value(payload, "OPERATOR", "KARSILASTIRMA")
                        ) or "=",
                        "value": text(
                            payload_value(
                                payload,
                                "DEGER",
                                "OZELLIK_DEGER_ID",
                                "STOK_OZELLIK_DEGER_ID",
                            )
                        ),
                        "raw_payload": payload,
                    }
                )
        route_conditions: dict[str, list[dict[str, object]]] = defaultdict(list)
        for external, payload in tables.get("ROTA_KOSUL_ROTA", []):
            condition_id = text(
                payload_value(payload, "ROTA_KOSUL_ID", "KOSUL_ID")
            )
            route_id = text(payload_value(payload, "ROTA_ID"))
            if not condition_id or not route_id:
                continue
            condition = dict(condition_headers.get(condition_id, {}))
            condition.setdefault("external_id", condition_id)
            condition["values"] = condition_values.get(condition_id, [])
            condition["route_link_external_id"] = identity(payload, external)
            condition["route_sequence_no"] = int(
                number(payload_value(payload, "SIRA", "ONCELIK"))
            )
            condition["route_link_raw_payload"] = payload
            route_conditions[route_id].append(condition)

        recipe_details: dict[str, list[tuple[str, dict[str, object]]]] = defaultdict(list)
        for external, payload in tables.get("RECETE_D", []):
            recipe_id = text(
                payload_value(payload, "RECETE_ID", "RECETE_BASLIK_ID")
            )
            if recipe_id:
                recipe_details[recipe_id].append((identity(payload, external), payload))
        for external, payload in tables.get("RECETE", []):
            source_id = identity(payload, external)
            details = recipe_details.get(source_id, [])
            detail = details[0][1] if details else {}

            def recipe_value(*keys: str) -> object:
                return payload_value(detail, *keys) or payload_value(payload, *keys)

            profile_id = text(recipe_value("PROFIL_ID"))
            profile = profile_data.get(profile_id, {})
            profile_code = text(recipe_value("PROFIL_KOD")) or text(
                profile.get("profile_code")
            )
            recipe_code = text(recipe_value("KOD", "RECETE_KOD", "FIS_NO"))
            if not profile_code or not recipe_code:
                continue
            route_id = text(recipe_value("ROTA_ID"))
            ordered_steps = sorted(
                route_steps.get(route_id, []),
                key=lambda item: (
                    int(item.get("route_sequence_no") or 0),
                    int(item.get("sequence_no") or 0),
                ),
            )
            route_text = " - ".join(
                text(step.get("station") or step.get("operation"))
                for step in ordered_steps
                if text(step.get("station") or step.get("operation"))
            )
            if not route_text:
                route_text = route_names.get(route_id, "PRES 1 - TERMİK")
            detail_lines = []
            for detail_external, detail_payload in details:
                detail_lines.append(
                    {
                        "external_id": detail_external,
                        "parent_recipe_external_id": text(
                            payload_value(detail_payload, "ALT_RECETE_ID")
                        ),
                        "operation_external_id": text(
                            payload_value(detail_payload, "OPERASYON_ID")
                        ),
                        "station_external_id": text(
                            payload_value(detail_payload, "ISTASYON_ID")
                        ),
                        "process_type": text(
                            payload_value(detail_payload, "ISLEM_TIP", "ISLEM_TIPI")
                        ),
                        "sequence_no": int(
                            number(payload_value(detail_payload, "SIRA", "SIRA_NO"))
                        ),
                        "route_sequence_no": int(
                            number(payload_value(detail_payload, "ROTA_SIRA"))
                        ),
                        "stock_external_id": text(
                            payload_value(detail_payload, "STOK_ID")
                        ),
                        "quantity": number(payload_value(detail_payload, "MIKTAR")),
                        "unit_external_id": text(
                            payload_value(detail_payload, "BIRIM_ID")
                        ),
                        "main_unit_external_id": text(
                            payload_value(detail_payload, "ANA_BIRIM_ID")
                        ),
                        "main_quantity": number(
                            payload_value(detail_payload, "ANA_MIKTAR")
                        ),
                        "numerator": number(payload_value(detail_payload, "PAY")),
                        "denominator": number(payload_value(detail_payload, "PAYDA")),
                        "description": text(
                            payload_value(detail_payload, "ACIKLAMA")
                        ),
                        "warehouse_external_id": text(
                            payload_value(detail_payload, "AMBAR_ID")
                        ),
                        "external_unit_weight": number(
                            payload_value(detail_payload, "EX_BIRIM_AGIRLIK")
                        ),
                        "external_kg": number(payload_value(detail_payload, "EX_KG")),
                        "external_quantity": number(
                            payload_value(detail_payload, "EX_ADET")
                        ),
                        "external_metre": number(
                            payload_value(detail_payload, "EX_M")
                        ),
                        "raw_payload": detail_payload,
                    }
                )
            recipes.append(
                (
                    f"RECETE:{external}",
                    {
                        "company": text(profile.get("company")),
                        "order_ref": recipe_code,
                        "profile_code": profile_code,
                        "stock_name": text(
                            recipe_value("AD", "RECETE_AD", "STOK_AD")
                        ) or f"{profile_code} reçetesi",
                        "production_length_mm": number(
                            recipe_value("URETIM_BOY", "BOY", "BOY_MM")
                        ),
                        "surface": text(recipe_value("YUZEY")) or "PRES",
                        "color": text(recipe_value("RENK")) or "*",
                        "alloy": text(recipe_value("ALASIM"))
                        or text(profile.get("alloy"))
                        or "6060B",
                        "temper": text(recipe_value("SERTLIK"))
                        or text(profile.get("temper"))
                        or "T5",
                        "mechanical": text(recipe_value("MEKANIK")),
                        "external_id": source_id,
                        "route_external_id": route_id,
                        "route_name": route_names.get(route_id, route_text),
                        "route_steps": ordered_steps,
                        "route_conditions": route_conditions.get(route_id, []),
                        "detail_lines": detail_lines,
                        "main_stock_external_id": text(
                            recipe_value("STOK_ID", "ANA_STOK_ID")
                        ),
                        "raw_material_stock_external_id": text(
                            recipe_value("HAMMADDE_STOK_ID", "HAMMADDE_ID")
                        ),
                        "saw_allowance_mm": number(
                            recipe_value("TESTERE_PAY", "TESTERE_PAYI")
                        ),
                        "hanger_allowance_mm": number(
                            recipe_value("ASKI_PAY", "ASKI_PAYI")
                        ),
                        "raw_payload": payload,
                        "status": "AÇIK"
                        if bool_value(recipe_value("AKTIF"), True)
                        else "KAPALI",
                        "note": f"Eski sistem rota: {route_text}",
                    },
                )
            )

        for external, payload in tables.get("STOK", []):
            source_id = identity(payload, external)
            code = text(payload_value(payload, "KOD", "STOK_KOD"))
            name = text(payload_value(payload, "AD", "STOK_AD"))
            if not code or not name:
                continue
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            values = {
                "stock_code": code,
                "stock_name": name,
                "stock_group": text(payload_value(payload, "STOK_GRUP", "GRUP")),
                "warehouse": text(payload_value(payload, "AMBAR_AD", "AMBAR_ID")),
                "quantity": number(payload_value(payload, "MIKTAR", "BAKIYE", "KG")),
                "unit": text(payload_value(payload, "BIRIM", "ANA_BIRIM")) or "KG",
                "profile_code": text(profile.get("profile_code")),
                "unit_weight": number(profile.get("unit_weight")),
                "status": "TASLAK",
                "note": note,
            }
            stock_data[source_id] = values
            stocks.append((f"STOK:{external}", values))

        for external, payload in tables.get("SIPARIS", []):
            order_headers[identity(payload, external)] = {**payload, "_external": external}

        order_rows = tables.get("SIPARIS_D", []) or tables.get("SIPARIS", [])
        for external, payload in order_rows:
            header_id = text(payload_value(payload, "SIPARIS_ID", "SIPARIS_BASLIK_ID"))
            header = order_headers.get(header_id, payload)
            order_ref = text(
                payload_value(
                    header,
                    "FIS_NO",
                    "SIPARIS_NO",
                    "BELGE_NO",
                    "SIPARIS_KOD",
                )
            ) or f"SIP-{header_id or external}"
            company_id = text(payload_value(header, "FIRMA_ID", "MUSTERI_ID"))
            company = company_names.get(company_id) or text(
                payload_value(header, "FIRMA_AD", "MUSTERI")
            ) or "FİRMA BELİRTİLMEDİ"
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            stock = stock_data.get(text(payload_value(payload, "STOK_ID")), {})
            profile_code = text(payload_value(payload, "PROFIL_KOD")) or text(
                profile.get("profile_code")
            )
            stock_name = text(payload_value(payload, "STOK_AD", "PROFIL_AD")) or text(
                stock.get("stock_name") or profile.get("profile_name")
            ) or "SİPARİŞ KALEMİ"
            values = {
                "company": company,
                "document_no": order_ref,
                "msp": text(payload_value(header, "MSP")),
                "order_date": date_text(payload_value(header, "TARIH", "SIPARIS_TARIH")),
                "delivery_date": date_text(
                    payload_value(payload, "TESLIM_TARIH", "TERMIN_TARIH")
                    or payload_value(header, "TESLIM_TARIH", "TERMIN_TARIH")
                ),
                "profile_code": profile_code,
                "stock_name": stock_name,
                "length_mm": number(payload_value(payload, "BOY", "BOY_MM")),
                "surface": text(payload_value(payload, "YUZEY")) or "PRES",
                "color": text(payload_value(payload, "RENK")) or "*",
                "alloy": text(payload_value(payload, "ALASIM")) or "6060B",
                "temper": text(payload_value(payload, "SERTLIK")) or "T5",
                "quantity": number(payload_value(payload, "ADET", "MIKTAR")),
                "kg": number(payload_value(payload, "KG", "SIPARIS_KG")),
                "unit_price": number(payload_value(payload, "BIRIM_FIYAT", "FIYAT")),
                "currency": text(payload_value(header, "DOVIZ")) or "TL",
                "status": "AÇIK",
                "production_approval": "BEKLİYOR",
                "note": note,
            }
            orders.append((f"SIPARIS:{external}", values))

        for external, payload in tables.get("URETIM_EMRI", []):
            source_id = identity(payload, external)
            production_ref = text(
                payload_value(payload, "URETIM_EMRI_NO", "FIS_NO", "EMIR_NO")
            ) or f"UEM-{source_id}"
            production_refs[source_id] = production_ref
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            profile_code = text(payload_value(payload, "PROFIL_KOD")) or text(
                profile.get("profile_code")
            )
            if not profile_code:
                continue
            company = company_names.get(
                text(payload_value(payload, "FIRMA_ID", "MUSTERI_ID")),
                "FİRMA BELİRTİLMEDİ",
            )
            order_ref = text(
                payload_value(payload, "SIPARIS_NO", "SIPARIS_REF", "SIPARIS_ID")
            ) or production_ref
            production_orders.append(
                (
                    f"URETIM_EMRI:{external}",
                    {
                        "company": company,
                        "order_ref": order_ref,
                        "raw_material": text(payload_value(payload, "HAMMADDE", "BILLET"))
                        or "AL. BİLLET 6063B",
                        "profile_code": profile_code,
                        "stock_name": text(profile.get("profile_name")),
                        "quantity": number(payload_value(payload, "ADET", "MIKTAR")),
                        "unit_weight": number(profile.get("unit_weight")),
                        "kg": number(payload_value(payload, "KG", "URETIM_KG")),
                        "production_date": date_text(payload_value(payload, "TARIH")),
                        "status": "AÇIK",
                        "note": note,
                    },
                )
            )

        for external, payload in tables.get("IS_EMRI", []):
            source_id = identity(payload, external)
            work_ref = text(payload_value(payload, "IS_EMRI_NO", "FIS_NO", "EMIR_NO"))
            work_ref = work_ref or f"IEM-{source_id}"
            work_refs[source_id] = work_ref
            production_id = text(payload_value(payload, "URETIM_EMRI_ID"))
            production_ref = production_refs.get(production_id) or production_id or work_ref
            order_ref = text(
                payload_value(payload, "SIPARIS_NO", "SIPARIS_REF", "SIPARIS_ID")
            ) or production_ref
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            work_orders.append(
                (
                    f"IS_EMRI:{external}",
                    {
                        "production_order_ref": production_ref,
                        "work_order_ref": work_ref,
                        "order_ref": order_ref,
                        "company": company_names.get(
                            text(payload_value(payload, "FIRMA_ID", "MUSTERI_ID")), ""
                        ),
                        "operation": text(payload_value(payload, "OPERASYON", "ROTA_AD"))
                        or "EKSTRÜZYON",
                        "station": text(payload_value(payload, "ISTASYON", "ISTASYON_AD"))
                        or "PRES 1",
                        "profile_code": text(profile.get("profile_code")),
                        "quantity": number(payload_value(payload, "ADET", "MIKTAR")),
                        "produced_quantity": number(
                            payload_value(payload, "URETILEN_ADET", "TAMAMLANAN_ADET")
                        ),
                        "kg": number(payload_value(payload, "KG", "EMIR_KG")),
                        "produced_kg": number(
                            payload_value(payload, "URETILEN_KG", "TAMAMLANAN_KG")
                        ),
                        "priority": int(number(payload_value(payload, "ONCELIK"))) or 50,
                        "start_date": date_text(payload_value(payload, "BASLANGIC_TARIH")),
                        "end_date": date_text(payload_value(payload, "BITIS_TARIH")),
                        "status": "AÇIK",
                        "note": note,
                    },
                )
            )

        for external, payload in tables.get("PRES_BASLIK", []):
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            profile_code = text(payload_value(payload, "PROFIL_KOD")) or text(
                profile.get("profile_code")
            )
            work_id = text(payload_value(payload, "IS_EMRI_ID"))
            work_ref = work_refs.get(work_id) or work_id
            order_ref = text(payload_value(payload, "SIPARIS_NO", "SIPARIS_ID"))
            if not profile_code or not work_ref or not order_ref:
                continue
            press_records.append(
                (
                    f"PRES:{external}",
                    {
                        "press_status": "TAMAMLANDI",
                        "saw_status": "TAMAMLANDI",
                        "station": text(payload_value(payload, "ISTASYON", "PRES"))
                        or "PRES 1",
                        "operator": text(payload_value(payload, "OPERATOR")),
                        "order_ref": order_ref,
                        "work_order_ref": work_ref,
                        "company": company_names.get(
                            text(payload_value(payload, "FIRMA_ID")), ""
                        ),
                        "profile_code": profile_code,
                        "die_code": text(payload_value(payload, "KALIP_KOD")),
                        "metre": number(payload_value(payload, "METRE", "NET_METRE")),
                        "gross_kg": number(payload_value(payload, "BRUT_KG", "BILLET_KG")),
                        "net_kg": number(payload_value(payload, "NET_KG", "URETIM_KG")),
                        "start_at": text(payload_value(payload, "BASLANGIC_TARIH")),
                        "end_at": text(payload_value(payload, "BITIS_TARIH")),
                        "note": note,
                    },
                )
            )

        def packing_values(
            table: str,
            external: str,
            payload: dict[str, object],
        ) -> dict[str, Any] | None:
            package_no = text(
                payload_value(payload, "PAKET_NO", "KASA_NO", "FIS_NO", "KOD")
            ) or f"{table}-{external}"
            profile = profile_data.get(text(payload_value(payload, "PROFIL_ID")), {})
            stock = stock_data.get(text(payload_value(payload, "STOK_ID")), {})
            stock_name = text(payload_value(payload, "STOK_AD", "PROFIL_AD")) or text(
                stock.get("stock_name") or profile.get("profile_name")
            ) or "PROFİL"
            return {
                "company": company_names.get(
                    text(payload_value(payload, "FIRMA_ID", "MUSTERI_ID")),
                    "FİRMA BELİRTİLMEDİ",
                ),
                "package_no": package_no,
                "profile_code": text(profile.get("profile_code")),
                "stock_name": stock_name,
                "order_ref": text(
                    payload_value(payload, "SIPARIS_NO", "SIPARIS_REF", "SIPARIS_ID")
                ) or package_no,
                "net_kg": number(payload_value(payload, "NET_KG", "KG")),
                "gross_kg": number(payload_value(payload, "BRUT_KG")),
                "package_count": int(number(payload_value(payload, "PAKET_ADET"))) or 1,
                "quantity": number(payload_value(payload, "ADET", "MIKTAR")),
                "kg": number(payload_value(payload, "KG", "NET_KG")),
                "warehouse": text(payload_value(payload, "AMBAR", "AMBAR_AD"))
                or "SEVK ÖN",
                "packing_date": date_text(payload_value(payload, "TARIH")),
                "status": "HAZIR" if table == "KASA_BASLIK" else "KASALANIYOR",
                "note": note,
            }

        for table in ("PAKET_BASLIK", "PAKET"):
            for external, payload in tables.get(table, []):
                values = packing_values(table, external, payload)
                if values:
                    packages.append((f"{table}:{external}", values))
        for external, payload in tables.get("KASA_BASLIK", []):
            values = packing_values("KASA_BASLIK", external, payload)
            if values:
                cases.append((f"KASA:{external}", values))

        for external, payload in tables.get("STOK_HA", []):
            stock = stock_data.get(text(payload_value(payload, "STOK_ID")), {})
            code = text(stock.get("stock_code")) or text(payload_value(payload, "STOK_KOD"))
            name = text(stock.get("stock_name")) or text(payload_value(payload, "STOK_AD"))
            if not code or not name:
                continue
            stock_movements.append(
                (
                    f"STOK_HA:{external}",
                    {
                        **stock,
                        "stock_code": code,
                        "stock_name": name,
                        "lot_no": text(payload_value(payload, "LOT_NO")),
                        "warehouse": text(payload_value(payload, "AMBAR_AD", "AMBAR_ID")),
                        "quantity": number(payload_value(payload, "MIKTAR", "KG")),
                        "order_ref": text(payload_value(payload, "SIPARIS_NO", "FIS_NO")),
                        "note": note,
                    },
                )
            )

        for external, payload in tables.get("BAKIM_EMIR", []):
            name = text(payload_value(payload, "AD", "BAKIM_AD", "ACIKLAMA"))
            if not name:
                continue
            maintenance.append(
                (
                    f"BAKIM:{external}",
                    {
                        "maintenance_type": text(payload_value(payload, "BAKIM_TIP"))
                        or "PERİYODİK",
                        "name": name,
                        "operation": text(payload_value(payload, "OPERASYON")),
                        "station": text(payload_value(payload, "ISTASYON")),
                        "planned_start": text(payload_value(payload, "PLAN_BASLANGIC")),
                        "planned_end": text(payload_value(payload, "PLAN_BITIS")),
                        "actual_start": text(payload_value(payload, "BASLANGIC")),
                        "actual_end": text(payload_value(payload, "BITIS")),
                        "status": "TAMAMLANDI"
                        if payload_value(payload, "BITIS")
                        else "BAKIM BEKLİYOR",
                        "note": note,
                    },
                )
            )

        totals = {"inserted": 0, "updated": 0, "skipped": 0}
        destinations = (
            ("Satış", "Müşteriler", customers),
            ("Kalıphane", "Profil Kartları", profiles),
            ("Kalıphane", "Kalıp Kartları", dies),
            ("Malzeme Yönetimi", "Stok Kartları", stocks),
            ("Malzeme Yönetimi", "Stok Hareketleri", stock_movements),
            ("Satış", "Satış Siparişleri", orders),
            ("Üretim", "Üretim Siparişleri", orders),
            ("Üretim", "Reçeteler", recipes),
            ("Üretim", "Üretim Emirleri", production_orders),
            ("Üretim", "İş Emirleri", work_orders),
            ("Üretim", "Pres Üretim Fişleri", press_records),
            ("Sevkiyat", "Kasalama Fişleri", packages),
            ("Sevkiyat", "Hazır Kasalar", cases),
            ("Bakım", "Bakım Emirleri", maintenance),
        )
        for department, module_name, records in destinations:
            if not records:
                continue
            self._merge_counts(
                totals,
                self.erp.upsert_external_records(department, module_name, records),
            )
        return totals

    def sync_connected_workflow(self) -> dict[str, int]:
        """Aktarılan kart ve reçeteleri canlı yerel operasyon şemasına bağlar."""
        def values(department: str, module: str) -> list[dict[str, object]]:
            return [
                dict(record["data"])
                for record in self.erp.list_records(department, module)
            ]

        return self.workflow.import_master_cards(
            customers=values("Satış", "Müşteriler"),
            profiles=values("Kalıphane", "Profil Kartları"),
            dies=values("Kalıphane", "Kalıp Kartları"),
            recipes=values("Üretim", "Reçeteler"),
        )

    @staticmethod
    def _json_value(value: object) -> object:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return f"<binary:{len(value)}>"
        return str(value)

    def _start_batch(self, source_type: str, source_name: str) -> int:
        with closing(self.staging_connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_batches(source_type, source_name, started_at, status)
                VALUES (?, ?, ?, 'ÇALIŞIYOR')
                """,
                (source_type, source_name, datetime.now().isoformat(timespec="seconds")),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def _finish_batch(
        self,
        batch_id: int,
        totals: dict[str, int],
        errors: list[str],
    ) -> None:
        with closing(self.staging_connect()) as connection:
            connection.execute(
                """
                UPDATE import_batches
                SET completed_at = ?, status = ?, inserted_count = ?,
                    updated_count = ?, skipped_count = ?, error_text = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    "UYARILI" if errors else "TAMAMLANDI",
                    totals["inserted"],
                    totals["updated"],
                    totals["skipped"],
                    "\n".join(errors)[:8000],
                    int(batch_id),
                ),
            )
            connection.commit()

    def _fail_batch(self, batch_id: int, error: str) -> None:
        with closing(self.staging_connect()) as connection:
            connection.execute(
                """
                UPDATE import_batches
                SET completed_at = ?, status = 'HATA', error_text = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    error[:8000],
                    int(batch_id),
                ),
            )
            connection.commit()
