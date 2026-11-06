#!/usr/bin/env python3
"""Tüm modül/sekmeleri gezip detay ekranlarını ve sütun tanımlarını denetler."""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QLabel, QTableWidget  # noqa: E402

from pages.workflow import WorkflowPage  # noqa: E402
from services.local_workflow import LocalWorkflowService  # noqa: E402
from ui.record_details_dialog import RecordDetailsDialog  # noqa: E402


def seed(service: LocalWorkflowService, notes: list[str]) -> None:
    """Tam iş akışını kurar: sipariş → üretim → paket → çeki → sevkiyat → fatura."""

    def step(label: str, function):
        try:
            return function()
        except Exception as error:  # denetim scripti: eksik akışı raporla, devam et
            notes.append(f"SEED ATLANDI  {label}: {type(error).__name__}: {error}")
            return None

    customer_id = service.create_customer("MUS-001", "AKSEKİ YAPI", username="patron")
    profile_id = service.create_profile(
        "PRF-001", "KAPI PROFİLİ", unit_weight_kg_m=1.25,
        customer_id=customer_id, username="patron",
    )
    die_id = service.create_die(
        profile_id, "KLP-001", life_limit_kg=100_000, username="kaliphane"
    )
    service.create_route(
        profile_id, "R-PRES-TERMIK-PKT", "Pres - Termik - Paketleme",
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
    route_id = service.list_routes(profile_id)[0]["id"]
    service.create_recipe(
        profile_id, route_id, "RC-PRES-TERMIK-PKT", "Pres - Termik - Paketleme reçetesi",
        [
            {"operation": "PRES ÜRETİM", "station": "PRES 1", "numerator": 1, "denominator": 1},
            {"operation": "TERMİK ÇIKIŞ", "station": "TERMİK 1", "numerator": 1, "denominator": 1},
            {"operation": "PAKETLEME", "station": "PAKETLEME 1", "numerator": 1, "denominator": 1},
        ],
        username="uretim_planlama", production_length_mm=6000,
    )
    order_id = service.create_sales_order(
        customer_id, order_date="2026-08-04", delivery_date="2026-08-20",
        lines=[{
            "profile_id": profile_id, "die_id": die_id, "length_mm": 6000,
            "surface": "PRES", "quantity": 200, "kg": 1000, "unit_price": 4.20,
        }],
        username="satis",
    )
    line_id = service.order_progress(order_id)["lines"][0]["id"]
    service.approve_sales_order(order_id, username="uretim_planlama")
    production_id = service.plan_sales_order_line(
        line_id, planned_quantity=200, planned_kg=1000,
        route_id=route_id, username="uretim_planlama",
    )

    for work_order in service.work_orders_for_production(production_id):
        service.record_work_order_output(
            work_order["id"], quantity=200,
            gross_kg=1020 if work_order["sequence_no"] == 1 else 1000,
            net_kg=1000, metre=800,
            die_id=die_id if work_order["sequence_no"] == 1 else None,
            lot_no="LOT-001", shift="GÜNDÜZ", username="operator",
        )

    package_id = step("paket", lambda: service.create_package(
        line_id, quantity=200, net_kg=1000, gross_kg=1025,
        lot_no="LOT-001", username="paketleme",
    ))
    if package_id:
        step("çeki listesi", lambda: service.create_weighing_list(
            [package_id], username="sevkiyat"
        ))
        step("sevkiyat", lambda: service.create_shipment(
            [package_id], shipment_date="2026-08-05",
            vehicle_plate="35 ABC 123", username="sevkiyat",
        ))
        shipments = service.list_shipments()
        if shipments:
            step("satış faturası", lambda: service.create_sales_invoice(
                int(shipments[0]["id"]), invoice_date="2026-08-06",
                currency="TRY", exchange_rate=1, lme_usd_ton=3229.0,
                premium_usd_ton=250.0, pricing_mode="BİRİM FİYAT",
                username="muhasebe",
            ))

    # --- Satın alma zinciri ---
    stock_id = service.create_stock_item(
        "HM-6060", "6060 BİLLET", stock_group="HAMMADDE", unit="KG",
        tracks_lot=True, minimum_quantity=10_000, username="depo",
    )
    supplier_id = service.create_supplier(
        "TED-001", "BİLLET TEDARİK A.Ş.", tax_office="KONAK",
        tax_number="1234567890", currency="USD", username="satinalma",
    )
    request_id = service.create_purchase_request(
        request_date="2026-08-04", username="pres_sorumlusu",
        lines=[{
            "stock_item_id": stock_id, "warehouse_code": "HAMMADDE",
            "required_date": "2026-08-10", "quantity": 25_000,
            "reason": "Ağustos üretim planı",
        }],
    )
    service.approve_purchase_request(request_id, username="patron")
    purchase_order_id = service.create_purchase_order_from_request(
        request_id, supplier_id, order_date="2026-08-04",
        delivery_date="2026-08-10", currency="USD", username="satinalma",
    )
    service.receive_purchase_order(
        purchase_order_id, receipt_date="2026-08-06",
        dispatch_note_no="IRS-55", lot_no="LOT-6060-01", username="depo",
    )

    # --- Yan kartlar ---
    step("birim seti", lambda: service.create_unit_set(
        "BS-KG", "Kilogram Seti", base_unit="KG",
        lines=[{"unit_code": "TON", "factor": 1000, "description": "Ton"}],
        username="depo",
    ))
    step("satış teklifi", lambda: service.create_sales_quote(
        customer_id, quote_date="2026-08-01", valid_until="2026-09-01",
        lines=[{
            "profile_id": profile_id, "length_mm": 6000,
            "quantity": 100, "kg": 500, "unit_price": 4.5,
        }],
        username="satis",
    ))
    step("stok fişi", lambda: service.create_stock_document(
        document_type="GİRİŞ", document_date="2026-08-06",
        target_warehouse_id=int(service.list_warehouses()[0]["id"]),
        reference_no="SF-001",
        lines=[{"stock_item_id": stock_id, "quantity": 500, "lot_no": "LOT-SF"}],
        username="depo",
    ))
    step("kalıp tenefer hareketi", lambda: service.send_die_to_tenefer(
        die_id, company="TENEFER AŞ", username="kaliphane",
    ))

    # --- Kalıphane tooling ---
    step("kalıp talebi", lambda: service.create_die_tooling_request(
        username="kaliphane", profile_id=profile_id,
        request_date="2026-08-03", figure_no="RES-001", supplier_id=supplier_id,
    ))
    step("kalıp iş emri", lambda: service.create_die_tooling_work_order(
        username="kaliphane", profile_id=profile_id, die_id=die_id,
        order_date="2026-08-03", order_type="BAKIM",
    ))
    step("kalıp fişi", lambda: service.create_die_tooling_slip(
        username="kaliphane", die_id=die_id, profile_id=profile_id,
        slip_date="2026-08-04", slip_type="BAKIM",
    ))
    step("kalıp problemi", lambda: service.create_die_tooling_problem(
        username="kaliphane", die_id=die_id, profile_id=profile_id,
        record_date="2026-08-04", problem_type="ÇİZİK",
    ))

    # --- Üretim yan kayıtları ---
    # Eloksal fişi yalnız ELOKSAL operasyonlu iş emri için açılabilir:
    # ikinci profil + eloksallı rota kurulur.
    eloksal_profile_id = step("eloksal profili", lambda: service.create_profile(
        "PRF-ELX", "ELOKSAL PROFİLİ", unit_weight_kg_m=1.10,
        customer_id=customer_id, username="patron",
    ))
    if eloksal_profile_id:
        def build_eloksal_chain() -> None:
            service.create_route(
                eloksal_profile_id, "R-PRES-ELOKSAL", "Pres - Eloksal",
                [
                    {"operation": "PRES ÜRETİM", "station": "PRES 1",
                     "input_warehouse": "HAMMADDE", "output_warehouse": "PRES"},
                    {"operation": "ELOKSAL", "station": "ELOKSAL 1",
                     "input_warehouse": "PRES", "output_warehouse": "SEVK_ON"},
                ],
                username="uretim_planlama",
            )
            elx_route_id = service.list_routes(eloksal_profile_id)[0]["id"]
            service.create_recipe(
                eloksal_profile_id, elx_route_id, "RC-ELX", "Eloksal reçetesi",
                [
                    {"operation": "PRES ÜRETİM", "station": "PRES 1",
                     "numerator": 1, "denominator": 1},
                    {"operation": "ELOKSAL", "station": "ELOKSAL 1",
                     "numerator": 1, "denominator": 1},
                ],
                username="uretim_planlama", production_length_mm=6000,
            )
            elx_order_id = service.create_sales_order(
                customer_id, order_date="2026-08-04", delivery_date="2026-08-22",
                lines=[{
                    "profile_id": eloksal_profile_id, "length_mm": 6000,
                    "surface": "ELOKSAL", "quantity": 100, "kg": 500,
                    "unit_price": 5.10,
                }],
                username="satis",
            )
            elx_line_id = service.order_progress(elx_order_id)["lines"][0]["id"]
            service.approve_sales_order(elx_order_id, username="uretim_planlama")
            elx_production_id = service.plan_sales_order_line(
                elx_line_id, planned_quantity=100, planned_kg=500,
                route_id=elx_route_id, username="uretim_planlama",
            )
            elx_work_orders = service.work_orders_for_production(elx_production_id)
            eloksal_wo = next(
                (w for w in elx_work_orders
                 if "ELOKSAL" in str(w.get("operation") or "").upper()),
                None,
            )
            if eloksal_wo is not None:
                service.create_eloksal_slip(
                    work_order_id=int(eloksal_wo["id"]), hanger_no="ASK-01",
                    color_group="MAT", hanging_quantity=100, hanging_kg=500,
                    username="eloksal",
                )

        step("eloksal zinciri", build_eloksal_chain)

    step("duruş kaydı", lambda: service.create_downtime_event(
        reason="ELEKTRİK KESİNTİSİ", operation="PRES ÜRETİM",
        station="PRES 1", username="operator",
    ))

    # --- Kalıphane durum çeşitliliği (hurda / imalatta / tedarik bekleyen / tenefer yakın) ---
    def scrap_new_die() -> None:
        scrap_id = service.create_die(
            profile_id, "KLP-HURDA", life_limit_kg=50_000, username="kaliphane"
        )
        service.scrap_die(scrap_id, username="kaliphane")

    step("hurda kalıp", scrap_new_die)

    def set_die_state(code: str, status: str) -> None:
        """Denetim fikstürü: servis API'sinde doğrudan durum atama yok."""
        new_id = service.create_die(
            profile_id, code, life_limit_kg=50_000, username="kaliphane"
        )
        with closing(service.connect()) as connection:
            connection.execute(
                "UPDATE dies SET status = ? WHERE id = ?", (status, int(new_id))
            )
            connection.commit()

    for die_code, die_status in (
        ("KLP-IMALAT", "İMALATTA"),
        ("KLP-TEDARIK", "TEDARİK BEKLİYOR"),
    ):
        step(
            f"kalıp durumu {die_status}",
            lambda c=die_code, s=die_status: set_die_state(c, s),
        )

    def make_near_tenefer_die() -> None:
        near_id = service.create_die(
            profile_id, "KLP-TNF-YAKIN", life_limit_kg=50_000, username="kaliphane"
        )
        with closing(service.connect()) as connection:
            connection.execute(
                "UPDATE dies SET tenefer_limit_m = 2000, tenefer_used_m = 1900 WHERE id = ?",
                (int(near_id),),
            )
            connection.commit()

    step("tenefer yaklaşan kalıp", make_near_tenefer_die)

    # Kalıp verilmeyen sipariş satırı (die_id boş)
    step("kalıpsız sipariş", lambda: service.create_sales_order(
        customer_id, order_date="2026-08-05", delivery_date="2026-08-25",
        lines=[{
            "profile_id": profile_id, "length_mm": 6000, "surface": "PRES",
            "quantity": 50, "kg": 250, "unit_price": 4.30,
        }],
        username="satis",
    ))

    # --- Bakım ---
    step("bakım emri", lambda: service.create_maintenance_order(
        order_type="PLANLI", name="PRES YAĞ DEĞİŞİMİ",
        operation="PRES ÜRETİM", station="PRES 1",
        planned_start="2026-08-10", planned_end="2026-08-11",
        username="bakim",
    ))
    instruction_id = step("bakım talimatı", lambda: service.create_maintenance_instruction(
        instruction_type="PERİYODİK", name="PRES HİDROLİK YAĞ KONTROLÜ",
        description="Yağ seviyesi ve filtre kirlilik kontrolü yapılır.",
        operation="PRES ÜRETİM", station="PRES 1", period_days=30,
        username="bakim",
    ))
    step("arızi bakım talimatı", lambda: service.create_maintenance_instruction(
        instruction_type="ARİZİ", name="ELOKSAL POMPA ARIZA MÜDAHALE",
        description="Pompa durduğunda uygulanacak müdahale adımları.",
        operation="ELOKSAL", station="ELOKSAL 1", period_days=0,
        username="bakim",
    ))
    if instruction_id:
        step("talimattan bakım emri",
             lambda: service.create_maintenance_order_from_instruction(
                 int(instruction_id), planned_start="2026-08-12", username="bakim",
             ))

    # --- Satın alma yan kayıtları ---
    receipts = service.list_goods_receipts()
    if receipts:
        step("satın alma faturası", lambda: service.create_purchase_invoice_from_receipt(
            int(receipts[0]["id"]), username="muhasebe",
        ))
    step("satın alma teklifi", lambda: service.create_purchase_quote(
        request_id=request_id, supplier_id=supplier_id,
        unit_price=2.75, quantity=25_000, currency="USD",
        delivery_date="2026-08-12", username="satinalma",
    ))

    # --- Satış yan kayıtları ---
    step("şikayet", lambda: service.create_customer_complaint(
        username="satis", customer_id=customer_id,
        complaint_date="2026-08-05", subject="YÜZEY HATASI",
        profile_code="PRF-001",
    ))
    price_list_id = step("fiyat listesi", lambda: service.create_sales_price_list(
        username="satis", list_name="2026 LİSTE", currency="USD",
        customer_id=customer_id, valid_from="2026-01-01",
    ))
    if price_list_id:
        step("fiyat listesi satırı", lambda: service.create_sales_price_list_line(
            price_list_id=int(price_list_id), profile_id=profile_id,
            unit_price=4.75, username="satis",
        ))

    # --- Malzeme yönetimi yan kartları ---
    step("müşteri ürün kodu", lambda: service.create_party_product_code(
        username="depo", party_type="CUSTOMER", party_id=customer_id,
        external_code="MUS-KOD-1", external_name="MÜŞTERİ PROFİLİ",
        stock_item_id=stock_id,
    ))
    step("tedarikçi ürün kodu", lambda: service.create_party_product_code(
        username="depo", party_type="SUPPLIER", party_id=supplier_id,
        external_code="TED-KOD-1", external_name="TEDARİKÇİ BİLLET",
        stock_item_id=stock_id,
    ))
    step("fasoncu", lambda: service.create_subcontractor(
        "FSN-001", "KAPLAMA FASON", username="satinalma",
    ))
    step("hizmet kartı", lambda: service.create_service_item_master(
        code="HZM-001", name="NAKLİYE", unit="SEFER", username="depo",
    ))
    property_set_id = step("özellik seti", lambda: service.create_property_set_master(
        code="YUZ-01", name="YÜZEY SETİ", property_kind="YÜZEY", username="depo",
    ))
    if property_set_id:
        step("özellik değeri", lambda: service.create_property_set_value(
            property_set_id=int(property_set_id), code="MAT",
            name="MAT ELOKSAL", username="depo",
        ))
    step("talep sebebi", lambda: service.create_request_reason(
        code="TS-01", name="ÜRETİM İHTİYACI", username="satinalma",
    ))


def audit() -> int:
    app = QApplication.instance() or QApplication([])
    del app
    temp = tempfile.TemporaryDirectory()
    service = LocalWorkflowService(Path(temp.name) / "rigel_operations.db")

    notes: list[str] = []
    try:
        seed(service, notes)
    except Exception:
        print("SEED HATASI:")
        traceback.print_exc()

    captured: dict[str, RecordDetailsDialog] = {}
    original_exec = RecordDetailsDialog.exec

    def fake_exec(self) -> int:
        captured["last"] = self
        return 0

    RecordDetailsDialog.exec = fake_exec  # type: ignore[method-assign]

    page = WorkflowPage(username="patron", service=service)
    problems: list[str] = []
    empty_views: list[str] = []
    coverage: list[tuple[str, int, int]] = []
    stats = {"context": 0, "with_rows": 0, "details_ok": 0}

    for (department, module), view in sorted(WorkflowPage.CONTEXT_VIEW.items()):
        label = f"{department} / {module} [{view}]"
        try:
            page.set_context(department, module)
        except Exception as error:
            problems.append(f"CONTEXT ÇÖKTÜ  {label}: {type(error).__name__}: {error}")
            continue
        stats["context"] += 1

        columns_key = page.active_columns_key()
        if columns_key not in WorkflowPage.COLUMNS:
            problems.append(f"SÜTUN TANIMSIZ {label}: '{columns_key}'")
            continue

        expected = len(WorkflowPage.COLUMNS[columns_key])
        if page.table.columnCount() != expected:
            problems.append(
                f"SÜTUN SAYISI   {label}: tablo {page.table.columnCount()} != tanım {expected}"
            )

        if page.table.rowCount() == 0:
            empty_views.append(label)
            continue
        stats["with_rows"] += 1

        page.table.selectRow(0)
        captured.pop("last", None)
        try:
            page.show_record_details()
        except Exception as error:
            problems.append(f"DETAY ÇÖKTÜ    {label}: {type(error).__name__}: {error}")
            continue

        dialog = captured.get("last")
        if dialog is None:
            problems.append(f"DETAY AÇILMADI {label}")
            continue
        stats["details_ok"] += 1

        value_labels = [
            widget for widget in dialog.findChildren(QLabel)
            if widget.objectName() == "detailsValue"
        ]
        if not value_labels:
            problems.append(f"DETAY ALANSIZ  {label}: etiket/değer alanı üretilmedi")
        else:
            filled = [w for w in value_labels if w.text() not in {"", "—"}]
            if not filled:
                problems.append(f"DETAY BOŞ      {label}: hiçbir alan dolu değil")

        grids = dialog.findChildren(QTableWidget)
        for grid in grids:
            if grid.columnCount() == 0:
                problems.append(f"DETAY TABLO    {label}: sütunsuz tablo")
        coverage.append((label, len(value_labels), len(grids)))
        dialog.deleteLater()

    RecordDetailsDialog.exec = original_exec  # type: ignore[method-assign]
    page.close()

    print("=" * 68)
    print("RIGEL COST PRO — MODÜL / SEKME DENETİMİ")
    print("=" * 68)
    print(f"Kontrol edilen sekme  : {stats['context']} / {len(WorkflowPage.CONTEXT_VIEW)}")
    print(f"Veri bulunan sekme    : {stats['with_rows']}")
    print(f"Detay ekranı çalışan  : {stats['details_ok']}")
    print(f"Sorun sayısı          : {len(problems)}")
    if notes:
        print("\nSeed notları:")
        for note in notes:
            print("  •", note)
    if problems:
        print("\nSORUNLAR:")
        for problem in problems:
            print("  ✗", problem)
    if empty_views:
        print(f"\nVerisiz sekmeler ({len(empty_views)}) — denetim dışı:")
        for item in empty_views:
            print("  ·", item)

    if os.environ.get("AUDIT_COVERAGE"):
        without_table = [row for row in coverage if row[2] == 0]
        print(f"\nBağlı satır tablosu OLMAYAN detaylar ({len(without_table)}):")
        for label, field_count, _ in sorted(without_table):
            print(f"  · {label} — {field_count} alan")

    temp.cleanup()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(audit())
