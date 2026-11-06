from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from reports.exporters import _register_pdf_fonts


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def export_grid_excel(
    *,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    destination: str | Path,
    title: str = "",
    subtitle: str = "",
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (title or "Liste")[:31]

    navy = "163A70"
    light = "DCE6F1"
    border = Border(
        left=Side(style="thin", color="D0D7DE"),
        right=Side(style="thin", color="D0D7DE"),
        top=Side(style="thin", color="D0D7DE"),
        bottom=Side(style="thin", color="D0D7DE"),
    )

    row_index = 1
    if title:
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(headers), 1))
        cell = sheet.cell(row=1, column=1, value=title.upper())
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.font = Font(color="FFFFFF", bold=True, size=13)
        cell.alignment = Alignment(horizontal="center")
        row_index = 2
    if subtitle:
        sheet.merge_cells(
            start_row=row_index,
            start_column=1,
            end_row=row_index,
            end_column=max(len(headers), 1),
        )
        cell = sheet.cell(row=row_index, column=1, value=subtitle)
        cell.font = Font(color="667085", italic=True, size=9)
        cell.alignment = Alignment(horizontal="center")
        row_index += 1

    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=row_index, column=column, value=header)
        cell.fill = PatternFill("solid", fgColor=light)
        cell.font = Font(color=navy, bold=True)
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
    header_row = row_index
    row_index += 1

    for values in rows:
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=_format_cell(value))
            cell.border = border
        row_index += 1

    for column in range(1, len(headers) + 1):
        width = max(
            len(str(headers[column - 1])),
            max((len(_format_cell(row[column - 1])) for row in rows), default=0),
            8,
        )
        sheet.column_dimensions[get_column_letter(column)].width = min(width + 2, 42)
    sheet.freeze_panes = f"A{header_row + 1}"
    workbook.save(path)
    return path


def export_grid_pdf(
    *,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    destination: str | Path,
    title: str = "",
    subtitle: str = "",
    landscape_mode: bool = False,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    regular_font, bold_font = _register_pdf_fonts()
    page_size = landscape(A4) if landscape_mode or len(headers) > 8 else A4
    margin = 12 * mm

    document = SimpleDocTemplate(
        str(path),
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=title or "RIGEL COST PRO",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "GridTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=14,
        textColor=colors.HexColor("#163A70"),
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        "GridSubtitle",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=8,
        textColor=colors.HexColor("#667085"),
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )

    story: list[Any] = []
    if title:
        story.append(Paragraph(html.escape(title.upper()), title_style))
    meta = subtitle or f"Rapor tarihi: {datetime.now():%d.%m.%Y %H:%M}"
    story.append(Paragraph(html.escape(meta), subtitle_style))

    cell_style = ParagraphStyle(
        "GridCell",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=6 if len(headers) > 12 else 7 if len(headers) > 8 else 8,
        leading=8,
        textColor=colors.HexColor("#101828"),
    )
    header_style = ParagraphStyle(
        "GridHeader",
        parent=cell_style,
        fontName=bold_font,
        textColor=colors.HexColor("#163A70"),
        alignment=TA_CENTER,
    )

    def _cell(value: Any, *, header: bool = False) -> Paragraph:
        text = html.escape(_format_cell(value)).replace("\n", "<br/>")
        return Paragraph(text or "&nbsp;", header_style if header else cell_style)

    table_data: list[list[Any]] = [[_cell(header, header=True) for header in headers]]
    table_data.extend(
        [[_cell(value) for value in row] for row in rows]
    )
    usable_width = page_size[0] - 2 * margin
    # Önemli sütunlara biraz daha fazla yer ver; diğerleri eşit bölünür.
    n = max(len(headers), 1)
    weights = []
    for header in headers:
        key = str(header).upper()
        if any(token in key for token in ("FİRMA", "FIRMA", "MÜŞTERİ", "MUSTERI", "PROFİL", "PROFIL", "AÇIKLAMA")):
            weights.append(1.6)
        elif any(token in key for token in ("NO", "KG", "%", "DÖVİZ", "DOVIZ", "TARİH", "TARIH")):
            weights.append(1.1)
        else:
            weights.append(1.0)
    total_w = sum(weights)
    col_widths = [usable_width * (w / total_w) for w in weights]
    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D7DE")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.extend([table, Spacer(1, 2 * mm)])
    document.build(story)
    return path


def grid_html_document(
    *,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: str = "",
    subtitle: str = "",
) -> str:
    meta = subtitle or f"Rapor tarihi: {datetime.now():%d.%m.%Y %H:%M}"
    parts = [
        "<html><head><meta charset='utf-8'>",
        "<style>",
        "body { font-family: Arial, sans-serif; color:#1D2939; margin:12px; }",
        "h1 { color:#163A70; font-size:18px; text-align:center; margin:0 0 4px; }",
        "p.meta { color:#667085; font-size:10px; text-align:center; margin:0 0 12px; }",
        "table { border-collapse:collapse; width:100%; font-size:10px; }",
        "th { background:#DCE6F1; color:#163A70; padding:6px; border:1px solid #D0D7DE; }",
        "td { padding:5px; border:1px solid #D0D7DE; }",
        "tr:nth-child(even) td { background:#F4F7FB; }",
        "</style></head><body>",
    ]
    if title:
        parts.append(f"<h1>{html.escape(title.upper())}</h1>")
    parts.append(f"<p class='meta'>{html.escape(meta)}</p>")
    parts.append("<table><thead><tr>")
    parts.extend(f"<th>{html.escape(str(header))}</th>" for header in headers)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        parts.extend(f"<td>{html.escape(_format_cell(value))}</td>" for value in row)
        parts.append("</tr>")
    parts.append("</tbody></table></body></html>")
    return "".join(parts)
