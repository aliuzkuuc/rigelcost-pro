from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from main import apply_rigel_flat_theme, apply_rigel_light_palette
from models.erp_definitions import get_module_spec
from pages.department import AttachmentPicker, RecordDialog
from services.erp import ErpService


class CardWorkflowUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_rigel_light_palette(cls.app)
        apply_rigel_flat_theme(cls.app)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = ErpService(Path(self.temp_dir.name) / "erp.db")
        self.service.create_record(
            "Satış",
            "Müşteriler",
            {"code": "MUS-001", "name": "ÖRNEK MÜŞTERİ", "active": True},
        )
        self.service.create_record(
            "Kalıphane",
            "Profil Kartları",
            {
                "profile_code": "PRF-100",
                "profile_name": "KAPI PROFİLİ",
                "company": "ÖRNEK MÜŞTERİ",
                "unit_weight": 1.245,
                "active": True,
            },
        )
        self.service.create_record(
            "Kalıphane",
            "Kalıp Kartları",
            {
                "die_code": "KLP-100",
                "profile_code": "PRF-100",
                "spare_no": 1,
                "status": "AKTİF",
            },
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sales_order_selects_existing_customer_profile_and_die_cards(self) -> None:
        dialog = RecordDialog(
            get_module_spec("Satış", "Satış Siparişleri"),
            service=self.service,
        )

        company = dialog.editors["company"]
        profile = dialog.editors["profile_code"]
        die = dialog.editors["die_code"]
        stock = dialog.editors["stock_name"]
        for editor in (company, profile, die, stock):
            self.assertIsInstance(editor, QComboBox)
            self.assertTrue(editor.property("cardLookup"))

        company.setCurrentIndex(company.findData("ÖRNEK MÜŞTERİ"))
        profile.setCurrentIndex(profile.findData("PRF-100"))

        self.assertGreaterEqual(die.findData("KLP-100"), 0)
        die.setCurrentIndex(die.findData("KLP-100"))
        self.assertEqual(stock.currentData(), "KAPI PROFİLİ")
        self.assertEqual(dialog.values()["company"], "ÖRNEK MÜŞTERİ")
        self.assertEqual(dialog.values()["profile_code"], "PRF-100")
        self.assertEqual(dialog.values()["die_code"], "KLP-100")
        dialog.close()

    def test_die_card_selects_profile_and_has_pdf_and_image_buttons(self) -> None:
        dialog = RecordDialog(
            get_module_spec("Kalıphane", "Kalıp Kartları"),
            service=self.service,
        )

        self.assertIsInstance(dialog.editors["profile_code"], QComboBox)
        self.assertIsInstance(dialog.editors["pdf_path"], AttachmentPicker)
        self.assertIsInstance(dialog.editors["image_path"], AttachmentPicker)
        self.assertEqual(
            dialog.editors["pdf_path"].choose_button.text(),
            "PDF EKLE",
        )
        self.assertEqual(
            dialog.editors["image_path"].choose_button.text(),
            "JPG / PNG EKLE",
        )
        dialog.close()

    def test_profile_card_has_pdf_and_image_buttons(self) -> None:
        dialog = RecordDialog(
            get_module_spec("Kalıphane", "Profil Kartları"),
            service=self.service,
        )
        self.assertIsInstance(dialog.editors["drawing_path"], AttachmentPicker)
        self.assertIsInstance(dialog.editors["image_path"], AttachmentPicker)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
