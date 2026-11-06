#!/usr/bin/env python3
"""RigelCost uçtan uca operasyon duman testi — CI ve gece kontrolü için."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.local_workflow import LocalWorkflowService


def run_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "smoke.db"
        service = LocalWorkflowService(database_path=db)

        customer_id = service.create_customer(
            code="SMK-01", name="Smoke Test AŞ", username="smoke"
        )
        profile_id, _die_id = _seed_profile_route(service)

        order_id = service.create_sales_order(
            customer_id,
            order_date="2026-08-05",
            delivery_date="2026-08-20",
            lines=[{
                "profile_id": profile_id,
                "die_id": _die_id,
                "length_mm": 6000,
                "surface": "PRES",
                "alloy": "6060B",
                "temper": "T5",
                "quantity": 200,
                "kg": 1000,
                "unit_price": 4.5,
            }],
            username="smoke",
        )
        service.approve_sales_order(order_id, username="smoke")
        line_id = service.order_progress(order_id)["lines"][0]["id"]
        route_id = service.list_routes(profile_id)[0]["id"]
        production_id = service.plan_sales_order_line(
            line_id,
            planned_quantity=200,
            planned_kg=1000,
            route_id=route_id,
            username="smoke",
        )
        die_id = service.list_dies(profile_id=profile_id)[0]["id"]

        for work in service.work_orders_for_production(production_id):
            service.record_work_order_output(
                work["id"],
                quantity=200,
                gross_kg=1020 if work["sequence_no"] == 1 else 1000,
                net_kg=1000,
                die_id=die_id if work["sequence_no"] == 1 else None,
                username="smoke",
            )

        progress = service.order_progress(order_id)
        assert progress["lines"][0]["produced_kg"] == 1000, progress

        line_id = progress["lines"][0]["id"]
        package_id = service.create_package(
            line_id, quantity=200, net_kg=1000, gross_kg=1025, username="smoke"
        )
        wl_id = service.create_weighing_list([package_id], username="smoke")
        service.create_shipment(
            [package_id],
            shipment_date="2026-08-05",
            vehicle_plate="35 SMK 001",
            username="smoke",
        )

        shipped = service.order_progress(order_id)
        assert shipped["order"]["status"] == "SEVK EDİLDİ", shipped
        assert shipped["lines"][0]["shipped_kg"] == 1000, shipped

        doc = service.shipment_document(service.list_shipments()[0]["id"])
        assert doc["lines"], doc

        wl_doc = service.weighing_list_document(wl_id)
        assert wl_doc["header"]["weighing_list_no"], wl_doc

        print("SMOKE OK — sipariş → üretim → paket → çeki → sevkiyat → belge")


def _seed_profile_route(service: LocalWorkflowService) -> tuple[int, int]:
    profile_id = service.create_profile(
        "SMK-100", "Smoke Profil", unit_weight_kg_m=0.833, username="smoke"
    )
    die_id = service.create_die(
        profile_id, "SMK-D01", username="smoke", compatible_stations=["PRES 1"]
    )
    route_id = service.create_route(
        profile_id,
        "R-SMK-100",
        "Smoke rota",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
            {"operation": "TERMİK GİRİŞ", "station": "TERMİK 1", "input_warehouse": "PRES", "output_warehouse": "TERMIK_ON"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "input_warehouse": "TERMIK_ON", "output_warehouse": "SEVK_ON"},
        ],
        username="smoke",
    )
    service.create_recipe(
        profile_id,
        route_id,
        "RC-SMK-100",
        "Smoke reçete",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "route_sequence_no": 1, "numerator": 1, "denominator": 1, "unit_code": "KG", "stock_code": "AL-BILLET"},
            {"operation": "TERMİK GİRİŞ", "station": "TERMİK 1", "route_sequence_no": 2, "numerator": 1, "denominator": 1, "unit_code": "KG"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "route_sequence_no": 3, "numerator": 1, "denominator": 1, "unit_code": "KG"},
        ],
        username="smoke",
        raw_material_stock_code="AL-BILLET",
    )
    return profile_id, die_id


if __name__ == "__main__":
    run_smoke()
