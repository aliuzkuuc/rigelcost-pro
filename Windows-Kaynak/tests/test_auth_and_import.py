from __future__ import annotations

import os
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtWidgets import QAbstractButton, QApplication

from main import COST_PAGE, DASHBOARD_PAGE, MainWindow
from services.data_import import (
    DataImportService,
    EncryptedConnectionStringError,
)
from services.auth import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    VIEW_COST,
    VIEW_DIE,
    VIEW_SALES,
    AuthService,
    UserSession,
)
from services.erp import ErpService


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = AuthService(Path(self.temp_dir.name) / "security.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_password_is_hashed_and_sales_permissions_are_limited(self) -> None:
        user_id = self.service.create_user(
            "satis01", "Satış Kullanıcısı", "Guvenli123", "SATIŞ"
        )
        session = self.service.authenticate("satis01", "Guvenli123")

        self.assertIsNotNone(session)
        self.assertTrue(session.can(VIEW_SALES))
        self.assertFalse(session.can(VIEW_COST))
        self.assertFalse(session.can(VIEW_DIE))
        with closing(sqlite3.connect(self.service.database_path)) as connection:
            salt, password_hash = connection.execute(
                "SELECT password_salt, password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        self.assertNotIn(b"Guvenli123", bytes(salt) + bytes(password_hash))

    def test_last_active_owner_cannot_be_demoted(self) -> None:
        user_id = self.service.create_first_owner("patron", "Patron", "Patron123")
        with self.assertRaisesRegex(ValueError, "Son aktif patron"):
            self.service.update_user(
                user_id,
                display_name="Patron",
                role="YÖNETİCİ",
                permissions=ROLE_PERMISSIONS["YÖNETİCİ"],
                active=True,
                actor="patron",
            )


class PermissionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_sales_user_cannot_open_hidden_cost_or_die_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth = AuthService(Path(temp) / "security.db")
            session = UserSession(
                7,
                "satis01",
                "Satış Kullanıcısı",
                "SATIŞ",
                ROLE_PERMISSIONS["SATIŞ"],
            )
            previous = os.environ.get("RIGELCOST_DATA_DIR")
            os.environ["RIGELCOST_DATA_DIR"] = temp
            try:
                window = MainWindow(session=session, auth_service=auth)
                self.assertFalse(hasattr(window, "cost_nav_button"))
                self.assertFalse(hasattr(window, "die_nav_button"))
                self.assertEqual(window.stack.currentIndex(), DASHBOARD_PAGE)
                self.assertFalse(window.show_page(COST_PAGE))
                self.assertEqual(window.stack.currentIndex(), DASHBOARD_PAGE)
                window.show_department("Kalıphane", "Kalıp Kartları")
                self.assertEqual(window.stack.currentIndex(), DASHBOARD_PAGE)
                window.show_department("Satış", "Satış Siparişleri")
                self.assertEqual(window.workflow_page.department, "Satış")
                self.assertEqual(window.workflow_page.module, "Satış Siparişleri")
                window.close()
            finally:
                if previous is None:
                    os.environ.pop("RIGELCOST_DATA_DIR", None)
                else:
                    os.environ["RIGELCOST_DATA_DIR"] = previous

    def test_initial_import_menu_is_visible_only_to_developer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            previous = os.environ.get("RIGELCOST_DATA_DIR")
            os.environ["RIGELCOST_DATA_DIR"] = temp
            try:
                developer = MainWindow(session=UserSession.owner("aliuzkuc"))
                developer_labels = {
                    button.text() for button in developer.findChildren(QAbstractButton)
                }
                self.assertIn("İlk Veri Aktarımı", developer_labels)
                developer.close()

                normal_owner = MainWindow(session=UserSession.owner("patron"))
                normal_labels = {
                    button.text() for button in normal_owner.findChildren(QAbstractButton)
                }
                self.assertNotIn("İlk Veri Aktarımı", normal_labels)
                normal_owner.close()
            finally:
                if previous is None:
                    os.environ.pop("RIGELCOST_DATA_DIR", None)
                else:
                    os.environ["RIGELCOST_DATA_DIR"] = previous

    def test_first_install_import_marker_prevents_second_automatic_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth = AuthService(Path(temp) / "security.db")
            session = UserSession(
                9,
                "patron",
                "Patron",
                "PATRON",
                ALL_PERMISSIONS,
            )
            previous = os.environ.get("RIGELCOST_DATA_DIR")
            os.environ["RIGELCOST_DATA_DIR"] = temp
            try:
                window = MainWindow(session=session, auth_service=auth)
                self.assertTrue(window.should_show_initial_import())
                with patch.object(window, "open_initial_import") as open_import:
                    window.open_initial_import_once()
                    open_import.assert_called_once_with(force=True)
                self.assertTrue(window.initial_import_marker.exists())
                self.assertFalse(window.should_show_initial_import())
                window.close()
            finally:
                if previous is None:
                    os.environ.pop("RIGELCOST_DATA_DIR", None)
                else:
                    os.environ["RIGELCOST_DATA_DIR"] = previous


class DataImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.erp = ErpService(root / "erp.db")
        self.importer = DataImportService(self.erp, root / "data_import.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_profile_customer_and_die_import_is_repeatable(self) -> None:
        source = Path(self.temp_dir.name) / "import_source"
        source.mkdir()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Profil Kodu",
                "Profil Adı",
                "Firma",
                "Birim Ağırlık",
                "Yedek No",
                "Kalıpçı Kodu",
                "Tedarikçi",
                "Figür",
                "Aktif",
            ]
        )
        sheet.append(
            ["P-100", "Kapı Profili", "Örnek Müşteri", 1.25, 1, "K-100", "Kalıp AŞ", 2, True]
        )
        workbook.save(source / "Profil Kartları.xlsx")
        recipes = Workbook()
        recipe_sheet = recipes.active
        recipe_sheet.append(
            [
                "Reçete Kod", "Reçete Ad", "Rota", "Stok Ad", "Profil Kod",
                "Profil Firma", "U.Boy (mm)", "Yüzey", "Renk", "Alaşım",
                "Sertlik", "Mekanik", "Aktif", "Birim Ağırlık",
            ]
        )
        recipe_sheet.append(
            [
                "REC-100", "Kapı Profil Reçetesi", "PRES 1 - TERMİK",
                "Kapı Profili", "P-100", "Örnek Müşteri", 6000, "PRES", "*",
                "6060B", "T5", "YOK", True, 1.25,
            ]
        )
        recipes.save(source / "Reçeteler.xlsx")
        shared = source / "SharedFiles" / "PROFIL"
        shared.mkdir(parents=True)
        (shared / "P-100 Teknik Resim.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
        (shared / "P-100 Profil.jpg").write_bytes(b"fake-jpg")
        die_shared = source / "SharedFiles" / "KALIP"
        die_shared.mkdir(parents=True)
        (die_shared / "K-100 Kalip.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
        (die_shared / "K-100 Kalip.jpg").write_bytes(b"fake-jpg")

        first = self.importer.import_excel_folder(source)
        second = self.importer.import_excel_folder(source)

        self.assertEqual(first["errors"], [])
        self.assertGreaterEqual(first["inserted"], 3)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(len(self.erp.list_records("Satış", "Müşteriler")), 1)
        self.assertEqual(len(self.erp.list_records("Kalıphane", "Profil Kartları")), 1)
        profile = self.erp.list_records("Kalıphane", "Profil Kartları")[0]
        self.assertTrue(Path(profile["data"]["drawing_path"]).exists())
        self.assertTrue(Path(profile["data"]["image_path"]).exists())
        self.assertEqual(first["attachments"]["copied"], 4)
        self.assertEqual(second["attachments"]["unchanged"], 4)
        dies = self.erp.list_records("Kalıphane", "Kalıp Kartları")
        self.assertEqual(len(dies), 1)
        self.assertEqual(dies[0]["data"]["die_code"], "K-100")
        self.assertTrue(Path(dies[0]["data"]["pdf_path"]).exists())
        self.assertTrue(Path(dies[0]["data"]["image_path"]).exists())
        self.assertEqual(first["attachments"]["linked_dies"], 1)
        self.assertEqual(first["connected_workflow"]["customers"], 1)
        self.assertEqual(first["connected_workflow"]["attachments"], 4)
        self.assertEqual(len(self.importer.workflow.list_customers()), 1)
        self.assertEqual(len(self.importer.workflow.list_profiles()), 1)
        self.assertEqual(len(self.importer.workflow.list_dies()), 1)
        self.assertEqual(self.importer.workflow.list_profiles()[0]["has_route"], 1)
        local_profile = self.importer.workflow.list_profiles()[0]
        local_die = self.importer.workflow.list_dies()[0]
        self.assertEqual(
            len(self.importer.workflow.list_attachments("PROFILE", local_profile["id"])),
            2,
        )
        self.assertEqual(
            len(self.importer.workflow.list_attachments("DIE", local_die["id"])),
            2,
        )

    def test_real_profile_die_exports_and_documents_are_mapped(self) -> None:
        source = Path(self.temp_dir.name) / "ornek-gercek-basliklar"
        source.mkdir()

        profiles = Workbook()
        profile_sheet = profiles.active
        profile_sheet.append(
            [
                "PROFİL KODU", "RESİM", "PROFİL ADI", "ÖZEL KOD",
                "FİRMA ADI", "FİRMA PROFİL KODU", "GRUP ADI",
                "BİRİM AĞIRLIK (Kg/m)", "ÇİZİM YAPAN", "AÇIKLAMA",
                "KALIP ADET", "TEDARIK EDILIYOR", "KALIP CİNSİ",
            ]
        )
        profile_sheet.append(
            [
                "1002", None, "GENİŞ MAKAS U", "OZ-2",
                "RİGEL ALÜMİNYUM AŞ.", "M-1002", "PANJUR", 0.334,
                "Teknik", "Profil açıklaması", 1, False, "SOLİT TAKIM",
            ]
        )
        profiles.save(source / "Profil Listesi (profil kartları ).xlsx")

        dies = Workbook()
        die_sheet = dies.active
        die_sheet.append(
            [
                "PROFİL KODU", "GRUP ADI", "YEDEK NO", "DURUM", "RESIM",
                "TEDARİKÇİ ADI", "PROFİL ADI", "TENEFER ÖMRÜ M",
                "BİRİM AĞIRLIK", "FİRMA", "KALIPÇI KODU", "KALIP CİNS",
                "FİGÜR ADET", "GERÇEK GRAMAJ", "RAF", "AKTİF",
                "TENEFER BASILAN M", "PRES NET KG", "AÇIKLAMA",
            ]
        )
        die_sheet.append(
            [
                "1002", "PANJUR", 0, "ARŞİVDE", None,
                "DOĞUŞ KALIP LTD.ŞTİ", "GENİŞ MAKAS U", 8000,
                0.334, "RİGEL ALÜMİNYUM AŞ.", "33705", "SOLİT TAKIM",
                2, 0.326, "A1", True, 11001.41, 9241.68,
                "Kalıp açıklaması",
            ]
        )
        dies.save(source / "Kalıp Listesi (kalıp kartları ).xlsx")

        pending = Workbook()
        pending_sheet = pending.active
        pending_sheet.append(
            [
                "İŞ EMRİ TARİHİ", "İMALAT TERMİN", "DURUM", "RESİM",
                "PROFİL KODU", "YEDEK NO", "PROFİL ADI", "MÜŞTERİ",
                "KALIP CİNS", "FİGÜR ADET", "SON HAREKET",
                "SON HAREKET TARİH", "SON HAREKET PARÇA",
                "SON HAREKET İŞLEM NO", "SON HAREKET AÇIKLAMA",
            ]
        )
        pending_sheet.append(
            [
                "2026-08-01", "2026-08-20", "İMALATTA", None,
                "1002", 0, "GENİŞ MAKAS U", "RİGEL ALÜMİNYUM AŞ.",
                "SOLİT TAKIM", 2, "TEDARİKÇİDE", "2026-08-03",
                "GÖBEK", "20", "İmalat devam ediyor",
            ]
        )
        # Legacy exports sometimes append a single summary value.
        pending_sheet.append([None, None, None, None, 5])
        pending.save(source / "Üretilecek Kalıplar Listesi ( imalattaki kalıplar).xlsx")

        profile_dir = source / "SharedFiles" / "PROFIL" / "1002"
        die_dir = source / "SharedFiles" / "KALIP" / "88"
        profile_dir.mkdir(parents=True)
        die_dir.mkdir(parents=True)
        (profile_dir / "misnamed-drawing.jpg").write_bytes(b"fake-jpg")
        (die_dir / "1002-Model.pdf").write_bytes(b"%PDF-1.4\n%%EOF")

        result = self.importer.import_excel_folder(source)

        self.assertEqual(result["errors"], [])
        customers = self.erp.list_records("Satış", "Müşteriler")
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["data"]["name"], "RİGEL ALÜMİNYUM AŞ.")

        imported_profiles = self.erp.list_records("Kalıphane", "Profil Kartları")
        self.assertEqual(len(imported_profiles), 1)
        profile = imported_profiles[0]["data"]
        self.assertEqual(profile["profile_code"], "1002")
        self.assertAlmostEqual(profile["unit_weight"], 0.334)
        self.assertEqual(profile["company"], "RİGEL ALÜMİNYUM AŞ.")
        self.assertEqual(profile["customer_code"], "M-1002")
        self.assertEqual(profile["group"], "PANJUR")
        self.assertTrue(Path(profile["image_path"]).exists())

        imported_dies = self.erp.list_records("Kalıphane", "Kalıp Kartları")
        self.assertEqual(len(imported_dies), 1)
        die = imported_dies[0]["data"]
        self.assertEqual(die["die_code"], "33705")
        self.assertEqual(die["supplier"], "DOĞUŞ KALIP LTD.ŞTİ")
        self.assertEqual(die["figure"], 2)
        self.assertEqual(die["status"], "ARŞİVDE")
        self.assertEqual(die["location"], "A1")
        self.assertAlmostEqual(die["tenefer_limit_m"], 8000)
        self.assertAlmostEqual(die["tenefer_used_m"], 11001.41)
        self.assertAlmostEqual(die["used_kg"], 9241.68)
        self.assertTrue(Path(die["pdf_path"]).exists())

        pending_records = self.erp.list_records("Kalıphane", "İmalattaki Kalıplar")
        self.assertEqual(len(pending_records), 1)
        self.assertEqual(pending_records[0]["data"]["status"], "İMALATTA")
        self.assertEqual(pending_records[0]["data"]["profile_code"], "1002")
        self.assertEqual(len(self.importer.workflow.list_profiles()), 1)
        self.assertEqual(len(self.importer.workflow.list_dies()), 1)

    def test_encrypted_config_is_detected_before_sql_connection(self) -> None:
        config = Path(self.temp_dir.name) / "rigel.config"
        config.write_text(
            """
            <configuration><appSettings>
              <add key="ConnectionString" value="QWx1ZGF0YUVuY3J5cHRlZERhdGE=" />
            </appSettings></configuration>
            """,
            encoding="utf-8",
        )
        with self.assertRaises(EncryptedConnectionStringError):
            self.importer.parse_config_connection(config)

    def test_plain_config_connection_is_supported(self) -> None:
        config = Path(self.temp_dir.name) / "rigel.config"
        config.write_text(
            """
            <configuration><appSettings>
              <add key="ConnectionString"
                   value="Server=192.168.1.135;Database=RIGEL;User ID=reader;Password=secret" />
            </appSettings></configuration>
            """,
            encoding="utf-8",
        )
        values = self.importer.parse_config_connection(config)
        self.assertEqual(values["SERVER"], "192.168.1.135")
        self.assertEqual(values["DATABASE"], "RIGEL")

    def test_server_is_inferred_from_shared_path_when_connection_is_encrypted(self) -> None:
        config = Path(self.temp_dir.name) / "rigel.config"
        config.write_text(
            r"""
            <configuration><appSettings>
              <add key="ConnectionString" value="QWx1ZGF0YUVuY3J5cHRlZERhdGE=" />
              <add key="PaylasimPath" value="\\192.168.1.135\shared\SharedFiles" />
            </appSettings></configuration>
            """,
            encoding="utf-8",
        )
        self.assertEqual(
            self.importer.infer_server_from_config(config),
            "192.168.1.135",
        )

    def test_sql_staging_materializes_connected_business_records(self) -> None:
        rows = {
            "FIRMA": [("1", {"ID": 1, "KOD": "M-1", "FIRMA_AD": "Müşteri A"})],
            "PROFIL": [
                ("10", {"ID": 10, "KOD": "P-10", "AD": "Kapı Profili", "FIRMA_ID": 1})
            ],
            "KALIP": [
                ("20", {"ID": 20, "KALIP_KOD": "K-20", "PROFIL_ID": 10, "YEDEK_NO": 1})
            ],
            "ROTA": [
                ("80", {"ID": 80, "KOD": "R-80", "AD": "PRES TERMİK"})
            ],
            "ROTA_D": [
                ("81", {"ID": 81, "ROTA_ID": 80, "SIRA": 1, "ISTASYON_AD": "PRES 1"}),
                ("82", {"ID": 82, "ROTA_ID": 80, "SIRA": 2, "ISTASYON_AD": "TERMİK"}),
            ],
            "RECETE": [
                (
                    "90",
                    {
                        "ID": 90, "KOD": "REC-90", "AD": "Kapı reçetesi",
                        "PROFIL_ID": 10, "ROTA_ID": 80, "URETIM_BOY": 6000,
                        "YUZEY": "PRES", "ALASIM": "6060B", "SERTLIK": "T5",
                        "AKTIF": True,
                    },
                )
            ],
            "STOK": [
                ("30", {"ID": 30, "KOD": "S-30", "AD": "Kapı Profili", "PROFIL_ID": 10})
            ],
            "SIPARIS": [
                ("40", {"ID": 40, "FIS_NO": "SIP-40", "FIRMA_ID": 1, "TARIH": "2026-08-03"})
            ],
            "SIPARIS_D": [
                ("41", {"ID": 41, "SIPARIS_ID": 40, "PROFIL_ID": 10, "STOK_ID": 30, "KG": 1250})
            ],
            "URETIM_EMRI": [
                ("50", {"ID": 50, "URETIM_EMRI_NO": "UEM-50", "SIPARIS_NO": "SIP-40", "PROFIL_ID": 10, "FIRMA_ID": 1, "KG": 1250})
            ],
            "IS_EMRI": [
                ("60", {"ID": 60, "IS_EMRI_NO": "IEM-60", "URETIM_EMRI_ID": 50, "SIPARIS_NO": "SIP-40", "PROFIL_ID": 10})
            ],
            "PAKET_BASLIK": [
                ("70", {"ID": 70, "PAKET_NO": "PK-70", "FIRMA_ID": 1, "PROFIL_ID": 10, "SIPARIS_NO": "SIP-40", "NET_KG": 500})
            ],
        }
        with closing(self.importer.staging_connect()) as connection:
            for table, table_rows in rows.items():
                for external_key, payload in table_rows:
                    connection.execute(
                        """
                        INSERT INTO raw_records(source_table, external_key, payload_json, imported_at)
                        VALUES (?, ?, ?, '2026-08-03T12:00:00')
                        """,
                        (table, external_key, json.dumps(payload)),
                    )
            connection.commit()

        result = self.importer.materialize_sql_masters()
        connected = self.importer.sync_connected_workflow()

        self.assertGreaterEqual(result["inserted"], 9)
        self.assertEqual(len(self.erp.list_records("Satış", "Müşteriler")), 1)
        self.assertEqual(len(self.erp.list_records("Kalıphane", "Profil Kartları")), 1)
        self.assertEqual(len(self.erp.list_records("Kalıphane", "Kalıp Kartları")), 1)
        self.assertEqual(len(self.erp.list_records("Malzeme Yönetimi", "Stok Kartları")), 1)
        self.assertEqual(len(self.erp.list_records("Satış", "Satış Siparişleri")), 1)
        self.assertEqual(len(self.erp.list_records("Üretim", "Üretim Emirleri")), 1)
        self.assertEqual(len(self.erp.list_records("Üretim", "Reçeteler")), 1)
        self.assertEqual(len(self.erp.list_records("Üretim", "İş Emirleri")), 1)
        self.assertEqual(len(self.erp.list_records("Sevkiyat", "Kasalama Fişleri")), 1)
        self.assertEqual(connected["customers"], 1)
        self.assertEqual(len(self.importer.workflow.list_profiles()), 1)
        self.assertEqual(self.importer.workflow.list_profiles()[0]["has_route"], 1)

    def test_shared_files_are_linked_by_sql_record_folder_id(self) -> None:
        self.erp.upsert_external_records(
            "Kalıphane",
            "Profil Kartları",
            [
                (
                    "PROFIL:10",
                    {
                        "profile_code": "P-XYZ",
                        "profile_name": "Profil XYZ",
                        "active": True,
                    },
                )
            ],
        )
        self.erp.upsert_external_records(
            "Kalıphane",
            "Kalıp Kartları",
            [
                (
                    "KALIP:20",
                    {
                        "die_code": "K-XYZ",
                        "profile_code": "P-XYZ",
                        "status": "AKTİF",
                    },
                )
            ],
        )
        source = Path(self.temp_dir.name) / "network_share"
        profile_dir = source / "SharedFiles" / "PROFIL" / "10"
        die_dir = source / "SharedFiles52" / "KALIP" / "20"
        profile_dir.mkdir(parents=True)
        die_dir.mkdir(parents=True)
        (profile_dir / "technical-model.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
        (die_dir / "photo-without-code.jpg").write_bytes(b"fake-jpg")

        result = self.importer.import_shared_files(source)

        profile = self.erp.list_records("Kalıphane", "Profil Kartları")[0]
        die = self.erp.list_records("Kalıphane", "Kalıp Kartları")[0]
        self.assertTrue(Path(profile["data"]["drawing_path"]).exists())
        self.assertTrue(Path(die["data"]["image_path"]).exists())
        self.assertEqual(result["linked_profiles"], 1)
        self.assertEqual(result["linked_dies"], 1)


if __name__ == "__main__":
    unittest.main()
