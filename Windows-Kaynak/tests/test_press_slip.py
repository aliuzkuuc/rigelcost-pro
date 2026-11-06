"""Pres üretim fişi: servis, ekran ve çıktı için regresyon testleri.

Sayılar sahadan alınan örnek PRES ÜRETİM FİŞİ çıktısıyla aynıdır.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from reports.production_documents import press_slip_html
from reports.shipment_documents import weighing_list_html
from scripts.e2e_pres_fisi import BASKETS, BILLETS, SCRAPS, kur
from services.local_workflow import LocalWorkflowService
from ui.press_production_dialog import PressProductionDialog

GROSS = 189.82
NET = 76.19
QUANTITY = 83


class PressSlipServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )
        self.work_order_id = kur(self.service)
        self.context = self.service.press_entry_context(self.work_order_id)

    def _record(self, **overrides: object) -> int:
        payload: dict[str, object] = {
            "quantity": QUANTITY,
            "gross_kg": GROSS,
            "net_kg": NET,
            "metre": QUANTITY * 6.0,
            "die_id": int(self.context["die_id"]),
            "lot_no": "6612",
            "shift": "2.VARDİYA",
            "username": "PRES",
            "complete": False,
            "billets": BILLETS,
            "baskets": BASKETS,
            "scraps": SCRAPS,
        }
        payload.update(overrides)
        return self.service.record_work_order_output(self.work_order_id, **payload)

    def test_context_carries_die_and_profile_details(self) -> None:
        context = self.context
        self.assertEqual(context["profile_code"], "2082")
        self.assertEqual(context["die_code"], "2082-A")
        self.assertEqual(int(context["figure_count"]), 4)
        self.assertEqual(str(context["tenefer_no"]), "6")
        self.assertEqual(context["order_line_ref"], "R260000001-1")
        self.assertGreater(float(context["tenefer_remaining_m"]), 0)

    def test_slip_stores_all_breakdowns(self) -> None:
        entry_id = self._record(
            qc_username="KK", test_result="BAŞARILI",
            die_problem="GÖRÜNTÜ BOZUK", die_problem_note="4 FİGÜRDE ÇATI KAYIK",
            remaining_quantity=1417,
        )
        document = self.service.press_slip_document(entry_id)
        header = document["header"]
        self.assertTrue(header["slip_no"])
        self.assertAlmostEqual(float(header["gross_kg"]), GROSS, places=2)
        self.assertAlmostEqual(float(header["net_kg"]), NET, places=2)
        self.assertAlmostEqual(float(header["scrap_kg"]), 113.63, places=2)
        self.assertAlmostEqual(float(header["fire_pct"]), 59.86, places=1)
        self.assertEqual(header["die_problem"], "GÖRÜNTÜ BOZUK")
        self.assertEqual(header["test_result"], "BAŞARILI")
        self.assertEqual(len(document["billets"]), 2)
        self.assertEqual(len(document["baskets"]), 1)
        self.assertEqual(len(document["scraps"]), 2)
        self.assertAlmostEqual(
            float(document["billets"][0]["container_temp_c"]), 420.0, places=1
        )
        self.assertAlmostEqual(
            float(document["billets"][0]["press_speed_m_s"]), 4.4, places=2
        )

    def test_slip_numbers_are_sequential_and_unique(self) -> None:
        first = self.service.press_slip_document(self._record())["header"]["slip_no"]
        second = self.service.press_slip_document(self._record())["header"]["slip_no"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(str(first)), 10)
        self.assertEqual(int(second), int(first) + 1)

    def test_billet_total_must_match_slip_gross(self) -> None:
        bozuk = [dict(BILLETS[0], gross_kg=10.0), dict(BILLETS[1])]
        with self.assertRaises(ValueError) as caught:
            self._record(billets=bozuk)
        self.assertIn("Billet brüt", str(caught.exception))

    def test_basket_total_must_match_slip_net(self) -> None:
        bozuk = [dict(BASKETS[0], net_kg=10.0)]
        with self.assertRaises(ValueError) as caught:
            self._record(baskets=bozuk)
        self.assertIn("Sepet net", str(caught.exception))

    def test_basket_quantity_must_match_net_quantity(self) -> None:
        bozuk = [dict(BASKETS[0], quantity=5)]
        with self.assertRaises(ValueError) as caught:
            self._record(baskets=bozuk)
        self.assertIn("Sepet adet", str(caught.exception))

    def test_scrap_breakdown_must_match_fire(self) -> None:
        bozuk = [dict(SCRAPS[0], kg=1.0), dict(SCRAPS[1])]
        with self.assertRaises(ValueError) as caught:
            self._record(scraps=bozuk)
        self.assertIn("Hurda kırılımı", str(caught.exception))

    def test_actual_billets_bypass_theoretical_equality_check(self) -> None:
        """Gerçek döküm varsa tartılan değer teorik hesaba ezdirilmemeli."""
        entry_id = self._record(billet_count=8, theoretical_weight_kg_m=0.153)
        header = self.service.press_slip_document(entry_id)["header"]
        self.assertAlmostEqual(float(header["gross_kg"]), GROSS, places=2)

    def test_work_order_and_die_are_updated(self) -> None:
        self._record()
        work_order = next(
            row for row in self.service.list_work_orders()
            if int(row["id"]) == self.work_order_id
        )
        self.assertAlmostEqual(float(work_order["produced_kg"]), NET, places=2)
        self.assertAlmostEqual(float(work_order["scrap_kg"]), 113.63, places=2)
        die = next(
            row for row in self.service.list_dies()
            if int(row["id"]) == int(self.context["die_id"])
        )
        self.assertAlmostEqual(float(die["used_kg"]), NET, places=2)


class PressSlipDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        service = LocalWorkflowService(Path(cls.temp_dir.name) / "rigel.db")
        work_order_id = kur(service)
        context = service.press_entry_context(work_order_id)
        entry_id = service.record_work_order_output(
            work_order_id, quantity=QUANTITY, gross_kg=GROSS, net_kg=NET,
            metre=QUANTITY * 6.0, die_id=int(context["die_id"]), lot_no="6612",
            shift="2.VARDİYA", username="PRES", complete=False,
            qc_username="KK", test_result="BAŞARILI",
            die_problem="GÖRÜNTÜ BOZUK", remaining_quantity=1417,
            billets=BILLETS, baskets=BASKETS, scraps=SCRAPS,
        )
        cls.document = service.press_slip_document(entry_id)
        cls.html = press_slip_html(cls.document)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_html_contains_every_section(self) -> None:
        for marker in (
            "PRES ÜRETİM FİŞİ", "Billet Boyları", "Sepet Verileri",
            "Hurda Verileri", "KONTROL EDEN", "ONAY",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_html_contains_slip_values(self) -> None:
        for value in (
            "189,82", "76,19", "113,63", "AKSEKİ YAPI MENDERES(ALM.)",
            "ÖMER SİVRİ", "6612", "420 °C", "520 °C", "GÖRÜNTÜ BOZUK", "Z8",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.html)

    def test_tables_declare_width_attribute(self) -> None:
        """Qt zengin metin motoru CSS genişliğini yok sayar; öznitelik şart."""
        self.assertNotIn("<table class='grid'>", self.html)
        self.assertNotIn("<table class='head'>", self.html)
        self.assertEqual(self.html.count("width='100%'"), self.html.count("<table"))

    def test_font_sizes_use_points_not_pixels(self) -> None:
        """px, yazıcı çözünürlüğünde yorumlanıp çıktıyı okunmaz hâle getirir."""
        for source in (self.html, weighing_list_html({}, [])):
            with self.subTest(source=source[:40]):
                self.assertNotIn("px;", source.split("</style>")[0])

    def test_document_renders_to_multiple_pages_without_error(self) -> None:
        document = QTextDocument()
        document.setHtml(self.html)
        self.assertGreater(document.pageCount(), 0)
        self.assertGreater(document.size().width(), 0)


class PressProductionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )
        self.work_order_id = kur(self.service)
        context = self.service.press_entry_context(self.work_order_id)
        context["id"] = self.work_order_id
        self.dialog = PressProductionDialog(
            context, username="PRES", slip_no=self.service.peek_next_no("PF")
        )
        self.addCleanup(self.dialog.close)

    def _fill(self) -> None:
        self.dialog.billet_grid.set_rows(BILLETS)
        self.dialog.basket_grid.set_rows(BASKETS)
        self.dialog.scrap_grid.set_rows(SCRAPS)

    def test_totals_follow_the_breakdowns(self) -> None:
        self._fill()
        labels = self.dialog.total_labels
        self.assertEqual(labels["gross"].text(), "189,82")
        self.assertEqual(labels["net"].text(), "76,19")
        self.assertEqual(labels["quantity"].text(), "83")
        self.assertEqual(labels["scrap"].text(), "113,63")
        self.assertEqual(labels["fire_pct"].text(), "59,9")
        self.assertEqual(labels["remaining"].text(), "1.417")

    def test_real_weight_is_derived_from_output(self) -> None:
        self._fill()
        values = self.dialog.values()
        self.assertAlmostEqual(values["real_weight_kg_m"], 0.153, places=3)

    def test_duration_follows_start_and_end(self) -> None:
        self._fill()
        self.assertEqual(self.dialog.duration_min.text(), "30")

    def test_values_round_trip_into_the_service(self) -> None:
        self._fill()
        payload = self.dialog.values()
        entry_id = self.service.record_work_order_output(
            self.work_order_id,
            die_id=int(self.dialog.work_order["die_id"]),
            username="PRES",
            **payload,
        )
        document = self.service.press_slip_document(entry_id)
        self.assertAlmostEqual(
            float(document["header"]["gross_kg"]), 189.82, places=2
        )
        self.assertEqual(len(document["billets"]), 2)
        self.assertEqual(len(document["scraps"]), 2)

    def test_inconsistent_scrap_is_reported_on_screen(self) -> None:
        self.dialog.billet_grid.set_rows(BILLETS)
        self.dialog.basket_grid.set_rows(BASKETS)
        self.dialog.scrap_grid.set_rows([{"scrap_reason": "HURDA", "kg": 1.0}])
        self.assertIn("eşit olmalı", self.dialog.consistency.text())

    def test_editable_grid_appends_row_when_last_is_filled(self) -> None:
        grid = self.dialog.scrap_grid
        before = grid.rowCount()
        grid.setItem(before - 1, 0, self._item("HURDA"))
        self.assertEqual(grid.rowCount(), before + 1)

    @staticmethod
    def _item(text: str):
        from PySide6.QtWidgets import QTableWidgetItem

        return QTableWidgetItem(text)

    def test_blank_rows_are_dropped_from_values(self) -> None:
        self._fill()
        self.dialog.billet_grid.add_row()
        self.assertEqual(len(self.dialog.values()["billets"]), 2)


class PressWorkflowWiringTests(unittest.TestCase):
    """Üretim Girişi düğmesi pres iş emrinde yeni fiş ekranını açmalı."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QDialog, QMessageBox

        import ui.press_production_dialog as press_module
        from pages.workflow import WorkflowPage

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )
        kur(self.service)

        original_init = press_module.PressProductionDialog.__init__

        def filled_init(dialog, work_order, **kwargs):
            original_init(dialog, work_order, **kwargs)
            dialog.billet_grid.set_rows(BILLETS)
            dialog.basket_grid.set_rows(BASKETS)
            dialog.scrap_grid.set_rows(SCRAPS)

        press_module.PressProductionDialog.__init__ = filled_init
        press_module.PressProductionDialog.exec = lambda dialog: QDialog.Accepted
        self.addCleanup(
            setattr, press_module.PressProductionDialog, "__init__", original_init
        )
        for name in ("question", "warning", "information"):
            self.addCleanup(setattr, QMessageBox, name, getattr(QMessageBox, name))
        QMessageBox.question = lambda *a, **k: QMessageBox.No
        QMessageBox.warning = lambda *a, **k: QMessageBox.Ok
        QMessageBox.information = lambda *a, **k: QMessageBox.Ok

        self.page = WorkflowPage(username="operator", service=self.service)
        self.addCleanup(self.page.close)
        self.page.date_from.setDate(QDate(2026, 1, 1))
        self.page.date_to.setDate(QDate(2026, 12, 31))

    def _select_press_row(self) -> bool:
        self.page.set_context("Üretim", "İş Emirleri")
        for row in range(self.page.table.rowCount()):
            cells = [
                self.page.table.item(row, column).text()
                if self.page.table.item(row, column)
                else ""
                for column in range(self.page.table.columnCount())
            ]
            if any("PRES ÜRETİM" in cell for cell in cells):
                self.page.table.selectRow(row)
                return True
        return False

    def test_production_entry_button_creates_full_slip(self) -> None:
        self.assertTrue(self._select_press_row(), "Pres iş emri listede yok")
        self.page.run_primary()

        self.page.set_context("Üretim", "Üretim Fişleri")
        self.assertEqual(self.page.table.rowCount(), 1)
        record = self.page.records[0]
        self.assertTrue(record["slip_no"])
        self.assertAlmostEqual(float(record["gross_kg"]), GROSS, places=2)
        self.assertAlmostEqual(float(record["net_kg"]), NET, places=2)

        document = self.service.press_slip_document(int(record["id"]))
        self.assertEqual(len(document["billets"]), 2)
        self.assertEqual(len(document["baskets"]), 1)
        self.assertEqual(len(document["scraps"]), 2)

    def test_slip_number_is_the_first_column(self) -> None:
        self.assertTrue(self._select_press_row())
        self.page.run_primary()
        self.page.set_context("Üretim", "Üretim Fişleri")
        self.assertEqual(self.page.table.horizontalHeaderItem(0).text(), "FİŞ NO")
        self.assertTrue(self.page.table.item(0, 0).text().strip())

    def test_print_action_is_available_on_entries(self) -> None:
        from pages.workflow import WorkflowPage

        actions = {
            item["action"] for item in WorkflowPage.CONTEXT_MENUS["production_entries"]
        }
        self.assertIn("print_press_slip", actions)
        self.assertTrue(hasattr(self.page, "print_press_slip"))


if __name__ == "__main__":
    unittest.main()
