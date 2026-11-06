"""Tüm modül/sekmelerin detay ekranı denetimi — regresyon koruması."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from pages.workflow import WorkflowPage
from scripts.audit_all_modules import seed
from services.local_workflow import LocalWorkflowService
from ui.record_details_dialog import RecordDetailsDialog


class ModuleDetailAuditTests(unittest.TestCase):
    """Her sekmede sağ tık → Görüntüle çalışmalı ve dolu alan üretmeli."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.service = LocalWorkflowService(
            Path(cls.temp_dir.name) / "rigel_operations.db"
        )
        cls.seed_notes: list[str] = []
        seed(cls.service, cls.seed_notes)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_every_module_detail_screen_renders_fields(self) -> None:
        captured: dict[str, RecordDetailsDialog] = {}
        original_exec = RecordDetailsDialog.exec

        def fake_exec(dialog_self) -> int:
            captured["last"] = dialog_self
            return 0

        RecordDetailsDialog.exec = fake_exec  # type: ignore[method-assign]
        page = WorkflowPage(username="patron", service=self.service)
        try:
            checked = 0
            for (department, module) in sorted(WorkflowPage.CONTEXT_VIEW):
                with self.subTest(department=department, module=module):
                    page.set_context(department, module)

                    columns_key = page.active_columns_key()
                    self.assertIn(
                        columns_key,
                        WorkflowPage.COLUMNS,
                        f"{department}/{module}: sütun tanımı yok",
                    )
                    self.assertEqual(
                        page.table.columnCount(),
                        len(WorkflowPage.COLUMNS[columns_key]),
                        f"{department}/{module}: tablo sütun sayısı tanımla uyuşmuyor",
                    )

                    if page.table.rowCount() == 0:
                        continue

                    page.table.selectRow(0)
                    captured.pop("last", None)
                    page.show_record_details()

                    dialog = captured.get("last")
                    self.assertIsNotNone(
                        dialog, f"{department}/{module}: detay ekranı açılmadı"
                    )
                    assert dialog is not None

                    values = [
                        widget
                        for widget in dialog.findChildren(QLabel)
                        if widget.objectName() == "detailsValue"
                    ]
                    self.assertTrue(
                        values, f"{department}/{module}: etiket/değer alanı üretilmedi"
                    )
                    self.assertTrue(
                        [w for w in values if w.text() not in {"", "—"}],
                        f"{department}/{module}: hiçbir alan dolu değil",
                    )
                    for grid in dialog.findChildren(QTableWidget):
                        self.assertGreater(
                            grid.columnCount(),
                            0,
                            f"{department}/{module}: sütunsuz detay tablosu",
                        )
                    dialog.deleteLater()
                    checked += 1
            self.assertGreaterEqual(
                checked, 70, "Denetlenen sekme sayısı beklenenin altında"
            )
        finally:
            RecordDetailsDialog.exec = original_exec  # type: ignore[method-assign]
            page.close()

    def test_seed_covers_every_module_group(self) -> None:
        """Denetim fikstürü ana modül gruplarının hepsinde veri üretmeli."""
        page = WorkflowPage(username="patron", service=self.service)
        try:
            for department, module in (
                ("Satış", "Satış Siparişleri"),
                ("Satın Alma", "Satın Alma Siparişleri"),
                ("Malzeme Yönetimi", "Stok Kartları"),
                ("Kalıphane", "Kalıp Kartları"),
                ("Üretim", "İş Emirleri"),
                ("Sevkiyat", "Kasalama Fişleri"),
            ):
                with self.subTest(department=department, module=module):
                    page.set_context(department, module)
                    self.assertGreater(
                        page.table.rowCount(),
                        0,
                        f"{department}/{module}: denetim verisi üretilmedi",
                    )
        finally:
            page.close()


class PurchaseInvoiceTests(unittest.TestCase):
    """Satın alma faturası mal kabul satırlarından tutar hesaplar."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_invoice_total_comes_from_received_lines(self) -> None:
        stock_id = self.service.create_stock_item(
            "HM-6060", "6060 BİLLET", stock_group="HAMMADDE", unit="KG",
            tracks_lot=True, username="depo",
        )
        supplier_id = self.service.create_supplier(
            "TED-001", "BİLLET A.Ş.", currency="USD", username="satinalma",
        )
        request_id = self.service.create_purchase_request(
            request_date="2026-08-04", username="depo",
            lines=[{
                "stock_item_id": stock_id, "warehouse_code": "HAMMADDE",
                "quantity": 1_000,
            }],
        )
        self.service.approve_purchase_request(request_id, username="patron")
        # unit_prices talep satırı id'si ile anahtarlanır.
        request_line_id = int(
            self.service.list_purchase_request_lines(request_id)[0]["id"]
        )
        order_id = self.service.create_purchase_order_from_request(
            request_id, supplier_id, order_date="2026-08-04",
            currency="USD", unit_prices={request_line_id: 3.0},
            username="satinalma",
        )
        receipt_id = self.service.receive_purchase_order(
            order_id, receipt_date="2026-08-06", dispatch_note_no="IRS-1",
            lot_no="LOT-1", username="depo",
        )

        invoice_id = self.service.create_purchase_invoice_from_receipt(
            receipt_id, username="muhasebe"
        )
        self.assertGreater(invoice_id, 0)

        invoice = next(
            row for row in self.service.list_purchase_invoices()
            if int(row["id"]) == invoice_id
        )
        # Mal kabul edilen miktar × sipariş birim fiyatı
        self.assertAlmostEqual(float(invoice["subtotal"]), 3_000.0, places=2)
        self.assertAlmostEqual(float(invoice["tax_amount"]), 600.0, places=2)
        self.assertAlmostEqual(float(invoice["total_amount"]), 3_600.0, places=2)
        self.assertEqual(str(invoice["currency"]), "USD")

    def test_same_receipt_cannot_be_invoiced_twice(self) -> None:
        stock_id = self.service.create_stock_item(
            "HM-1", "BİLLET", stock_group="HAMMADDE", unit="KG", username="depo",
        )
        supplier_id = self.service.create_supplier(
            "TED-1", "TEDARİK", username="satinalma"
        )
        request_id = self.service.create_purchase_request(
            request_date="2026-08-04", username="depo",
            lines=[{"stock_item_id": stock_id, "warehouse_code": "HAMMADDE",
                    "quantity": 10}],
        )
        self.service.approve_purchase_request(request_id, username="patron")
        order_id = self.service.create_purchase_order_from_request(
            request_id, supplier_id, order_date="2026-08-04", username="satinalma",
        )
        receipt_id = self.service.receive_purchase_order(
            order_id, receipt_date="2026-08-06", username="depo",
        )
        self.service.create_purchase_invoice_from_receipt(
            receipt_id, username="muhasebe"
        )
        with self.assertRaisesRegex(ValueError, "zaten oluşturulmuş"):
            self.service.create_purchase_invoice_from_receipt(
                receipt_id, username="muhasebe"
            )


class ShipmentWeighingListTests(unittest.TestCase):
    """Sevkiyat, paketlerin bağlı olduğu çeki listesini kendiliğinden bulmalı."""

    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )

    def _ready_packages(self, count: int) -> tuple[int, list[int]]:
        """İki paketlik sevk hazır tek bir çeki listesi üretir."""
        customer_id = self.service.create_customer(
            "MUS-CL", "ÇEKİ TEST", username="satis"
        )
        profile_id = self.service.create_profile(
            "PRF-CL", "ÇEKİ PROFİL", unit_weight_kg_m=1.0,
            customer_id=customer_id, username="kaliphane",
        )
        die_id = self.service.create_die(
            profile_id, "KLP-CL", life_limit_kg=50_000, username="kaliphane"
        )
        self.service.create_route(
            profile_id, "ROTA-CL", "Tek adım",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1",
              "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="uretim_planlama",
        )
        route_id = int(self.service.list_routes(profile_id)[0]["id"])
        self.service.create_recipe(
            profile_id, route_id, "RC-CL", "Çeki testi reçetesi",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1",
              "numerator": 1, "denominator": 1}],
            username="uretim_planlama", production_length_mm=6000,
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-06", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "die_id": die_id, "length_mm": 6000,
                    "surface": "PRES", "quantity": 100 * count,
                    "kg": 100.0 * count, "unit_price": 3.0}],
            username="satis",
        )
        self.service.approve_sales_order(order_id, username="uretim_planlama")
        line_id = int(self.service.order_progress(order_id)["lines"][0]["id"])
        production_id = self.service.plan_sales_order_line(
            line_id, planned_quantity=100 * count, planned_kg=100.0 * count,
            route_id=route_id, username="uretim_planlama",
        )
        for work_order in self.service.work_orders_for_production(production_id):
            self.service.record_work_order_output(
                int(work_order["id"]), quantity=100 * count,
                gross_kg=100.0 * count, net_kg=100.0 * count, metre=100.0,
                die_id=die_id, lot_no="LOT-CL", shift="GÜNDÜZ", username="operator",
            )
        package_ids = [
            self.service.create_package(
                line_id, quantity=100, net_kg=100.0, gross_kg=101.0,
                lot_no="LOT-CL", username="paketleme",
            )
            for _ in range(count)
        ]
        weighing_id = self.service.create_weighing_list(
            package_ids, username="sevkiyat"
        )
        return weighing_id, package_ids

    def test_shipment_inherits_weighing_list_from_packages(self) -> None:
        weighing_id, package_ids = self._ready_packages(1)
        shipment_id = self.service.create_shipment(
            package_ids, shipment_date="2026-08-07",
            vehicle_plate="35 ABC 12", username="sevkiyat",
        )
        shipment = next(
            row for row in self.service.list_shipments()
            if int(row["id"]) == shipment_id
        )
        weighing = next(
            row for row in self.service.list_weighing_lists()
            if int(row["id"]) == weighing_id
        )
        self.assertEqual(
            shipment["weighing_list_no"], weighing["weighing_list_no"]
        )
        self.assertEqual(weighing["status"], "SEVK EDİLDİ")

    def test_weighing_list_closes_only_after_last_package_ships(self) -> None:
        """Kısmi sevkte liste açık kalmalı, son paket çıkınca kapanmalı."""
        weighing_id, package_ids = self._ready_packages(2)

        self.service.create_shipment(
            package_ids[:1], shipment_date="2026-08-07",
            vehicle_plate="35 ABC 12", username="sevkiyat",
        )
        weighing = next(
            row for row in self.service.list_weighing_lists()
            if int(row["id"]) == weighing_id
        )
        self.assertEqual(weighing["status"], "KISMİ SEVK")

        last_id = self.service.create_shipment(
            package_ids[1:], shipment_date="2026-08-08",
            vehicle_plate="35 ABC 12", username="sevkiyat",
        )
        weighing = next(
            row for row in self.service.list_weighing_lists()
            if int(row["id"]) == weighing_id
        )
        self.assertEqual(weighing["status"], "SEVK EDİLDİ")
        last = next(
            row for row in self.service.list_shipments()
            if int(row["id"]) == last_id
        )
        self.assertEqual(
            last["weighing_list_no"], weighing["weighing_list_no"]
        )

    def test_partial_then_full_ship_with_weighing_list_id(self) -> None:
        weighing_id, package_ids = self._ready_packages(2)
        first_id = self.service.create_shipment(
            package_ids[:1], shipment_date="2026-08-07",
            vehicle_plate="35 ABC 12", weighing_list_id=weighing_id,
            username="sevkiyat",
        )
        first = next(
            row for row in self.service.list_shipments()
            if int(row["id"]) == first_id
        )
        weighing = next(
            row for row in self.service.list_weighing_lists()
            if int(row["id"]) == weighing_id
        )
        self.assertIsNone(first.get("weighing_list_no"))
        self.assertEqual(weighing["status"], "KISMİ SEVK")

        last_id = self.service.create_shipment(
            package_ids[1:], shipment_date="2026-08-08",
            vehicle_plate="35 ABC 12", weighing_list_id=weighing_id,
            username="sevkiyat",
        )
        weighing = next(
            row for row in self.service.list_weighing_lists()
            if int(row["id"]) == weighing_id
        )
        last = next(
            row for row in self.service.list_shipments()
            if int(row["id"]) == last_id
        )
        self.assertEqual(weighing["status"], "SEVK EDİLDİ")
        self.assertEqual(
            last["weighing_list_no"], weighing["weighing_list_no"]
        )


class SummaryTotalsTests(unittest.TestCase):
    """Üst özet kartı ile alt bilgi satırı aynı toplamı göstermeli."""

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

    @staticmethod
    def _kpi_kg(text: str) -> float:
        return float(text.replace(" kg", "").replace(".", "").replace(",", "."))

    @staticmethod
    def _footer_kg(text: str) -> float:
        return float(text.split("toplam kg:")[1].strip().replace(",", ""))

    def test_footer_matches_summary_card_on_every_tab(self) -> None:
        page = WorkflowPage(username="patron", service=self.service)
        try:
            for department, module in sorted(WorkflowPage.CONTEXT_VIEW):
                page.set_context(department, module)
                if page.table.rowCount() == 0:
                    continue
                with self.subTest(department=department, module=module):
                    self.assertAlmostEqual(
                        self._kpi_kg(page.kpi_values[2].text()),
                        self._footer_kg(page.rigel_footer.text()),
                        places=2,
                        msg=f"{department}/{module}: kart ve alt bilgi farklı",
                    )
        finally:
            page.close()

    def test_quantity_views_report_non_zero_totals(self) -> None:
        """Miktar taşıyan sekmelerde özet sıfır kalmamalı."""
        page = WorkflowPage(username="patron", service=self.service)
        try:
            for department, module in (
                ("Sevkiyat", "Çeki Listeleri"),
                ("Sevkiyat", "Kasalama Fişleri"),
                ("Satış", "Satış İrsaliyeleri"),
                ("Satış", "Satış Siparişleri"),
                ("Satın Alma", "Satın Alma Siparişleri"),
                ("Üretim", "İş Emirleri"),
                ("Üretim", "Ambar Yükleri"),
            ):
                with self.subTest(department=department, module=module):
                    page.set_context(department, module)
                    self.assertGreater(page.table.rowCount(), 0)
                    self.assertGreater(
                        self._footer_kg(page.rigel_footer.text()),
                        0,
                        f"{department}/{module}: alt bilgi toplam kg sıfır",
                    )
        finally:
            page.close()

    def test_totals_handle_mixed_and_missing_fields(self) -> None:
        records = [
            {"ordered_kg": 100.0, "ordered_quantity": 10},
            {"net_kg": 250.5, "package_count": 2},
            {"balance": 12.25},
            {"kod": "ALFA"},
            {"net_kg": None, "balance": ""},
        ]
        self.assertAlmostEqual(WorkflowPage.total_kg(records), 362.75, places=3)
        self.assertAlmostEqual(WorkflowPage.total_quantity(records), 12.0, places=3)

    def test_totals_ignore_non_numeric_values(self) -> None:
        records = [{"net_kg": "abc"}, {"net_kg": "15.5"}]
        self.assertAlmostEqual(WorkflowPage.total_kg(records), 15.5, places=3)


class MaintenanceInstructionTests(unittest.TestCase):
    """Bakım talimatı kartı: oluşturma, düzenleme, durum ve emir açma."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = LocalWorkflowService(
            Path(self.temp_dir.name) / "rigel_operations.db"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create(self, **overrides) -> int:
        payload = {
            "instruction_type": "PERİYODİK",
            "name": "PRES HİDROLİK YAĞ KONTROLÜ",
            "description": "Yağ seviyesi kontrol edilir.",
            "operation": "PRES ÜRETİM",
            "station": "PRES 1",
            "period_days": 30,
            "username": "bakim",
        }
        payload.update(overrides)
        return self.service.create_maintenance_instruction(**payload)

    def test_instruction_is_created_with_sequential_number(self) -> None:
        first = self._create()
        second = self._create(name="ELOKSAL POMPA KONTROLÜ")
        numbers = [
            self.service.maintenance_instruction(first)["instruction_no"],
            self.service.maintenance_instruction(second)["instruction_no"],
        ]
        self.assertTrue(all(no.startswith("BT") for no in numbers), numbers)
        self.assertNotEqual(numbers[0], numbers[1])
        self.assertEqual(len(self.service.list_maintenance_instructions()), 2)

    def test_invalid_instructions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "adı zorunludur"):
            self._create(name="   ")
        with self.assertRaisesRegex(ValueError, "tipi şunlardan biri"):
            self._create(instruction_type="GÜNLÜK")
        with self.assertRaisesRegex(ValueError, "periyot zorunludur"):
            self._create(period_days=0)
        with self.assertRaisesRegex(ValueError, "negatif olamaz"):
            self._create(period_days=-5)
        self.assertEqual(self.service.list_maintenance_instructions(), [])

    def test_arizi_instruction_allows_zero_period(self) -> None:
        instruction_id = self._create(
            instruction_type="ARİZİ", name="POMPA ARIZA", period_days=0
        )
        record = self.service.maintenance_instruction(instruction_id)
        self.assertEqual(record["instruction_type"], "ARİZİ")
        self.assertEqual(record["period_days"], 0)

    def test_instruction_can_be_updated_and_deactivated(self) -> None:
        instruction_id = self._create()
        self.service.update_maintenance_instruction(
            instruction_id, instruction_type="ÖNLEYİCİ",
            name="PRES YAĞ VE FİLTRE", period_days=45,
            operation="PRES ÜRETİM", station="PRES 2", username="bakim",
        )
        record = self.service.maintenance_instruction(instruction_id)
        self.assertEqual(record["instruction_type"], "ÖNLEYİCİ")
        self.assertEqual(record["name"], "PRES YAĞ VE FİLTRE")
        self.assertEqual(record["period_days"], 45)
        self.assertEqual(record["station"], "PRES 2")

        self.service.set_maintenance_instruction_active(
            instruction_id, False, username="bakim"
        )
        self.assertEqual(
            self.service.maintenance_instruction(instruction_id)["active"], 0
        )
        self.assertEqual(
            self.service.list_maintenance_instructions(include_inactive=False), []
        )
        self.assertEqual(len(self.service.list_maintenance_instructions()), 1)

    def test_order_from_instruction_uses_period_for_planned_end(self) -> None:
        instruction_id = self._create(period_days=30)
        order_id = self.service.create_maintenance_order_from_instruction(
            instruction_id, planned_start="2026-08-10", username="bakim"
        )
        order = next(
            row for row in self.service.list_maintenance_orders()
            if int(row["id"]) == order_id
        )
        self.assertEqual(order["planned_start"], "2026-08-10")
        self.assertEqual(order["planned_end"], "2026-09-09")
        self.assertEqual(order["name"], "PRES HİDROLİK YAĞ KONTROLÜ")
        self.assertEqual(order["operation"], "PRES ÜRETİM")

    def test_passive_instruction_cannot_open_order(self) -> None:
        instruction_id = self._create()
        self.service.set_maintenance_instruction_active(
            instruction_id, False, username="bakim"
        )
        with self.assertRaisesRegex(ValueError, "Pasif bakım talimatından"):
            self.service.create_maintenance_order_from_instruction(
                instruction_id, username="bakim"
            )

    def test_dialog_defaults_and_validation(self) -> None:
        from pages.workflow import MaintenanceInstructionDialog

        dialog = MaintenanceInstructionDialog(self.service)
        self.assertEqual(dialog.instruction_type.currentText(), "PERİYODİK")
        self.assertEqual(
            dialog.period_days.value(), MaintenanceInstructionDialog.DEFAULT_PERIOD_DAYS
        )

        dialog.instruction_type.setCurrentText("ARİZİ")
        self.assertEqual(dialog.period_days.minimum(), 0)
        dialog.period_days.setValue(0)
        dialog.instruction_type.setCurrentText("PERİYODİK")
        self.assertEqual(
            dialog.period_days.value(), MaintenanceInstructionDialog.DEFAULT_PERIOD_DAYS
        )

        # Mevcut kaydın periyodu varsayılana ezilmemeli.
        instruction_id = self._create(period_days=7)
        record = self.service.maintenance_instruction(instruction_id)
        edit_dialog = MaintenanceInstructionDialog(self.service, None, record)
        self.assertEqual(edit_dialog.period_days.value(), 7)
        self.assertEqual(edit_dialog.name.text(), record["name"])
        self.assertEqual(
            edit_dialog.values()["instruction_type"], record["instruction_type"]
        )
        dialog.deleteLater()
        edit_dialog.deleteLater()

    def test_order_dialog_prefills_from_instruction(self) -> None:
        from pages.workflow import MaintenanceOrderDialog

        self._create(period_days=10)
        dialog = MaintenanceOrderDialog(self.service)
        # 0. sıra "talimatsız", 1. sıra ilk talimat
        self.assertGreaterEqual(dialog.instruction.count(), 2)
        dialog.instruction.setCurrentIndex(1)
        self.assertEqual(dialog.name.text(), "PRES HİDROLİK YAĞ KONTROLÜ")
        self.assertEqual(
            dialog.planned_end.date(), dialog.planned_start.date().addDays(10)
        )
        dialog.deleteLater()

    def test_page_exposes_maintenance_instruction_actions(self) -> None:
        self._create()
        page = WorkflowPage(username="patron", service=self.service)
        try:
            page.set_context("Bakım", "Bakım Talimatları")
            self.assertEqual(page.view, "maintenance_instructions")
            self.assertEqual(page.table.rowCount(), 1)
            self.assertEqual(page.primary.text(), "＋ YENİ BAKIM TALİMATI")
            actions = page.context_action_texts()
            for expected in ("Ekle", "Değiştir", "Bakım Emri Aç", "Aktif / Pasif"):
                self.assertIn(expected, actions)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
