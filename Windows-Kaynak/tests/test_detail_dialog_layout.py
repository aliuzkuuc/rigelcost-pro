"""Detay fişi düzeni — üst form, sağ miktar paneli ve alt sekme ızgaraları."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from pages.workflow import WorkflowPage
from scripts.audit_all_modules import seed
from services.local_workflow import LocalWorkflowService
from ui.record_details_dialog import DetailGrid, RecordDetailsDialog


def _labels(dialog: RecordDetailsDialog, object_name: str) -> list[str]:
    return [
        widget.text()
        for widget in dialog.findChildren(QLabel)
        if widget.objectName() == object_name
    ]


def _tab_titles(dialog: RecordDetailsDialog) -> list[str]:
    return [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]


class VoucherLayoutTests(unittest.TestCase):
    """Genel detay penceresi fabrika ERP fişi gibi kurulmalı."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self) -> RecordDetailsDialog:
        return RecordDetailsDialog(
            "Üretim Emri",
            fields=[
                ("FİŞ NO", "UE260000002"),
                ("SİPARİŞ", "R260000002-1"),
                ("STOK KOD", "PRF-ELX"),
            ],
            tables=[
                {
                    "title": "İş Emirleri",
                    "headers": ["FİŞ NO", "OPERASYON", "PLAN ADET", "PLAN KG"],
                    "rows": [
                        ["00000004", "PRES ÜRETİM", "100", "500,00"],
                        ["00000005", "ELOKSAL", "100", "500,00"],
                    ],
                },
                {
                    "title": "Reçete",
                    "pinned": True,
                    "headers": ["İŞLEM TİPİ", "STOK KOD", "KG"],
                    "rows": [["GİRDİ", "AL-BILLET", "520,00"]],
                },
                {"title": "Kalıplar", "headers": ["KALIP KOD", "DURUM"], "rows": []},
            ],
            stats=[["SİPARİŞ", "100", "500,00"], ["ÜRETİM", "0", "0,00"]],
            stats_headers=("DURUM", "ADET", "KG"),
            subtitle="AKSEKİ YAPI",
            status="planlandı",
        )

    def test_header_form_status_and_footer(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(_labels(dialog, "detailsHeading"), ["ÜRETİM EMRİ"])
        self.assertEqual(_labels(dialog, "detailsStatus"), ["PLANLANDI"])
        self.assertIn("AKSEKİ YAPI", _labels(dialog, "detailsSubtitle"))
        self.assertEqual(
            _labels(dialog, "detailsKey"), ["FİŞ NO", "SİPARİŞ", "STOK KOD"]
        )
        self.assertEqual(
            _labels(dialog, "detailsValue"),
            ["UE260000002", "R260000002-1", "PRF-ELX"],
        )
        buttons = [
            button.text()
            for button in dialog.findChildren(QPushButton)
            if button.objectName() == "detailsClose"
        ]
        self.assertEqual(buttons, ["KAPAT"])

    def test_quantity_panel_renders_rows(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        table = dialog.stats_table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.columnCount(), 3)
        self.assertEqual(
            [table.horizontalHeaderItem(i).text() for i in range(3)],
            ["DURUM", "ADET", "KG"],
        )
        self.assertEqual(table.item(0, 0).text(), "SİPARİŞ")
        self.assertEqual(table.item(0, 2).text(), "500,00")

    def test_tables_become_subtabs_with_row_counts(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        # Sabitlenen reçete ızgarası sekme değil, altta ayrı bölmededir.
        self.assertEqual(_tab_titles(dialog), ["İŞ EMİRLERİ  (2)", "KALIPLAR  (0)"])
        self.assertEqual([grid.grid_title for grid in dialog.pinned_grids], ["Reçete"])
        self.assertEqual(len(dialog.grids), 3)

    def test_every_grid_has_filter_row_and_counter(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        for grid in dialog.grids:
            with self.subTest(grid=grid.grid_title):
                columns = grid.table.columnCount()
                self.assertGreater(columns, 0)
                self.assertTrue(grid.filter_bar.isVisible() or not dialog.isVisible())
                for index in range(columns):
                    self.assertIsNotNone(grid.filter_bar.editor_for(f"c{index}"))
                self.assertIsNone(grid.filter_bar.editor_for(f"c{columns}"))
                self.assertEqual(grid.count_label.text(), f"{grid.row_count()} satır")

    def test_empty_grid_keeps_headers(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        empty = next(grid for grid in dialog.grids if grid.grid_title == "Kalıplar")
        self.assertEqual(empty.row_count(), 0)
        self.assertEqual(empty.table.columnCount(), 2)
        self.assertEqual(empty.table.horizontalHeaderItem(0).text(), "KALIP KOD")

    def test_column_filter_hides_rows_and_updates_counter(self) -> None:
        dialog = self._dialog()
        self.addCleanup(dialog.deleteLater)

        grid = dialog.grids[0]
        grid.filter_bar.set_column_filter("c1", values={"PRES ÜRETİM"})
        self.assertEqual(grid.visible_row_count(), 1)
        self.assertEqual(grid.count_label.text(), "1 / 2 satır")

        grid.filter_bar.clear_filters()
        self.assertEqual(grid.visible_row_count(), 2)
        self.assertEqual(grid.count_label.text(), "2 satır")

    def test_totals_strip_sums_only_quantity_columns(self) -> None:
        grid = DetailGrid(
            ["SIRA", "PLAN ADET", "PLAN KG", "BOY"],
            [[1, "100", "500,00", "6.000"], [2, "100", "500,00", "6.000"]],
            title="İş Emirleri",
        )
        self.addCleanup(grid.deleteLater)

        totals = grid.totals_label.text()
        self.assertIn("PLAN ADET: 200", totals)
        self.assertIn("PLAN KG: 1.000", totals)
        self.assertNotIn("SIRA", totals)
        self.assertNotIn("BOY", totals)


class ModuleVoucherTests(unittest.TestCase):
    """Üretim emri, satış siparişi ve iş emri detayları fiş düzenini kullanmalı."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.service = LocalWorkflowService(
            Path(cls.temp_dir.name) / "rigel_operations.db"
        )
        seed(cls.service, [])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self._captured: dict[str, RecordDetailsDialog] = {}
        self._original_exec = RecordDetailsDialog.exec

        def fake_exec(dialog_self) -> int:
            self._captured["last"] = dialog_self
            return 0

        RecordDetailsDialog.exec = fake_exec  # type: ignore[method-assign]
        self.page = WorkflowPage(username="patron", service=self.service)

    def tearDown(self) -> None:
        RecordDetailsDialog.exec = self._original_exec  # type: ignore[method-assign]
        self.page.close()

    def _open(self, department: str, module: str) -> RecordDetailsDialog:
        self.page.set_context(department, module)
        self.assertGreater(
            self.page.table.rowCount(), 0, f"{department}/{module}: kayıt yok"
        )
        self.page.table.selectRow(0)
        self.page.show_record_details()
        dialog = self._captured.get("last")
        self.assertIsNotNone(dialog, f"{department}/{module}: detay açılmadı")
        assert dialog is not None
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_production_order_uses_reference_voucher(self) -> None:
        dialog = self._open("Üretim", "Üretim Emirleri")

        titles = _tab_titles(dialog)
        for expected in (
            "İŞ EMİRLERİ", "SİPARİŞ BİLGİLERİ", "TÜM SİPARİŞLER", "KALIPLAR", "STOKLAR"
        ):
            self.assertTrue(
                any(title.startswith(expected) for title in titles),
                f"{expected} alt sekmesi yok: {titles}",
            )
        self.assertEqual([grid.grid_title for grid in dialog.pinned_grids], ["Reçete"])

        keys = _labels(dialog, "detailsKey")
        for expected in (
            "FİŞ NO", "TARİH", "SİPARİŞ", "STOK KOD", "STOK AD", "REÇETE",
            "ROTA", "HAMMADDE", "MİKTAR", "ÜRETİM BOY", "TESTERE PAYI",
        ):
            self.assertIn(expected, keys)

        stat_labels = [row[0] for row in dialog.stat_rows]
        self.assertEqual(stat_labels[1:4], ["STOK", "PRES STOK", "SİPARİŞ"])
        self.assertTrue(stat_labels[0].endswith("UYGUN"), stat_labels[0])
        for expected in ("PLAN", "İŞ EMRİ", "ÜRETİM", "HURDA", "KALAN"):
            self.assertIn(expected, stat_labels)

        work_orders = next(
            grid for grid in dialog.grids if grid.grid_title == "İş Emirleri"
        )
        self.assertGreater(work_orders.row_count(), 0)
        headers = [
            work_orders.table.horizontalHeaderItem(index).text()
            for index in range(work_orders.table.columnCount())
        ]
        for expected in ("FİŞ NO", "OPERASYON", "İSTASYON", "PLAN KG", "DURUM"):
            self.assertIn(expected, headers)

    def test_sales_order_detail_has_line_production_and_package_tabs(self) -> None:
        dialog = self._open("Satış", "Satış Siparişleri")

        titles = _tab_titles(dialog)
        for expected in ("SİPARİŞ SATIRLARI", "ÜRETİM EMİRLERİ", "PAKETLER"):
            self.assertTrue(
                any(title.startswith(expected) for title in titles),
                f"{expected} alt sekmesi yok: {titles}",
            )
        lines = next(
            grid for grid in dialog.grids if grid.grid_title == "Sipariş Satırları"
        )
        self.assertGreater(lines.row_count(), 0)
        self.assertIn("SİPARİŞ", [row[0] for row in dialog.stat_rows])

    def test_work_order_detail_lists_entries_movements_and_route(self) -> None:
        dialog = self._open("Üretim", "İş Emirleri")

        self.assertEqual(
            [grid.grid_title for grid in dialog.grids],
            ["Üretim Fişleri", "Ambar Hareketleri", "Rota Adımları"],
        )
        route = dialog.grids[2]
        self.assertGreater(route.row_count(), 0)

    def test_every_module_detail_grid_has_filter_row(self) -> None:
        checked = 0
        for department, module in sorted(WorkflowPage.CONTEXT_VIEW):
            self.page.set_context(department, module)
            if self.page.table.rowCount() == 0:
                continue
            with self.subTest(department=department, module=module):
                self.page.table.selectRow(0)
                self._captured.pop("last", None)
                self.page.show_record_details()
                dialog = self._captured.get("last")
                assert dialog is not None
                for grid in dialog.grids:
                    columns = grid.table.columnCount()
                    self.assertGreater(
                        columns, 0, f"{module}/{grid.grid_title}: sütunsuz ızgara"
                    )
                    self.assertIsNotNone(
                        grid.filter_bar.editor_for(f"c{columns - 1}"),
                        f"{module}/{grid.grid_title}: filtre satırı eksik",
                    )
                    self.assertEqual(
                        grid.table.verticalHeader().defaultSectionSize(),
                        22,
                        f"{module}/{grid.grid_title}: satır yoğunluğu bozuk",
                    )
                dialog.deleteLater()
                checked += 1
        self.assertGreaterEqual(checked, 70, "Denetlenen sekme sayısı düşük")


if __name__ == "__main__":
    unittest.main()
