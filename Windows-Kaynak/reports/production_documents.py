"""Üretim belgeleri. PRES ÜRETİM FİŞİ, operatör fişinin resmi çıktısıdır."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Sequence

TURKISH_MONTHS = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)
TURKISH_DAYS = (
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value).strip())


def _kg(value: Any) -> str:
    try:
        return f"{float(value or 0):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    except (TypeError, ValueError):
        return "0,00"


def _qty(value: Any) -> str:
    try:
        return f"{float(value or 0):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _decimal(value: Any, places: int = 3) -> str:
    try:
        formatted = f"{float(value or 0):,.{places}f}"
    except (TypeError, ValueError):
        return "0"
    return formatted.replace(",", "#").replace(".", ",").replace("#", ".")


def _temp(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"{number:.0f} °C" if number else ""


def _date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[: len(pattern) + 2].strip(), pattern).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return html.escape(raw)


def _datetime(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, pattern).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            continue
    return _date(raw)


def _delivery_week(value: Any) -> str:
    raw = str(value or "").strip()[:10]
    try:
        moment = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return ""
    week = moment.isocalendar()
    return f"{week.week}/{week.year}"


def _printed_stamp() -> str:
    now = datetime.now()
    return (
        f"{now.day} {TURKISH_MONTHS[now.month - 1]} {now.year} "
        f"{TURKISH_DAYS[now.weekday()]} {now:%H:%M}"
    )


def _styles() -> str:
    # Qt zengin metin motoru px birimini yazıcı çözünürlüğünde yorumladığı için
    # tüm ölçüler punto verilir; aksi hâlde çıktı okunamayacak kadar küçülür.
    return """
    body { font-family: Arial, sans-serif; color:#101828; margin:0; font-size:7pt; }
    h2 { font-size:8.5pt; color:#163A70; margin:7pt 0 2pt; text-transform:uppercase;
         letter-spacing:.4pt; }
    td.page { border:2px solid #163A70; padding:7pt; }
    td.brandmark { font-size:17pt; font-weight:bold; color:#163A70;
                   letter-spacing:2pt; vertical-align:middle; }
    td.brandsub { font-size:6.5pt; color:#5B6B80; letter-spacing:1.5pt; }
    td.doctitle { font-size:15pt; font-weight:bold; color:#163A70;
                  text-align:right; letter-spacing:1pt; vertical-align:middle; }
    table.head td { padding:2pt 3pt; vertical-align:top; font-size:7pt;
                    border:1px solid #C6D0DC; }
    table.head td.k { color:#475467; font-weight:bold; background:#F2F6FB; }
    table.head td.v { color:#101828; font-weight:bold; }
    table.grid { font-size:6.5pt; }
    table.grid th { background:#DCE6F1; color:#163A70; border:1px solid #AFC0D4;
                    padding:2pt 3pt; text-align:center; font-size:6pt; font-weight:bold; }
    table.grid td { border:1px solid #CFD8E3; padding:2pt 3pt; font-size:6.5pt; }
    table.grid td.n { text-align:right; }
    table.grid td.c { text-align:center; }
    table.grid tr.total td { background:#EEF3F9; font-weight:bold; }
    table.cols td { vertical-align:top; }
    table.sign th { border:1px solid #98A2B3; background:#F2F6FB; padding:3pt;
                    text-align:center; color:#163A70; font-weight:bold; font-size:8pt; }
    table.sign td { border:1px solid #98A2B3; padding:3pt; }
    .foot { margin-top:5pt; font-size:6pt; color:#98A2B3; text-align:right; }
    .slip { text-align:center; font-size:10pt; font-weight:bold; color:#163A70;
            background:#EEF3F9; padding:2pt; margin:6pt 0 2pt; }
    .rule { border-bottom:2px solid #163A70; margin:3pt 0 5pt; }
    """


def _head_rows(pairs: Sequence[tuple[str, str]], per_row: int = 3) -> str:
    cells: list[str] = ["<table class='head' width='100%' cellspacing='0'>"]
    for index in range(0, len(pairs), per_row):
        cells.append("<tr>")
        chunk = pairs[index : index + per_row]
        for label, value in chunk:
            cells.append(f"<td class='k'>{_text(label)}</td><td class='v'>{value}</td>")
        for _ in range(per_row - len(chunk)):
            cells.append("<td class='k'></td><td class='v'></td>")
        cells.append("</tr>")
    cells.append("</table>")
    return "".join(cells)


def press_slip_html(document: dict[str, Any]) -> str:
    """PRES ÜRETİM FİŞİ belgesinin tüm bölümlerini üretir."""
    header = document.get("header", {})
    billets = document.get("billets", [])
    baskets = document.get("baskets", [])
    scraps = document.get("scraps", [])

    order_ref = _text(header.get("order_no"))
    line_no = header.get("line_no")
    if line_no:
        order_ref = f"{order_ref}-{_text(line_no)}"

    parts = [
        "<html><head><meta charset='utf-8'><style>",
        _styles(),
        "</style></head><body>",
        "<table class='frame' width='100%' cellspacing='0'><tr><td class='page'>",
        "<table class='brand' width='100%' cellspacing='0'><tr>"
        "<td class='brandmark'>RIGEL</td>"
        "<td class='doctitle'>PRES ÜRETİM FİŞİ</td></tr>"
        "<tr><td class='brandsub'>COST PRO</td><td></td></tr></table>",
        "<div class='rule'></div>",
    ]

    parts.append(
        _head_rows(
            (
                ("FİRMA", _text(header.get("customer_name"))),
                ("SİPARİŞ REF", order_ref),
                ("SİPARİŞ TEMSİLCİSİ", _text(header.get("representative"))),
                ("SİPARİŞ TARİHİ", _date(header.get("order_date"))),
                ("TESLİM TARİHİ", _date(header.get("delivery_date"))),
                ("YÜZEY", _text(header.get("surface"))),
                ("BELGE NO", _text(header.get("customer_document_no"))),
                ("TESLİM HAFTA", _delivery_week(header.get("delivery_date"))),
                ("RENK", _text(header.get("color")) or "*"),
                ("PROFİL", _text(header.get("profile_code"))),
                ("SİPARİŞ KG", _kg(header.get("ordered_kg"))),
                ("SERTLİK", _text(header.get("temper"))),
                ("ALAŞIM", _text(header.get("alloy"))),
                ("SİPARİŞ ADET", _qty(header.get("ordered_quantity"))),
                ("MEKANİK İŞLEM", _text(header.get("mechanical")) or "YOK"),
                ("BOY (mm)", _qty(header.get("line_length_mm"))),
                ("STOK BOY (mm)", _qty(header.get("stock_length_mm"))),
                ("PROFİL AD", _text(header.get("profile_name"))),
            )
        )
    )

    parts.append(
        f"<div class='slip'>PRES ÜRETİM FİŞİ &nbsp;—&nbsp; "
        f"{_text(header.get('slip_no'))}</div>"
    )

    gross = float(header.get("gross_kg") or 0)
    net = float(header.get("net_kg") or 0)
    scrap = float(header.get("scrap_kg") or 0)
    parts.append(
        _head_rows(
            (
                ("OPERATÖR", _text(header.get("operator_username"))),
                ("BAŞLANGIÇ", _datetime(header.get("started_at"))),
                ("BİTİŞ", _datetime(header.get("ended_at"))),
                ("İSTASYON", _text(header.get("station"))),
                ("VARDİYA", _text(header.get("shift"))),
                ("ÇALIŞMA DK", _decimal(header.get("duration_min"), 0)),
                ("KALIP", _text(header.get("die_code"))),
                ("YEDEK NO", _qty(header.get("spare_no"))),
                ("KALIP HAZIRLIK DK", _decimal(header.get("preparation_min"), 0)),
                ("TENEFER NO", _text(header.get("tenefer_no"))),
                ("FİGÜR ADET", _qty(header.get("figure_count"))),
                ("GRAMAJ", _decimal(header.get("real_weight_kg_m"), 3)),
                ("BRÜT KG", _kg(gross)),
                ("NET KG", _kg(net)),
                ("FİRE KG", _kg(scrap)),
                ("NET ADET", _qty(header.get("quantity"))),
                ("FİRE (%)", _decimal(header.get("fire_pct"), 1)),
                ("KALAN ADET", _qty(header.get("remaining_quantity"))),
                ("ÜRETİM TİPİ", _text(header.get("production_type"))),
                ("ÜRETİM DURUMU", _text(header.get("press_status"))),
                ("TESTERE DURUMU", _text(header.get("saw_status"))),
                ("HAMMADDE STOK", _text(header.get("raw_material_stock"))),
                ("KK KULLANICISI", _text(header.get("qc_username"))),
                ("TEST SONUCU", _text(header.get("test_result"))),
            )
        )
    )

    if header.get("die_problem") or header.get("die_problem_note"):
        parts.append(
            _head_rows(
                (
                    ("KALIP PROBLEMİ", _text(header.get("die_problem"))),
                    ("AÇIKLAMA", _text(header.get("die_problem_note"))),
                ),
                per_row=2,
            )
        )
    if header.get("note"):
        parts.append(_head_rows((("NOT", _text(header.get("note"))),), per_row=1))

    parts.append("<h2>Billet Boyları</h2>")
    parts.append("<table class='grid' width='100%' cellspacing='0'><thead><tr>")
    for column in (
        "BİLLET BOY", "BİLLET ADET", "BOY ADEDİ", "TOPLAM BOY", "BRÜT KG",
        "HAMMADDE", "LOT NO", "DÜPÇİK", "BASKI ZAM.", "KOVAN", "KALIP",
        "BİLLET", "ÇIKIŞ",
    ):
        parts.append(f"<th>{column}</th>")
    parts.append("</tr></thead><tbody>")
    if billets:
        totals = [0.0, 0.0, 0.0, 0.0]
        for row in billets:
            totals[0] += float(row.get("billet_count") or 0)
            totals[1] += float(row.get("length_count") or 0)
            totals[2] += float(row.get("total_length_count") or 0)
            totals[3] += float(row.get("gross_kg") or 0)
            parts.append(
                "<tr>"
                f"<td class='n'>{_qty(row.get('billet_length_mm'))}</td>"
                f"<td class='n'>{_qty(row.get('billet_count'))}</td>"
                f"<td class='n'>{_qty(row.get('length_count'))}</td>"
                f"<td class='n'>{_qty(row.get('total_length_count'))}</td>"
                f"<td class='n'>{_kg(row.get('gross_kg'))}</td>"
                f"<td>{_text(row.get('raw_material_stock'))}</td>"
                f"<td class='c'>{_text(row.get('lot_no'))}</td>"
                f"<td class='n'>{_qty(row.get('dummy_length_mm'))}</td>"
                f"<td class='c'>{_decimal(row.get('press_speed_m_s'), 1)} m/sn</td>"
                f"<td class='c'>{_temp(row.get('container_temp_c'))}</td>"
                f"<td class='c'>{_temp(row.get('die_temp_c'))}</td>"
                f"<td class='c'>{_temp(row.get('billet_temp_c'))}</td>"
                f"<td class='c'>{_temp(row.get('exit_temp_c'))}</td>"
                "</tr>"
            )
        parts.append(
            "<tr class='total'>"
            f"<td class='n'>TOPLAM</td><td class='n'>{_qty(totals[0])}</td>"
            f"<td class='n'>{_qty(totals[1])}</td><td class='n'>{_qty(totals[2])}</td>"
            f"<td class='n'>{_kg(totals[3])}</td>"
            "<td colspan='8'></td></tr>"
        )
    else:
        parts.append("<tr><td colspan='13' class='c'>Billet dökümü girilmedi.</td></tr>")
    parts.append("</tbody></table>")

    parts.append("<table class='cols' width='100%' cellspacing='0'><tr><td style='width:58%;padding-right:6px;'>")
    parts.append("<h2>Sepet Verileri</h2>")
    parts.append(
        "<table class='grid' width='100%' cellspacing='0'><thead><tr><th>SEPET NO</th><th>BOY (mm)</th>"
        "<th>ADET</th><th>KG</th><th>İŞ EMRİ NO</th></tr></thead><tbody>"
    )
    if baskets:
        basket_qty = sum(float(row.get("quantity") or 0) for row in baskets)
        basket_kg = sum(float(row.get("net_kg") or 0) for row in baskets)
        for row in baskets:
            parts.append(
                "<tr>"
                f"<td class='c'>{_text(row.get('basket_no'))}</td>"
                f"<td class='n'>{_qty(row.get('length_mm'))}</td>"
                f"<td class='n'>{_qty(row.get('quantity'))}</td>"
                f"<td class='n'>{_kg(row.get('net_kg'))}</td>"
                f"<td class='c'>{_text(row.get('work_order_no'))}</td>"
                "</tr>"
            )
        parts.append(
            f"<tr class='total'><td>TOPLAM</td><td></td>"
            f"<td class='n'>{_qty(basket_qty)}</td>"
            f"<td class='n'>{_kg(basket_kg)}</td><td></td></tr>"
        )
    else:
        parts.append("<tr><td colspan='5' class='c'>Sepet dökümü girilmedi.</td></tr>")
    parts.append("</tbody></table>")

    parts.append("</td><td style='width:42%;'>")
    parts.append("<h2>Hurda Verileri</h2>")
    parts.append(
        "<table class='grid' width='100%' cellspacing='0'><thead><tr><th>HURDA SEBEBİ</th>"
        "<th>ADET</th><th>KG</th></tr></thead><tbody>"
    )
    if scraps:
        scrap_qty = sum(float(row.get("quantity") or 0) for row in scraps)
        scrap_kg = sum(float(row.get("kg") or 0) for row in scraps)
        for row in scraps:
            parts.append(
                "<tr>"
                f"<td>{_text(row.get('scrap_reason'))}</td>"
                f"<td class='n'>{_qty(row.get('quantity'))}</td>"
                f"<td class='n'>{_kg(row.get('kg'))}</td>"
                "</tr>"
            )
        parts.append(
            f"<tr class='total'><td>TOPLAM</td>"
            f"<td class='n'>{_qty(scrap_qty)}</td>"
            f"<td class='n'>{_kg(scrap_kg)}</td></tr>"
        )
    else:
        parts.append(
            f"<tr><td>FİRE</td><td class='n'>—</td><td class='n'>{_kg(scrap)}</td></tr>"
        )
    parts.append("</tbody></table></td></tr></table>")

    parts.append("<p>&nbsp;</p>")
    parts.append(
        "<table class='sign' width='100%' cellspacing='0'>"
        "<tr><th>KONTROL EDEN</th><th>ONAY</th></tr>"
        "<tr><td>&nbsp;<br>&nbsp;<br>&nbsp;</td>"
        "<td>&nbsp;<br>&nbsp;<br>&nbsp;</td></tr></table>"
    )
    parts.append(f"<p class='foot'>{_printed_stamp()} &nbsp; 1/1</p>")
    parts.append("</td></tr></table>")
    parts.append("</body></html>")
    return "".join(parts)
