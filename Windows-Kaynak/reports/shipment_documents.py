from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Sequence


def _fmt_kg(value: Any) -> str:
    try:
        return f"{float(value or 0):,.3f}"
    except (TypeError, ValueError):
        return "0,000"


def _fmt_qty(value: Any) -> str:
    try:
        return f"{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "0"


def _base_styles() -> str:
    # Qt zengin metin motoru px birimini yazıcı çözünürlüğünde yorumlar; çıktının
    # okunabilir kalması için tüm yazı ölçüleri punto verilir.
    return """
    body { font-family: Arial, sans-serif; color:#1D2939; margin:0; font-size:8pt; }
    h1 { color:#163A70; font-size:15pt; text-align:center; margin:0 0 4pt; }
    h2 { color:#163A70; font-size:10pt; margin:10pt 0 4pt; }
    p.meta { color:#667085; font-size:7.5pt; text-align:center; margin:0 0 8pt; }
    table.info td { padding:2pt 4pt; vertical-align:top; font-size:8pt; }
    table.info td.label { color:#667085; font-weight:bold; }
    table.grid { font-size:8pt; }
    table.grid th { background:#DCE6F1; color:#163A70; padding:3pt 4pt;
                    border:1px solid #D0D7DE; font-size:7.5pt; font-weight:bold; }
    table.grid td { padding:3pt 4pt; border:1px solid #D0D7DE; font-size:8pt; }
    .totals { margin-top:6pt; font-size:9pt; font-weight:bold; text-align:right; }
    .label-sheet { border:2px solid #163A70; padding:6mm; }
    .label-title { font-size:14pt; font-weight:bold; color:#163A70; text-align:center;
                   margin-bottom:4mm; }
    .label-row { font-size:10pt; margin:2mm 0; }
    .label-row span { color:#667085; }
    """


def weighing_list_html(header: dict[str, Any], lines: Sequence[dict[str, Any]]) -> str:
    meta = (
        f"Müşteri: {header.get('customer_name', '')}  |  "
        f"Tarih: {header.get('created_at', '')[:10]}  |  "
        f"Hazırlayan: {header.get('created_by', '')}  |  "
        f"Durum: {header.get('status', '')}"
    )
    parts = [
        "<html><head><meta charset='utf-8'><style>",
        _base_styles(),
        "</style></head><body>",
        f"<h1>ÇEKİ LİSTESİ — {html.escape(str(header.get('weighing_list_no') or ''))}</h1>",
        f"<p class='meta'>{html.escape(meta)}</p>",
    ]
    if header.get("note"):
        parts.append(f"<p class='meta'>{html.escape(str(header['note']))}</p>")
    parts.append("<table class='grid' width='100%' cellspacing='0'><thead><tr>")
    for col in ("Paket No", "Sipariş", "Profil", "Adet", "Net kg", "Brüt kg", "Lot"):
        parts.append(f"<th>{col}</th>")
    parts.append("</tr></thead><tbody>")
    total_net = 0.0
    total_gross = 0.0
    for row in lines:
        net = float(row.get("net_kg") or 0)
        gross = float(row.get("gross_kg") or 0)
        total_net += net
        total_gross += gross
        parts.append("<tr>")
        parts.extend(
            [
                f"<td>{html.escape(str(row.get('package_no') or ''))}</td>",
                f"<td>{html.escape(str(row.get('order_no') or ''))}</td>",
                f"<td>{html.escape(str(row.get('profile_code') or ''))}</td>",
                f"<td>{_fmt_qty(row.get('quantity'))}</td>",
                f"<td>{_fmt_kg(net)}</td>",
                f"<td>{_fmt_kg(gross)}</td>",
                f"<td>{html.escape(str(row.get('lot_no') or ''))}</td>",
            ]
        )
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append(
        f"<p class='totals'>Toplam: {len(lines)} paket — "
        f"Net {_fmt_kg(total_net)} kg — Brüt {_fmt_kg(total_gross)} kg</p>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def shipment_dispatch_html(header: dict[str, Any], lines: Sequence[dict[str, Any]]) -> str:
    meta = (
        f"İrsaliye: {header.get('dispatch_note_no') or header.get('shipment_no', '')}  |  "
        f"Tarih: {header.get('shipment_date', '')}  |  "
        f"Araç: {header.get('vehicle_plate', '')}  |  "
        f"Konteyner: {header.get('container_no', '')}"
    )
    parts = [
        "<html><head><meta charset='utf-8'><style>",
        _base_styles(),
        "</style></head><body>",
        f"<h1>SEVK İRSALİYESİ — {html.escape(str(header.get('shipment_no') or ''))}</h1>",
        f"<p class='meta'>{html.escape(meta)}</p>",
        "<table class='info' width='100%' cellspacing='0'>",
        f"<tr><td class='label'>Müşteri</td><td>{html.escape(str(header.get('customer_name') or ''))}</td>"
        f"<td class='label'>Çeki Listesi</td><td>{html.escape(str(header.get('weighing_list_no') or ''))}</td></tr>",
        f"<tr><td class='label'>Teslimat Adresi</td><td colspan='3'>{html.escape(str(header.get('delivery_address') or ''))}</td></tr>",
        "</table>",
        "<table class='grid' width='100%' cellspacing='0'><thead><tr>",
    ]
    for col in ("Paket No", "Sipariş", "Profil", "Adet", "Net kg", "Brüt kg"):
        parts.append(f"<th>{col}</th>")
    parts.append("</tr></thead><tbody>")
    total_net = 0.0
    total_gross = 0.0
    for row in lines:
        net = float(row.get("net_kg") or 0)
        gross = float(row.get("gross_kg") or 0)
        total_net += net
        total_gross += gross
        parts.append("<tr>")
        parts.extend(
            [
                f"<td>{html.escape(str(row.get('package_no') or ''))}</td>",
                f"<td>{html.escape(str(row.get('order_no') or ''))}</td>",
                f"<td>{html.escape(str(row.get('profile_code') or ''))}</td>",
                f"<td>{_fmt_qty(row.get('quantity'))}</td>",
                f"<td>{_fmt_kg(net)}</td>",
                f"<td>{_fmt_kg(gross)}</td>",
            ]
        )
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append(
        f"<p class='totals'>Toplam: {len(lines)} paket — "
        f"Net {_fmt_kg(total_net)} kg — Brüt {_fmt_kg(total_gross)} kg</p>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def package_label_html(header: dict[str, Any], lines: Sequence[dict[str, Any]]) -> str:
    line = lines[0] if lines else {}
    parts = [
        "<html><head><meta charset='utf-8'><style>",
        _base_styles(),
        "</style></head><body>",
        "<div class='label-sheet'>",
        f"<div class='label-title'>{html.escape(str(header.get('package_no') or ''))}</div>",
        f"<div class='label-row'><span>Müşteri</span>{html.escape(str(header.get('customer_name') or ''))}</div>",
        f"<div class='label-row'><span>Sipariş</span>{html.escape(str(line.get('order_no') or header.get('order_nos') or ''))}</div>",
        f"<div class='label-row'><span>Profil</span>{html.escape(str(line.get('profile_code') or header.get('profile_codes') or ''))}</div>",
        f"<div class='label-row'><span>Adet</span>{_fmt_qty(line.get('quantity') or header.get('package_count'))}</div>",
        f"<div class='label-row'><span>Net kg</span>{_fmt_kg(header.get('net_kg'))}</div>",
        f"<div class='label-row'><span>Brüt kg</span>{_fmt_kg(header.get('gross_kg'))}</div>",
        f"<div class='label-row'><span>Lot</span>{html.escape(str(line.get('lot_no') or ''))}</div>",
        f"<div class='label-row'><span>Ambar</span>{html.escape(str(header.get('warehouse_name') or ''))}</div>",
        f"<div class='label-row'><span>Tarih</span>{html.escape(str(header.get('packed_at') or '')[:10])}</div>",
        "</div></body></html>",
    ]
    return "".join(parts)


def work_order_slip_html(header: dict[str, Any]) -> str:
    meta = (
        f"Sipariş: {header.get('order_no', '')}  |  "
        f"Satır: {header.get('line_no', '')}  |  "
        f"Müşteri: {header.get('customer_name', '')}  |  "
        f"Teslim: {header.get('delivery_date', '')}"
    )
    parts = [
        "<html><head><meta charset='utf-8'><style>",
        _base_styles(),
        "</style></head><body>",
        f"<h1>İŞ EMRİ — {html.escape(str(header.get('work_order_no') or ''))}</h1>",
        f"<p class='meta'>{html.escape(meta)}</p>",
        "<table class='info' width='100%' cellspacing='0'>",
        f"<tr><td class='label'>Üretim Emri</td><td>{html.escape(str(header.get('production_order_no') or ''))}</td>"
        f"<td class='label'>Operasyon</td><td>{html.escape(str(header.get('operation') or ''))}</td></tr>",
        f"<tr><td class='label'>İstasyon</td><td>{html.escape(str(header.get('station') or ''))}</td>"
        f"<td class='label'>Sıra</td><td>{html.escape(str(header.get('sequence_no') or ''))}</td></tr>",
        f"<tr><td class='label'>Profil</td><td>{html.escape(str(header.get('profile_code') or ''))} {html.escape(str(header.get('profile_name') or ''))}</td>"
        f"<td class='label'>Kalıp</td><td>{html.escape(str(header.get('die_code') or ''))}</td></tr>",
        f"<tr><td class='label'>Boy mm</td><td>{html.escape(str(header.get('production_length_mm') or ''))}</td>"
        f"<td class='label'>Yüzey</td><td>{html.escape(str(header.get('surface') or ''))}</td></tr>",
        f"<tr><td class='label'>Plan Adet</td><td>{_fmt_qty(header.get('planned_quantity'))}</td>"
        f"<td class='label'>Plan kg</td><td>{_fmt_kg(header.get('planned_kg'))}</td></tr>",
        f"<tr><td class='label'>Giriş Ambarı</td><td>{html.escape(str(header.get('input_warehouse_name') or ''))}</td>"
        f"<td class='label'>Çıkış Ambarı</td><td>{html.escape(str(header.get('output_warehouse_name') or ''))}</td></tr>",
        f"<tr><td class='label'>Durum</td><td>{html.escape(str(header.get('status') or ''))}</td>"
        f"<td class='label'>Öncelik</td><td>{html.escape(str(header.get('priority') or ''))}</td></tr>",
        "</table>",
        f"<p class='meta'>Yazdırma: {datetime.now():%d.%m.%Y %H:%M}</p>",
        "</body></html>",
    ]
    return "".join(parts)
