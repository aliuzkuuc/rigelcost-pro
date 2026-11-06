#!/usr/bin/env python3
"""Uçtan uca akış: sipariş → üretim → ambar → çeki listesi → sevkiyat.

Her adım işlendikten sonra sonuç servisten geri okunarak doğrulanır.
Varsayılan olarak geçici veritabanı kullanır; --canli ile uygulamanın
kendi veritabanına yazar.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from services.local_workflow import LocalWorkflowService  # noqa: E402


class Adim:
    """Numaralı adım çıktısı ve doğrulama yardımcıları."""

    def __init__(self) -> None:
        self.no = 0
        self.hata = 0

    def basla(self, baslik: str) -> None:
        self.no += 1
        print(f"\n{'─' * 70}")
        print(f"ADIM {self.no}: {baslik}")
        print("─" * 70)

    def kontrol(self, aciklama: str, gercek, beklenen=None) -> None:
        if beklenen is None:
            ok = bool(gercek)
            detay = f"{gercek}"
        else:
            ok = gercek == beklenen
            detay = f"{gercek}" if ok else f"{gercek}  (beklenen: {beklenen})"
        if not ok:
            self.hata += 1
        print(f"  [{'OK ' if ok else 'HATA'}] {aciklama}: {detay}")


def ambar_tablosu(service: LocalWorkflowService, baslik: str) -> None:
    print(f"\n  {baslik}")
    print(f"  {'AMBAR':<14} {'STOK':<12} {'LOT':<14} {'BAKİYE':>14} {'BİRİM':<6}")
    print(f"  {'-' * 14} {'-' * 12} {'-' * 14} {'-' * 14} {'-' * 6}")
    rows = [r for r in service.list_warehouse_balances() if abs(float(r["balance"] or 0)) > 1e-9]
    if not rows:
        print("  (hareket yok)")
        return
    for row in sorted(rows, key=lambda r: (str(r["warehouse_code"]), str(r["stock_code"]))):
        print(
            f"  {str(row['warehouse_code']):<14} {str(row['stock_code']):<12} "
            f"{str(row['lot_no'] or '-'):<14} {float(row['balance']):>14,.3f} "
            f"{str(row['unit'] or ''):<6}"
        )


def calistir(service: LocalWorkflowService, etiket: str) -> int:
    a = Adim()
    lot = f"LOT-{etiket}"

    a.basla("Ana veriler — müşteri, profil, kalıp, rota, reçete")
    customer_id = service.create_customer(
        f"MUS-{etiket}", f"DEMO MÜŞTERİ {etiket}", city="İZMİR",
        phone="0232 000 00 00", currency="EUR", username="satis",
    )
    profile_id = service.create_profile(
        f"PRF-{etiket}", f"DEMO PROFİL {etiket}", unit_weight_kg_m=1.250,
        customer_id=customer_id, username="kaliphane",
    )
    die_id = service.create_die(
        profile_id, f"KLP-{etiket}", life_limit_kg=100_000, username="kaliphane"
    )
    service.create_route(
        profile_id, f"ROTA-{etiket}", "Pres → Termik → Paketleme",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1",
             "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1",
             "input_warehouse": "PRES", "output_warehouse": "TERMIK"},
            {"operation": "PAKETLEME", "station": "PAKETLEME 1",
             "input_warehouse": "TERMIK", "output_warehouse": "SEVK_ON"},
        ],
        username="uretim_planlama",
    )
    route_id = int(service.list_routes(profile_id)[0]["id"])
    service.create_recipe(
        profile_id, route_id, f"RC-{etiket}", "Demo reçete",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
            {"operation": "PAKETLEME", "station": "PAKETLEME 1", "numerator": 1, "denominator": 1},
        ],
        username="uretim_planlama", production_length_mm=6000,
    )
    a.kontrol("Müşteri", service.list_customers()[0]["name"] is not None)
    a.kontrol("Profile bağlı kalıp sayısı", len(service.list_dies(profile_id)), 1)
    a.kontrol("Rota adım sayısı", len(service.list_route_steps(route_id)), 3)

    a.basla("Satış siparişi oluştur")
    order_id = service.create_sales_order(
        customer_id, order_date="2026-08-06", delivery_date="2026-08-28",
        lines=[{
            "profile_id": profile_id, "die_id": die_id, "length_mm": 6000,
            "surface": "PRES", "quantity": 200, "kg": 1000, "unit_price": 4.20,
        }],
        username="satis",
    )
    progress = service.order_progress(order_id)
    order_no = str(progress["order"]["order_no"])
    line_id = int(progress["lines"][0]["id"])
    print(f"  Sipariş no: {order_no}")
    a.kontrol("Sipariş kg", float(progress["lines"][0]["ordered_kg"]), 1000.0)
    a.kontrol("Başlangıç durumu", str(progress["order"]["status"]))

    a.basla("Siparişi onayla ve üretime planla")
    service.approve_sales_order(order_id, username="uretim_planlama")
    production_id = service.plan_sales_order_line(
        line_id, planned_quantity=200, planned_kg=1000,
        route_id=route_id, username="uretim_planlama",
    )
    work_orders = service.work_orders_for_production(production_id)
    print(f"  Üretim emri satır sayısı: {len(work_orders)}")
    for w in work_orders:
        print(f"    {w['work_order_no']}  {w['operation']:<14} {w['station']:<14} {w['status']}")
    a.kontrol("İş emri sayısı", len(work_orders), 3)
    a.kontrol(
        "İlk iş emri HAZIR, diğerleri BEKLİYOR",
        [w["status"] for w in work_orders],
        ["HAZIR", "BEKLİYOR", "BEKLİYOR"],
    )

    ambar_tablosu(service, "Üretim öncesi ambar bakiyeleri:")

    a.basla("Üretimi işle — her operasyon ambarı doldurur")
    for w in sorted(work_orders, key=lambda r: int(r["sequence_no"])):
        service.record_work_order_output(
            int(w["id"]), quantity=200,
            gross_kg=1020 if int(w["sequence_no"]) == 1 else 1000,
            net_kg=1000, metre=800,
            die_id=die_id if int(w["sequence_no"]) == 1 else None,
            lot_no=lot, shift="GÜNDÜZ", username="operator",
        )
        guncel = service.work_orders_for_production(production_id)
        durum = next(r for r in guncel if int(r["id"]) == int(w["id"]))["status"]
        print(f"    {w['work_order_no']} {w['operation']:<14} → {durum}")
        ambar_tablosu(service, f"    {w['operation']} sonrası:")

    bitmis = service.work_orders_for_production(production_id)
    a.kontrol(
        "Tüm iş emirleri tamamlandı",
        [r["status"] for r in bitmis],
        ["TAMAMLANDI"] * 3,
    )
    progress = service.order_progress(order_id)
    a.kontrol("Üretilen kg", float(progress["lines"][0]["produced_kg"]), 1000.0)
    a.kontrol("Sipariş durumu", str(progress["order"]["status"]), "HAZIR")

    bakiyeler = {
        (r["warehouse_code"], r["stock_code"]): float(r["balance"])
        for r in service.list_warehouse_balances()
        if str(r["lot_no"]) == lot
    }
    a.kontrol("SEVK_ON ambarında mamul", bakiyeler.get(("SEVK_ON", f"PRF-{etiket}")), 1000.0)
    a.kontrol("HAMMADDE ambarından düşen", bakiyeler.get(("HAMMADDE", "AL-BILLET")), -1020.0)

    a.basla("Kasalama — paket oluştur")
    paketlenebilir = service.list_packable_lines()
    a.kontrol("Paketlenebilir satır var", len(paketlenebilir) > 0)
    package_id = service.create_package(
        line_id, quantity=200, net_kg=1000, gross_kg=1025,
        lot_no=lot, username="paketleme",
    )
    paket = next(r for r in service.list_packages() if int(r["id"]) == package_id)
    print(f"  Paket no: {paket['package_no']}")
    a.kontrol("Paket durumu", str(paket["status"]), "SEVK ÖN")
    a.kontrol("Paket net kg", float(paket["net_kg"]), 1000.0)

    a.basla("Çeki listesi oluştur")
    weighing_id = service.create_weighing_list([package_id], username="sevkiyat")
    ceki = next(r for r in service.list_weighing_lists() if int(r["id"]) == weighing_id)
    print(f"  Çeki listesi no: {ceki['weighing_list_no']}")
    a.kontrol("Çeki listesi paket sayısı", int(ceki["package_count"]), 1)
    a.kontrol("Çeki listesi net kg", float(ceki["net_kg"]), 1000.0)
    paket = next(r for r in service.list_packages() if int(r["id"]) == package_id)
    a.kontrol("Paket durumu çeki sonrası", str(paket["status"]), "SEVK HAZIR")
    ambar_tablosu(service, "Çeki listesi sonrası ambar bakiyeleri:")

    a.basla("Sevkiyat — irsaliye kes")
    shipment_id = service.create_shipment(
        [package_id], shipment_date="2026-08-07",
        vehicle_plate="35 RGL 026", username="sevkiyat",
    )
    sevk = next(r for r in service.list_shipments() if int(r["id"]) == shipment_id)
    print(f"  İrsaliye no: {sevk['dispatch_note_no']}  |  Plaka: {sevk['vehicle_plate']}")
    a.kontrol("Sevk net kg", float(sevk["net_kg"]), 1000.0)
    a.kontrol("Sevkiyattaki paket sayısı", int(sevk["package_count"]), 1)
    a.kontrol(
        "İrsaliyeye bağlı paketler okunuyor",
        len(service.packages_for_shipment(shipment_id)), 1,
    )
    a.kontrol(
        "İrsaliyede çeki listesi görünüyor",
        str(sevk["weighing_list_no"]), str(ceki["weighing_list_no"]),
    )
    ceki = next(r for r in service.list_weighing_lists() if int(r["id"]) == weighing_id)
    a.kontrol("Çeki listesi durumu", str(ceki["status"]), "SEVK EDİLDİ")

    progress = service.order_progress(order_id)
    a.kontrol("Sevk edilen kg", float(progress["lines"][0]["shipped_kg"]), 1000.0)
    a.kontrol("Sipariş kapanış durumu", str(progress["order"]["status"]), "SEVK EDİLDİ")
    a.kontrol("Sevk ilerleme %", int(progress["lines"][0]["progress_pct"]), 100)
    sevk_hazir_balance = sum(
        float(row["balance"] or 0)
        for row in service.list_warehouse_balances()
        if str(row["warehouse_code"]) == "SEVK_HAZIR"
    )
    a.kontrol("SEVK_HAZIR bakiye", round(sevk_hazir_balance, 3), 0.0)
    ambar_tablosu(service, "Sevkiyat sonrası ambar bakiyeleri:")

    a.basla("Satış faturası kes")
    invoice_id = service.create_sales_invoice(
        shipment_id, invoice_date="2026-08-07", currency="EUR",
        exchange_rate=1, lme_usd_ton=0, premium_usd_ton=0,
        pricing_mode="BİRİM FİYAT", username="muhasebe",
    )
    fatura = next(r for r in service.list_sales_invoices() if int(r["id"]) == invoice_id)
    print(f"  Fatura no: {fatura['invoice_no']}")
    a.kontrol("Fatura tutarı", float(fatura["total_amount"]), 4200.0)
    a.kontrol("Fatura para birimi", str(fatura["currency"]), "EUR")

    print(f"\n{'═' * 70}")
    if a.hata:
        print(f"SONUÇ: {a.hata} DOĞRULAMA BAŞARISIZ")
    else:
        print("SONUÇ: TÜM ADIMLAR DOĞRULANDI")
    print("═" * 70)
    print("\nProgramda göreceğiniz kayıtlar:")
    print(f"  Satış → Satış Siparişleri ....... {order_no}")
    print(f"  Üretim → İş Emirleri ............ {len(work_orders)} iş emri (TAMAMLANDI)")
    print(f"  Sevkiyat → Kasalama Fişleri ..... {paket['package_no']}")
    print(f"  Sevkiyat → Çeki Listeleri ....... {ceki['weighing_list_no']}")
    print(f"  Satış → Satış İrsaliyeleri ...... {sevk['dispatch_note_no']}")
    print(f"  Satış → Satış Faturaları ........ {fatura['invoice_no']}")
    return 1 if a.hata else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--canli", action="store_true",
        help="Uygulamanın kendi veritabanına yazar (varsayılan: geçici kopya)",
    )
    parser.add_argument("--etiket", default="E2E", help="Kayıt kodlarında kullanılacak ek")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    if args.canli:
        app.setApplicationName("Rigel Cost Pro")
        app.setOrganizationName("Rigel Alüminyum")
        service = LocalWorkflowService()
        print(f"CANLI VERİTABANI: {service.database_path}")
        return calistir(service, args.etiket)

    with tempfile.TemporaryDirectory() as tmp:
        service = LocalWorkflowService(Path(tmp) / "rigel_operations.db")
        print(f"GEÇİCİ VERİTABANI: {service.database_path}")
        return calistir(service, args.etiket)


if __name__ == "__main__":
    raise SystemExit(main())
