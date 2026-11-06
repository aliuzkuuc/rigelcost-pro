"""Sütun filtre satırı — Excel tarzı çoklu seçim (checkbox)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TEST_DATA_DIR = tempfile.TemporaryDirectory()
os.environ["RIGELCOST_DATA_DIR"] = _TEST_DATA_DIR.name

from PySide6.QtWidgets import QApplication

from pages.workflow import WorkflowPage
from services.local_workflow import LocalWorkflowService
from ui.column_filter_bar import (
    ColumnFilterBar,
    MultiSelectFilterButton,
    MultiSelectFilterPopup,
    normalize_tr,
)


class ColumnFilterBarUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_normalize_tr_is_turkish_friendly(self) -> None:
        self.assertEqual(normalize_tr("İMALATTA"), normalize_tr("imalatta"))
        self.assertEqual(normalize_tr("ŞİRİN"), normalize_tr("şirin"))
        self.assertIn(normalize_tr("kalıp"), normalize_tr("KALIP KOD"))

    def test_multi_select_values_and_deselect_one(self) -> None:
        bar = ColumnFilterBar()
        bar.configure(
            (("status", "Durum"), ("customer_name", "Firma"), ("code", "Kod"))
        )
        editors = bar._editors
        self.assertIsInstance(editors[0], MultiSelectFilterButton)
        editors[0].set_available_values(["AÇIK", "HAZIR", "İMALATTA"])
        editors[1].set_available_values(["Alpha", "Beta", "Gamma"])

        # Tümünü seç (None) → filtre yok
        editors[0].set_filter(values=None, emit=False)
        self.assertFalse(bar.has_active_filters())
        self.assertTrue(bar.row_matches({"status": "AÇIK", "customer_name": "Alpha"}))

        # 3 değerden 2'sini seç (birini çıkar)
        editors[0].set_filter(values={"AÇIK", "HAZIR"}, emit=False)
        self.assertTrue(bar.has_active_filters())
        self.assertTrue(bar.row_matches({"status": "AÇIK", "customer_name": "X"}))
        self.assertTrue(bar.row_matches({"status": "HAZIR", "customer_name": "X"}))
        self.assertFalse(bar.row_matches({"status": "İMALATTA", "customer_name": "X"}))

        # Çoklu firma seçimi
        editors[1].set_filter(values={"Alpha", "Gamma"}, emit=False)
        self.assertTrue(
            bar.row_matches({"status": "AÇIK", "customer_name": "Alpha", "code": "1"})
        )
        self.assertFalse(
            bar.row_matches({"status": "AÇIK", "customer_name": "Beta", "code": "1"})
        )

        bar.clear_filters()
        self.assertFalse(bar.has_active_filters())
        self.assertTrue(
            bar.row_matches({"status": "İMALATTA", "customer_name": "Beta", "code": "1"})
        )
        bar.close()

    def test_select_all_then_deselect_one_via_api(self) -> None:
        bar = ColumnFilterBar()
        bar.configure((("status", "Durum"),))
        editor = bar._editors[0]
        values = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J"}
        editor.set_available_values(sorted(values))
        # Tümünü seç
        editor.set_filter(values=set(values), emit=False)
        self.assertFalse(editor.is_active())  # hepsi = filtre yok
        # Birini çıkar
        editor.set_filter(values=values - {"C"}, emit=False)
        self.assertTrue(editor.is_active())
        self.assertEqual(len(editor.selected_values() or ()), 9)
        self.assertTrue(bar.row_matches({"status": "A"}))
        self.assertFalse(bar.row_matches({"status": "C"}))
        bar.close()

    def test_text_contains_optional(self) -> None:
        bar = ColumnFilterBar()
        bar.configure((("profile_code", "Profil"),))
        bar._editors[0].set_available_values(["PRF-100", "PRF-200", "ABC-1"])
        bar.set_column_filter("profile_code", contains="PRF", emit=False)
        self.assertTrue(bar.row_matches({"profile_code": "PRF-100"}))
        self.assertFalse(bar.row_matches({"profile_code": "ABC-1"}))
        bar.close()

    def test_update_distinct_values_feeds_checkboxes(self) -> None:
        bar = ColumnFilterBar()
        bar.configure((("customer_name", "Firma"), ("status", "Durum")))
        bar.update_distinct_values(
            [
                {"customer_name": "Filtre A", "status": "AÇIK"},
                {"customer_name": "Filtre B", "status": "HAZIR"},
                {"customer_name": "Filtre A", "status": "AÇIK"},
            ]
        )
        firm = bar.editor_for("customer_name")
        assert firm is not None
        self.assertIn("Filtre A", firm.available_values())
        self.assertIn("Filtre B", firm.available_values())
        bar.close()

    def test_popup_select_all_deselect_one_and_multi(self) -> None:
        """Excel tarzı popup: Tümünü seç, birini çıkar, ~10 değer seç."""
        popup = MultiSelectFilterPopup()
        values = [f"V{i}" for i in range(1, 13)]
        popup.populate(values, selected=None)  # hepsi işaretli
        self.assertEqual(popup.selected_values(), set(values))

        popup.clear_btn.click()
        self.assertEqual(popup.selected_values(), set())

        popup.select_all_btn.click()
        self.assertEqual(popup.selected_values(), set(values))

        # Birini çıkar
        popup._checks["V3"].setChecked(False)
        chosen = popup.selected_values()
        self.assertEqual(len(chosen), 11)
        self.assertNotIn("V3", chosen)

        # Yaklaşık 10 değer seç
        popup.clear_btn.click()
        for key in values[:10]:
            popup._checks[key].setChecked(True)
        self.assertEqual(len(popup.selected_values()), 10)

        applied = []
        popup.applied.connect(lambda: applied.append(True))
        popup.apply_btn.click()
        self.assertTrue(applied)
        popup.close()

    def test_button_apply_from_popup_updates_filter(self) -> None:
        bar = ColumnFilterBar()
        bar.configure((("status", "Durum"),))
        editor = bar._editors[0]
        assert isinstance(editor, MultiSelectFilterButton)
        values = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        editor.set_available_values(values)
        editor._open_popup()
        popup = editor._popup
        self.assertTrue(popup.isVisible())
        popup.clear_btn.click()
        for key in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"):
            if key != "C":
                popup._checks[key].setChecked(True)
            else:
                popup._checks[key].setChecked(False)
        popup.apply_btn.click()
        self.assertTrue(editor.is_active())
        self.assertEqual(len(editor.selected_values() or ()), 9)
        self.assertFalse(bar.row_matches({"status": "C"}))
        self.assertTrue(bar.row_matches({"status": "A"}))
        bar.close()


class WorkflowColumnFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "rigel_operations.db"
        self.service = LocalWorkflowService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _seed_order_and_dies(self) -> None:
        customer_id = self.service.create_customer(
            "M-FLT", "Filtre Müşteri A.Ş.", username="satis"
        )
        profile_id = self.service.create_profile(
            "PRF-FLT", "Filtre Profil", unit_weight_kg_m=1.25,
            customer_id=customer_id, username="patron",
        )
        self.service.create_die(
            profile_id, "KLP-A", life_limit_kg=50_000, username="kaliphane"
        )
        die_b = self.service.create_die(
            profile_id, "KLP-B", life_limit_kg=40_000, username="kaliphane"
        )
        from contextlib import closing

        with closing(self.service.connect()) as connection:
            connection.execute(
                "UPDATE dies SET status = 'İMALATTA' WHERE id = ?",
                (die_b,),
            )
            connection.commit()
        self.service.create_sales_order(
            customer_id,
            order_date="2026-08-01",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id, "length_mm": 6000, "surface": "PRES",
                "quantity": 100, "kg": 500, "unit_price": 4.5,
            }],
            username="satis",
        )
        other = self.service.create_customer(
            "M-DIGER", "Diğer Firma", username="satis"
        )
        self.service.create_sales_order(
            other,
            order_date="2026-08-02",
            delivery_date="2026-08-22",
            lines=[{
                "profile_id": profile_id, "length_mm": 6000, "surface": "PRES",
                "quantity": 50, "kg": 250, "unit_price": 4.5,
            }],
            username="satis",
        )

    def test_orders_grid_multi_select_and_clear(self) -> None:
        self._seed_order_and_dies()
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Satış", "Satış Siparişleri")
        self.assertFalse(page.column_filter_bar.isHidden())
        self.assertEqual(
            len(page.column_filter_bar._editors),
            page.table.columnCount(),
        )
        total = page.table.rowCount()
        self.assertGreaterEqual(total, 2)

        firm_editor = page.column_filter_bar.editor_for("customer_name")
        self.assertIsInstance(firm_editor, MultiSelectFilterButton)
        assert firm_editor is not None
        available = firm_editor.available_values()
        self.assertGreaterEqual(len(available), 2)
        target = next(v for v in available if "Filtre" in v)
        firm_editor.set_filter(values={target}, emit=True)
        page.refresh_data()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertIn("Filtre", page.records[0]["customer_name"])

        page.column_filter_bar.clear_filters()
        page.refresh_data()
        self.assertEqual(page.table.rowCount(), total)
        page.close()

    def test_dies_grid_status_multi_select(self) -> None:
        self._seed_order_and_dies()
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Kalıphane", "Kalıp Kartları")
        self.assertFalse(page.column_filter_bar.isHidden())
        total = page.table.rowCount()
        self.assertGreaterEqual(total, 2)

        status_editor = page.column_filter_bar.editor_for("status")
        self.assertIsInstance(status_editor, MultiSelectFilterButton)
        assert status_editor is not None
        # Tümünü seç sonra birini bırak (İMALATTA)
        all_vals = set(status_editor.available_values())
        status_editor.set_filter(values=all_vals, emit=False)
        self.assertFalse(status_editor.is_active())
        status_editor.set_filter(values={"İMALATTA"}, emit=True)
        page.refresh_data()
        self.assertGreaterEqual(page.table.rowCount(), 1)
        self.assertLess(page.table.rowCount(), total)
        for row in page.records:
            self.assertIn("İMALATTA", str(row.get("status") or "").upper())

        page.clear_column_filters.click()
        page.refresh_data()
        self.assertEqual(page.table.rowCount(), total)
        page.close()

    def test_filter_bar_present_on_many_modules(self) -> None:
        page = WorkflowPage(username="patron", service=self.service)
        modules = (
            ("Satış", "Satış Siparişleri"),
            ("Kalıphane", "Kalıp Kartları"),
            ("Kalıphane", "Profil Kartları"),
            ("Üretim", "İş Emirleri"),
            ("Malzeme Yönetimi", "Stok Kartları"),
            ("Sevkiyat", "Hazır Kasalar"),
        )
        for department, module in modules:
            page.set_context(department, module)
            self.assertFalse(
                page.column_filter_bar.isHidden(),
                f"{department}/{module}: filtre satırı gizli",
            )
            self.assertEqual(
                len(page.column_filter_bar._editors),
                page.table.columnCount(),
                f"{department}/{module}: filtre hücresi ≠ sütun",
            )
            self.assertTrue(
                all(
                    isinstance(ed, MultiSelectFilterButton)
                    for ed in page.column_filter_bar._editors
                ),
                f"{department}/{module}: çoklu seçim değil",
            )
        page.close()


if __name__ == "__main__":
    unittest.main()
