"""KALIP KART ekranını örnek veriyle açar / ekran görüntüsü alır.

Kullanım:
    python scripts/onizle_kalip_kart.py            # pencereyi açar
    python scripts/onizle_kalip_kart.py cikti.png  # offscreen görüntü alır
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if len(sys.argv) > 1:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from services.local_workflow import LocalWorkflowService  # noqa: E402
from ui.corporate_theme import apply_corporate_typography  # noqa: E402
from ui.die_card_dialog import DieCardDialog  # noqa: E402


def seed(service: LocalWorkflowService) -> int:
    customer_id = service.create_customer("M-1", "AKSEKİ YAPI A.Ş. ÇİĞLİ", username="demo")
    profile_id = service.create_profile(
        "1099", "YAN DÖKME 62", unit_weight_kg_m=0.501, username="demo",
        customer_id=customer_id,
    )
    with service.connect() as connection:
        connection.execute(
            """
            UPDATE profiles
            SET profile_group = 'PANJUR', perimeter_mm = 262.40, area_mm2 = 184.871
            WHERE id = ?
            """,
            (profile_id,),
        )
    die_id = service.create_die(
        profile_id, "1099", figure_count=2, tenefer_no="8",
        tenefer_type="KÖPRÜLÜ TAKIM", life_limit_kg=500_000,
        compatible_stations=["PRES 1", "PRES 2"], supplier_name="ÜSTÜNEL KALIP",
        username="demo",
    )
    route_id = service.create_route(
        profile_id, "R-1", "Panjur rotası",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1",
             "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1",
             "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
        ],
        username="demo", surface="PRES",
    )
    service.create_recipe(
        profile_id, route_id, "RC-1", "Panjur reçetesi",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1,
             "denominator": 1, "stock_code": "AL-BILLET"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1,
             "denominator": 1},
        ],
        username="demo", raw_material_stock_code="AL-BILLET",
    )
    for index in range(6):
        order_id = service.create_sales_order(
            customer_id, order_date="2026-03-01", delivery_date="2026-04-01",
            lines=[{
                "profile_id": profile_id, "die_id": die_id, "length_mm": 6000,
                "quantity": 100 + index * 10, "kg": 500 + index * 40,
                "unit_price": 4.0,
            }],
            username="demo",
        )
        service.approve_sales_order(order_id, username="demo")
        line_id = service.order_progress(order_id)["lines"][0]["id"]
        production_id = service.plan_sales_order_line(
            line_id, planned_quantity=100 + index * 10,
            planned_kg=500 + index * 40, route_id=route_id, username="demo",
        )
        works = service.work_orders_for_production(production_id)
        service.record_work_order_output(
            works[0]["id"], quantity=100 + index * 10,
            gross_kg=(500 + index * 40) * 1.05, net_kg=500 + index * 40,
            metre=(100 + index * 10) * 6.0, die_id=die_id,
            shift=f"{index % 3 + 1}.VARDİYA",
            production_type="TEST" if index == 5 else "PLANLI ÜRETİM",
            die_problem="AKIŞ DENGESİZ" if index == 2 else "",
            username="operator",
        )
    service.send_die_to_tenefer(die_id, company="TENEFERCİ A.Ş.", username="demo")
    service.receive_die_from_tenefer(
        die_id, company="TENEFERCİ A.Ş.", new_tenefer_no="8", username="demo",
    )
    return die_id


def main() -> int:
    app = QApplication(sys.argv[:1])
    apply_corporate_typography(app)
    with tempfile.TemporaryDirectory() as folder:
        service = LocalWorkflowService(Path(folder) / "kalip_kart.db")
        die_id = seed(service)
        dialog = DieCardDialog(service, die_id, username="demo")
        dialog.resize(1520, 900)
        if len(sys.argv) > 1:
            dialog.show()
            app.processEvents()
            for index in range(dialog.tabs.count()):
                dialog.tabs.setCurrentIndex(index)
                for _ in range(4):
                    app.processEvents()
                target = Path(sys.argv[1])
                dialog.grab().save(
                    str(target.with_name(f"{target.stem}_{index}{target.suffix}"))
                )
            return 0
        dialog.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
