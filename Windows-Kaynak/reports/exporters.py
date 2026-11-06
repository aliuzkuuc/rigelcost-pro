from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as ReportLabImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.calculator import MALIYET_ANA_LABELS


REPORT_AUTHOR = "ALİ UZKUC"
REPORT_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.jpg"

INPUT_FIELDS = [
    ("uretim", "Aylık net üretim", "kg"),
    ("lme", "LME", "USD/ton"),
    ("prim", "Prim", "USD/ton"),
    ("usd", "USD/TL kuru", "TL"),
    ("fire_orani", "Fabrika fire oranı", "oran (0-1)"),
    (
        "ergitme_kaybi_orani",
        "Geri dönüşümde ergitme kaybı",
        "oran (0-1)",
    ),
    ("fason_usd_kg", "Fason ergitme fiyatı", "USD/kg"),
    ("elektrik_kwh_ton", "Elektrik tüketimi", "kWh/ton"),
    ("elektrik_fiyat", "Elektrik birim fiyatı", "TL/kWh"),
    ("gaz_sm3_ton", "Doğalgaz tüketimi", "Sm³/ton"),
    ("gaz_fiyat", "Doğalgaz toplam birim fiyatı", "TL/Sm³"),
    ("su_m3_ton", "Su tüketimi", "m³/ton"),
    ("su_birim_fiyat", "Su birim fiyatı", "TL/m³"),
    ("iscilik", "Toplam maaş hakedişi (SGK dahil)", "TL/ay"),
    ("yemek", "Yemek", "TL/ay"),
    ("kira", "Bina kirası", "TL/ay"),
    ("amortisman", "Amortisman", "TL/ay"),
    ("genel_gider", "Genel gider", "TL/ay"),
    ("kalip", "Kalıp maliyeti", "TL/ay"),
    ("sarf", "Fabrika iş akışı", "TL/ay"),
    ("mazot", "Araç yakıt", "TL/ay"),
    ("nakliye", "Nakliye", "TL/ay"),
    ("tenefer", "Tenefer", "TL/ay"),
    ("ambalaj", "Paketleme", "TL/ay"),
]


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _summary_rows(report_data: dict[str, Any]) -> list[tuple[str, float]]:
    results = report_data.get("results", {})
    totals = results.get("maliyet_ana_tl") or {}
    labels = results.get("maliyet_ana_labels") or {}
    rows = [
        (
            str(labels.get(key, default_label)),
            _number(totals.get(key)),
        )
        for key, default_label in MALIYET_ANA_LABELS
    ]
    rows.append(
        (
            "FABRİKA MALİYETİ TOPLAMI",
            _number(results.get("maliyet_ana_toplam_tl")),
        )
    )
    return rows


def _unit_values(
    total_tl: float,
    production_kg: float,
    usd_rate: float,
) -> tuple[float, float]:
    if production_kg <= 0 or usd_rate <= 0:
        return 0.0, 0.0
    tl_per_kg = total_tl / production_kg
    usd_per_ton = tl_per_kg * 1000 / usd_rate
    return tl_per_kg, usd_per_ton


def _all_unit_values(
    total_tl: float,
    production_kg: float,
    usd_rate: float,
) -> tuple[float, float, float, float]:
    if production_kg <= 0 or usd_rate <= 0:
        return 0.0, 0.0, 0.0, 0.0
    tl_per_kg = total_tl / production_kg
    total_usd = total_tl / usd_rate
    usd_per_kg = total_usd / production_kg
    usd_per_ton = usd_per_kg * 1000
    return tl_per_kg, total_usd, usd_per_kg, usd_per_ton


def _format_tr(value: float, decimals: int = 2) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _add_excel_logo(worksheet, anchor: str = "A1") -> None:
    if not REPORT_LOGO_PATH.exists():
        return
    logo = ExcelImage(str(REPORT_LOGO_PATH))
    logo.width = 63
    logo.height = 45
    worksheet.add_image(logo, anchor)


def export_excel(report_data: dict[str, Any], destination: str | Path) -> Path:
    """Maliyet özetini ve girdileri biçimlendirilmiş XLSX dosyasına yazar."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    inputs = report_data.get("inputs", {})
    results = report_data.get("results", {})
    production = _number(inputs.get("uretim"))
    usd_rate = _number(inputs.get("usd"))

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Maliyet Özeti"
    inputs_sheet = workbook.create_sheet("Girdiler")

    navy = "163A70"
    light_blue = "DCE6F1"
    pale = "F4F7FB"
    white = "FFFFFF"
    border_side = Side(style="thin", color="D0D7DE")
    thin_border = Border(
        left=border_side,
        right=border_side,
        top=border_side,
        bottom=border_side,
    )

    summary.merge_cells("A1:F1")
    summary["A1"] = "RIGEL COST PRO — FABRİKA MALİYET RAPORU"
    summary["A1"].fill = PatternFill("solid", fgColor=navy)
    summary["A1"].font = Font(color=white, bold=True, size=16)
    summary["A1"].alignment = Alignment(horizontal="center", vertical="center")
    summary.row_dimensions[1].height = 38
    _add_excel_logo(summary)

    summary.merge_cells("A2:F2")
    summary["A2"] = (
        f"Rapor tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  "
        f"Üretim: {_format_tr(production, 0)} kg  |  "
        f"Kur: {_format_tr(usd_rate, 4)} TL  |  "
        f"Geliştiren: {REPORT_AUTHOR}"
    )
    summary["A2"].alignment = Alignment(horizontal="center")
    summary["A2"].font = Font(color="667085", italic=True, size=10)

    headers = [
        "Maliyet kalemi",
        "Toplam (TL)",
        "Toplam (USD)",
        "TL/kg",
        "USD/kg",
        "USD/ton",
    ]
    for column, header in enumerate(headers, start=1):
        cell = summary.cell(row=4, column=column, value=header)
        cell.fill = PatternFill("solid", fgColor=light_blue)
        cell.font = Font(color=navy, bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    rows = _summary_rows(report_data)
    for row_index, (label, total_tl) in enumerate(rows, start=5):
        tl_per_kg, total_usd, usd_per_kg, usd_per_ton = _all_unit_values(
            total_tl, production, usd_rate
        )
        values = [
            label,
            total_tl,
            total_usd,
            tl_per_kg,
            usd_per_kg,
            usd_per_ton,
        ]
        for column, value in enumerate(values, start=1):
            cell = summary.cell(row=row_index, column=column, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="left" if column == 1 else "right"
            )
            if column > 1:
                cell.number_format = '#,##0.00'

        if row_index == 4 + len(rows):
            for column in range(1, 7):
                cell = summary.cell(row=row_index, column=column)
                cell.fill = PatternFill("solid", fgColor=navy)
                cell.font = Font(color=white, bold=True)

    detail_start = 5 + len(rows) + 1
    summary.merge_cells(
        start_row=detail_start,
        start_column=1,
        end_row=detail_start,
        end_column=6,
    )
    summary.cell(detail_start, 1, "TEKNİK ÖZET")
    summary.cell(detail_start, 1).fill = PatternFill("solid", fgColor=navy)
    summary.cell(detail_start, 1).font = Font(color=white, bold=True)
    summary.cell(detail_start, 1).alignment = Alignment(horizontal="center")

    detail_rows = [
        ("Billet ihtiyacı", results.get("billet_ihtiyaci", 0), "kg"),
        ("İlk fire", results.get("fire", 0), "kg"),
        ("Geri kazanılan fire", results.get("geri_donusum", 0), "kg"),
        ("Nihai metal kaybı", results.get("ergitme", 0), "kg"),
        ("Fire maliyeti", results.get("fire_toplam", 0), "TL"),
        ("Elektrik tüketimi", results.get("elektrik_tuketim", 0), "kWh"),
        ("Doğalgaz tüketimi", results.get("gaz_tuketim", 0), "Sm³"),
        ("Su tüketimi", results.get("su_tuketim", 0), "m³"),
        (
            "Fabrika maliyeti toplamı",
            results.get("maliyet_ana_toplam_tl", 0),
            "TL",
        ),
        (
            "Fabrika maliyeti",
            (
                _number(results.get("maliyet_ana_toplam_tl")) / production
                if production > 0
                else 0
            ),
            "TL/kg",
        ),
        (
            "Fabrika maliyeti",
            results.get("maliyet_ana_toplam_usd", 0),
            "USD",
        ),
        (
            "Fabrika maliyeti",
            results.get("maliyet_ana_usd_kg_toplam", 0),
            "USD/kg",
        ),
        (
            "Fabrika maliyeti",
            results.get("maliyet_ana_usd_ton_toplam", 0),
            "USD/ton",
        ),
    ]
    for row_index, (label, value, unit) in enumerate(
        detail_rows, start=detail_start + 1
    ):
        summary.cell(row_index, 1, label)
        summary.cell(row_index, 2, _number(value))
        summary.cell(row_index, 3, unit)
        for column in range(1, 7):
            cell = summary.cell(row_index, column)
            cell.border = thin_border
            if row_index % 2:
                cell.fill = PatternFill("solid", fgColor=pale)
        summary.cell(row_index, 2).number_format = '#,##0.00'

    summary.freeze_panes = "A5"
    widths = [29, 18, 18, 15, 15, 17]
    for column, width in enumerate(widths, start=1):
        summary.column_dimensions[get_column_letter(column)].width = width
    summary.sheet_properties.pageSetUpPr.fitToPage = True
    summary.page_setup.orientation = "landscape"
    summary.page_setup.paperSize = summary.PAPERSIZE_A4
    summary.page_setup.fitToWidth = 1
    summary.page_setup.fitToHeight = 1
    summary.page_margins = PageMargins(
        left=0.25,
        right=0.25,
        top=0.35,
        bottom=0.35,
        header=0.1,
        footer=0.1,
    )
    summary.print_area = f"A1:F{detail_start + len(detail_rows)}"

    inputs_sheet.merge_cells("A1:C1")
    inputs_sheet["A1"] = "HESAPLAMA GİRDİLERİ"
    inputs_sheet["A1"].fill = PatternFill("solid", fgColor=navy)
    inputs_sheet["A1"].font = Font(color=white, bold=True, size=14)
    inputs_sheet["A1"].alignment = Alignment(horizontal="center")
    inputs_sheet.row_dimensions[1].height = 38
    _add_excel_logo(inputs_sheet)

    inputs_sheet.merge_cells("A2:C2")
    inputs_sheet["A2"] = f"Geliştiren: {REPORT_AUTHOR}"
    inputs_sheet["A2"].alignment = Alignment(horizontal="center")
    inputs_sheet["A2"].font = Font(color="667085", italic=True, size=9)

    for column, header in enumerate(["Alan", "Değer", "Birim"], start=1):
        cell = inputs_sheet.cell(row=3, column=column, value=header)
        cell.fill = PatternFill("solid", fgColor=light_blue)
        cell.font = Font(color=navy, bold=True)
        cell.border = thin_border

    for row_index, (key, label, unit) in enumerate(INPUT_FIELDS, start=4):
        inputs_sheet.cell(row_index, 1, label)
        inputs_sheet.cell(row_index, 2, _number(inputs.get(key)))
        inputs_sheet.cell(row_index, 3, unit)
        for column in range(1, 4):
            cell = inputs_sheet.cell(row_index, column)
            cell.border = thin_border
            if row_index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=pale)
        inputs_sheet.cell(row_index, 2).number_format = '#,##0.00'

    inputs_sheet.freeze_panes = "A4"
    for column, width in enumerate([30, 20, 18], start=1):
        inputs_sheet.column_dimensions[get_column_letter(column)].width = width
    inputs_sheet.sheet_properties.pageSetUpPr.fitToPage = True
    inputs_sheet.page_setup.orientation = "portrait"
    inputs_sheet.page_setup.paperSize = inputs_sheet.PAPERSIZE_A4
    inputs_sheet.page_setup.fitToWidth = 1
    inputs_sheet.page_setup.fitToHeight = 1
    inputs_sheet.page_margins = PageMargins(
        left=0.3,
        right=0.3,
        top=0.4,
        bottom=0.4,
        header=0.1,
        footer=0.1,
    )
    inputs_sheet.print_area = f"A1:C{3 + len(INPUT_FIELDS)}"

    workbook.save(path)
    return path


def _register_pdf_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular is None:
        return "Helvetica", "Helvetica-Bold"

    regular_name = "RigelReportRegular"
    bold_name = "RigelReportBold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
    if bold:
        if bold_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
    else:
        bold_name = regular_name
    return regular_name, bold_name


def export_pdf(report_data: dict[str, Any], destination: str | Path) -> Path:
    """Maliyet özetini yazdırılabilir PDF raporuna dönüştürür."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    inputs = report_data.get("inputs", {})
    results = report_data.get("results", {})
    production = _number(inputs.get("uretim"))
    usd_rate = _number(inputs.get("usd"))
    regular_font, bold_font = _register_pdf_fonts()

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Rigel Cost Pro Fabrika Maliyet Raporu",
        author=REPORT_AUTHOR,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RigelTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#163A70"),
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    subtitle_style = ParagraphStyle(
        "RigelSubtitle",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#667085"),
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    heading_style = ParagraphStyle(
        "RigelHeading",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=12,
        textColor=colors.HexColor("#163A70"),
        spaceBefore=3 * mm,
        spaceAfter=3 * mm,
    )
    normal_style = ParagraphStyle(
        "RigelNormal",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=9,
        leading=12,
    )

    title_block = [
        Paragraph("RIGEL COST PRO", title_style),
        Paragraph("Fabrika Maliyet Raporu", subtitle_style),
    ]
    if REPORT_LOGO_PATH.exists():
        logo = ReportLabImage(
            str(REPORT_LOGO_PATH),
            width=28 * mm,
            height=20 * mm,
        )
        report_header = Table(
            [[logo, title_block]],
            colWidths=[34 * mm, 144 * mm],
        )
        report_header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story: list[Any] = [report_header]
    else:
        story = title_block
    story.extend(
        [
        Paragraph(
            f"Rapor tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp; | &nbsp; "
            f"Üretim: {_format_tr(production, 0)} kg &nbsp; | &nbsp; "
            f"USD/TL: {_format_tr(usd_rate, 4)}",
            subtitle_style,
        ),
        Paragraph(f"Geliştiren: {REPORT_AUTHOR}", subtitle_style),
        Paragraph("Maliyet Özeti", heading_style),
        ]
    )

    summary_data: list[list[Any]] = [
        [
            "Maliyet kalemi",
            "Toplam TL",
            "Toplam USD",
            "TL/kg",
            "USD/kg",
            "USD/ton",
        ]
    ]
    for label, total_tl in _summary_rows(report_data):
        tl_per_kg, total_usd, usd_per_kg, usd_per_ton = _all_unit_values(
            total_tl, production, usd_rate
        )
        summary_data.append(
            [
                label,
                _format_tr(total_tl),
                _format_tr(total_usd),
                _format_tr(tl_per_kg, 4),
                _format_tr(usd_per_kg, 4),
                _format_tr(usd_per_ton),
            ]
        )

    summary_table = Table(
        summary_data,
        colWidths=[47 * mm, 29 * mm, 28 * mm, 22 * mm, 22 * mm, 27 * mm],
        repeatRows=1,
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular_font),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, -1), (-1, -1), bold_font),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163A70")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#163A70")),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [
                    colors.white,
                    colors.HexColor("#F4F7FB"),
                ]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, PageBreak()])

    story.append(Paragraph("Teknik Özet", heading_style))
    technical_data = [
        ["Billet ihtiyacı", f"{_format_tr(_number(results.get('billet_ihtiyaci')))} kg"],
        ["İlk fire", f"{_format_tr(_number(results.get('fire')))} kg"],
        ["Geri kazanılan fire", f"{_format_tr(_number(results.get('geri_donusum')))} kg"],
        ["Nihai metal kaybı", f"{_format_tr(_number(results.get('ergitme')))} kg"],
        ["Fire maliyeti", f"{_format_tr(_number(results.get('fire_toplam')))} TL"],
        ["Elektrik tüketimi", f"{_format_tr(_number(results.get('elektrik_tuketim')))} kWh"],
        ["Doğalgaz tüketimi", f"{_format_tr(_number(results.get('gaz_tuketim')))} Sm³"],
        ["Su tüketimi", f"{_format_tr(_number(results.get('su_tuketim')))} m³"],
        [
            "Fabrika maliyeti toplamı",
            f"{_format_tr(_number(results.get('maliyet_ana_toplam_tl')))} TL",
        ],
        [
            "Fabrika maliyeti",
            (
                f"{_format_tr(_number(results.get('maliyet_ana_toplam_tl')) / production, 4)} TL/kg"
                if production > 0
                else "0,0000 TL/kg"
            ),
        ],
        [
            "Fabrika maliyeti",
            f"{_format_tr(_number(results.get('maliyet_ana_toplam_usd')))} USD",
        ],
        [
            "Fabrika maliyeti",
            f"{_format_tr(_number(results.get('maliyet_ana_usd_kg_toplam')), 4)} USD/kg",
        ],
        [
            "Fabrika maliyeti",
            f"{_format_tr(_number(results.get('maliyet_ana_usd_ton_toplam')))} USD/ton",
        ],
    ]
    technical_table = Table(technical_data, colWidths=[75 * mm, 75 * mm])
    technical_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular_font),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F7FB")),
                ("FONTNAME", (0, 0), (0, -1), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([technical_table, Spacer(1, 5 * mm)])

    story.append(Paragraph("Hesaplama Girdileri", heading_style))
    input_data: list[list[Any]] = [["Alan", "Değer", "Birim"]]
    for key, label, unit in INPUT_FIELDS:
        input_data.append([label, _format_tr(_number(inputs.get(key))), unit])

    input_table = Table(
        input_data,
        colWidths=[78 * mm, 48 * mm, 38 * mm],
        repeatRows=1,
    )
    input_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular_font),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163A70")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F4F7FB"),
                ]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D7DE")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            input_table,
            Spacer(1, 6 * mm),
            Paragraph(
                "Bu rapor, uygulamaya girilen değerler ve mevcut model "
                "katsayıları kullanılarak hazırlanmıştır.",
                normal_style,
            ),
        ]
    )

    document.build(story)
    return path
