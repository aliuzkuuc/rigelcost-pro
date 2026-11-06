from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pages.workflow import (
    BranchDialog,
    CustomerDialog,
    GoodsReceiptDialog,
    PurchaseOrderDialog,
    PurchaseRequestDialog,
    ProductionPlanDialog,
    ProductionEntryDialog,
    ProfileRouteDialog,
    RecipeDialog,
    SalesOrderDialog,
    StockDocumentDialog,
    StockItemDialog,
    SupplierDialog,
    WarehouseDialog,
    WorkflowPage,
)
from services.local_workflow import LocalWorkflowService


class LocalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "rigel_operations.db"
        self.service = LocalWorkflowService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_approved_order(self) -> tuple[int, int, int]:
        customer_id = self.service.create_customer(
            "MUS-001", "AKSEKİ YAPI", username="patron"
        )
        profile_id = self.service.create_profile(
            "PRF-001",
            "KAPI PROFİLİ",
            unit_weight_kg_m=1.25,
            customer_id=customer_id,
            username="patron",
        )
        die_id = self.service.create_die(
            profile_id,
            "KLP-001",
            life_limit_kg=100_000,
            username="kaliphane",
        )
        self.service.create_route(
            profile_id,
            "R-PRES-TERMIK-PKT",
            "Pres - Termik - Paketleme",
            [
                {
                    "operation": "PRES ÜRETİM",
                    "station": "PRES 1",
                    "input_warehouse": "HAMMADDE",
                    "output_warehouse": "PRES",
                },
                {
                    "operation": "TERMİK ÇIKIŞ",
                    "station": "TERMİK 1",
                    "input_warehouse": "PRES",
                    "output_warehouse": "TERMIK",
                },
                {
                    "operation": "PAKETLEME",
                    "station": "PAKETLEME 1",
                    "input_warehouse": "TERMIK",
                    "output_warehouse": "SEVK_ON",
                },
            ],
            username="uretim_planlama",
        )
        route_id = self.service.list_routes(profile_id)[0]["id"]
        self.service.create_recipe(
            profile_id,
            route_id,
            "RC-PRES-TERMIK-PKT",
            "Pres - Termik - Paketleme reçetesi",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
                {"operation": "PAKETLEME", "station": "PAKETLEME 1", "numerator": 1, "denominator": 1},
            ],
            username="uretim_planlama",
            production_length_mm=6000,
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-04",
            delivery_date="2026-08-20",
            lines=[
                {
                    "profile_id": profile_id,
                    "die_id": die_id,
                    "length_mm": 6000,
                    "surface": "PRES",
                    "quantity": 200,
                    "kg": 1000,
                    "unit_price": 4.20,
                }
            ],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.approve_sales_order(order_id, username="uretim_planlama")
        production_id = self.service.plan_sales_order_line(
            line_id,
            planned_quantity=200,
            planned_kg=1000,
            route_id=route_id,
            username="uretim_planlama",
        )
        return order_id, production_id, die_id

    def test_order_to_production_package_and_shipment_is_linked(self) -> None:
        order_id, production_id, die_id = self._create_approved_order()
        self.assertEqual(len(self.service.list_customers()), 1)
        self.assertEqual(len(self.service.list_profiles()), 1)
        self.assertEqual(len(self.service.list_dies()), 1)
        self.assertEqual(len(self.service.list_sales_orders()), 1)
        self.assertEqual(len(self.service.list_production_orders()), 1)
        work_orders = self.service.work_orders_for_production(production_id)
        self.assertEqual(
            [row["status"] for row in work_orders],
            ["HAZIR", "BEKLİYOR", "BEKLİYOR"],
        )

        for index, work_order in enumerate(work_orders):
            self.service.record_work_order_output(
                work_order["id"],
                quantity=200,
                gross_kg=1020 if index == 0 else 1000,
                net_kg=1000,
                metre=800,
                die_id=die_id if index == 0 else None,
                lot_no="LOT-001",
                shift="GÜNDÜZ",
                username="operator",
            )
            refreshed = self.service.work_orders_for_production(production_id)
            self.assertEqual(refreshed[index]["status"], "TAMAMLANDI")
            if index + 1 < len(refreshed):
                self.assertEqual(refreshed[index + 1]["status"], "HAZIR")

        progress = self.service.order_progress(order_id)
        self.assertEqual(progress["order"]["status"], "HAZIR")
        self.assertEqual(progress["lines"][0]["produced_kg"], 1000)
        line_id = progress["lines"][0]["id"]
        self.assertEqual(len(self.service.list_packable_lines()), 1)

        package_id = self.service.create_package(
            line_id,
            quantity=200,
            net_kg=1000,
            gross_kg=1025,
            lot_no="LOT-001",
            username="paketleme",
        )
        self.assertEqual(self.service.list_packages()[0]["status"], "SEVK ÖN")
        with self.assertRaisesRegex(ValueError, "çeki listesine"):
            self.service.create_shipment(
                [package_id],
                shipment_date="2026-08-05",
                vehicle_plate="35 ABC 123",
                username="sevkiyat",
            )
        weighing_list_id = self.service.create_weighing_list(
            [package_id], username="sevkiyat"
        )
        self.assertGreater(weighing_list_id, 0)
        self.assertEqual(self.service.list_packages()[0]["status"], "SEVK HAZIR")
        self.assertEqual(self.service.table_count("weighing_lists"), 1)
        self.service.create_shipment(
            [package_id],
            shipment_date="2026-08-05",
            vehicle_plate="35 ABC 123",
            username="sevkiyat",
        )

        shipped = self.service.order_progress(order_id)
        self.assertEqual(shipped["order"]["status"], "SEVK EDİLDİ")
        self.assertEqual(shipped["lines"][0]["shipped_kg"], 1000)
        self.assertEqual(shipped["lines"][0]["progress_pct"], 100)
        self.assertEqual(self.service.list_packages()[0]["status"], "SEVK EDİLDİ")
        sevk_hazir_balance = sum(
            float(row["balance"] or 0)
            for row in self.service.list_warehouse_balances()
            if str(row["warehouse_code"]) == "SEVK_HAZIR"
        )
        self.assertAlmostEqual(sevk_hazir_balance, 0.0, places=3)
        # Her operasyon girdi ve çıktı ambar hareketini üretir; buna çeki
        # listesi transferi ve sevkiyat çıkışı eklenir.
        self.assertEqual(self.service.table_count("stock_movements"), 9)
        self.assertEqual(self.service.table_count("shipments"), 1)
        self.assertEqual(self.service.list_shipments()[0]["net_kg"], 1000)
        self.assertGreaterEqual(self.service.table_count("audit_log"), 8)

    def test_waiting_work_order_cannot_be_reported_early(self) -> None:
        _order_id, production_id, _die_id = self._create_approved_order()
        work_orders = self.service.work_orders_for_production(production_id)
        with self.assertRaisesRegex(ValueError, "henüz üretime hazır değil"):
            self.service.record_work_order_output(
                work_orders[1]["id"],
                quantity=1,
                gross_kg=10,
                net_kg=9,
                username="operator",
            )

    def test_warehouse_loads_are_calculated_from_stock_movement_ledger(self) -> None:
        _order_id, production_id, die_id = self._create_approved_order()
        for work_order in self.service.work_orders_for_production(production_id):
            self.service.record_work_order_output(
                work_order["id"], quantity=200,
                gross_kg=1020 if work_order["sequence_no"] == 1 else 1000,
                net_kg=1000, metre=800,
                die_id=die_id if work_order["sequence_no"] == 1 else None,
                lot_no="LOT-AMBAR", username="operator",
            )
        balances = self.service.list_warehouse_balances()
        by_warehouse = {
            (row["warehouse_code"], row["stock_code"], row["lot_no"]): row["balance"]
            for row in balances
        }
        self.assertEqual(by_warehouse[("SEVK_ON", "PRF-001", "LOT-AMBAR")], 1000)
        self.assertEqual(by_warehouse[("HAMMADDE", "AL-BILLET", "LOT-AMBAR")], -1020)
        self.assertTrue(WorkflowPage.handles_context("Üretim", "Ambar Yükleri"))
        self.assertTrue(WorkflowPage.handles_context("Malzeme Yönetimi", "Stok Hareketleri"))

    def test_material_stock_card_is_shared_with_relational_warehouse_views(self) -> None:
        stock_id = self.service.create_stock_item(
            "AMB-001", "AMBALAJ KÖŞEBENT", stock_group="AMBALAJ",
            unit="ADET", tracks_lot=True, minimum_quantity=500,
            username="depo",
        )
        card = self.service.stock_item(stock_id)
        self.assertEqual(card["stock_group"], "AMBALAJ")
        self.assertEqual(card["unit"], "ADET")
        self.service.update_stock_item(
            stock_id, name="KARTON KÖŞEBENT", minimum_quantity=750,
            username="depo",
        )
        listed = next(row for row in self.service.list_stock_items() if row["id"] == stock_id)
        self.assertEqual(listed["name"], "KARTON KÖŞEBENT")
        self.assertEqual(listed["minimum_quantity"], 750)
        self.assertTrue(WorkflowPage.handles_context("Malzeme Yönetimi", "Stok Kartları"))

    def test_purchase_request_order_receipt_updates_the_same_stock_ledger(self) -> None:
        stock_id = self.service.create_stock_item(
            "HM-6060", "6060 BİLLET", stock_group="HAMMADDE", unit="KG",
            tracks_lot=True, minimum_quantity=10_000, username="depo",
        )
        supplier_id = self.service.create_supplier(
            "TED-001", "BİLLET TEDARİK A.Ş.", tax_office="KONAK",
            tax_number="1234567890", currency="USD", username="satinalma",
        )
        request_id = self.service.create_purchase_request(
            request_date="2026-08-04", username="pres_sorumlusu",
            lines=[{
                "stock_item_id": stock_id, "warehouse_code": "HAMMADDE",
                "required_date": "2026-08-10", "quantity": 25_000,
                "reason": "Ağustos üretim planı",
            }],
        )
        self.service.approve_purchase_request(request_id, username="patron")
        order_id = self.service.create_purchase_order_from_request(
            request_id, supplier_id, order_date="2026-08-04",
            delivery_date="2026-08-10", currency="USD", username="satinalma",
        )
        receipt_id = self.service.receive_purchase_order(
            order_id, receipt_date="2026-08-06", dispatch_note_no="IRS-55",
            lot_no="LOT-6060-01", username="depo",
        )
        self.assertGreater(receipt_id, 0)
        self.assertEqual(self.service.list_purchase_requests()[0]["status"], "SİPARİŞE DÖNÜŞTÜ")
        self.assertEqual(self.service.list_purchase_orders()[0]["status"], "TAMAMLANDI")
        self.assertEqual(self.service.list_goods_receipts()[0]["received_quantity"], 25_000)
        balance = next(
            row for row in self.service.list_warehouse_balances()
            if row["stock_code"] == "HM-6060"
        )
        self.assertEqual(balance["warehouse_code"], "HAMMADDE")
        self.assertEqual(balance["lot_no"], "LOT-6060-01")
        self.assertEqual(balance["balance"], 25_000)
        self.assertTrue(WorkflowPage.handles_context("Satın Alma", "Talep Fişleri"))
        self.assertTrue(WorkflowPage.handles_context("Satın Alma", "Satın Alma Siparişleri"))
        self.assertTrue(WorkflowPage.handles_context("Satın Alma", "Satın Alma İrsaliyeleri"))

    def test_unit_set_converts_recipe_consumption_to_stock_ledger(self) -> None:
        unit_set_id = self.service.create_unit_set(
            "BS-001", "Profil seti",
            base_unit="KG",
            lines=[
                {"unit_code": "KG", "factor": 1},
                {"unit_code": "ADET", "factor": 0.01},
                {"unit_code": "METRE", "factor": 0.001},
            ],
            username="depo",
        )
        customer_id = self.service.create_customer("M-800", "BIRIM TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-800", "BIRIM PROFIL", unit_weight_kg_m=1.0,
            customer_id=customer_id, username="patron",
        )
        stock_id = self.service.create_stock_item(
            "ST-800", "TEST STOK", stock_group="SARF", unit="ADET",
            tracks_lot=False, username="depo",
        )
        with closing(self.service.connect()) as connection:
            connection.execute(
                "UPDATE stock_items SET unit_set_id = ? WHERE id = ?",
                (unit_set_id, stock_id),
            )
            connection.commit()
        route_id = self.service.create_route(
            profile_id, "R-800", "BIRIM ROTASI",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        self.service.create_recipe(
            profile_id, route_id, "RC-800", "ADET REÇETE",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "stock_code": "ST-800", "unit_code": "ADET", "numerator": 1, "denominator": 1}],
            username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 100, "kg": 600}],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.approve_sales_order(order_id, username="planlama")
        production_id = self.service.plan_sales_order_line(
            line_id, planned_quantity=100, planned_kg=600,
            route_id=route_id, username="planlama",
        )
        work_id = self.service.work_orders_for_production(production_id)[0]["id"]
        self.service.record_work_order_output(
            work_id, quantity=100, gross_kg=620, net_kg=600, metre=600,
            username="operator",
        )
        movements = self.service.list_stock_movements(work_order_id=work_id)
        output_moves = [row for row in movements if row["direction"] == 1]
        self.assertEqual(len(output_moves), 1)
        self.assertAlmostEqual(float(output_moves[0]["quantity"]), 100.0)
        self.assertEqual(output_moves[0]["stock_code"], "ST-800")
        self.assertTrue(WorkflowPage.handles_context("Malzeme Yönetimi", "Birim Setleri"))
        self.assertEqual(len(self.service.list_unit_set_lines(unit_set_id)), 3)

    def test_press_theory_links_profile_weight_to_billet_length(self) -> None:
        theory = self.service.calculate_press_theory(
            quantity=100,
            result_length_mm=6000,
            profile_weight_kg_m=0.655,
            billet_count=9,
            billet_diameter_mm=152.4,
            billet_density_kg_m3=2700,
            fire_pct=3,
        )
        self.assertAlmostEqual(theory["net_metre"], 600.0, places=3)
        self.assertAlmostEqual(theory["theoretical_net_kg"], 393.0, places=3)
        self.assertAlmostEqual(theory["billet_weight_kg_m"], 49.251967, places=5)
        self.assertAlmostEqual(theory["billet_length_mm"], 914.018, places=2)

    def test_different_press_length_updates_downstream_work_orders(self) -> None:
        order_id, production_id, die_id = self._create_approved_order()
        work_orders = self.service.work_orders_for_production(production_id)
        pres = work_orders[0]
        termik_before = work_orders[1]
        self.service.record_work_order_output(
            pres["id"],
            quantity=200,
            gross_kg=1020,
            net_kg=1000,
            metre=1160,
            die_id=die_id,
            username="operator",
            result_length_mm=5800,
        )
        refreshed = self.service.work_orders_for_production(production_id)
        termik = refreshed[1]
        self.assertAlmostEqual(float(termik["production_length_mm"]), 5800.0)
        self.assertLess(float(termik["planned_metre"]), float(termik_before["planned_metre"]))
        audits = self.service.audit_history("WORK_ORDER", int(pres["id"]))
        self.assertTrue(any(row["action"] == "LENGTH_CONTINUATION" for row in audits))

    def test_module_workflow_pages_are_wired(self) -> None:
        self.assertTrue(WorkflowPage.handles_context("Kalıphane", "Kalıp Hareketleri"))
        self.assertTrue(WorkflowPage.handles_context("Kalıphane", "İmalattaki Kalıplar"))
        self.assertTrue(WorkflowPage.handles_context("Üretim", "Eloksal Fişleri"))
        self.assertTrue(WorkflowPage.handles_context("Üretim", "Duruşlar"))
        self.assertTrue(WorkflowPage.handles_context("Bakım", "Bakım Emirleri"))
        self.assertTrue(WorkflowPage.handles_context("Satın Alma", "Satın Alma Faturaları"))
        self.assertTrue(WorkflowPage.handles_context("Satın Alma", "Teklif Karşılaştırma"))
        self.assertTrue(WorkflowPage.handles_context("Satış", "Teklifler"))
        self.assertTrue(WorkflowPage.handles_context("Satış", "Sipariş Detay (Satış)"))

    def test_eloksal_downtime_and_purchase_invoice_records(self) -> None:
        downtime_id = self.service.create_downtime_event(
            reason="MEKANİK ARIZA",
            station="PRES 1",
            username="operator",
        )
        self.assertGreater(downtime_id, 0)
        self.service.close_downtime_event(downtime_id, username="operator")
        self.assertEqual(self.service.list_downtime_events()[0]["status"], "KAPALI")
        maintenance_id = self.service.create_maintenance_order(
            order_type="PERİYODİK",
            name="Pres yağlama",
            station="PRES 1",
            username="bakim",
        )
        self.assertGreater(maintenance_id, 0)
        self.assertEqual(len(self.service.list_maintenance_orders()), 1)

    def test_package_cannot_exceed_produced_quantity(self) -> None:
        order_id, _production_id, _die_id = self._create_approved_order()
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        with self.assertRaisesRegex(ValueError, "üretilmiş miktarı aşamaz"):
            self.service.create_package(
                line_id,
                quantity=200,
                net_kg=1000,
                gross_kg=1020,
                username="paketleme",
            )

    def test_partial_final_operation_moves_full_completed_quantity_to_stock(self) -> None:
        order_id, production_id, die_id = self._create_approved_order()
        work_orders = self.service.work_orders_for_production(production_id)
        for work_order in work_orders[:-1]:
            self.service.record_work_order_output(
                work_order["id"],
                quantity=200,
                gross_kg=1000,
                net_kg=1000,
                die_id=die_id if work_order["sequence_no"] == 1 else None,
                username="operator",
            )
        final_id = work_orders[-1]["id"]
        self.service.record_work_order_output(
            final_id,
            quantity=80,
            gross_kg=400,
            net_kg=400,
            username="operator",
            complete=False,
        )
        self.service.record_work_order_output(
            final_id,
            quantity=120,
            gross_kg=600,
            net_kg=600,
            username="operator",
            complete=True,
        )
        progress = self.service.order_progress(order_id)
        self.assertEqual(progress["lines"][0]["produced_quantity"], 200)
        self.assertEqual(progress["lines"][0]["produced_kg"], 1000)
        with closing(self.service.connect()) as connection:
            stock_quantity = connection.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) FROM stock_movements
                WHERE movement_type = 'PAKETLEME GİRİŞ' AND direction = 1
                """
            ).fetchone()[0]
        self.assertEqual(stock_quantity, 1000)

    def test_next_station_cannot_consume_more_than_previous_output(self) -> None:
        _order_id, production_id, die_id = self._create_approved_order()
        work_orders = self.service.work_orders_for_production(production_id)
        self.service.record_work_order_output(
            work_orders[0]["id"],
            quantity=100,
            gross_kg=520,
            net_kg=500,
            die_id=die_id,
            username="pres_operatoru",
        )
        with self.assertRaisesRegex(ValueError, "önceki istasyondan"):
            self.service.record_work_order_output(
                work_orders[1]["id"],
                quantity=120,
                gross_kg=600,
                net_kg=590,
                username="termik_operatoru",
            )

    def test_shipment_can_be_created_from_weighing_list_once(self) -> None:
        order_id, production_id, die_id = self._create_approved_order()
        for work_order in self.service.work_orders_for_production(production_id):
            self.service.record_work_order_output(
                work_order["id"],
                quantity=200,
                gross_kg=1_020 if work_order["sequence_no"] == 1 else 1_000,
                net_kg=1_000,
                die_id=die_id if work_order["sequence_no"] == 1 else None,
                username="operator",
            )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        package_id = self.service.create_package(
            line_id, quantity=200, net_kg=1_000, gross_kg=1_025,
            username="paketleme",
        )
        weighing_list_id = self.service.create_weighing_list(
            [package_id], username="sevkiyat"
        )
        shipment_id = self.service.create_shipment(
            [package_id],
            shipment_date="2026-08-05",
            weighing_list_id=weighing_list_id,
            username="sevkiyat",
        )
        self.assertGreater(shipment_id, 0)
        self.assertEqual(self.service.list_weighing_lists()[0]["status"], "SEVK EDİLDİ")
        invoice_id = self.service.create_sales_invoice(
            shipment_id,
            invoice_date="2026-08-05",
            currency="USD",
            exchange_rate=47.5,
            lme_usd_ton=3_200,
            premium_usd_ton=600,
            pricing_mode="LME + PRİM",
            username="muhasebe",
        )
        self.assertGreater(invoice_id, 0)
        invoice = self.service.list_sales_invoices()[0]
        self.assertAlmostEqual(invoice["total_amount"], 3_800)
        self.assertEqual(invoice["dispatch_note_no"], invoice["shipment_no"])
        with self.assertRaisesRegex(ValueError, "daha önce sevk"):
            self.service.create_shipment(
                [package_id],
                shipment_date="2026-08-05",
                weighing_list_id=weighing_list_id,
                username="sevkiyat",
            )

    def test_irsaliye_clears_sevk_hazir_and_updates_order_progress(self) -> None:
        order_id, production_id, die_id = self._create_approved_order()
        for work_order in self.service.work_orders_for_production(production_id):
            self.service.record_work_order_output(
                work_order["id"],
                quantity=200,
                gross_kg=1_020 if work_order["sequence_no"] == 1 else 1_000,
                net_kg=1_000,
                die_id=die_id if work_order["sequence_no"] == 1 else None,
                username="operator",
            )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        package_ids = [
            self.service.create_package(
                line_id, quantity=100, net_kg=500, gross_kg=510,
                username="paketleme",
            )
            for _ in range(2)
        ]
        weighing_list_id = self.service.create_weighing_list(
            package_ids, username="sevkiyat"
        )
        self.service.create_shipment(
            package_ids[:1],
            shipment_date="2026-08-05",
            weighing_list_id=weighing_list_id,
            username="sevkiyat",
        )
        partial = self.service.order_progress(order_id)
        self.assertEqual(partial["order"]["status"], "KISMİ SEVK")
        self.assertEqual(partial["lines"][0]["progress_pct"], 50)
        self.assertEqual(
            self.service.list_weighing_lists()[0]["status"], "KISMİ SEVK"
        )
        sevk_hazir_balance = sum(
            float(row["balance"] or 0)
            for row in self.service.list_warehouse_balances()
            if str(row["warehouse_code"]) == "SEVK_HAZIR"
        )
        self.assertAlmostEqual(sevk_hazir_balance, 500.0, places=3)

        self.service.create_shipment(
            package_ids[1:],
            shipment_date="2026-08-06",
            weighing_list_id=weighing_list_id,
            username="sevkiyat",
        )
        full = self.service.order_progress(order_id)
        self.assertEqual(full["order"]["status"], "SEVK EDİLDİ")
        self.assertEqual(full["lines"][0]["progress_pct"], 100)
        self.assertEqual(
            self.service.list_weighing_lists()[0]["status"], "SEVK EDİLDİ"
        )
        sevk_hazir_balance = sum(
            float(row["balance"] or 0)
            for row in self.service.list_warehouse_balances()
            if str(row["warehouse_code"]) == "SEVK_HAZIR"
        )
        self.assertAlmostEqual(sevk_hazir_balance, 0.0, places=3)
        exits = [
            row for row in self.service.list_stock_movements()
            if str(row.get("movement_type")) == "SEVKİYAT ÇIKIŞ"
            and str(row.get("warehouse_code")) == "SEVK_HAZIR"
        ]
        self.assertEqual(len(exits), 2)

    def test_order_selects_recipe_by_length_surface_alloy_and_temper(self) -> None:
        customer_id = self.service.create_customer("M-1", "MÜŞTERİ", username="patron")
        profile_id = self.service.create_profile(
            "P-1", "PROFİL", unit_weight_kg_m=1.2,
            customer_id=customer_id, username="patron",
        )
        common_press = {
            "operation": "PRES ÜRETİM", "station": "PRES 1",
            "input_warehouse": "HAMMADDE", "output_warehouse": "PRES",
        }
        packing = {
            "operation": "PAKETLEME", "station": "PAKETLEME 1",
            "input_warehouse": "PRES", "output_warehouse": "SEVK_ON",
        }
        self.service.create_route(
            profile_id, "R-PRES", "Pres reçetesi", [common_press, packing],
            production_length_mm=6000, surface="PRES", alloy="6060B", temper="T5",
            username="planlama",
        )
        self.service.create_route(
            profile_id,
            "R-ELOKSAL",
            "Eloksal reçetesi",
            [
                common_press,
                {
                    "operation": "ELOKSAL", "station": "ELOKSAL 1",
                    "input_warehouse": "PRES", "output_warehouse": "YUZEY",
                },
                {
                    "operation": "PAKETLEME", "station": "PAKETLEME 1",
                    "input_warehouse": "YUZEY", "output_warehouse": "SEVK_ON",
                },
            ],
            production_length_mm=6000,
            surface="ELOKSAL",
            alloy="6060B",
            temper="T5",
            username="planlama",
        )
        pres_route_id = self.service.list_routes(profile_id)[0]["id"]
        elok_route_id = self.service.list_routes(profile_id)[1]["id"]
        self.service.create_recipe(
            profile_id, pres_route_id, "RC-PRES", "Pres reçetesi",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "PAKETLEME", "station": "PAKETLEME 1", "numerator": 1, "denominator": 1},
            ],
            username="planlama", production_length_mm=6000,
        )
        self.service.create_recipe(
            profile_id, elok_route_id, "RC-ELOKSAL", "Eloksal reçetesi",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "ELOKSAL", "station": "ELOKSAL 1", "numerator": 1, "denominator": 1},
                {"operation": "PAKETLEME", "station": "PAKETLEME 1", "numerator": 1, "denominator": 1},
            ],
            username="planlama", production_length_mm=6000,
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-04",
            delivery_date="2026-08-20",
            lines=[
                {
                    "profile_id": profile_id, "length_mm": 6000,
                    "surface": "ELOKSAL", "quantity": 100, "kg": 500,
                }
            ],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.approve_sales_order(order_id, username="planlama")
        production_id = self.service.plan_sales_order_line(
            line_id, planned_quantity=100, planned_kg=500,
            username="planlama",
        )
        operations = [
            row["operation"] for row in self.service.work_orders_for_production(production_id)
        ]
        self.assertEqual(operations, ["PRES ÜRETİM", "ELOKSAL", "PAKETLEME"])

    def test_route_condition_selects_route_linked_to_matching_property(self) -> None:
        customer_id = self.service.create_customer("M-RC", "ROTA KOSUL", username="patron")
        profile_id = self.service.create_profile(
            "P-RC", "ROTA PROFİL", unit_weight_kg_m=1.0,
            customer_id=customer_id, username="patron",
        )
        pres_route_id = self.service.create_route(
            profile_id, "R-PRES-GEN", "Genel pres",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        elok_route_id = self.service.create_route(
            profile_id, "R-ELOKSAL-GEN", "Genel eloksal",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
                {"operation": "ELOKSAL", "station": "ELOKSAL 1", "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
            ],
            username="patron",
        )
        self.service.create_recipe(
            profile_id, pres_route_id, "RC-PRES-GEN", "Pres reçetesi",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1}],
            username="patron",
        )
        self.service.create_recipe(
            profile_id, elok_route_id, "RC-ELOKSAL-GEN", "Eloksal reçetesi",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "ELOKSAL", "station": "ELOKSAL 1", "numerator": 1, "denominator": 1},
            ],
            username="patron",
        )
        with closing(self.service.connect()) as connection:
            organization_id = self.service.organization_id(connection)
            condition_id = int(
                connection.execute(
                    """
                    INSERT INTO route_conditions(
                        organization_id, external_source, external_id, code, name, priority, active
                    ) VALUES (?, 'TEST', 'KOSUL-ELOKSAL', 'KOSUL-ELOKSAL', 'Eloksal koşulu', 10, 1)
                    """,
                    (organization_id,),
                ).lastrowid
            )
            connection.execute(
                """
                INSERT INTO route_condition_values(
                    route_condition_id, external_source, external_id,
                    property_external_id, operator, value_text
                ) VALUES (?, 'TEST', 'KOSUL-D-1', 'OZ-YUZEY', '=', 'ELOKSAL')
                """,
                (condition_id,),
            )
            connection.execute(
                """
                INSERT INTO route_condition_routes(
                    route_condition_id, route_id, route_external_id, sequence_no
                ) VALUES (?, ?, 'R-ELOKSAL-GEN', 1)
                """,
                (condition_id, elok_route_id),
            )
            connection.commit()
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "surface": "ELOKSAL", "quantity": 10, "kg": 60}],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.approve_sales_order(order_id, username="planlama")
        production_id = self.service.plan_sales_order_line(
            line_id, planned_quantity=10, planned_kg=60,
            username="planlama",
        )
        with closing(self.service.connect()) as connection:
            selected_route_id = int(
                connection.execute(
                    "SELECT route_id FROM production_orders WHERE id = ?",
                    (production_id,),
                ).fetchone()[0]
            )
        self.assertEqual(selected_route_id, elok_route_id)
        self.assertNotEqual(selected_route_id, pres_route_id)
        operations = [
            row["operation"] for row in self.service.work_orders_for_production(production_id)
        ]
        self.assertEqual(operations, ["PRES ÜRETİM", "ELOKSAL"])

    def test_approve_sales_order_does_not_create_production_orders(self) -> None:
        customer_id = self.service.create_customer("M-APPROVE", "ONAY TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-APPROVE", "ONAY PROFİL", unit_weight_kg_m=1,
            customer_id=customer_id, username="patron",
        )
        route_id = self.service.create_route(
            profile_id, "R-APPROVE", "Onay rotası",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        self.service.create_recipe(
            profile_id, route_id, "RC-APPROVE", "Onay reçetesi",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1}],
            username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 10, "kg": 60}],
            username="satis",
        )
        line_ids = self.service.approve_sales_order(order_id, username="planlama")
        self.assertEqual(len(line_ids), 1)
        self.assertEqual(self.service.table_count("production_orders"), 0)

    def test_recipe_import_preserves_all_lines_and_does_not_invent_steps(self) -> None:
        counts = self.service.import_master_cards(
            customers=[{"code": "M-ALU", "name": "ÖRNEK MÜŞTERİ"}],
            profiles=[
                {
                    "profile_code": "P-ALU",
                    "profile_name": "ÖRNEK PROFİL",
                    "company": "ÖRNEK MÜŞTERİ",
                }
            ],
            dies=[],
            recipes=[
                {
                    "external_id": "REC-42",
                    "recipe_code": "RCP-42",
                    "profile_code": "P-ALU",
                    "stock_name": "PRES + TERMİK REÇETESİ",
                    "route_external_id": "ROTA-9",
                    "route_steps": [
                        {
                            "external_id": "RD-1",
                            "sequence_no": 1,
                            "operation_external_id": "OP-PRES",
                            "operation": "PRES ÜRETİM",
                            "station_external_id": "ST-PRES-1",
                            "station": "PRES 1",
                        },
                        {
                            "external_id": "RD-2",
                            "sequence_no": 2,
                            "operation_external_id": "OP-TERMIK",
                            "operation": "TERMİK ÇIKIŞ",
                            "station_external_id": "ST-TERMIK-1",
                            "station": "TERMİK 1",
                        },
                    ],
                    "detail_lines": [
                        {
                            "external_id": "RECD-1",
                            "operation_external_id": "OP-PRES",
                            "station_external_id": "ST-PRES-1",
                            "process_type": "GİRDİ",
                            "sequence_no": 1,
                            "stock_external_id": "STOK-BILLET",
                            "quantity": 1,
                            "unit_external_id": "KG",
                        },
                        {
                            "external_id": "RECD-2",
                            "operation_external_id": "OP-TERMIK",
                            "station_external_id": "ST-TERMIK-1",
                            "process_type": "ÇIKTI",
                            "sequence_no": 2,
                            "stock_external_id": "STOK-PROFIL",
                            "quantity": 1,
                            "unit_external_id": "KG",
                        },
                    ],
                    "route_conditions": [
                        {
                            "external_id": "KOSUL-1",
                            "name": "Yüzey PRES",
                            "values": [
                                {
                                    "external_id": "KOSUL-D-1",
                                    "property_external_id": "OZ-YUZEY",
                                    "operator": "=",
                                    "value": "PRES",
                                }
                            ],
                        }
                    ],
                }
            ],
            username="aktarim",
        )
        self.assertEqual(counts["recipes"], 1)
        self.assertEqual(counts["recipe_lines"], 2)
        self.assertEqual(counts["route_conditions"], 1)
        with closing(self.service.connect()) as connection:
            operations = [
                row[0]
                for row in connection.execute(
                    "SELECT operation FROM route_steps ORDER BY sequence_no"
                )
            ]
            recipe_line_count = connection.execute(
                "SELECT COUNT(*) FROM recipe_lines"
            ).fetchone()[0]
        self.assertEqual(operations, ["PRES ÜRETİM", "TERMİK ÇIKIŞ"])
        self.assertNotIn("PAKETLEME", operations)
        self.assertEqual(recipe_line_count, 2)

    def test_branch_warehouse_and_negative_stock_policy_are_relational(self) -> None:
        self.assertEqual(self.service.list_branches()[0]["code"], "FABRIKA")
        branch_id = self.service.create_branch(
            "DEPO-1", "Harici Depo", city="İzmir", username="patron"
        )
        warehouse_id = self.service.create_warehouse(
            "TEST-DEPO", "Test Deposu", warehouse_type="SARF",
            branch_id=branch_id, negative_stock_policy="ENGELLE",
            username="patron",
        )
        warehouse = next(
            row for row in self.service.list_warehouses() if row["id"] == warehouse_id
        )
        self.assertEqual(warehouse["branch_code"], "DEPO-1")
        self.assertEqual(warehouse["negative_stock_policy"], "ENGELLE")
        stock_id = self.service.create_stock_item(
            "TEST-001", "POLİTİKA TESTİ", stock_group="SARF", unit="ADET",
            username="depo",
        )
        with closing(self.service.connect()) as connection:
            organization_id = self.service.organization_id(connection)
            with self.assertRaisesRegex(sqlite3.IntegrityError, "NEGATIVE_STOCK_BLOCKED"):
                connection.execute(
                    """
                    INSERT INTO stock_movements(
                        organization_id, stock_item_id, warehouse_id, movement_type,
                        direction, quantity, lot_no, document_no, created_by
                    ) VALUES (?, ?, ?, 'TEST ÇIKIŞ', -1, 1, '', 'TEST-1', 'depo')
                    """,
                    (organization_id, stock_id, warehouse_id),
                )
            connection.execute(
                """
                INSERT INTO stock_movements(
                    organization_id, stock_item_id, warehouse_id, movement_type,
                    direction, quantity, lot_no, document_no, created_by
                ) VALUES (?, ?, ?, 'TEST GİRİŞ', 1, 10, '', 'TEST-2', 'depo')
                """,
                (organization_id, stock_id, warehouse_id),
            )
            connection.execute(
                """
                INSERT INTO stock_movements(
                    organization_id, stock_item_id, warehouse_id, movement_type,
                    direction, quantity, lot_no, document_no, created_by
                ) VALUES (?, ?, ?, 'TEST ÇIKIŞ', -1, 10, '', 'TEST-3', 'depo')
                """,
                (organization_id, stock_id, warehouse_id),
            )
            connection.commit()

    def test_stock_document_transfer_is_atomic_and_respects_negative_policy(self) -> None:
        branch_id = self.service.list_branches()[0]["id"]
        source_id = self.service.create_warehouse(
            "DEPO-KAYNAK", "Kaynak Depo", warehouse_type="HAMMADDE",
            branch_id=branch_id, negative_stock_policy="İZİN", username="depo",
        )
        target_id = self.service.create_warehouse(
            "DEPO-HEDEF", "Hedef Depo", warehouse_type="YARI MAMUL",
            branch_id=branch_id, negative_stock_policy="ENGELLE", username="depo",
        )
        stock_id = self.service.create_stock_item(
            "HM-6063", "6063 BİLLET", stock_group="HAMMADDE", unit="KG",
            tracks_lot=True, username="depo",
        )
        incoming_id = self.service.create_stock_document(
            document_type="GİRİŞ", document_date="2026-08-04",
            target_warehouse_id=source_id, reference_no="IRS-1",
            lines=[{"stock_item_id": stock_id, "quantity": 100, "lot_no": "SARJ-1"}],
            username="depo",
        )
        transfer_id = self.service.create_stock_document(
            document_type="TRANSFER", document_date="2026-08-04",
            source_warehouse_id=source_id, target_warehouse_id=target_id,
            lines=[{"stock_item_id": stock_id, "quantity": 60, "lot_no": "SARJ-1"}],
            username="depo",
        )
        self.assertEqual(len(self.service.list_stock_document_lines(incoming_id)), 1)
        self.assertEqual(len(self.service.list_stock_document_lines(transfer_id)), 1)
        balances = {
            (row["warehouse_code"], row["lot_no"]): row["balance"]
            for row in self.service.list_warehouse_balances()
            if row["stock_code"] == "HM-6063"
        }
        self.assertAlmostEqual(balances[("DEPO-KAYNAK", "SARJ-1")], 40.0)
        self.assertAlmostEqual(balances[("DEPO-HEDEF", "SARJ-1")], 60.0)

        self.service.update_warehouse_policy(
            source_id, branch_id=branch_id, negative_stock_policy="ENGELLE",
            allow_mixed_lots=True, active=True, username="patron",
        )
        with self.assertRaisesRegex(ValueError, "negatif stok"):
            self.service.create_stock_document(
                document_type="TRANSFER", document_date="2026-08-04",
                source_warehouse_id=source_id, target_warehouse_id=target_id,
                lines=[{"stock_item_id": stock_id, "quantity": 50, "lot_no": "SARJ-1"}],
                username="depo",
            )
        self.assertEqual(len(self.service.list_stock_documents()), 2)
        balances = {
            (row["warehouse_code"], row["lot_no"]): row["balance"]
            for row in self.service.list_warehouse_balances()
            if row["stock_code"] == "HM-6063"
        }
        self.assertAlmostEqual(balances[("DEPO-KAYNAK", "SARJ-1")], 40.0)
        self.assertAlmostEqual(balances[("DEPO-HEDEF", "SARJ-1")], 60.0)

    def test_fis_numarasi_formati(self) -> None:
        with closing(self.service.connect()) as connection:
            first = self.service._next_no(connection, "R")
            second = self.service._next_no(connection, "R")
            work_order = self.service._next_no(connection, "IE")
        self.assertRegex(first, r"^R\d{9}$")
        self.assertRegex(second, r"^R\d{9}$")
        self.assertNotEqual(first, second)
        self.assertEqual(int(second[-7:]), int(first[-7:]) + 1)
        self.assertRegex(work_order, r"^\d{8}$")
        next_order_preview = self.service.peek_next_no("R")

        customer_id = self.service.create_customer(
            "MUS-FIS", "FİŞ TEST", username="patron"
        )
        profile_id = self.service.create_profile(
            "PRF-FIS", "TEST PROFİL", unit_weight_kg_m=1.0, username="patron"
        )
        self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id,
                "length_mm": 6000,
                "quantity": 100,
                "kg": 500,
            }],
            username="patron",
            customer_document_no="BLG-001",
            msp="MSP-01",
        )
        row = self.service.list_sales_orders()[0]
        self.assertEqual(row["order_no"], next_order_preview)
        self.assertEqual(row["revision_display"], "00")
        self.assertIn("progress_pct", row)
        self.assertIn("pending_kg", row)
        self.assertIn("delivery_week", row)
        self.assertIn("branch_name", row)
        self.assertIn("order_approval", row)
        self.assertIn("close_status", row)
        self.assertEqual(row["currency_display"], "TL")

    def test_sales_order_list_columns_match_expected_headers(self) -> None:
        expected_headers = (
            "%", "FİŞ NO", "REV. NO", "BELGE NO", "MSP", "FİRMA", "TARİH",
            "TESLİM TARİHİ", "TESLİM HFT.", "TESLİM YILI", "SİPARİŞ KG", "SEVK KG",
            "BEKLEYEN KG", "TOPLAM", "DÖVİZLİ TOPLAM", "DÖVİZ", "USD TOPLAM",
            "ŞUBE", "AMBAR", "KULLANICI", "TEMSİLCİ", "ONAY", "ÜRETİM ONAY",
            "ONAY AÇIKLAMASI", "KAPANMA DURUM", "SİPARİŞ DURUM",
        )
        rigel_labels = [
            label for _key, label in WorkflowPage.COLUMNS["orders_grid"]
        ]
        self.assertEqual(rigel_labels, list(expected_headers))

    def test_faz2_column_headers(self) -> None:
        self.assertEqual(
            [label for _key, label in WorkflowPage.COLUMNS["purchase_requests_grid"]][0],
            "FİŞ NO",
        )
        self.assertEqual(
            [label for _key, label in WorkflowPage.COLUMNS["stock_items_grid"]][0],
            "STOK KOD",
        )
        self.assertIn(
            "BEKLEYEN",
            [label for _key, label in WorkflowPage.COLUMNS["purchase_orders_grid"]],
        )

    def test_purchase_pending_views_filter_records(self) -> None:
        stock_id = self.service.create_stock_item(
            "HM-F2", "FAZ2 HAMMADDE", stock_group="HAMMADDE", unit="KG", username="depo",
        )
        request_id = self.service.create_purchase_request(
            request_date="2026-08-05",
            lines=[{"stock_item_id": stock_id, "quantity": 100, "warehouse_code": "HAMMADDE"}],
            username="depo",
        )
        all_requests = self.service.list_purchase_requests()
        self.assertEqual(len(all_requests), 1)
        self.assertEqual(all_requests[0]["approval_display"], "BEKLİYOR")
        self.service.approve_purchase_request(request_id, username="patron")
        approved = self.service.list_purchase_requests()[0]
        self.assertEqual(approved["approval_display"], "KABUL")
        order_id = self.service.create_purchase_order_from_request(
            request_id,
            self.service.create_supplier("TED-F2", "FAZ2 TEDARİK", username="satinalma"),
            order_date="2026-08-05",
            username="satinalma",
        )
        orders = self.service.list_purchase_orders()
        self.assertEqual(len(orders), 1)
        self.assertGreater(float(orders[0]["pending_quantity"]), 0)
        self.service.receive_purchase_order(
            order_id, receipt_date="2026-08-06", username="depo", lot_no="LOT-F2",
            quantities={int(self.service.list_purchase_order_lines(order_id)[0]["id"]): 100},
        )
        purchase_moves = self.service.list_stock_movements(
            movement_types=["SATIN ALMA MAL KABUL"],
        )
        self.assertEqual(len(purchase_moves), 1)
        self.assertEqual(purchase_moves[0]["movement_type"], "SATIN ALMA MAL KABUL")


class LocalWorkflowUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "rigel_operations.db"
        self.service = LocalWorkflowService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    _create_approved_order = LocalWorkflowTests._create_approved_order

    def test_connected_page_reads_same_relational_workflow(self) -> None:
        _order_id, _production_id, _die_id = self._create_approved_order()
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Satış", "Satış Siparişleri")
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.view, "orders")
        page.set_context("Üretim", "İş Emirleri")
        self.assertEqual(page.table.rowCount(), 3)
        self.assertEqual(page.records[0]["status"], "HAZIR")
        page.set_context("Sevkiyat", "Hazır Kasalar")
        self.assertEqual(page.table.rowCount(), 0)
        page.close()

    def test_stock_document_dialog_and_page_are_connected(self) -> None:
        stock_id = self.service.create_stock_item(
            "SARF-001", "TEST SARF", stock_group="SARF", unit="ADET",
            username="depo",
        )
        dialog = StockDocumentDialog(self.service)
        dialog.document_type.setCurrentText("GİRİŞ")
        dialog.target.setCurrentIndex(1)
        dialog.stock.setCurrentIndex(dialog.stock.findData(stock_id))
        dialog.quantity.setValue(25)
        dialog.add_line()
        self.assertEqual(len(dialog.rows), 1)
        dialog.close()

        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Malzeme Yönetimi", "Stok Fişleri")
        self.assertEqual(page.view, "stock_documents")
        self.assertEqual(page.primary.text(), "＋ YENİ STOK FİŞİ")
        self.assertIn("Ekle", page.context_action_texts())
        page.close()

    def test_workflow_tables_offer_context_specific_right_click_actions(self) -> None:
        self._create_approved_order()
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Satış", "Satış Siparişleri")
        order_actions = page.context_action_texts()
        self.assertIn("Değiştir", order_actions)
        self.assertIn("Sipariş Onay", order_actions)
        self.assertIn("Kopyasını Oluştur", order_actions)
        self.assertIn("Üretim Onay", order_actions)
        self.assertIn("Bağlı Çeki Listeleri", order_actions)
        self.assertIn("Sütunları Sıfırla", order_actions)
        self.assertGreaterEqual(len(order_actions), 25)
        page.set_context("Üretim", "İstasyon Yükleri")
        self.assertEqual(page.table.contextMenuPolicy(), Qt.CustomContextMenu)
        self.assertIn("Operatör Üretim Fişi", page.context_action_texts())
        self.assertIn("Öncelik Değiştir", page.context_action_texts())
        page.set_context("Kalıphane", "Kalıp Kartları")
        self.assertIn("Kalıp Hareketi Gir", page.context_action_texts())
        self.assertIn("Dokümanlar", page.context_action_texts())
        page.set_context("Satış", "Satış İrsaliyeleri")
        self.assertEqual(page.view, "shipments")
        self.assertIn("Faturala", page.context_action_texts())
        page.set_context("Satış", "Müşteriler")
        self.assertIn("Ekle", page.context_action_texts())
        self.assertIn("Değiştir", page.context_action_texts())
        self.assertIn("Pasife Al / Aktifleştir", page.context_action_texts())
        page.close()

    def test_profile_card_belongs_to_installed_factory(self) -> None:
        dialog = ProfileRouteDialog(self.service)
        self.assertEqual(dialog.organization.text(), "Rigel Alüminyum")
        self.assertFalse(hasattr(dialog, "customer"))
        dialog.close()

    def test_station_loads_have_date_and_warehouse_filters(self) -> None:
        self._create_approved_order()
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Üretim", "İstasyon Yükleri")
        self.assertFalse(page.station_filter_bar.isHidden())
        options = [
            page.warehouse_filter.itemText(index)
            for index in range(page.warehouse_filter.count())
        ]
        self.assertTrue(any("Termik Giriş" in option for option in options))
        self.assertTrue(any("Termik Çıkış" in option for option in options))
        page.warehouse_filter.setCurrentIndex(
            page.warehouse_filter.findData("HAMMADDE")
        )
        self.assertEqual(page.table.rowCount(), 1)
        page.close()

    def test_press_dialog_calculates_read_only_input_output(self) -> None:
        dialog = ProductionEntryDialog(
            {
                "work_order_no": "IE-TEST",
                "customer_name": "AKSEKİ YAPI",
                "profile_code": "1100",
                "operation": "PRES ÜRETİM",
                "station": "PRES 1",
                "planned_quantity": 100,
                "planned_kg": 393,
                "unit_weight_kg_m": 0.655,
                "production_length_mm": 6000,
            }
        )
        dialog.billet_count.setValue(9)
        self.assertAlmostEqual(dialog.metre.value(), 600.0, places=2)
        self.assertAlmostEqual(dialog.net.value(), 393.0, places=2)
        self.assertAlmostEqual(dialog.billet_length.value(), 914.0, places=0)
        self.assertTrue(dialog.net.isReadOnly())
        self.assertTrue(dialog.gross.isReadOnly())
        dialog.resize(520, 400)
        self.app.processEvents()
        self.assertLessEqual(dialog.width(), 540)
        dialog.close()

    def test_customer_dialog_can_shrink_and_scroll(self) -> None:
        dialog = CustomerDialog()
        dialog.resize(520, 400)
        self.app.processEvents()
        self.assertLessEqual(dialog.width(), 540)
        self.assertLessEqual(dialog.height(), 420)
        dialog.close()

    def test_customer_card_can_be_updated_and_safely_deactivated(self) -> None:
        customer_id = self.service.create_customer(
            "M-100", "İLK FİRMA", city="İZMİR", currency="EUR", username="patron"
        )
        self.service.update_customer(
            customer_id,
            code="M-100",
            name="GÜNCEL FİRMA",
            city="MANİSA",
            phone="0232 000 00 00",
            currency="USD",
            username="patron",
        )
        customer = self.service.customer(customer_id)
        self.assertEqual(customer["name"], "GÜNCEL FİRMA")
        self.assertEqual(customer["city"], "MANİSA")
        self.assertEqual(customer["currency"], "USD")

        self.service.set_customer_active(customer_id, False, username="patron")
        self.assertEqual(self.service.list_customers(), [])
        inactive = self.service.list_customers(include_inactive=True)
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]["active"], 0)

        self.service.set_customer_active(customer_id, True, username="patron")
        self.assertEqual(len(self.service.list_customers()), 1)

    def test_corporate_customer_card_keeps_multiple_contacts(self) -> None:
        customer_id = self.service.create_customer(
            "M-200", "ÖRNEK SANAYİ VE TİCARET A.Ş.", short_name="ÖRNEK",
            tax_office="KONAK", tax_number="1234567890", sector="ALÜMİNYUM",
            district="KEMALPAŞA", phone2="0232 111 22 33", fax="0232 111 22 34",
            order_note="Paletli sevk", is_supplier=True,
            contacts=[
                {"name": "AYŞE YILMAZ", "role": "SATIN ALMA", "phone1": "5551"},
                {"name": "MEHMET DEMİR", "role": "MUHASEBE", "email": "m@example.com"},
            ],
            username="patron",
        )
        customer = self.service.customer(customer_id)
        self.assertEqual(customer["short_name"], "ÖRNEK")
        self.assertEqual(customer["sector"], "ALÜMİNYUM")
        self.assertEqual(customer["is_supplier"], 1)
        contacts = self.service.list_customer_contacts(customer_id)
        self.assertEqual([row["role"] for row in contacts], ["SATIN ALMA", "MUHASEBE"])

        self.service.update_customer(
            customer_id, username="patron",
            contacts=[{"name": "ALİ KAYA", "role": "KALİTE", "phone1": "5552"}],
        )
        contacts = self.service.list_customer_contacts(customer_id)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["name"], "ALİ KAYA")

    def test_sales_order_kg_is_automatic_from_quantity_length_and_profile_weight(self) -> None:
        customer_id = self.service.create_customer("M-300", "KG TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-300", "TEST PROFİL", unit_weight_kg_m=1.25,
            customer_id=customer_id, username="patron",
        )
        self.service.create_die(
            profile_id, "K-300", tenefer_no="TN-10", tenefer_type="STANDART",
            tenefer_limit_m=50_000, username="patron",
        )
        self.service.create_route(
            profile_id, "R-300", "TEST ROTASI",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        dialog = SalesOrderDialog(self.service)
        dialog.profile.setCurrentIndex(dialog.profile.findData(profile_id))
        dialog.length.setValue(6000)
        dialog.quantity.setValue(100)
        self.assertTrue(dialog.kg.isReadOnly())
        self.assertAlmostEqual(dialog.kg.value(), 750.0)
        dialog.close()

        die = self.service.list_dies(profile_id)[0]
        self.assertEqual(die["tenefer_no"], "TN-10")
        self.assertEqual(die["tenefer_limit_m"], 50_000)

    def test_one_order_line_can_be_split_and_recipe_ratios_plan_each_station(self) -> None:
        customer_id = self.service.create_customer("M-400", "PLAN TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-400", "PLAN PROFİL", unit_weight_kg_m=1.0,
            customer_id=customer_id, username="patron",
        )
        die_id = self.service.create_die(
            profile_id, "K-400", compatible_stations=["PRES 1"], username="patron"
        )
        route_id = self.service.create_route(
            profile_id, "R-400", "PRES TERMİK ROTASI",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "input_warehouse": "PRES", "output_warehouse": "TERMIK"},
            ],
            username="patron", production_length_mm=6000, surface="PRES",
        )
        recipe_id = self.service.create_recipe(
            profile_id, route_id, "RC-400", "PRES TERMİK REÇETESİ",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 105, "denominator": 100},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 98, "denominator": 100},
            ],
            username="patron", production_length_mm=6000,
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "die_id": die_id, "length_mm": 6000, "surface": "PRES", "quantity": 100, "kg": 500}],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        first = self.service.plan_sales_order_line(
            line_id, planned_quantity=40, planned_kg=200,
            route_id=route_id, username="planlama",
        )
        second = self.service.plan_sales_order_line(
            line_id, planned_quantity=60, planned_kg=300,
            route_id=route_id, username="planlama",
        )
        self.assertNotEqual(first, second)
        first_steps = self.service.work_orders_for_production(first)
        self.assertAlmostEqual(first_steps[0]["planned_quantity"], 42.0)
        self.assertAlmostEqual(first_steps[0]["planned_kg"], 210.0)
        self.assertAlmostEqual(first_steps[1]["planned_quantity"], 39.2)
        self.assertAlmostEqual(first_steps[1]["planned_kg"], 196.0)
        self.assertEqual(first_steps[0]["recipe_line_id"], self.service.list_recipe_lines(recipe_id)[0]["id"])
        planning = self.service.list_order_lines_for_planning()[0]
        self.assertAlmostEqual(planning["remaining_quantity"], 0.0)
        self.assertAlmostEqual(planning["remaining_kg"], 0.0)
        self.assertEqual(planning["production_order_count"], 2)
        self.assertEqual(self.service.approve_sales_order(order_id, username="planlama"), [line_id])

    def test_incompatible_die_cannot_be_planned_on_press(self) -> None:
        customer_id = self.service.create_customer("M-500", "KALIP TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-500", "KALIP PROFİL", unit_weight_kg_m=1,
            customer_id=customer_id, username="patron",
        )
        die_id = self.service.create_die(
            profile_id, "K-500", compatible_stations=["PRES 2"], username="patron"
        )
        self.service.create_route(
            profile_id, "R-500", "PRES 1 ROTASI",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"}],
            username="patron",
        )
        route_id = self.service.list_routes(profile_id)[0]["id"]
        self.service.create_recipe(
            profile_id, route_id, "RC-500", "Pres reçetesi",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1}],
            username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "die_id": die_id, "length_mm": 6000, "quantity": 10, "kg": 60}],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.approve_sales_order(order_id, username="planlama")
        with self.assertRaisesRegex(ValueError, "istasyonunda çalışmaya tanımlı değil"):
            self.service.plan_sales_order_line(
                line_id, planned_quantity=10, planned_kg=60,
                route_id=route_id, username="planlama",
            )

    def test_customer_multiple_addresses_link_to_sales_order(self) -> None:
        customer_id = self.service.create_customer(
            "M-600", "ADRES TEST", username="patron",
            addresses=[
                {"name": "MERKEZ", "city": "İZMİR", "address": "Sanayi Cad. 1"},
                {"name": "FABRİKA", "city": "MANİSA", "address": "OSB 2. Kısım"},
            ],
        )
        addresses = self.service.list_customer_addresses(customer_id)
        self.assertEqual([row["name"] for row in addresses], ["FABRİKA", "MERKEZ"])
        profile_id = self.service.create_profile(
            "P-600", "ADRES PROFİL", unit_weight_kg_m=1,
            customer_id=customer_id, username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            delivery_address_id=addresses[0]["id"],
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 10, "kg": 60}],
            username="satis",
        )
        with closing(self.service.connect()) as connection:
            selected = connection.execute(
                "SELECT delivery_address_id FROM sales_orders WHERE id = ?", (order_id,)
            ).fetchone()[0]
        self.assertEqual(selected, addresses[0]["id"])

    def test_sales_order_crud_and_approval_flow(self) -> None:
        customer_id = self.service.create_customer("M-CRUD", "CRUD TEST", username="patron")
        profile_id = self.service.create_profile(
            "P-CRUD", "CRUD PROFİL", unit_weight_kg_m=1.2, username="patron",
        )
        self.service.create_route(
            profile_id, "R-CRUD", "CRUD rotası",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-25",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 100, "kg": 720, "unit_price": 4.5}],
            username="patron",
            customer_document_no="MUS-001",
            payment_method="VADELİ",
            maturity_days=30,
            contact_name="Ahmet Yılmaz",
            usd_rate=34.5,
            lme_usd_ton=2450,
            note="Test siparişi",
        )
        progress = self.service.order_progress(order_id)
        self.assertEqual(progress["order"]["customer_document_no"], "MUS-001")
        self.assertEqual(progress["order"]["payment_method"], "VADELİ")
        self.assertEqual(int(progress["order"]["maturity_days"]), 30)
        self.assertEqual(progress["order"]["contact_name"], "Ahmet Yılmaz")
        self.assertAlmostEqual(float(progress["order"]["usd_rate"]), 34.5)
        self.assertEqual(progress["order"]["status"], "ONAY BEKLİYOR")

        self.service.confirm_sales_order(order_id, username="patron")
        self.assertEqual(self.service.order_progress(order_id)["order"]["status"], "AÇIK")

        self.service.update_sales_order(
            order_id,
            customer_id,
            order_date="2026-08-06",
            delivery_date="2026-08-26",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 120, "kg": 864, "unit_price": 4.8}],
            username="patron",
            customer_document_no="MUS-001-R",
            note="Güncellendi",
        )
        updated = self.service.order_progress(order_id)
        self.assertEqual(updated["order"]["customer_document_no"], "MUS-001-R")
        self.assertAlmostEqual(float(updated["lines"][0]["ordered_kg"]), 864.0)

        copied_id = self.service.copy_sales_order(order_id, username="patron")
        copied = self.service.order_progress(copied_id)
        self.assertNotEqual(copied["order"]["order_no"], updated["order"]["order_no"])
        self.assertEqual(copied["order"]["customer_document_no"], "MUS-001-R")
        self.assertEqual(copied["order"]["status"], "ONAY BEKLİYOR")

        self.service.delete_sales_order(copied_id, username="patron")
        with self.assertRaises(ValueError):
            self.service.order_progress(copied_id)

        self.service.close_sales_order(order_id, username="patron")
        self.assertEqual(self.service.order_progress(order_id)["order"]["status"], "KAPALI")
        with self.assertRaises(ValueError):
            self.service.update_sales_order(
                order_id,
                customer_id,
                order_date="2026-08-07",
                delivery_date="2026-08-27",
                lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 10, "kg": 72}],
                username="patron",
            )

    def test_recipe_stores_selected_raw_material_for_press_consumption(self) -> None:
        profile_id = self.service.create_profile(
            "P-HM", "Hammadde Profil", unit_weight_kg_m=1.0, username="planlama",
        )
        stock_id = self.service.create_stock_item(
            "HM-6063", "6063 BİLLET", stock_group="HAMMADDE", unit="KG", username="depo",
        )
        route_id = self.service.create_route(
            profile_id, "R-HM", "Hammadde rotası",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="planlama",
        )
        recipe_id = self.service.create_recipe(
            profile_id, route_id, "RC-HM", "Hammadde reçetesi",
            [{
                "operation": "PRES ÜRETİM", "station": "PRES 1",
                "route_sequence_no": 1, "numerator": 1, "denominator": 1,
                "warehouse_code": "SEVK_ON", "unit_code": "KG", "stock_code": "HM-6063",
            }],
            raw_material_stock_code="HM-6063",
            username="planlama",
        )
        recipes = self.service.list_recipes(profile_id)
        self.assertEqual(recipes[0]["raw_material_code"], "HM-6063")
        lines = self.service.list_recipe_lines(recipe_id)
        self.assertEqual(lines[0]["stock_code"], "HM-6063")

    def test_profile_update_and_price_list_apply(self) -> None:
        customer_id = self.service.create_customer(
            "MUS-PL", "Price List Müşteri", username="satis"
        )
        profile_id = self.service.create_profile(
            "PRF-PL", "Fiyat Profili", unit_weight_kg_m=1.0, username="patron"
        )
        self.service.create_die(profile_id, "KLP-PL", username="kaliphane")
        list_id = self.service.create_sales_price_list(
            list_code="FL-TEST",
            list_name="Test Listesi",
            currency="USD",
            username="satis",
        )
        with closing(self.service.connect()) as connection:
            connection.execute(
                """
                INSERT INTO sales_price_list_lines(
                    price_list_id, profile_id, surface, alloy, temper,
                    unit_price, currency
                ) VALUES (?, ?, 'PRES', '6060B', 'T5', 5.75, 'USD')
                """,
                (list_id, profile_id),
            )
            connection.commit()
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id,
                "length_mm": 6000,
                "surface": "PRES",
                "quantity": 100,
                "kg": 500,
                "unit_price": 4.0,
            }],
            username="satis",
        )
        updated = self.service.apply_price_list_to_order(
            order_id, list_id, username="satis"
        )
        self.assertEqual(updated, 1)
        line = self.service.order_progress(order_id)["lines"][0]
        self.assertEqual(float(line["unit_price"]), 5.75)

        self.service.update_profile(
            profile_id,
            profile_name="Güncellenmiş Profil",
            unit_weight_kg_m=1.15,
            alloy="6063B",
            temper="T6",
            username="patron",
        )
        profile = self.service.profile(profile_id)
        self.assertEqual(profile["profile_name"], "Güncellenmiş Profil")
        self.assertAlmostEqual(float(profile["unit_weight_kg_m"]), 1.15)

    def test_maturity_pricing_and_counter_purchase_request(self) -> None:
        customer_id = self.service.create_customer("MUS-MAT", "Maturity Müşteri", username="satis")
        profile_id = self.service.create_profile(
            "PRF-MAT", "Mat Profil", unit_weight_kg_m=1.0, username="patron"
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            payment_method="VADELİ",
            maturity_days=90,
            lines=[{
                "profile_id": profile_id,
                "length_mm": 6000,
                "quantity": 100,
                "kg": 500,
                "unit_price": 10.0,
            }],
            username="satis",
        )
        updated = self.service.apply_maturity_pricing_to_order(
            order_id, annual_rate_pct=12.0, username="satis"
        )
        self.assertEqual(updated, 1)
        new_price = float(self.service.order_progress(order_id)["lines"][0]["unit_price"])
        self.assertGreater(new_price, 10.0)
        request_id = self.service.create_purchase_request_from_sales_order(
            order_id, username="satinalma"
        )
        self.assertGreater(request_id, 0)
        self.assertEqual(len(self.service.list_purchase_requests()), 1)

    def test_recipe_and_planning_modules_use_relational_workflow_pages(self) -> None:
        customer_id = self.service.create_customer("M-700", "UI PLAN", username="patron")
        profile_id = self.service.create_profile(
            "P-700", "UI PROFİL", unit_weight_kg_m=1,
            customer_id=customer_id, username="patron",
        )
        route_id = self.service.create_route(
            profile_id, "R-700", "UI ROTASI",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "SEVK_ON"}],
            username="patron",
        )
        self.service.create_recipe(
            profile_id, route_id, "RC-700", "UI REÇETE",
            [{"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1}],
            username="patron",
        )
        self.service.create_sales_order(
            customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
            lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 10, "kg": 60}],
            username="satis",
        )
        self.assertTrue(WorkflowPage.handles_context("Üretim", "Reçeteler"))
        self.assertTrue(WorkflowPage.handles_context("Üretim", "Üretim Planlama"))
        page = WorkflowPage(username="patron", service=self.service)
        page.set_context("Üretim", "Reçeteler")
        self.assertEqual(page.view, "recipes")
        self.assertEqual(page.table.rowCount(), 1)
        page.set_context("Üretim", "Üretim Planlama")
        self.assertEqual(page.view, "planning")
        self.assertEqual(page.table.rowCount(), 1)
        recipe_dialog = RecipeDialog(self.service)
        stock_dialog = StockItemDialog()
        supplier_dialog = SupplierDialog()
        request_dialog = PurchaseRequestDialog(self.service)
        purchase_order_dialog = PurchaseOrderDialog(self.service)
        goods_receipt_dialog = GoodsReceiptDialog(self.service)
        branch_dialog = BranchDialog()
        warehouse_dialog = WarehouseDialog(self.service)
        recipe_dialog.resize(520, 400)
        plan_dialog = ProductionPlanDialog(self.service)
        plan_dialog.resize(520, 400)
        self.app.processEvents()
        self.assertLessEqual(recipe_dialog.width(), 540)
        self.assertLessEqual(plan_dialog.width(), 540)
        recipe_dialog.close()
        plan_dialog.close()
        stock_dialog.close()
        supplier_dialog.close()
        request_dialog.close()
        purchase_order_dialog.close()
        goods_receipt_dialog.close()
        branch_dialog.close()
        warehouse_dialog.close()
        page.close()


if __name__ == "__main__":
    unittest.main()
