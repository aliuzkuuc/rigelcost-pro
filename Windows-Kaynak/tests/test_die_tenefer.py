"""Kalıp / tenefer ömrü — üretim, hareket ve sevkiyat testleri."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from services.local_workflow import LocalWorkflowService


def _full_setup(
    service: LocalWorkflowService,
    *,
    suffix: str,
    figure_count: int = 1,
    tenefer_no: str = "1",
    tenefer_limit_m: float = 0,
) -> tuple[int, int, int, int]:
    customer_id = service.create_customer(f"M-{suffix}", f"Müşteri {suffix}", username="test")
    profile_id = service.create_profile(
        f"P-{suffix}", f"Profil {suffix}", unit_weight_kg_m=1.0, username="test",
    )
    die_id = service.create_die(
        profile_id,
        f"K-{suffix}",
        figure_count=figure_count,
        tenefer_no=tenefer_no,
        tenefer_type="STANDART",
        tenefer_limit_m=tenefer_limit_m,
        life_limit_kg=500_000,
        compatible_stations=["PRES 1"],
        username="test",
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
    )
    service.create_recipe(
        profile_id,
        route_id,
        f"RC-{suffix}",
        f"Reçete {suffix}",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1,
             "stock_code": "AL-BILLET"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
        ],
        username="test",
        raw_material_stock_code="AL-BILLET",
    )
    return customer_id, profile_id, die_id, route_id


def _produce_line(
    service: LocalWorkflowService,
    *,
    customer_id: int,
    profile_id: int,
    die_id: int,
    route_id: int,
    length_mm: float,
    quantity: float,
    kg: float,
    suffix: str,
) -> tuple[int, int]:
    order_id = service.create_sales_order(
        customer_id,
        order_date="2026-08-06",
        delivery_date="2026-08-20",
        lines=[{
            "profile_id": profile_id,
            "die_id": die_id,
            "length_mm": length_mm,
            "quantity": quantity,
            "kg": kg,
            "unit_price": 4.0,
        }],
        username="satis",
    )
    service.approve_sales_order(order_id, username="plan")
    line_id = service.order_progress(order_id)["lines"][0]["id"]
    production_id = service.plan_sales_order_line(
        line_id,
        planned_quantity=quantity,
        planned_kg=kg,
        route_id=route_id,
        username="plan",
    )
    work_orders = service.work_orders_for_production(production_id)
    press = work_orders[0]
    metre = quantity * (length_mm / 1000.0)
    service.record_work_order_output(
        press["id"],
        quantity=quantity,
        gross_kg=kg * 1.02,
        net_kg=kg,
        metre=metre,
        die_id=die_id,
        username="op",
    )
    for work in work_orders[1:]:
        service.record_work_order_output(
            work["id"],
            quantity=quantity,
            gross_kg=kg,
            net_kg=kg,
            username="op",
        )
    return order_id, line_id


class DieTeneferStandardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = LocalWorkflowService(Path(self.temp_dir.name) / "die_tenefer.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_tenefer_standard_limits_seeded(self) -> None:
        with self.service.connect() as connection:
            row1 = connection.execute(
                "SELECT limit_m FROM tenefer_life_standards WHERE tenefer_no = 1"
            ).fetchone()
            row2 = connection.execute(
                "SELECT limit_m FROM tenefer_life_standards WHERE tenefer_no = 2"
            ).fetchone()
        self.assertAlmostEqual(float(row1["limit_m"]), 2000.0)
        self.assertAlmostEqual(float(row2["limit_m"]), 3000.0)

    def test_create_die_applies_standard_tenefer_limit(self) -> None:
        _, profile_id, _, _ = _full_setup(
            self.service, suffix="STD", tenefer_no="1", tenefer_limit_m=0,
        )
        die = self.service.list_dies(profile_id)[0]
        self.assertAlmostEqual(float(die["tenefer_limit_m"]), 2000.0)

    def test_production_increments_tenefer_by_figure_times_metre(self) -> None:
        customer_id, profile_id, die_id, route_id = _full_setup(
            self.service, suffix="FIG2", figure_count=2, tenefer_no="1",
        )
        _produce_line(
            self.service,
            customer_id=customer_id,
            profile_id=profile_id,
            die_id=die_id,
            route_id=route_id,
            length_mm=6000,
            quantity=100,
            kg=500,
            suffix="FIG2",
        )
        die = next(d for d in self.service.list_dies() if d["id"] == die_id)
        expected_metre = 100 * 6.0 * 2
        self.assertAlmostEqual(float(die["used_kg"]), 500.0, places=2)
        self.assertAlmostEqual(float(die["tenefer_used_m"]), expected_metre, places=2)
        movements = self.service.list_die_movements(die_id)
        prod_moves = [m for m in movements if m["movement_type"] == "ÜRETİM"]
        self.assertEqual(len(prod_moves), 1)
        self.assertAlmostEqual(float(prod_moves[0]["metre"]), expected_metre, places=2)

    def test_tenefer_send_and_receive_resets_usage_and_updates_limit(self) -> None:
        customer_id, profile_id, die_id, route_id = _full_setup(
            self.service, suffix="TNFR", figure_count=1, tenefer_no="1",
        )
        _produce_line(
            self.service,
            customer_id=customer_id,
            profile_id=profile_id,
            die_id=die_id,
            route_id=route_id,
            length_mm=6000,
            quantity=50,
            kg=250,
            suffix="TNFR",
        )
        die_before = next(d for d in self.service.list_dies() if d["id"] == die_id)
        self.assertGreater(float(die_before["tenefer_used_m"]), 0)
        self.service.send_die_to_tenefer(
            die_id, company="TENEFERCI AŞ", username="kaliphane",
        )
        die_out = next(d for d in self.service.list_dies() if d["id"] == die_id)
        self.assertEqual(int(die_out["is_external"]), 1)
        self.assertEqual(die_out["external_company"], "TENEFERCI AŞ")
        self.assertEqual(die_out["status"], "DIŞARIDA")
        self.service.receive_die_from_tenefer(
            die_id,
            company="TENEFERCI AŞ",
            new_tenefer_no="2",
            username="kaliphane",
        )
        die_back = next(d for d in self.service.list_dies() if d["id"] == die_id)
        self.assertEqual(die_back["tenefer_no"], "2")
        self.assertAlmostEqual(float(die_back["tenefer_used_m"]), 0.0)
        self.assertAlmostEqual(float(die_back["tenefer_limit_m"]), 3000.0)
        self.assertEqual(int(die_back["is_external"]), 0)
        self.assertEqual(die_back["status"], "ARŞİVDE")
        self.assertAlmostEqual(float(die_back["tenefer_remaining_m"]), 3000.0)
        self.assertEqual(die_back["last_movement"], "TENEFER GELDİ")
        docs = self.service.list_tenefer_documents(die_id)
        self.assertEqual(len(docs), 2)
        self.assertEqual({d["direction"] for d in docs}, {"GİDEN", "GELEN"})
        # Dışarıdaki kalıba üretim girilemez
        self.service.send_die_to_tenefer(
            die_id, company="TENEFERCI AŞ", username="kaliphane",
        )
        with self.assertRaises(ValueError):
            _produce_line(
                self.service,
                customer_id=customer_id,
                profile_id=profile_id,
                die_id=die_id,
                route_id=route_id,
                length_mm=6000,
                quantity=10,
                kg=50,
                suffix="BLOCK",
            )

    def test_full_flow_order_produce_ship_then_die_counters(self) -> None:
        customer_id, profile_id, die_id, route_id = _full_setup(
            self.service, suffix="FULL", figure_count=2, tenefer_no="1",
        )
        order_id, line_id = _produce_line(
            self.service,
            customer_id=customer_id,
            profile_id=profile_id,
            die_id=die_id,
            route_id=route_id,
            length_mm=6000,
            quantity=80,
            kg=400,
            suffix="FULL",
        )
        package_id = self.service.create_package(
            line_id, quantity=80, net_kg=400, gross_kg=408, username="paket",
        )
        self.service.create_weighing_list([package_id], username="sevk")
        self.service.create_shipment(
            [package_id],
            shipment_date="2026-08-06",
            vehicle_plate="34 DIE 1",
            username="sevk",
        )
        die = next(d for d in self.service.list_dies() if d["id"] == die_id)
        self.assertAlmostEqual(float(die["used_kg"]), 400.0, places=2)
        self.assertAlmostEqual(float(die["tenefer_used_m"]), 80 * 6.0 * 2, places=2)
        progress = self.service.order_progress(order_id)
        self.assertAlmostEqual(float(progress["lines"][0]["produced_kg"]), 400.0, places=2)

    def test_massive_production_matrix(self) -> None:
        """Çoklu boy/adet/figür kombinasyonları — tenefer metre doğrulama."""
        lengths = (4000, 5000, 6000, 6500, 7000, 7500)
        quantities = (20, 40, 60, 80, 100, 120, 150)
        figures = (1, 2, 3)
        iteration = 0
        for length in lengths:
            for qty in quantities:
                for figure in figures:
                    iteration += 1
                    with self.subTest(iteration=iteration, length=length, qty=qty, figure=figure):
                        customer_id, profile_id, die_id, route_id = _full_setup(
                            self.service,
                            suffix=f"M{iteration}",
                            figure_count=figure,
                            tenefer_no=str((iteration % 3) + 1),
                        )
                        kg = round(qty * length / 6000 * 5.0, 3)
                        _produce_line(
                            self.service,
                            customer_id=customer_id,
                            profile_id=profile_id,
                            die_id=die_id,
                            route_id=route_id,
                            length_mm=length,
                            quantity=qty,
                            kg=kg,
                            suffix=f"M{iteration}",
                        )
                        die = next(
                            d for d in self.service.list_dies()
                            if d["id"] == die_id
                        )
                        expected_m = qty * (length / 1000.0) * figure
                        self.assertAlmostEqual(
                            float(die["tenefer_used_m"]), expected_m, places=2,
                            msg=f"iter={iteration} figure={figure}",
                        )
                        self.assertAlmostEqual(float(die["used_kg"]), kg, places=2)


if __name__ == "__main__":
    unittest.main()
