from __future__ import annotations

import os
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TEST_DATA_DIR = tempfile.TemporaryDirectory()
os.environ["RIGELCOST_DATA_DIR"] = _TEST_DATA_DIR.name

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QMessageBox,
    QScrollArea,
    QTableWidgetItem,
)

from main import MainWindow, apply_rigel_flat_theme, apply_rigel_typography


class UiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.corporate_font = apply_rigel_typography(cls.app)
        apply_rigel_flat_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        _TEST_DATA_DIR.cleanup()

    def setUp(self) -> None:
        data_file = Path(_TEST_DATA_DIR.name) / "expense_details.json"
        data_file.unlink(missing_ok=True)
        production_file = Path(_TEST_DATA_DIR.name) / "production_dashboard.json"
        production_file.unlink(missing_ok=True)

    @staticmethod
    def set_cell(table, row: int, column: int, value: object) -> None:
        table.setItem(row, column, QTableWidgetItem(str(value)))

    def test_packaging_detail_total_reaches_home_page(self) -> None:
        window = MainWindow()
        automatic_total = (
            window.expense_details_page.pallet_panel.last_result["toplam"]
        )
        table = window.expense_details_page.packaging_table.table
        self.set_cell(table, 0, 0, "Streç")
        self.set_cell(table, 0, 1, "Tedarikçi")
        self.set_cell(table, 0, 3, "80000")
        self.assertAlmostEqual(
            window.home_page.ambalaj.value(),
            automatic_total + 80_000,
            places=2,
        )

        window.home_page.uretim.setValue(300_000)
        updated_automatic_total = (
            window.expense_details_page.pallet_panel.last_result["toplam"]
        )
        self.assertAlmostEqual(
            window.home_page.ambalaj.value(),
            updated_automatic_total + 80_000,
            places=2,
        )
        self.assertGreater(updated_automatic_total, automatic_total)
        window.close()

    def test_corporate_typography_is_applied_to_the_whole_application(self) -> None:
        window = MainWindow()

        self.assertEqual(self.app.font().family(), self.corporate_font)
        self.assertEqual(
            self.app.property("rigelCorporateFont"),
            self.corporate_font,
        )
        self.assertGreaterEqual(self.app.font().pointSizeF(), 11.0)
        self.assertLessEqual(self.app.font().pointSizeF(), 12.5)
        self.assertEqual(window.home_page.font().family(), self.corporate_font)
        self.assertEqual(
            window.expense_details_page.font().family(),
            self.corporate_font,
        )
        self.assertEqual(
            window.workflow_page.font().family(),
            self.corporate_font,
        )
        self.assertIn("font-family", self.app.styleSheet().casefold())
        self.assertNotIn("consolas", self.app.styleSheet().casefold())
        window.close()

    def test_meal_day_and_night_total_reaches_home(self) -> None:
        window = MainWindow()
        table = window.expense_details_page.meal_table.table
        self.set_cell(table, 0, 1, 26)
        self.set_cell(table, 0, 2, 22)
        self.set_cell(table, 0, 3, 160)
        self.set_cell(table, 1, 1, 6)
        self.set_cell(table, 1, 2, 20)
        self.set_cell(table, 1, 3, 350)

        self.assertAlmostEqual(window.home_page.yemek.value(), 133_520)
        window.close()

    def test_legacy_meal_rows_are_migrated_with_one_day(self) -> None:
        data_file = Path(_TEST_DATA_DIR.name) / "expense_details.json"
        data_file.write_text(
            json.dumps(
                {
                    "rent": 0,
                    "tables": {
                        "yemek": [["Gündüz", "10", "20", "200"]]
                    },
                    "fire": {},
                }
            ),
            encoding="utf-8",
        )

        window = MainWindow()

        self.assertEqual(
            window.expense_details_page.meal_table.table.columnCount(),
            8,
        )
        self.assertAlmostEqual(window.home_page.yemek.value(), 200)
        window.close()

    def test_electricity_unit_price_flows_from_detail_tab(self) -> None:
        window = MainWindow()
        table = window.expense_details_page.electricity_table.table
        self.set_cell(table, 0, 1, "2,40")
        self.set_cell(table, 0, 2, "0,30")
        self.set_cell(table, 0, 3, "0,24")
        self.set_cell(table, 0, 5, "1")
        expected = 2.94 * 1.01
        self.assertAlmostEqual(window.home_page.elektrik.value(), expected, places=3)
        window.close()

    def test_general_expense_uses_tutar_without_double_counting(self) -> None:
        window = MainWindow()
        table = window.expense_details_page.general_table.table
        self.set_cell(table, 0, 1, "77.777,50")
        self.set_cell(table, 0, 2, 10)
        self.set_cell(table, 0, 3, 20_000)

        self.assertAlmostEqual(
            window.home_page.genel_gider.value(),
            77_777.50,
        )
        window.close()

    def test_application_starts_on_dashboard_not_cost_page(self) -> None:
        window = MainWindow()

        self.assertEqual(window.stack.currentWidget(), window.dashboard_page)
        self.assertTrue(window.dashboard_nav_button.isChecked())
        window.close()

    def test_home_calculation_enables_exports(self) -> None:
        window = MainWindow()
        window.home_page.hesapla()

        self.assertTrue(window.home_page.excel_button.isEnabled())
        self.assertTrue(window.home_page.pdf_button.isEnabled())
        self.assertIsNotNone(window.home_page.last_report_data)
        self.assertEqual(window.home_page.cost_table.rowCount(), 15)
        window.close()

    def test_net_production_change_recalculates_costs_live(self) -> None:
        window = MainWindow()
        window.home_page.iscilik.setValue(1_000_000)
        window.expense_details_page.rent.setValue(250_000)
        window.home_page.hesapla()
        base = window.home_page.last_result

        window.home_page.uretim.setValue(300_000)
        updated = window.home_page.last_result

        self.assertAlmostEqual(
            updated["elektrik_tuketim"],
            base["elektrik_tuketim"] * 1.5,
        )
        self.assertAlmostEqual(updated["iscilik"], 1_000_000)
        self.assertAlmostEqual(updated["kira"], 250_000)
        self.assertAlmostEqual(
            updated["fire_toplam"],
            base["fire_toplam"] * 1.5,
        )
        self.assertEqual(
            window.home_page.production_value.text(),
            "300.000 kg",
        )
        window.close()

    def test_inventory_navigation_opens_relational_stock_cards(self) -> None:
        window = MainWindow()
        window.workflow_page.service.create_stock_item(
            "BLT-TEST",
            "Test billet",
            stock_group="BILLET",
            unit="KG",
            tracks_lot=False,
            username="depo",
        )
        window.inventory_nav_button.click()

        self.assertEqual(window.stack.currentWidget(), window.workflow_page)
        self.assertTrue(window.inventory_nav_button.isChecked())
        self.assertEqual(window.workflow_page.module_label.text(), "Stok Kartları")
        self.assertGreaterEqual(window.workflow_page.table.rowCount(), 1)
        window.close()

    def test_dashboard_expense_navigation_opens_detail_page(self) -> None:
        window = MainWindow()
        window.dashboard_page.open_expenses_requested.emit()

        self.assertEqual(
            window.stack.currentWidget(),
            window.expense_details_page,
        )
        window.close()

    def test_dashboard_pallet_navigation_opens_pallet_tab(self) -> None:
        window = MainWindow()
        window.dashboard_page.open_pallet_requested.emit()

        self.assertEqual(
            window.stack.currentWidget(),
            window.expense_details_page,
        )
        self.assertEqual(
            window.expense_details_page.tabs.tabText(
                window.expense_details_page.tabs.currentIndex()
            ),
            "Palet Hesabı",
        )
        window.close()

    def test_dashboard_stock_movement_opens_relational_stock_movements(self) -> None:
        window = MainWindow()
        window.dashboard_page.open_stock_movement_requested.emit()

        self.assertEqual(window.stack.currentWidget(), window.workflow_page)
        self.assertEqual(window.workflow_page.module_label.text(), "Stok Hareketleri")
        window.close()

    def test_exit_button_asks_for_confirmation(self) -> None:
        window = MainWindow()

        with (
            patch(
                "main.ExitConfirmDialog.confirm",
                return_value=False,
            ),
            patch.object(window, "close") as close,
        ):
            window.confirm_exit()
            close.assert_not_called()

        with (
            patch(
                "main.ExitConfirmDialog.confirm",
                return_value=True,
            ),
            patch.object(window, "close") as close,
        ):
            window.confirm_exit()
            close.assert_called_once_with()
        window.close()

    def test_dashboard_reflows_when_window_is_narrow(self) -> None:
        window = MainWindow()
        dashboard = window.dashboard_page

        dashboard.apply_responsive_layout(
            force=True,
            available_width=800,
        )
        self.assertTrue(dashboard._compact_layout)

        dashboard.apply_responsive_layout(
            force=True,
            available_width=1400,
        )
        self.assertFalse(dashboard._compact_layout)
        window.close()

    def test_mouse_wheel_cannot_change_input_values(self) -> None:
        window = MainWindow()
        window.resize(1_120, 720)
        window.show_page(1)
        window.show()
        self.app.processEvents()
        page = window.expense_details_page
        spinboxes = [
            window.home_page.elektrik_kwh_ton,
            page.rent,
            page.pallet_panel.wood_price,
        ]

        for spinbox in spinboxes:
            before = spinbox.value()
            spinbox.setFocus()
            event = QWheelEvent(
                QPointF(4, 4),
                QPointF(4, 4),
                QPoint(),
                QPoint(0, 120),
                Qt.NoButton,
                Qt.NoModifier,
                Qt.ScrollUpdate,
                False,
            )
            QApplication.sendEvent(spinbox, event)
            self.assertEqual(spinbox.value(), before)

        combo = page.packaging_table.table.cellWidget(0, 2)
        self.assertIsInstance(combo, QComboBox)
        combo_before = combo.currentIndex()
        combo.setFocus()
        combo_event = QWheelEvent(
            QPointF(4, 4),
            QPointF(4, 4),
            QPoint(),
            QPoint(0, 120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(combo, combo_event)
        self.assertEqual(combo.currentIndex(), combo_before)

        scroll = window.home_page.findChild(QScrollArea)
        self.assertIsNotNone(scroll)
        scroll.verticalScrollBar().setValue(0)
        scroll_event = QWheelEvent(
            QPointF(4, 4),
            QPointF(4, 4),
            QPoint(),
            QPoint(0, -120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(
            window.home_page.elektrik_kwh_ton,
            scroll_event,
        )
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        window.close()

    def test_die_cost_is_quantity_times_unit_price(self) -> None:
        window = MainWindow()
        table = window.expense_details_page.die_table.table
        self.set_cell(table, 0, 0, "Kalıpçı")
        self.set_cell(table, 0, 1, "KLP-01")
        self.set_cell(table, 0, 2, 3)
        self.set_cell(table, 0, 3, 25_000)

        self.assertAlmostEqual(window.home_page.kalip.value(), 75_000)
        self.assertEqual(table.horizontalHeaderItem(3).text(), "Birim Fiyat")
        window.close()

    def test_workflow_cost_is_quantity_times_unit_price_and_rate(self) -> None:
        window = MainWindow()
        page = window.expense_details_page
        page.set_market_values(usd=50, eur=55, lme=3_200)
        table = page.workflow_table.table
        self.set_cell(table, 0, 0, "KOSTİK")
        self.set_cell(table, 0, 1, "KORUMA")
        self.set_cell(table, 0, 2, 1_250)
        self.set_cell(table, 0, 3, 1_000)
        currency = table.cellWidget(0, 4)
        self.assertIsInstance(currency, QComboBox)
        currency.setCurrentText("USD")

        self.assertEqual(table.horizontalHeaderItem(3).text(), "Birim Fiyat")
        self.assertAlmostEqual(page.workflow_table.last_total, 62_500_000)
        self.assertAlmostEqual(window.home_page.sarf.value(), 62_500_000)
        window.close()

    def test_eur_expense_uses_current_rate_and_recalculates_on_refresh(self) -> None:
        window = MainWindow()
        page = window.expense_details_page
        page.set_market_values(usd=50, eur=55, lme=3_200)
        table = page.die_table.table
        self.set_cell(table, 0, 0, "ALUPORT")
        self.set_cell(table, 0, 1, "KÖPRÜLÜ")
        self.set_cell(table, 0, 2, 5)
        self.set_cell(table, 0, 3, 560)
        currency = table.cellWidget(0, 4)
        self.assertIsInstance(currency, QComboBox)
        currency.setCurrentText("EUR")

        self.assertAlmostEqual(window.home_page.kalip.value(), 154_000)
        self.assertEqual(table.item(0, 5).text(), "55,0000")

        page.set_market_values(eur=56)
        self.assertAlmostEqual(window.home_page.kalip.value(), 156_800)
        self.assertEqual(table.item(0, 5).text(), "56,0000")
        window.close()

    def test_all_manual_expense_tables_have_currency_and_rate_columns(self) -> None:
        window = MainWindow()
        for detail in window.expense_details_page.detail_tables.values():
            table = detail.table
            self.assertIsNotNone(detail.currency_column)
            self.assertIsNotNone(detail.rate_column)
            self.assertEqual(
                table.horizontalHeaderItem(detail.currency_column).text(),
                "Döviz",
            )
            self.assertEqual(
                table.horizontalHeaderItem(detail.rate_column).text(),
                "Kur",
            )
            currency = table.cellWidget(0, detail.currency_column)
            self.assertIsInstance(currency, QComboBox)
            self.assertGreaterEqual(currency.findText("TL"), 0)
            self.assertGreaterEqual(currency.findText("USD"), 0)
            self.assertGreaterEqual(currency.findText("EUR"), 0)
        window.close()

    def test_rent_can_be_entered_in_usd(self) -> None:
        window = MainWindow()
        page = window.expense_details_page
        page.set_market_values(usd=50, eur=55)
        page.rent.setValue(10_000)
        page.rent_currency.setCurrentText("USD")

        self.assertAlmostEqual(window.home_page.kira.value(), 500_000)
        self.assertAlmostEqual(page.rent_total_tl.value(), 500_000)
        window.close()

    def test_legacy_die_total_is_preserved_during_migration(self) -> None:
        data_file = Path(_TEST_DATA_DIR.name) / "expense_details.json"
        data_file.write_text(
            json.dumps(
                {
                    "rent": 0,
                    "tables": {
                        "kalip": [
                            [
                                "Kalıpçı",
                                "KLP-ESKİ",
                                "2",
                                "100.000",
                                "100.000,00",
                            ]
                        ]
                    },
                    "fire": {},
                }
            ),
            encoding="utf-8",
        )

        window = MainWindow()
        table = window.expense_details_page.die_table.table

        self.assertAlmostEqual(window.home_page.kalip.value(), 100_000)
        self.assertAlmostEqual(
            float(table.item(0, 3).text().replace(".", "").replace(",", ".")),
            50_000,
        )
        window.close()

    def test_all_expense_tables_have_note_field(self) -> None:
        window = MainWindow()

        for table in window.expense_details_page.detail_tables.values():
            widget = table.table
            self.assertEqual(
                widget.horizontalHeaderItem(
                    widget.columnCount() - 1
                ).text(),
                "Not",
            )
        self.assertIsNotNone(window.expense_details_page.rent_note)
        self.assertEqual(
            window.expense_details_page.fire_table.horizontalHeaderItem(
                window.expense_details_page.fire_table.columnCount() - 1
            ).text(),
            "Not",
        )
        window.close()

    def test_packaging_units_include_metre(self) -> None:
        window = MainWindow()
        combo = window.expense_details_page.packaging_table.table.cellWidget(
            0, 2
        )

        self.assertIsInstance(combo, QComboBox)
        self.assertGreaterEqual(combo.findText("METRE"), 0)
        window.close()

    def test_pallet_calculation_is_linked_to_packaging_and_home(self) -> None:
        window = MainWindow()
        page = window.expense_details_page
        result = page.pallet_panel.last_result

        self.assertEqual(result["palet_adedi"], 308)
        self.assertAlmostEqual(result["kereste"], 77_874.72)
        self.assertAlmostEqual(result["kosebent"], 7_546)
        self.assertAlmostEqual(result["cember"], 8_624)
        self.assertEqual(result["strec_adedi"], 168)
        self.assertAlmostEqual(
            window.home_page.ambalaj.value(),
            result["toplam"],
            places=2,
        )
        self.assertEqual(
            page.packaging_auto_table.item(0, 0).text(),
            "Kereste",
        )
        window.close()

    def test_pallet_navigation_opens_pallet_tab(self) -> None:
        window = MainWindow()
        window.pallet_nav_button.click()

        page = window.expense_details_page
        self.assertEqual(window.stack.currentWidget(), page)
        self.assertEqual(
            page.tabs.tabText(page.tabs.currentIndex()),
            "Palet Hesabı",
        )
        self.assertTrue(window.pallet_nav_button.isChecked())
        window.close()

    def test_pallet_settings_and_notes_are_persisted(self) -> None:
        window = MainWindow()
        panel = window.expense_details_page.pallet_panel
        panel.wood_price.setValue(15_500)
        panel.yansiz_rate.setValue(68)
        panel.nylon_rate.setValue(70)
        panel.wood_note.setText("Yeni kereste teklifi")
        expected_total = panel.last_result["toplam"]
        window.close()

        reopened = MainWindow()
        restored = reopened.expense_details_page.pallet_panel
        self.assertEqual(restored.wood_price.value(), 15_500)
        self.assertEqual(restored.yansiz_rate.value(), 68)
        self.assertEqual(restored.yanli_rate.value(), 32)
        self.assertEqual(restored.nylon_rate.value(), 70)
        self.assertEqual(
            restored.wood_note.text(),
            "Yeni kereste teklifi",
        )
        self.assertAlmostEqual(
            restored.last_result["toplam"],
            expected_total,
        )
        reopened.close()

    def test_expense_details_scrolls_in_short_window(self) -> None:
        window = MainWindow()
        window.resize(1_120, 780)
        window.show_pallet_calculation()
        self.app.processEvents()

        self.assertGreater(
            window.expense_details_page.page_scroll.verticalScrollBar().maximum(),
            0,
        )
        window.close()

    def test_legacy_automatic_packaging_rows_are_not_double_counted(
        self,
    ) -> None:
        data_file = Path(_TEST_DATA_DIR.name) / "expense_details.json"
        data_file.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "tables": {
                        "ambalaj": [
                            ["KERESTE", "Firma", "M3", "1000", "", ""],
                            ["KARTON KÖŞEBENT", "Firma", "ADET", "2000", "", ""],
                            ["Ek Paketleme", "Firma", "ADET", "3000", "", ""],
                        ]
                    },
                    "fire": {},
                }
            ),
            encoding="utf-8",
        )

        window = MainWindow()
        page = window.expense_details_page
        automatic_total = page.pallet_panel.last_result["toplam"]

        self.assertEqual(page.packaging_table.table.rowCount(), 1)
        self.assertEqual(
            page.packaging_table.table.item(0, 0).text(),
            "Ek Paketleme",
        )
        self.assertAlmostEqual(
            window.home_page.ambalaj.value(),
            automatic_total + 3_000,
            places=2,
        )
        window.close()

    def test_notes_are_persisted(self) -> None:
        window = MainWindow()
        window.expense_details_page.rent_note.setText("Kira notu")
        table = window.expense_details_page.packaging_table.table
        self.set_cell(table, 0, 7, "Paketleme notu")
        window.expense_details_page.fire_table.item(0, 7).setText(
            "Fire notu"
        )
        window.close()

        reopened = MainWindow()
        self.assertEqual(
            reopened.expense_details_page.rent_note.text(),
            "Kira notu",
        )
        self.assertEqual(
            reopened.expense_details_page.packaging_table.table.item(
                0, 7
            ).text(),
            "Paketleme notu",
        )
        self.assertEqual(
            reopened.expense_details_page.fire_table.item(0, 7).text(),
            "Fire notu",
        )
        reopened.close()

    def test_home_reflows_to_one_column_when_window_is_narrow(self) -> None:
        window = MainWindow()
        window.home_page.apply_responsive_form_layout(
            force=True,
            available_width=800,
        )

        self.assertTrue(window.home_page._compact_form_layout)

        window.home_page.apply_responsive_form_layout(
            force=True,
            available_width=1400,
        )
        self.assertFalse(window.home_page._compact_form_layout)
        window.close()

    def test_application_has_no_license_or_login_ui(self) -> None:
        window = MainWindow()

        self.assertFalse(hasattr(window, "license_label"))
        self.assertFalse(hasattr(window, "license_manager"))
        self.assertEqual(
            window.dashboard_page.welcome_label.text(),
            "HOŞ GELDİNİZ",
        )
        window.close()

    def test_dashboard_has_monthly_production_chart_and_entry_button(self) -> None:
        window = MainWindow()

        self.assertIsNotNone(window.dashboard_page.production_chart)
        self.assertEqual(
            window.dashboard_page.production_edit_button.text(),
            "VERİ GİR / EXCEL AKTAR",
        )
        self.assertEqual(
            window.dashboard_page.production_total_value.text(),
            "0,00 ton",
        )
        window.close()

    def test_die_shop_navigation_opens_connected_workflow_page(self) -> None:
        window = MainWindow()
        window.die_nav_button.click()

        self.assertEqual(window.stack.currentWidget(), window.workflow_page)
        self.assertEqual(
            window.workflow_page.department_label.text(),
            "KALIPHANE",
        )
        self.assertEqual(
            window.workflow_page.module_label.text(),
            "Kalıp Kartları",
        )
        self.assertTrue(window.die_nav_button.isChecked())
        window.close()


if __name__ == "__main__":
    unittest.main()
