from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TEST_DATA_DIR = tempfile.TemporaryDirectory()
os.environ["RIGELCOST_DATA_DIR"] = _TEST_DATA_DIR.name

from PySide6.QtWidgets import QApplication

from main import apply_rigel_typography
from pages.workflow import ProductionPlanDialog, WorkflowPage
from services.local_workflow import LocalWorkflowService
from ui.corporate_theme import BASE_POINT_SIZE, TABLE_POINT_SIZE
from ui.master_data_dialogs import DieCreateDialog, ProfileCreateDialog


class CustomerDieCrudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_rigel_typography(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        _TEST_DATA_DIR.cleanup()

    def setUp(self) -> None:
        self.db = Path(_TEST_DATA_DIR.name) / f"crud_{self.id().split('.')[-1]}.sqlite"
        if self.db.exists():
            self.db.unlink()
        self.service = LocalWorkflowService(self.db)

    def test_fonts_are_readable(self) -> None:
        # Tam ekranda grid kaydırmasız sığsın diye yoğunluk 11–11.5pt aralığında.
        self.assertGreaterEqual(BASE_POINT_SIZE, 11.0)
        self.assertGreaterEqual(TABLE_POINT_SIZE, 11.0)
        self.assertGreaterEqual(self.app.font().pointSizeF(), 11.0)

    def test_customer_create_and_delete(self) -> None:
        customer_id = self.service.create_customer(
            "M-DEL-1", "Silinecek Müşteri", username="test"
        )
        self.assertTrue(
            any(int(r["id"]) == customer_id for r in self.service.list_customers())
        )
        self.service.delete_customer(customer_id, username="test")
        self.assertFalse(
            any(
                int(r["id"]) == customer_id
                for r in self.service.list_customers(include_inactive=True)
            )
        )

    def test_customer_delete_blocked_by_order(self) -> None:
        customer_id = self.service.create_customer("M-ORD", "Siparişli", username="test")
        profile_id = self.service.create_profile(
            "P-ORD", "Profil ORD", unit_weight_kg_m=1.2, username="test"
        )
        die_id = self.service.create_die(
            profile_id,
            "D-ORD",
            username="test",
            tenefer_no="1",
            tenefer_limit_m=2000,
        )
        self.service.create_sales_order(
            customer_id,
            order_date="2026-08-01",
            delivery_date="2026-08-15",
            lines=[{
                "profile_id": profile_id,
                "die_id": die_id,
                "quantity": 10,
                "length_mm": 6000,
                "kg": 12.0,
                "unit_price": 1,
            }],
            username="test",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.delete_customer(customer_id, username="test")
        self.assertIn("silinemez", str(ctx.exception).casefold())

    def test_die_create_and_delete(self) -> None:
        profile_id = self.service.create_profile(
            "P-DIE", "Profil DIE", unit_weight_kg_m=1.5, username="test"
        )
        die_id = self.service.create_die(
            profile_id,
            "KLP-DEL",
            spare_no=1,
            figure_count=2,
            tenefer_no="1",
            tenefer_type="STANDART",
            tenefer_limit_m=2000,
            supplier_name="TEST TEDARIK",
            note="silinecek",
            username="test",
        )
        die = self.service.die(die_id)
        self.assertEqual(die["die_code"], "KLP-DEL")
        self.assertEqual(die["supplier_name"], "TEST TEDARIK")
        self.service.delete_die(die_id, username="test")
        with self.assertRaises(ValueError):
            self.service.die(die_id)

    def test_workflow_labels_separate_profile_and_die(self) -> None:
        page = WorkflowPage(username="test", service=self.service)
        page.set_access(can_create=True, can_approve=True, can_edit=True, can_delete=True)
        page.set_context("Kalıphane", "Profil Kartları")
        self.assertEqual(page.primary.text(), "＋ PROFİL")
        self.assertNotIn("ROTA", page.primary.text())
        page.set_context("Kalıphane", "Kalıp Kartları")
        self.assertEqual(page.primary.text(), "＋ KALIP")
        self.assertNotIn("ROTA", page.primary.text())
        self.assertEqual(page.danger.text(), "SİL")
        self.assertFalse(page.danger.isHidden())
        labels = [
            spec["label"] for spec in page.CONTEXT_MENUS["customers"]
            if not spec.get("separator")
        ]
        self.assertIn("Ekle", labels)
        self.assertIn("Sil", labels)
        die_labels = [
            spec["label"] for spec in page.CONTEXT_MENUS["dies"]
            if not spec.get("separator")
        ]
        self.assertIn("Ekle", die_labels)
        self.assertIn("Sil", die_labels)
        page.close()

    def test_create_dialogs_have_no_route_fields(self) -> None:
        profile_dialog = ProfileCreateDialog()
        self.assertTrue(hasattr(profile_dialog, "code"))
        self.assertFalse(hasattr(profile_dialog, "route_steps"))
        self.assertFalse(hasattr(profile_dialog, "raw_material"))
        profile_dialog.close()

        profile_id = self.service.create_profile(
            "P-UI", "Profil UI", unit_weight_kg_m=1.1, username="test"
        )
        die_dialog = DieCreateDialog(self.service)
        self.assertTrue(hasattr(die_dialog, "die_code"))
        self.assertFalse(hasattr(die_dialog, "route_steps"))
        self.assertFalse(hasattr(die_dialog, "create_recipe"))
        die_dialog.profile.setCurrentIndex(die_dialog.profile.findData(profile_id))
        die_dialog.die_code.setText("KLP-UI")
        payload = die_dialog.values()
        self.assertEqual(payload["profile_id"], profile_id)
        self.assertNotIn("route", payload)
        die_dialog.close()

    def test_production_plan_dialog_has_recipe_route_material(self) -> None:
        dialog = ProductionPlanDialog(self.service)
        self.assertTrue(hasattr(dialog, "recipe"))
        self.assertTrue(hasattr(dialog, "route"))
        self.assertTrue(hasattr(dialog, "raw_material"))
        self.assertTrue(hasattr(dialog, "stations"))
        self.assertEqual(dialog.windowTitle(), "Üretim Emri")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
