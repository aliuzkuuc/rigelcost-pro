#!/usr/bin/env python3
"""Pres üretim fişini uçtan uca üretir ve PDF çıktısını yazar.

Sahadan alınan PRES ÜRETİM FİŞİ örneğindeki sayıların aynısı kullanılır; böylece
brüt/net/fire hesabının birebir örtüştüğü doğrulanabilir.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from reports.production_documents import press_slip_html  # noqa: E402
from services.local_workflow import LocalWorkflowService  # noqa: E402

# Örnek fişteki değerler.
BILLETS = [
    {
        "billet_length_mm": 430, "billet_count": 2, "length_count": 20,
        "total_length_count": 40, "gross_kg": 42.29,
        "raw_material_stock": "AL. BİLLET 6063B 152'LİK", "lot_no": "6612",
        "dummy_length_mm": 20, "press_speed_m_s": 4.4,
        "container_temp_c": 420, "die_temp_c": 435,
        "billet_temp_c": 450, "exit_temp_c": 520,
    },
    {
        "billet_length_mm": 500, "billet_count": 6, "length_count": 24,
        "total_length_count": 144, "gross_kg": 147.53,
        "raw_material_stock": "AL. BİLLET 6063B 152'LİK", "lot_no": "6612",
        "dummy_length_mm": 20, "press_speed_m_s": 4.4,
        "container_temp_c": 420, "die_temp_c": 435,
        "billet_temp_c": 450, "exit_temp_c": 520,
    },
]
BASKETS = [
    {"basket_no": "Z8", "length_mm": 6000, "quantity": 83, "net_kg": 76.19,
     "work_order_no": "000017452"},
]
SCRAPS = [
    {"scrap_reason": "ARA İŞ", "quantity": 0, "kg": 20.91},
    {"scrap_reason": "HURDA", "quantity": 101, "kg": 92.72},
]
GROSS = sum(row["gross_kg"] for row in BILLETS)
NET = sum(row["net_kg"] for row in BASKETS)
QUANTITY = sum(row["quantity"] for row in BASKETS)


def kur(service: LocalWorkflowService) -> int:
    """Pres iş emrine kadar olan zinciri kurar ve iş emri kimliğini döner."""
    customer_id = service.create_customer(
        "MUS-PRES", "AKSEKİ YAPI MENDERES(ALM.)", city="İZMİR",
        currency="EUR", username="satis",
    )
    profile_id = service.create_profile(
        "2082", "17x25 SİNEKLİK", unit_weight_kg_m=0.153,
        customer_id=customer_id, alloy="6060B", username="kaliphane",
    )
    die_id = service.create_die(
        profile_id, "2082-A", life_limit_kg=100_000, figure_count=4,
        tenefer_no="6", username="kaliphane",
    )
    service.create_route(
        profile_id, "ROTA-PRES", "Pres → Paketleme",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1",
             "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
            {"operation": "PAKETLEME", "station": "PAKETLEME 1",
             "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
        ],
        username="uretim_planlama",
    )
    route_id = int(service.list_routes(profile_id)[0]["id"])
    service.create_recipe(
        profile_id, route_id, "RC-PRES", "Pres reçetesi",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1",
             "numerator": 1, "denominator": 1},
            {"operation": "PAKETLEME", "station": "PAKETLEME 1",
             "numerator": 1, "denominator": 1},
        ],
        username="uretim_planlama", production_length_mm=6000,
    )
    order_id = service.create_sales_order(
        customer_id, order_date="2026-07-29", delivery_date="2026-08-28",
        representative="ÖMER SİVRİ",
        lines=[{
            "profile_id": profile_id, "die_id": die_id, "length_mm": 6000,
            "surface": "PRES", "quantity": 1500, "kg": 1350, "unit_price": 4.10,
        }],
        username="satis",
    )
    service.approve_sales_order(order_id, username="uretim_planlama")
    line_id = int(service.order_progress(order_id)["lines"][0]["id"])
    production_id = service.plan_sales_order_line(
        line_id, planned_quantity=1500, planned_kg=1350,
        route_id=route_id, username="uretim_planlama",
    )
    press = next(
        row for row in service.work_orders_for_production(production_id)
        if str(row["operation"]).startswith("PRES")
    )
    return int(press["id"])


def main() -> int:
    app = QApplication.instance() or QApplication([])
    hata = 0
    with tempfile.TemporaryDirectory() as tmp:
        service = LocalWorkflowService(Path(tmp) / "rigel_operations.db")
        work_order_id = kur(service)

        context = service.press_entry_context(work_order_id)
        print("EKRAN BAĞLAMI")
        for key in (
            "work_order_no", "profile_code", "profile_name", "die_code",
            "figure_count", "tenefer_no", "tenefer_remaining_m",
            "raw_material_stock", "customer_name", "order_line_ref",
        ):
            print(f"  {key:<22} {context.get(key)}")

        entry_id = service.record_work_order_output(
            work_order_id,
            quantity=QUANTITY, gross_kg=GROSS, net_kg=NET,
            metre=QUANTITY * 6.0, die_id=int(context["die_id"]),
            lot_no="6612", shift="2.VARDİYA", username="PRES",
            complete=False,
            production_type="PLANLI ÜRETİM",
            press_status="TAMAMLANDI", saw_status="TAMAMLANDI",
            real_weight_kg_m=0.153, theoretical_weight_kg_m=0.153,
            billet_count=8, result_length_mm=6000,
            preparation_min=5, duration_min=30,
            qc_username="KK", test_result="BAŞARILI",
            die_problem="GÖRÜNTÜ BOZUK",
            die_problem_note="3 VE 4 NO ALTTA - VAR 4 FİGÜRDE ÇATI KAYIK",
            spare_no=1, figure_count=4, tenefer_no="6",
            raw_material_stock="AL. BİLLET 6063B 152'LİK",
            remaining_quantity=1500 - QUANTITY,
            started_at="2026-08-06T01:40:00", ended_at="2026-08-06T02:10:00",
            billets=BILLETS, baskets=BASKETS, scraps=SCRAPS,
        )
        document = service.press_slip_document(entry_id)
        header = document["header"]

        print("\nFİŞ DOĞRULAMA")
        kontroller = (
            ("Fiş no üretildi", bool(header["slip_no"]), True),
            ("Brüt kg", round(float(header["gross_kg"]), 2), 189.82),
            ("Net kg", round(float(header["net_kg"]), 2), 76.19),
            ("Fire kg", round(float(header["scrap_kg"]), 2), 113.63),
            ("Fire %", round(float(header["fire_pct"]), 1), 59.9),
            ("Net adet", int(header["quantity"]), 83),
            ("Kalan adet", int(header["remaining_quantity"]), 1417),
            ("Billet satırı", len(document["billets"]), 2),
            ("Sepet satırı", len(document["baskets"]), 1),
            ("Hurda satırı", len(document["scraps"]), 2),
            ("Kovan sıcaklık", float(document["billets"][0]["container_temp_c"]), 420.0),
            ("Baskı hızı", float(document["billets"][0]["press_speed_m_s"]), 4.4),
            ("Kalıp problemi", header["die_problem"], "GÖRÜNTÜ BOZUK"),
            ("Müşteri", header["customer_name"], "AKSEKİ YAPI MENDERES(ALM.)"),
            ("Temsilci", header["representative"], "ÖMER SİVRİ"),
            ("Figür adet", int(header["figure_count"]), 4),
        )
        for isim, gercek, beklenen in kontroller:
            ok = gercek == beklenen
            if not ok:
                hata += 1
            print(f"  [{'OK ' if ok else 'HATA'}] {isim}: {gercek}"
                  + ("" if ok else f"  (beklenen {beklenen})"))

        html = press_slip_html(document)
        out = Path("/tmp/rigel_pres")
        out.mkdir(exist_ok=True)
        (out / "pres_fisi.html").write_text(html, encoding="utf-8")

        from PySide6.QtGui import QPageLayout, QPageSize
        from PySide6.QtCore import QMarginsF
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtGui import QTextDocument

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(out / "PRES_URETIM_FISI.pdf"))
        printer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.A4), QPageLayout.Portrait,
                QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter,
            )
        )
        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)
        print(f"\nPDF: {out / 'PRES_URETIM_FISI.pdf'}")

    print("\n" + ("=" * 60))
    print("SONUÇ: " + ("TÜM KONTROLLER GEÇTİ" if not hata else f"{hata} KONTROL BAŞARISIZ"))
    print("=" * 60)
    return 1 if hata else 0


if __name__ == "__main__":
    raise SystemExit(main())
