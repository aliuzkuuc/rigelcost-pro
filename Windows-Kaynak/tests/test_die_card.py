"""KALIP KART alt sekmeleri — veri, sütun ve filtre testleri.

Kart tek bir kalıp kimliği etrafında kurulur; testler her alt sekmenin
beklenen sütunlarla açıldığını, tarih aralığının pres sekmesini süzdüğünü ve
tenefer sekmesinin iki ayrı gridi kendi kayıt sayacıyla doldurduğunu doğrular.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.local_workflow import LocalWorkflowService
from ui.die_card_dialog import (
    MOVEMENT_COLUMNS,
    ORDER_LINE_COLUMNS,
    PRESS_COLUMNS,
    PROBLEM_COLUMNS,
    STOCK_MOVEMENT_COLUMNS,
    TENEFER_DEFINITION_COLUMNS,
    TENEFER_USAGE_COLUMNS,
    DieCardDialog,
    format_cell,
    format_number,
)


def _plain(labels: list[str]) -> list[str]:
    return [" ".join(label.split()) for label in labels]


class DieCardFixture(unittest.TestCase):
    """Sipariş → üretim → hareket zincirini kuran ortak kalıp kartı verisi."""

    PRESS_RUNS = 5
    TEST_RUNS = 1

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = LocalWorkflowService(Path(self.temp_dir.name) / "die_card.db")
        self.die_id = self._seed()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _seed(self) -> int:
        service = self.service
        customer_id = service.create_customer("M-1", "AKSEKİ YAPI A.Ş.", username="test")
        profile_id = service.create_profile(
            "1099", "YAN DÖKME 62", unit_weight_kg_m=0.501,
            customer_id=customer_id, username="test",
        )
        with service.connect() as connection:
            connection.execute(
                """
                UPDATE profiles
                SET profile_group = 'PANJUR', perimeter_mm = 262.40,
                    area_mm2 = 184.871
                WHERE id = ?
                """,
                (profile_id,),
            )
        die_id = service.create_die(
            profile_id, "1099", figure_count=2, tenefer_no="8",
            tenefer_type="KÖPRÜLÜ TAKIM", life_limit_kg=500_000,
            compatible_stations=["PRES 1", "PRES 2"],
            supplier_name="ÜSTÜNEL KALIP", username="test",
        )
        route_id = service.create_route(
            profile_id, "R-1", "Panjur rotası",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1",
                 "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1",
                 "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
            ],
            username="test", surface="PRES",
        )
        service.create_recipe(
            profile_id, route_id, "RC-1", "Panjur reçetesi",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1",
                 "numerator": 1, "denominator": 1, "stock_code": "AL-BILLET"},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1",
                 "numerator": 1, "denominator": 1},
            ],
            username="test", raw_material_stock_code="AL-BILLET",
        )
        total = self.PRESS_RUNS + self.TEST_RUNS
        for index in range(total):
            quantity = 100 + index * 10
            kg = 500 + index * 40
            order_id = service.create_sales_order(
                customer_id, order_date="2026-03-01", delivery_date="2026-04-01",
                lines=[{
                    "profile_id": profile_id, "die_id": die_id,
                    "length_mm": 6000, "quantity": quantity, "kg": kg,
                    "unit_price": 4.0,
                }],
                username="test",
            )
            service.approve_sales_order(order_id, username="test")
            line_id = service.order_progress(order_id)["lines"][0]["id"]
            production_id = service.plan_sales_order_line(
                line_id, planned_quantity=quantity, planned_kg=kg,
                route_id=route_id, username="test",
            )
            works = service.work_orders_for_production(production_id)
            is_test = index >= self.PRESS_RUNS
            service.record_work_order_output(
                works[0]["id"], quantity=quantity, gross_kg=kg * 1.05,
                net_kg=kg, metre=quantity * 6.0, die_id=die_id,
                shift=f"{index % 3 + 1}.VARDİYA",
                production_type="TEST" if is_test else "PLANLI ÜRETİM",
                die_problem="AKIŞ DENGESİZ" if index == 2 else "",
                die_problem_note="Akış dengesiz, kalıp kontrol edilsin"
                if index == 2 else "",
                username="operator",
            )
        return die_id

    def dialog(self) -> DieCardDialog:
        card = DieCardDialog(self.service, self.die_id, username="test")
        self.addCleanup(card.deleteLater)
        return card


class DieCardDataTests(DieCardFixture):
    def test_header_carries_profile_and_production_totals(self) -> None:
        header = self.service.die_card_header(self.die_id)
        self.assertEqual(header["profile_code"], "1099")
        self.assertEqual(header["profile_group"], "PANJUR")
        self.assertEqual(header["owner_customer_name"], "AKSEKİ YAPI A.Ş.")
        self.assertEqual(header["is_customer_specific"], 1)
        self.assertEqual(int(header["total_usage"]), self.PRESS_RUNS + self.TEST_RUNS)
        self.assertEqual(int(header["test_count"]), self.TEST_RUNS)
        # Tenefer 8 standart ömrü 4500 m; kullanım figür sayısıyla çarpılır.
        self.assertAlmostEqual(float(header["tenefer_limit_m"]), 4500.0)
        self.assertGreater(float(header["total_net_kg"]), 0)
        self.assertGreater(float(header["total_metre"]), 0)

    def test_press_entries_reach_order_and_customer(self) -> None:
        rows = self.service.list_die_press_entries(self.die_id)
        self.assertEqual(len(rows), self.PRESS_RUNS + self.TEST_RUNS)
        first = rows[0]
        for key in ("slip_no", "order_ref", "work_order_no", "customer_name", "station"):
            self.assertTrue(str(first[key]).strip(), f"{key} boş kalmamalı")
        self.assertEqual(first["customer_name"], "AKSEKİ YAPI A.Ş.")
        # Fiş durum yazmadıysa iş emri durumu gösterilir.
        self.assertTrue(str(first["press_status"]).strip())

    def test_press_entries_respect_date_range(self) -> None:
        inside = self.service.list_die_press_entries(
            self.die_id, date_from="2000-01-01", date_to="2100-12-31"
        )
        self.assertEqual(len(inside), self.PRESS_RUNS + self.TEST_RUNS)
        outside = self.service.list_die_press_entries(
            self.die_id, date_from="1999-01-01", date_to="1999-12-31"
        )
        self.assertEqual(outside, [])

    def test_test_entries_split_from_planned_entries(self) -> None:
        rows = self.service.list_die_press_entries(self.die_id)
        tests = [row for row in rows if self.service.is_test_press_entry(row)]
        planned = [row for row in rows if not self.service.is_test_press_entry(row)]
        self.assertEqual(len(tests), self.TEST_RUNS)
        self.assertEqual(len(planned), self.PRESS_RUNS)

    def test_tenefer_life_returns_definitions_and_usage(self) -> None:
        life = self.service.die_card_tenefer_life(self.die_id)
        self.assertGreater(len(life["definitions"]), 1)
        self.assertEqual(len(life["usage"]), 1)
        self.assertEqual(
            {row["operator_label"] for row in life["definitions"]}, {"EŞİTTİR"}
        )
        usage = life["usage"][0]
        self.assertEqual(usage["tenefer_no"], "8")
        self.assertAlmostEqual(
            usage["remaining_m"], usage["limit_m"] - usage["used_m"], places=3
        )

    def test_problems_merge_cards_and_press_reports(self) -> None:
        rows = self.service.list_die_problems(self.die_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "PRES FİŞİ")
        self.assertEqual(rows[0]["problem_type"], "AKIŞ DENGESİZ")
        self.assertTrue(rows[0]["slip_no"])

    def test_order_lines_and_stock_movements_bind_to_die(self) -> None:
        lines = self.service.list_die_order_lines(self.die_id)
        self.assertEqual(len(lines), self.PRESS_RUNS + self.TEST_RUNS)
        self.assertEqual({row["profile_code"] for row in lines}, {"1099"})
        movements = self.service.list_die_stock_movements(self.die_id)
        self.assertTrue(movements)
        self.assertEqual(
            {row["direction_label"] for row in movements} - {"GİRİŞ", "ÇIKIŞ"}, set()
        )

    def test_die_movements_accept_date_range(self) -> None:
        everything = self.service.list_die_movements(self.die_id)
        self.assertTrue(everything)
        empty = self.service.list_die_movements(
            self.die_id, date_from="1999-01-01", date_to="1999-12-31"
        )
        self.assertEqual(empty, [])


class DieCardDialogTests(DieCardFixture):
    def test_six_reference_sub_tabs_in_order(self) -> None:
        card = self.dialog()
        titles = [card.tabs.tabText(i) for i in range(card.tabs.count())]
        self.assertEqual(
            titles,
            [
                "KALIP BİLGİLERİ",
                "TENEFER BİLGİLERİ",
                "HAREKETLER",
                "PRES ÜRETİM BİLGİLERİ",
                "KALIBIN PROBLEMLERİ",
                "SİPARİŞ/STOK HAREKETLERİ",
            ],
        )
        self.assertEqual(
            [card.press_tabs.tabText(i) for i in range(card.press_tabs.count())],
            ["PRES ÜRETİM BİLGİLERİ", "TEST ÜRETİMLERİ"],
        )
        self.assertEqual(
            [card.order_tabs.tabText(i) for i in range(card.order_tabs.count())],
            ["SİPARİŞ HAREKETLERİ", "STOK HAREKETLERİ"],
        )

    def test_every_tab_loads_rows_with_expected_columns(self) -> None:
        card = self.dialog()
        expected = {
            "press": PRESS_COLUMNS,
            "press_test": PRESS_COLUMNS,
            "movements": MOVEMENT_COLUMNS,
            "problems": PROBLEM_COLUMNS,
            "orders": ORDER_LINE_COLUMNS,
            "stock_movements": STOCK_MOVEMENT_COLUMNS,
            "tenefer": TENEFER_DEFINITION_COLUMNS,
            "tenefer_usage": TENEFER_USAGE_COLUMNS,
        }
        for key, columns in expected.items():
            grid = card.grids[key]
            with self.subTest(tab=key):
                self.assertEqual(grid.column_keys(), [c[0] for c in columns])
                self.assertEqual(grid.column_labels(), [c[1] for c in columns])
                self.assertEqual(grid.table.columnCount(), len(columns))
                self.assertGreater(grid.row_count(), 0, f"{key} sekmesi boş kaldı")
                self.assertEqual(grid.table.rowCount(), grid.row_count())

    def test_press_reference_columns_present(self) -> None:
        card = self.dialog()
        labels = _plain(card.grids["press"].column_labels())
        for expected in (
            "FİŞ NO", "ÜRETİM TİPİ", "PRES DURUM", "TESTERE DURUM", "İSTASYON",
            "OPERATÖR", "VARDİYA", "SİPARİŞ REF", "İŞ EMRİ NO", "MÜŞTERİ",
        ):
            self.assertIn(expected, labels)
        self.assertEqual(labels[:10], [
            "FİŞ NO", "ÜRETİM TİPİ", "PRES DURUM", "TESTERE DURUM", "İSTASYON",
            "OPERATÖR", "VARDİYA", "SİPARİŞ REF", "İŞ EMRİ NO", "MÜŞTERİ",
        ])

    def test_each_grid_has_group_hint_filter_row_and_row_counter(self) -> None:
        card = self.dialog()
        grid = card.grids["press"]
        self.assertIsNotNone(grid.group_bar)
        self.assertEqual(
            len(grid.filter_bar._editors), len(grid.column_keys()),
            "her sütun için bir filtre hücresi olmalı",
        )
        self.assertEqual(
            {editor.text() for editor in grid.filter_bar._editors}, {"="}
        )
        self.assertEqual(grid.footer.text(), format_number(self.PRESS_RUNS, 0))

    def test_press_tab_splits_test_productions(self) -> None:
        card = self.dialog()
        self.assertEqual(card.grids["press"].row_count(), self.PRESS_RUNS)
        self.assertEqual(card.grids["press_test"].row_count(), self.TEST_RUNS)
        self.assertEqual(
            {row["production_type"] for row in card.grids["press_test"].visible_rows()},
            {"TEST"},
        )

    def test_tenefer_tab_has_two_grids_with_own_counters(self) -> None:
        card = self.dialog()
        definitions = card.grids["tenefer"]
        usage = card.grids["tenefer_usage"]
        self.assertGreater(definitions.row_count(), 1)
        self.assertEqual(usage.row_count(), 1)
        self.assertNotEqual(definitions.footer.text(), usage.footer.text())
        self.assertEqual(usage.footer.text(), "1")
        self.assertEqual(
            _plain(definitions.column_labels()),
            ["TENEFER NO", "OPERATÖR", "ÖMÜR METRE"],
        )
        self.assertEqual(
            _plain(usage.column_labels()),
            ["TENEFER NO", "ÖMÜR M", "KULLANIM M", "KALAN M"],
        )

    def test_footer_date_range_filters_press_tab(self) -> None:
        from PySide6.QtCore import QDate

        card = self.dialog()
        self.assertEqual(card.grids["press"].row_count(), self.PRESS_RUNS)
        card.date_from.setDate(QDate(1999, 1, 1))
        card.date_to.setDate(QDate(1999, 12, 31))
        self.assertEqual(card.grids["press"].row_count(), 0)
        self.assertEqual(card.grids["press"].footer.text(), "0")
        self.assertEqual(card.grids["movements"].row_count(), 0)
        card.quick_range.setCurrentIndex(
            [card.quick_range.itemData(i) for i in range(card.quick_range.count())]
            .index("all")
        )
        self.assertEqual(card.grids["press"].row_count(), self.PRESS_RUNS)

    def test_column_filter_narrows_rows_and_row_counter(self) -> None:
        card = self.dialog()
        grid = card.grids["press"]
        total = grid.row_count()
        grid.filter_bar.set_column_filter("shift", values={"1.VARDİYA"})
        self.assertLess(grid.row_count(), total)
        self.assertTrue(
            all(row["shift"] == "1.VARDİYA" for row in grid.visible_rows())
        )
        self.assertEqual(
            grid.footer.text(),
            f"{format_number(grid.row_count(), 0)} / {format_number(total, 0)}",
        )
        grid.filter_bar.clear_filters()
        self.assertEqual(grid.row_count(), total)

    def test_grid_search_box_filters_rows(self) -> None:
        card = self.dialog()
        grid = card.grids["press"]
        grid.search.setText("BULUNMAYAN-DEĞER")
        self.assertEqual(grid.row_count(), 0)
        grid.search.setText("AKSEKİ")
        self.assertEqual(grid.row_count(), self.PRESS_RUNS)

    def test_die_info_tab_lists_siblings_stations_and_documents(self) -> None:
        card = self.dialog()
        self.assertEqual(card.grids["die_info"].row_count(), 1)
        self.assertEqual(
            {row["station_code"] for row in card.grids["die_stations"].visible_rows()},
            {"PRES_1", "PRES_2"},
        )
        self.assertEqual(card.grids["die_documents"].row_count(), 0)

    def test_attachment_shows_in_documents_grid(self) -> None:
        path = Path(self.temp_dir.name) / "kalip.pdf"
        path.write_bytes(b"%PDF-1.4 test")
        self.service.add_attachment(
            entity_type="DIE",
            entity_id=self.die_id,
            document_type="TEKNİK RESİM",
            file_path=str(path),
            username="test",
        )
        card = self.dialog()
        rows = card.grids["die_documents"].visible_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_name"], "kalip.pdf")

    def test_save_persists_editable_fields_without_touching_history(self) -> None:
        card = self.dialog()
        before = len(self.service.list_die_press_entries(self.die_id))
        card.figure_count.setValue(3)
        card.location_edit.setText("A-12")
        card.supplier_edit.setText("YENİ TEDARİKÇİ")
        card.accept()
        die = self.service.die(self.die_id)
        self.assertEqual(int(die["figure_count"]), 3)
        self.assertEqual(die["location"], "A-12")
        self.assertEqual(die["supplier_name"], "YENİ TEDARİKÇİ")
        self.assertEqual(
            len(self.service.list_die_press_entries(self.die_id)), before
        )

    def test_read_only_user_cannot_edit_or_save(self) -> None:
        card = DieCardDialog(
            self.service, self.die_id, username="test", can_edit=False
        )
        self.addCleanup(card.deleteLater)
        self.assertFalse(card.save_button.isEnabled())
        self.assertFalse(card.figure_count.isEnabled())
        self.assertGreater(card.grids["press"].row_count(), 0)

    def test_printable_rows_follow_active_tab(self) -> None:
        card = self.dialog()
        card.tabs.setCurrentIndex(3)
        card.press_tabs.setCurrentIndex(0)
        self.assertEqual(len(card.printable_rows()), self.PRESS_RUNS)
        card.press_tabs.setCurrentIndex(1)
        self.assertEqual(len(card.printable_rows()), self.TEST_RUNS)
        card.tabs.setCurrentIndex(5)
        card.order_tabs.setCurrentIndex(0)
        self.assertEqual(
            len(card.printable_rows()), self.PRESS_RUNS + self.TEST_RUNS
        )

    def test_filter_row_stays_between_header_and_data(self) -> None:
        card = self.dialog()
        card.tabs.setCurrentIndex(3)
        card.show()
        self.app.processEvents()
        table = card.grids["press"].table
        header = table.horizontalHeader()
        bar = table.filter_bar
        self.assertEqual(header.y() + header.height(), bar.y())
        self.assertLessEqual(bar.y() + bar.height(), table.viewport().y())
        card.hide()


class DieCardFormattingTests(unittest.TestCase):
    def test_turkish_number_and_date_formatting(self) -> None:
        self.assertEqual(format_number(31791.9, 2), "31.791,90")
        self.assertEqual(format_cell("int", 28), "28")
        self.assertEqual(format_cell("num1", 5529.24), "5.529,2")
        self.assertEqual(format_cell("date", "2026-05-31"), "31.05.2026")
        self.assertEqual(
            format_cell("datetime", "2026-05-31T09:23:11"), "31.05.2026 09:23"
        )
        self.assertEqual(format_cell("text", None), "")


if __name__ == "__main__":
    unittest.main()
