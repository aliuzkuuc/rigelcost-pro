"""Çoklu girdi kombinasyonları — operasyon motoru regresyon matrisi."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from services.local_workflow import LocalWorkflowService
from services.order_line_status import fulfillment_label


def _bootstrap(service: LocalWorkflowService, *, suffix: str) -> tuple[int, int, int, int]:
    customer_id = service.create_customer(
        f"M-{suffix}", f"Müşteri {suffix}", username="test"
    )
    profile_id = service.create_profile(
        f"P-{suffix}",
        f"Profil {suffix}",
        unit_weight_kg_m=0.85 + (len(suffix) % 5) * 0.1,
        username="test",
    )
    die_id = service.create_die(
        profile_id, f"D-{suffix}", username="test", compatible_stations=["PRES 1"]
    )
    route_id = service.create_route(
        profile_id,
        f"R-{suffix}",
        f"Rota {suffix}",
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
                "output_warehouse": "SEVK_ON",
            },
        ],
        username="test",
        surface="PRES",
        alloy="6060B",
        temper="T5",
    )
    service.create_recipe(
        profile_id,
        route_id,
        f"RC-{suffix}",
        f"Reçete {suffix}",
        [
            {
                "operation": "PRES ÜRETİM",
                "station": "PRES 1",
                "route_sequence_no": 1,
                "numerator": 1,
                "denominator": 1,
                "unit_code": "KG",
                "stock_code": "AL-BILLET",
            },
            {
                "operation": "TERMİK ÇIKIŞ",
                "station": "TERMİK 1",
                "route_sequence_no": 2,
                "numerator": 1,
                "denominator": 1,
                "unit_code": "KG",
            },
        ],
        username="test",
        raw_material_stock_code="AL-BILLET",
    )
    return customer_id, profile_id, die_id, route_id


class FulfillmentLabelTests(unittest.TestCase):
    def test_status_matrix(self) -> None:
        cases = (
            (1000, 0, 0, 1000, 0, "SEVK EDİLDİ"),
            (1000, 500, 0, 500, 0, "KISMİ SEVK"),
            (1000, 500, 0, 0, 0, "KISMİ ÜRETİM"),
            (1000, 1000, 0, 0, 0, "ÜRETİLDİ"),
            (1000, 0, 200, 0, 0, "SEVK BEKLİYOR"),
            (1000, 0, 0, 0, 150, "SAHADA"),
            (1000, 0, 0, 0, 0, "ÜRETİLECEK"),
            (0, 100, 0, 0, 0, "KISMİ ÜRETİM"),
        )
        for ordered, produced, ready, shipped, field, expected in cases:
            with self.subTest(
                ordered=ordered, produced=produced, ready=ready,
                shipped=shipped, field=field,
            ):
                self.assertEqual(
                    fulfillment_label(
                        ordered_kg=ordered,
                        produced_kg=produced,
                        ready_kg=ready,
                        shipped_kg=shipped,
                        field_kg=field,
                    ),
                    expected,
                )


class WorkflowInputMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = LocalWorkflowService(Path(self.temp_dir.name) / "variants.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sales_order_quantity_length_surface_matrix(self) -> None:
        variants = [
            {"qty": 50, "kg": 250, "length": 3000, "surface": "PRES", "alloy": "6060B", "temper": "T5"},
            {"qty": 100, "kg": 500, "length": 4000, "surface": "PRES", "alloy": "6063B", "temper": "T6"},
            {"qty": 200, "kg": 1000, "length": 6000, "surface": "ELOKSAL", "alloy": "6060B", "temper": "T5"},
            {"qty": 75, "kg": 375, "length": 5500, "surface": "BOYALI", "alloy": "6082", "temper": "T4"},
            {"qty": 10, "kg": 50, "length": 2000, "surface": "HAM", "alloy": "6060", "temper": "T66"},
            {"qty": 500, "kg": 2500, "length": 6500, "surface": "PRES", "alloy": "6060B", "temper": "T5"},
            {"qty": 1, "kg": 5.5, "length": 1000, "surface": "PRES", "alloy": "6060B", "temper": "T5"},
            {"qty": 320, "kg": 1600, "length": 5800, "surface": "PRES", "alloy": "6063B", "temper": "T5"},
        ]
        for index, variant in enumerate(variants):
            with self.subTest(index=index, **variant):
                customer_id, profile_id, die_id, _route_id = _bootstrap(
                    self.service, suffix=str(index)
                )
                order_id = self.service.create_sales_order(
                    customer_id,
                    order_date="2026-08-05",
                    delivery_date="2026-08-25",
                    currency="USD" if index % 2 == 0 else "EUR",
                    payment_method="VADELİ" if index % 3 == 0 else "PEŞİN",
                    maturity_days=30 if index % 3 == 0 else 0,
                    lines=[{
                        "profile_id": profile_id,
                        "die_id": die_id,
                        "length_mm": variant["length"],
                        "surface": variant["surface"],
                        "alloy": variant["alloy"],
                        "temper": variant["temper"],
                        "quantity": variant["qty"],
                        "kg": variant["kg"],
                        "unit_price": 3.5 + index * 0.1,
                    }],
                    username="satis",
                )
                progress = self.service.order_progress(order_id)
                line = progress["lines"][0]
                self.assertAlmostEqual(float(line["ordered_kg"]), variant["kg"], places=3)
                self.assertEqual(int(line["production_length_mm"]), variant["length"])

    def test_production_partial_and_full_matrix(self) -> None:
        batches = [
            (100, 500),
            (200, 1000),
            (150, 750),
        ]
        for index, (total_qty, total_kg) in enumerate(batches):
            with self.subTest(index=index, qty=total_qty, kg=total_kg):
                customer_id, profile_id, die_id, route_id = _bootstrap(
                    self.service, suffix=f"prod{index}"
                )
                order_id = self.service.create_sales_order(
                    customer_id,
                    order_date="2026-08-05",
                    delivery_date="2026-08-20",
                    lines=[{
                        "profile_id": profile_id,
                        "die_id": die_id,
                        "length_mm": 6000,
                        "quantity": total_qty,
                        "kg": total_kg,
                        "unit_price": 4.0,
                    }],
                    username="satis",
                )
                self.service.approve_sales_order(order_id, username="plan")
                line_id = self.service.order_progress(order_id)["lines"][0]["id"]
                production_id = self.service.plan_sales_order_line(
                    line_id,
                    planned_quantity=total_qty,
                    planned_kg=total_kg,
                    route_id=route_id,
                    username="plan",
                )
                work_orders = self.service.work_orders_for_production(production_id)
                for wo_index, work in enumerate(work_orders):
                    is_press = wo_index == 0
                    self.service.record_work_order_output(
                        work["id"],
                        quantity=total_qty,
                        gross_kg=total_kg * (1.02 if is_press else 1.0),
                        net_kg=total_kg,
                        die_id=die_id if is_press else None,
                        username="op",
                        complete=True,
                    )
                progress = self.service.order_progress(order_id)
                self.assertAlmostEqual(
                    float(progress["lines"][0]["produced_kg"]), total_kg, places=2
                )

    def test_master_data_create_variants(self) -> None:
        for index in range(12):
            with self.subTest(index=index):
                suffix = f"MD{index:02d}"
                self.service.create_request_reason(
                    code=f"RS-{suffix}", name=f"Sebep {index}", username="md"
                )
                self.service.create_service_item_master(
                    code=f"HZ-{suffix}",
                    name=f"Hizmet {index}",
                    unit=["KG", "ADET", "METRE"][index % 3],
                    username="md",
                )
                self.service.create_property_set_master(
                    code=f"PS-{suffix}",
                    name=f"Set {index}",
                    property_kind=["YÜZEY", "RENK", "ALAŞIM"][index % 3],
                    username="md",
                )
                sets = self.service.list_property_sets()
                set_id = next(r["id"] for r in sets if r["code"] == f"PS-{suffix}")
                self.service.create_property_set_value(
                    property_set_id=set_id,
                    code=f"V{index}",
                    name=f"Değer {index}",
                    sort_order=index,
                    username="md",
                )
                list_id = self.service.create_sales_price_list(
                    list_code=f"FL-{suffix}",
                    list_name=f"Liste {index}",
                    currency=["USD", "EUR", "TRY"][index % 3],
                    username="md",
                )
                profile_id = self.service.create_profile(
                    f"PP-{suffix}", f"Fiyat Profil {index}",
                    unit_weight_kg_m=1.0, username="md",
                )
                self.service.create_sales_price_list_line(
                    price_list_id=list_id,
                    profile_id=profile_id,
                    unit_price=2.5 + index * 0.05,
                    surface="PRES",
                    alloy="6060B",
                    temper="T5",
                    username="md",
                )

    def test_price_list_matching_variants(self) -> None:
        customer_id, profile_id, die_id, _ = _bootstrap(self.service, suffix="PL")
        list_id = self.service.create_sales_price_list(
            list_code="FL-MAT", list_name="Matris", currency="USD", username="satis"
        )
        prices = [4.10, 4.25, 4.50, 4.75, 5.00]
        for index, price in enumerate(prices):
            with self.subTest(price=price):
                pid = self.service.create_profile(
                    f"PL-{index}", f"Profil PL {index}",
                    unit_weight_kg_m=1.0, username="satis",
                )
                self.service.create_sales_price_list_line(
                    price_list_id=list_id,
                    profile_id=pid,
                    unit_price=price,
                    surface="PRES",
                    alloy="6060B",
                    temper="T5",
                    username="satis",
                )
                order_id = self.service.create_sales_order(
                    customer_id,
                    order_date="2026-08-05",
                    delivery_date="2026-08-20",
                    lines=[{
                        "profile_id": pid,
                        "die_id": die_id,
                        "length_mm": 6000,
                        "surface": "PRES",
                        "quantity": 100,
                        "kg": 500,
                        "unit_price": 1.0,
                    }],
                    username="satis",
                )
                updated = self.service.apply_price_list_to_order(
                    order_id, list_id, username="satis"
                )
                self.assertEqual(updated, 1)
                applied = float(
                    self.service.order_progress(order_id)["lines"][0]["unit_price"]
                )
                self.assertAlmostEqual(applied, price, places=4)

    def test_invalid_inputs_rejected(self) -> None:
        customer_id, profile_id, _die_id, route_id = _bootstrap(
            self.service, suffix="INV"
        )
        invalid_cases = [
            ("empty_order", lambda: self.service.create_sales_order(
                customer_id, order_date="2026-08-05", delivery_date="2026-08-20",
                lines=[], username="x",
            )),
            ("zero_kg", lambda: self.service.create_sales_order(
                customer_id, order_date="2026-08-05", delivery_date="2026-08-20",
                lines=[{"profile_id": profile_id, "length_mm": 6000, "quantity": 0, "kg": 0}],
                username="x",
            )),
            ("empty_route", lambda: self.service.create_route(
                profile_id, "", "Ad", [], username="x",
            )),
            ("empty_recipe", lambda: self.service.create_recipe(
                profile_id, route_id, "", "Ad", [], username="x",
            )),
            ("bad_price_list", lambda: self.service.apply_price_list_to_order(
                99999, 99999, username="x",
            )),
        ]
        for name, call in invalid_cases:
            with self.subTest(case=name):
                with self.assertRaises((ValueError, OSError)):
                    call()

    def test_document_generation_matrix(self) -> None:
        from reports.shipment_documents import (
            package_label_html,
            shipment_dispatch_html,
            weighing_list_html,
            work_order_slip_html,
        )

        customer_id, profile_id, die_id, route_id = _bootstrap(
            self.service, suffix="DOC"
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id, "die_id": die_id,
                "length_mm": 6000, "quantity": 100, "kg": 500, "unit_price": 4.0,
            }],
            username="satis",
        )
        self.service.approve_sales_order(order_id, username="plan")
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        production_id = self.service.plan_sales_order_line(
            line_id, planned_quantity=100, planned_kg=500,
            route_id=route_id, username="plan",
        )
        for work in self.service.work_orders_for_production(production_id):
            is_press = int(work["sequence_no"]) == 1
            self.service.record_work_order_output(
                work["id"], quantity=100, gross_kg=510 if is_press else 500,
                net_kg=500, die_id=die_id if is_press else None, username="op",
            )
        package_id = self.service.create_package(
            line_id, quantity=100, net_kg=500, gross_kg=510, username="paket"
        )
        wl_id = self.service.create_weighing_list([package_id], username="sevk")
        self.service.create_shipment(
            [package_id], shipment_date="2026-08-05",
            vehicle_plate="34 TEST 1", username="sevk",
        )
        docs = (
            ("weighing", weighing_list_html(
                self.service.weighing_list_document(wl_id)["header"],
                self.service.weighing_list_document(wl_id)["lines"],
            )),
            ("shipment", shipment_dispatch_html(
                self.service.shipment_document(
                    self.service.list_shipments()[0]["id"]
                )["header"],
                self.service.shipment_document(
                    self.service.list_shipments()[0]["id"]
                )["lines"],
            )),
            ("package", package_label_html(
                self.service.package_label_document(package_id)["header"],
                self.service.package_label_document(package_id)["lines"],
            )),
            ("work_order", work_order_slip_html(
                self.service.work_order_document(
                    self.service.list_work_orders()[0]["id"]
                ),
            )),
        )
        for name, html in docs:
            with self.subTest(document=name):
                self.assertIn("<html", html.lower())
                self.assertGreater(len(html), 200)

    def test_order_line_status_recalc_after_shipment(self) -> None:
        for index in range(6):
            with self.subTest(index=index):
                kg = 400 + index * 100
                customer_id, profile_id, die_id, route_id = _bootstrap(
                    self.service, suffix=f"ST{index}"
                )
                order_id = self.service.create_sales_order(
                    customer_id,
                    order_date="2026-08-05",
                    delivery_date="2026-08-20",
                    lines=[{
                        "profile_id": profile_id, "die_id": die_id,
                        "length_mm": 6000, "quantity": 80 + index * 10,
                        "kg": kg, "unit_price": 4.0,
                    }],
                    username="satis",
                )
                self.service.approve_sales_order(order_id, username="plan")
                line_id = self.service.order_progress(order_id)["lines"][0]["id"]
                production_id = self.service.plan_sales_order_line(
                    line_id, planned_quantity=80 + index * 10, planned_kg=kg,
                    route_id=route_id, username="plan",
                )
                for work in self.service.work_orders_for_production(production_id):
                    is_press = int(work["sequence_no"]) == 1
                    self.service.record_work_order_output(
                        work["id"], quantity=80 + index * 10,
                        gross_kg=kg * (1.02 if is_press else 1.0),
                        net_kg=kg, die_id=die_id if is_press else None,
                        username="op",
                    )
                package_id = self.service.create_package(
                    line_id, quantity=80 + index * 10, net_kg=kg,
                    gross_kg=kg * 1.02, username="paket",
                )
                self.service.create_weighing_list([package_id], username="sevk")
                self.service.create_shipment(
                    [package_id], shipment_date="2026-08-05",
                    vehicle_plate=f"34 T{index:03d}", username="sevk",
                )
                count = self.service.recalculate_all_order_line_status()
                self.assertGreaterEqual(count, 1)
                detail = [
                    r for r in self.service.list_sales_order_lines_detail()
                    if int(r["sales_order_id"]) == order_id
                ]
                self.assertEqual(len(detail), 1)
                self.assertAlmostEqual(float(detail[0]["shipped_kg"]), kg, places=2)
                self.assertEqual(detail[0]["fulfillment_status"], "SEVK EDİLDİ")

    def test_sales_quote_create_and_convert(self) -> None:
        customer_id, profile_id, die_id, route_id = _bootstrap(
            self.service, suffix="SQ"
        )
        quote_id = self.service.create_sales_quote(
            customer_id,
            quote_date="2026-08-05",
            valid_until="2026-09-05",
            lines=[{
                "profile_id": profile_id,
                "die_id": die_id,
                "length_mm": 6000,
                "quantity": 100,
                "kg": 500,
                "unit_price": 4.2,
                "surface": "PRES",
                "alloy": "6060B",
                "temper": "T5",
            }],
            currency="EUR",
            exchange_rate=35.5,
            username="satis",
        )
        quote = next(r for r in self.service.list_sales_quotes() if r["id"] == quote_id)
        self.assertEqual(quote["line_count"], 1)
        self.assertAlmostEqual(float(quote["total_amount"]), 2100.0, places=2)
        lines = self.service.list_sales_quote_lines(quote_id)
        self.assertEqual(len(lines), 1)
        order_id = self.service.convert_sales_quote_to_order(
            quote_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            username="satis",
        )
        progress = self.service.order_progress(order_id)
        self.assertAlmostEqual(float(progress["lines"][0]["ordered_kg"]), 500.0)
        quote = next(r for r in self.service.list_sales_quotes() if r["id"] == quote_id)
        self.assertEqual(quote["status"], "SİPARİŞE DÖNÜŞTÜ")

    def test_update_recipe_before_production(self) -> None:
        customer_id, profile_id, die_id, route_id = _bootstrap(
            self.service, suffix="UPDREC"
        )
        recipe_id = self.service.create_recipe(
            profile_id, route_id, "RC-UPD", "ESKİ REÇETE",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
            ],
            username="patron", production_length_mm=6000,
        )
        self.service.update_recipe(
            recipe_id,
            recipe_name="YENİ REÇETE",
            lines=[
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 105, "denominator": 100},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 98, "denominator": 100},
            ],
            production_length_mm=6500,
            saw_allowance_mm=5,
            hanger_allowance_mm=3,
            raw_material_stock_code="AL-BILLET",
            username="patron",
        )
        updated = self.service.get_recipe(recipe_id)
        self.assertEqual(updated["recipe_name"], "YENİ REÇETE")
        self.assertAlmostEqual(float(updated["production_length_mm"]), 6500)
        lines = self.service.list_recipe_lines(recipe_id)
        self.assertAlmostEqual(float(lines[0]["numerator"]), 105)
        self.assertAlmostEqual(float(lines[1]["numerator"]), 98)

    def test_update_route_before_production(self) -> None:
        customer_id, profile_id, die_id, route_id = _bootstrap(
            self.service, suffix="UPDRT"
        )
        self.service.update_route(
            route_id,
            name="GÜNCELLENMİŞ ROTA",
            steps=[
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
            ],
            recipe_name="ANA REÇETE",
            production_length_mm=6000,
            surface="PRES",
            username="patron",
        )
        routes = self.service.list_routes(profile_id)
        self.assertEqual(routes[0]["name"], "GÜNCELLENMİŞ ROTA")
        steps = self.service.list_route_steps(route_id)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1]["operation"], "TERMİK ÇIKIŞ")

    def test_update_recipe_blocked_after_planning(self) -> None:
        customer_id, profile_id, die_id, route_id = _bootstrap(
            self.service, suffix="BLKREC"
        )
        recipe_id = self.service.create_recipe(
            profile_id, route_id, "RC-BLK", "BLOK REÇETE",
            [
                {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
                {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
            ],
            username="patron",
        )
        order_id = self.service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id, "die_id": die_id,
                "length_mm": 6000, "quantity": 100, "kg": 500, "unit_price": 4.0,
            }],
            username="satis",
        )
        line_id = self.service.order_progress(order_id)["lines"][0]["id"]
        self.service.plan_sales_order_line(
            line_id, planned_quantity=100, planned_kg=500,
            route_id=route_id, username="plan",
        )
        with self.assertRaises(ValueError):
            self.service.update_recipe(
                recipe_id,
                recipe_name="DEĞİŞMEZ",
                lines=[
                    {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 2, "denominator": 1},
                    {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
                ],
                username="patron",
            )
        self.service.update_recipe(
            recipe_id,
            recipe_name="SADECE AD",
            lines=None,
            username="patron",
        )
        self.assertEqual(self.service.get_recipe(recipe_id)["recipe_name"], "SADECE AD")

    def test_repeated_order_workflow_iterations(self) -> None:
        """Çoklu farklı girdilerle tekrarlayan E2E akış."""
        lengths = (4000, 5000, 6000, 6500, 7000)
        quantities = (50, 80, 100, 120, 150, 200)
        for iteration in range(24):
            with self.subTest(iteration=iteration):
                length = lengths[iteration % len(lengths)]
                qty = quantities[iteration % len(quantities)]
                kg = round(qty * length / 6000 * 5.0, 3)
                customer_id, profile_id, die_id, route_id = _bootstrap(
                    self.service, suffix=f"IT{iteration}"
                )
                order_id = self.service.create_sales_order(
                    customer_id,
                    order_date="2026-08-05",
                    delivery_date="2026-08-20",
                    lines=[{
                        "profile_id": profile_id, "die_id": die_id,
                        "length_mm": length, "quantity": qty, "kg": kg,
                        "unit_price": 3.5 + (iteration % 5) * 0.1,
                    }],
                    username="satis",
                )
                self.service.approve_sales_order(order_id, username="plan")
                line_id = self.service.order_progress(order_id)["lines"][0]["id"]
                production_id = self.service.plan_sales_order_line(
                    line_id, planned_quantity=qty, planned_kg=kg,
                    route_id=route_id, username="plan",
                )
                work_orders = self.service.work_orders_for_production(production_id)
                for work in work_orders:
                    is_press = int(work["sequence_no"]) == 1
                    self.service.record_work_order_output(
                        work["id"], quantity=qty,
                        gross_kg=kg * (1.02 if is_press else 1.0),
                        net_kg=kg, die_id=die_id if is_press else None,
                        username="op",
                    )
                progress = self.service.order_progress(order_id)
                self.assertAlmostEqual(
                    float(progress["lines"][0]["produced_kg"]), kg, places=2
                )


if __name__ == "__main__":
    unittest.main()
