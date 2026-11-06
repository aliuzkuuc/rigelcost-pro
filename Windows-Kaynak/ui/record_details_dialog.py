"""Kayıt detay penceresi — fabrika ERP fiş düzeni.

Düzen dört parçadan oluşur: üstte fiş bilgisi formu, sağda miktar/özet
paneli, ortada sekmeli satır ızgaraları (her sekmede sütun filtre satırı ve
satır sayacı) ve altta sabit buton çubuğu.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyleOption,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.column_filter_bar import FilterRowTable
from ui.corporate_theme import stylesheet

# Sağ miktar panelinin kendiliğinden dolması için aranan alan adları.
QUANTITY_HINTS = (
    "kg",
    "adet",
    "miktar",
    "tutar",
    "bakiye",
    "metre",
    "boy",
    "fiyat",
    "toplam",
)
ROWS_PER_FORM_COLUMN = 7
MAX_FORM_COLUMNS = 3
# Kaydırma çubuğu çıkmadan gösterilebilecek en fazla form satırı.
MAX_FORM_ROWS = 10
FORM_ROW_HEIGHT = 28
# Yalnızca toplanabilir sütunlar alt şeritte özetlenir; sıra/boy/fiyat toplanmaz.
SUMMABLE_HEADER_HINTS = (
    "KG",
    "ADET",
    "MİKTAR",
    "TUTAR",
    "METRE",
    "BAKİYE",
    "TOPLAM",
    "FİRE",
    "HURDA",
)


def upper_tr(text: object) -> str:
    """Türkçe büyük harf — 'i' harfi noktalı 'İ' olur."""
    return str(text or "").replace("i", "İ").replace("ı", "I").upper()


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "EVET" if value else "HAYIR"
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{value:,.0f}"
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    text = str(value).strip()
    return text if text else "—"


def _is_numeric(text: str) -> bool:
    """Sayısal hücreler sağa dayanır; tarih ve kodlar sola kalır."""
    candidate = text.strip().replace(" ", "")
    if not candidate or candidate == "—":
        return False
    if any(character.isalpha() for character in candidate):
        return False
    if candidate.count("-") > 1 or candidate.count("/") > 0:
        return False
    # Baştan sıfırlı diziler fiş/iş emri kodudur, tutar değil.
    digits = candidate.lstrip("+-")
    if len(digits) > 1 and digits.startswith("0") and not digits.startswith("0."):
        return False
    return any(character.isdigit() for character in candidate)


def _to_float(text: str) -> float | None:
    """Hem 1.234,56 hem 1,234.56 biçimini toplanabilir sayıya çevirir."""
    raw = str(text or "").strip().replace(" ", "").replace("%", "")
    if not raw or raw == "—":
        return None
    if "," in raw and "." in raw:
        raw = (
            raw.replace(".", "").replace(",", ".")
            if raw.rfind(",") > raw.rfind(".")
            else raw.replace(",", "")
        )
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _format_total(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.3f}".rstrip("0").rstrip(".")
    return text.replace(",", "#").replace(".", ",").replace("#", ".")


class ValueLabel(QLabel):
    """Salt okunur form alanı — dar sütunda metni üç nokta ile kısaltır.

    ``text()`` tam değeri döndürmeye devam eder; kısaltma yalnızca çizimdedir.
    """

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt imzası
        hint = super().minimumSizeHint()
        return QSize(min(70, hint.width()), hint.height())

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt imzası
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)
        rect = self.contentsRect().adjusted(6, 0, -6, 0)
        elided = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, int(Qt.AlignLeft | Qt.AlignVCenter), elided)


class DetailGrid(QWidget):
    """Sekme içeriği: başlık altına gömülü filtre satırı + yoğun ızgara + toplam."""

    def __init__(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        *,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("detailGrid")
        self.grid_title = title
        self._headers = [upper_tr(header) for header in headers]
        column_count = len(self._headers)
        self._rows = [
            [_display(row[index] if index < len(row) else None) for index in range(column_count)]
            for row in rows
        ]
        self._keys = [f"c{index}" for index in range(column_count)]
        self._row_dicts = [dict(zip(self._keys, row)) for row in self._rows]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        caption = QLabel(upper_tr(title))
        caption.setObjectName("gridCaption")
        toolbar.addWidget(caption)
        toolbar.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setObjectName("gridCount")
        toolbar.addWidget(self.count_label)
        self.filter_toggle = QPushButton("FİLTRE SATIRI")
        self.filter_toggle.setObjectName("gridAction")
        self.filter_toggle.setCheckable(True)
        self.filter_toggle.setChecked(True)
        self.filter_toggle.toggled.connect(self._toggle_filter_row)
        toolbar.addWidget(self.filter_toggle)
        self.clear_filters = QPushButton("FİLTRE TEMİZLE")
        self.clear_filters.setObjectName("gridAction")
        self.clear_filters.clicked.connect(self._clear_filters)
        toolbar.addWidget(self.clear_filters)
        layout.addLayout(toolbar)

        self.table = FilterRowTable()
        self.table.setObjectName("detailsTable")
        self.table.setColumnCount(column_count)
        self.table.setRowCount(len(self._rows))
        self.table.setHorizontalHeaderLabels(self._headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setWordWrap(False)
        self.table.setCornerButtonEnabled(False)
        vertical = self.table.verticalHeader()
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(22)
        vertical.setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        for row_index, row in enumerate(self._rows):
            for column, text in enumerate(row):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if _is_numeric(text):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)

        # Filtre satırı tablo başlığının altına gömülür (fabrika ERP).
        self.filter_bar = self.table.filter_bar
        self.filter_bar.set_idle_caption("=")
        self.filter_bar.configure(list(zip(self._keys, self._headers)))
        self.filter_bar.update_distinct_values(self._row_dicts)
        self.filter_bar.filtersChanged.connect(self._apply_filters)
        layout.addWidget(self.table, 1)

        self.totals_label = QLabel()
        self.totals_label.setObjectName("gridTotals")
        self.totals_label.setVisible(False)
        layout.addWidget(self.totals_label)

        self._minimum_widths = self._measure_columns()
        self._refresh_summary(list(range(len(self._rows))))
        if not self._rows:
            # Boş sekmede sütun başlıkları + filtre satırı görünsün.
            self.table.setMaximumHeight(110)
            self.empty_hint = QLabel("Bu sekmede kayıt bulunmuyor.")
            self.empty_hint.setObjectName("detailsEmpty")
            layout.insertWidget(layout.indexOf(self.totals_label), self.empty_hint)
            layout.addStretch(1)

    # ---- iç yardımcılar ---------------------------------------------

    def _measure_columns(self) -> list[int]:
        self.table.resizeColumnsToContents()
        metrics = self.table.horizontalHeader().fontMetrics()
        return [
            max(
                60,
                min(
                    360,
                    max(
                        self.table.columnWidth(column),
                        metrics.horizontalAdvance(self._headers[column]) + 30,
                    ),
                ),
            )
            for column in range(self.table.columnCount())
        ]

    def _toggle_filter_row(self, visible: bool) -> None:
        self.filter_bar.setVisible(visible)
        if not visible:
            self.filter_bar.clear_filters()
        self.table.updateGeometries()

    def _clear_filters(self) -> None:
        self.filter_bar.clear_filters()

    def _apply_filters(self) -> None:
        visible: list[int] = []
        for index, row in enumerate(self._row_dicts):
            matches = self.filter_bar.row_matches(row)
            self.table.setRowHidden(index, not matches)
            if matches:
                visible.append(index)
        self._refresh_summary(visible)

    def _refresh_summary(self, visible_rows: Sequence[int]) -> None:
        total = len(self._rows)
        shown = len(visible_rows)
        self.count_label.setText(
            f"{shown} satır" if shown == total else f"{shown} / {total} satır"
        )
        parts: list[str] = []
        for column, header in enumerate(self._headers):
            if not any(hint in header for hint in SUMMABLE_HEADER_HINTS):
                continue
            values: list[float] = []
            numeric_only = True
            for index in visible_rows:
                text = self._rows[index][column]
                if text in {"", "—"}:
                    continue
                number = _to_float(text) if _is_numeric(text) else None
                if number is None:
                    numeric_only = False
                    break
                values.append(number)
            if not numeric_only or not values:
                continue
            parts.append(f"{header}: {_format_total(sum(values))}")
            if len(parts) >= 6:
                break
        self.totals_label.setText("TOPLAM   ·   " + "   ·   ".join(parts) if parts else "")
        self.totals_label.setVisible(bool(parts))

    def visible_row_count(self) -> int:
        return sum(
            1 for index in range(self.table.rowCount()) if not self.table.isRowHidden(index)
        )

    def row_count(self) -> int:
        return len(self._rows)

    def fit_columns(self) -> None:
        """Sütunları başlık+içerik genişliğinin altına düşürmeden yayar."""
        if not self._minimum_widths:
            return
        available = self.table.viewport().width()
        total = sum(self._minimum_widths)
        if total <= 0:
            return
        if available > total:
            scale = available / total
            widths = [int(width * scale) for width in self._minimum_widths]
            widths[-1] += available - sum(widths)
        else:
            widths = list(self._minimum_widths)
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)
        self.filter_bar.sync_widths()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt imzası
        super().showEvent(event)
        self.fit_columns()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt imzası
        super().resizeEvent(event)
        self.fit_columns()


class RecordDetailsDialog(QDialog):
    """Fiş bilgisi formu, miktar paneli ve alt sekmeli satır ızgaraları."""

    def __init__(
        self,
        title: str,
        text: str | None = None,
        parent: QWidget | None = None,
        *,
        fields: Sequence[tuple[str, Any]] | None = None,
        tables: Sequence[dict[str, Any]] | None = None,
        stats: Sequence[Sequence[Any]] | None = None,
        stats_headers: Sequence[str] | None = None,
        stats_title: str = "MİKTARLAR",
        header_title: str = "FİŞ BİLGİSİ",
        subtitle: str = "",
        status: str = "",
        image_path: str | None = None,
        actions: Sequence[tuple[str, Callable[[], None]]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(900, 600)
        self.resize(1320, 800)
        self.setSizeGripEnabled(True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.grids: list[DetailGrid] = []
        self._tables: list[QTableWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        root.addLayout(self._build_title_bar(title, subtitle, status))

        field_rows = self._normalize_fields(fields, text, tables)
        self.stat_rows = self._normalize_stats(stats, field_rows)
        self.stat_headers = list(stats_headers or ("BİLGİ", "DEĞER"))

        # Referans fiş: üstte FİŞ BİLGİSİ (+ görsel), altta sekmeler | MİKTARLAR.
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self._build_form_block(header_title, field_rows), 3)
        image_only = self._build_image_block(image_path)
        if image_only is not None:
            top.addWidget(image_only, 1)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("detailTabs")
        self.tabs.setDocumentMode(True)
        self.pinned_grids: list[DetailGrid] = []
        for table_spec in tables or []:
            headers = [str(header) for header in table_spec.get("headers") or []]
            rows = list(table_spec.get("rows") or [])
            grid_title = str(table_spec.get("title") or "Satırlar")
            if not headers and rows:
                headers = [f"S{index + 1}" for index in range(len(rows[0]))]
            grid = DetailGrid(headers, rows, title=grid_title)
            self.grids.append(grid)
            self._tables.append(grid.table)
            if table_spec.get("pinned"):
                self.pinned_grids.append(grid)
            else:
                self.tabs.addTab(grid, f"{upper_tr(grid_title)}  ({len(rows)})")
        body = self._build_grid_area()
        side = self._build_stats_block(stats_title)
        if body is not None or side is not None:
            middle = QHBoxLayout()
            middle.setSpacing(8)
            if body is not None:
                middle.addWidget(body, 4)
            if side is not None:
                middle.addWidget(side, 1)
            root.addLayout(middle, 1)
        else:
            root.addStretch(1)

        root.addLayout(self._build_footer(actions))
        self.setStyleSheet(stylesheet(self._qss()))

    # ---- bölümler ----------------------------------------------------

    def _build_grid_area(self) -> QWidget | None:
        """Sekmeli ızgaralar; sabitlenmiş ızgaralar altta ayrı bölmede kalır."""
        if not self.tabs.count() and not self.pinned_grids:
            return None
        pinned_frames: list[QWidget] = []
        for grid in self.pinned_grids:
            frame = QFrame()
            frame.setObjectName("voucherCard")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)
            frame_layout.addWidget(grid)
            pinned_frames.append(frame)
        if not pinned_frames:
            return self.tabs
        splitter = QSplitter(Qt.Vertical)
        splitter.setObjectName("detailSplitter")
        splitter.setChildrenCollapsible(False)
        if self.tabs.count():
            splitter.addWidget(self.tabs)
        for frame in pinned_frames:
            splitter.addWidget(frame)
        for index in range(splitter.count()):
            splitter.setStretchFactor(index, 2 if index == 0 else 1)
        return splitter

    def _build_title_bar(self, title: str, subtitle: str, status: str) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(10)
        heading = QLabel(upper_tr(title))
        heading.setObjectName("detailsHeading")
        bar.addWidget(heading)
        if subtitle:
            note = QLabel(subtitle)
            note.setObjectName("detailsSubtitle")
            bar.addWidget(note)
        bar.addStretch(1)
        if status:
            chip = QLabel(upper_tr(status))
            chip.setObjectName("detailsStatus")
            bar.addWidget(chip)
        return bar

    @staticmethod
    def _normalize_fields(
        fields: Sequence[tuple[str, Any]] | None,
        text: str | None,
        tables: Sequence[dict[str, Any]] | None,
    ) -> list[tuple[str, Any]]:
        field_rows = list(fields or [])
        if field_rows or not text or tables:
            return field_rows
        # Eski düz metin çağrıları: satırları etiket/değer çiftine ayır.
        for line in text.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if ":" in raw:
                label, _, value = raw.partition(":")
                field_rows.append((label.strip(), value.strip()))
            else:
                field_rows.append(("", raw))
        return field_rows

    @staticmethod
    def _normalize_stats(
        stats: Sequence[Sequence[Any]] | None,
        field_rows: Sequence[tuple[str, Any]],
    ) -> list[list[Any]]:
        if stats is not None:
            return [list(row) for row in stats]
        derived: list[list[Any]] = []
        for label, value in field_rows:
            key = str(label).casefold()
            if not any(hint in key for hint in QUANTITY_HINTS):
                continue
            shown = _display(value)
            if shown == "—" or not _is_numeric(shown):
                continue
            derived.append([upper_tr(label), shown])
            if len(derived) >= 14:
                break
        return derived

    def _build_form_block(
        self, header_title: str, field_rows: Sequence[tuple[str, Any]]
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("voucherCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        caption = QLabel(upper_tr(header_title))
        caption.setObjectName("cardCaption")
        outer.addWidget(caption)

        scroll = QScrollArea()
        scroll.setObjectName("formScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        visible = [(label, value) for label, value in field_rows]
        columns = 1
        if visible:
            columns = min(
                MAX_FORM_COLUMNS,
                max(1, -(-len(visible) // ROWS_PER_FORM_COLUMN)),
            )
        per_column = -(-len(visible) // columns) if visible else 0
        for index, (label, value) in enumerate(visible):
            column = index // per_column if per_column else 0
            row = index % per_column if per_column else index
            key = QLabel(upper_tr(label) if label else "")
            key.setObjectName("detailsKey")
            key.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            key.setMinimumWidth(88)
            val = ValueLabel(_display(value))
            val.setObjectName("detailsValue")
            val.setToolTip(_display(value))
            val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid.addWidget(key, row, column * 2)
            grid.addWidget(val, row, column * 2 + 1)
        for column in range(columns):
            grid.setColumnStretch(column * 2 + 1, 1)
        grid.setRowStretch(grid.rowCount(), 1)

        if not visible:
            empty = QLabel("Bu kart için alan tanımı bulunmuyor.")
            empty.setObjectName("detailsEmpty")
            grid.addWidget(empty, 0, 0)

        scroll.setWidget(body)
        outer.addWidget(scroll)
        rows_shown = min(per_column or 1, MAX_FORM_ROWS)
        card.setFixedHeight(52 + rows_shown * FORM_ROW_HEIGHT)
        return card

    def _build_image_block(self, image_path: str | None) -> QWidget | None:
        if not image_path:
            return None
        candidate = QPixmap(image_path)
        if candidate.isNull():
            return None
        frame = QFrame()
        frame.setObjectName("voucherCard")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(6, 6, 6, 6)
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setPixmap(
            candidate.scaled(240, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        frame_layout.addWidget(image)
        frame.setMinimumWidth(220)
        frame.setMaximumWidth(280)
        return frame

    def _build_stats_block(self, stats_title: str) -> QWidget | None:
        """MİKTARLAR paneli — sekmelerin sağında (referans üretim emri fişi)."""
        if not self.stat_rows:
            return None

        card = QFrame()
        card.setObjectName("voucherCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        caption = QLabel(upper_tr(stats_title))
        caption.setObjectName("cardCaption")
        card_layout.addWidget(caption)

        width = max(len(row) for row in self.stat_rows)
        headers = [upper_tr(header) for header in self.stat_headers]
        while len(headers) < width:
            headers.append("")
        self.stats_table = QTableWidget(len(self.stat_rows), width)
        self.stats_table.setObjectName("statsTable")
        self.stats_table.setHorizontalHeaderLabels(headers[:width])
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.verticalHeader().setDefaultSectionSize(21)
        self.stats_table.horizontalHeader().setFixedHeight(24)
        for row_index, row in enumerate(self.stat_rows):
            for column in range(width):
                text = _display(row[column] if column < len(row) else None)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if column and _is_numeric(text):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # Referans: uygun/stok satırları yeşil vurgu alır.
                if column == 0 and "UYGUN" in text.upper():
                    item.setBackground(QBrush(QColor("#D1FADF")))
                self.stats_table.setItem(row_index, column, item)
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, width):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        card_layout.addWidget(self.stats_table)
        card.setMinimumWidth(240)
        card.setMaximumWidth(360)
        return card

    def _build_side_block(self, stats_title: str, image_path: str | None) -> QWidget | None:
        """Geriye dönük: görsel + miktarlar tek blokta."""
        image = self._build_image_block(image_path)
        stats = self._build_stats_block(stats_title)
        if image is None and stats is None:
            return None
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        if stats is not None:
            layout.addWidget(stats, 1)
        if image is not None:
            layout.addWidget(image)
        container.setMinimumWidth(260)
        container.setMaximumWidth(400)
        return container

    def _build_footer(
        self, actions: Sequence[tuple[str, Callable[[], None]]] | None
    ) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setSpacing(8)
        summary = QLabel(
            "   ·   ".join(
                f"{upper_tr(grid.grid_title)}: {grid.row_count()}" for grid in self.grids
            )
        )
        summary.setObjectName("footerSummary")
        footer.addWidget(summary)
        footer.addStretch(1)
        for label, callback in actions or ():
            button = QPushButton(upper_tr(label))
            button.setObjectName("detailsAction")
            button.clicked.connect(callback)
            footer.addWidget(button)
        close = QPushButton("KAPAT")
        close.setObjectName("detailsClose")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        return footer

    @staticmethod
    def _qss() -> str:
        return """
        QDialog { background:#EEF2F6; color:#1D2939; }
        #detailsHeading {
            color:#0B437C; font-size:12pt; font-weight:800; letter-spacing:0.3px;
        }
        #detailsSubtitle { color:#475467; font-size:11pt; font-weight:700; }
        #detailsStatus {
            color:#0B4A82; background:#DCEBFA; border:1px solid #9EC5E8;
            border-radius:3px; padding:2px 10px; font-weight:800; font-size:10.5pt;
        }
        #voucherCard {
            background:#FFFFFF; border:1px solid #C7D2DE; border-radius:4px;
        }
        #cardCaption {
            background:#E8EFF7; color:#0B4A82; font-weight:800; font-size:10.5pt;
            padding:4px 8px; border-bottom:1px solid #C7D2DE; letter-spacing:0.4px;
        }
        #formScroll { background:#FFFFFF; border:0; }
        #formScroll > QWidget > QWidget { background:#FFFFFF; }
        #detailsKey { color:#475467; font-size:10.5pt; font-weight:700; }
        #detailsValue {
            color:#101828; font-size:11pt; font-weight:700;
            background:#F7F9FC; border:1px solid #DCE3EC; border-radius:3px;
            padding:2px 6px; min-height:18px;
        }
        #detailsEmpty { color:#98A2B3; font-size:11pt; padding:6px; }
        #detailTabs::pane {
            background:#FFFFFF; border:1px solid #C7D2DE; border-radius:4px; top:-1px;
        }
        #detailTabs QTabBar::tab {
            background:#DCE5EF; color:#33475E; border:1px solid #C7D2DE;
            border-bottom:0; padding:4px 12px; margin-right:2px; font-weight:700;
        }
        #detailTabs QTabBar::tab:selected {
            background:#FFFFFF; color:#0B4A82; font-weight:800;
        }
        #gridCaption { color:#0B4A82; font-size:10.5pt; font-weight:800; }
        #gridCount { color:#475467; font-size:10.5pt; font-weight:700; }
        #gridTotals {
            color:#0B4A82; background:#F2F6FB; border:1px solid #DCE3EC;
            border-radius:3px; padding:3px 8px; font-size:10.5pt; font-weight:800;
        }
        #gridAction {
            color:#163A70; background:#FFFFFF; border:1px solid #AFC3DC;
            border-radius:3px; padding:1px 8px; font-size:9.5pt; font-weight:700;
            min-height:20px;
        }
        #gridAction:checked { background:#DCEBFA; border-color:#7FAFDA; }
        #detailsTable, #statsTable {
            background:#FFFFFF; gridline-color:#E4E7EC;
            alternate-background-color:#F8FAFC; border:0;
        }
        #detailsTable QHeaderView::section, #statsTable QHeaderView::section {
            background:#0B4A82; color:#FFFFFF; font-weight:800; font-size:10.5pt;
            padding:3px 6px; border:0; border-right:1px solid #1A5F9A;
        }
        #columnFilterBar { background:#EDF2F8; border-bottom:1px solid #D0D5DD; }
        #columnFilterButton {
            background:#FFFFFF; border:1px solid #C7D2DE; border-radius:2px;
            color:#475467; font-size:9pt; padding:1px 4px;
        }
        #columnFilterButton[filterActive="true"] {
            background:#FEF0C7; border-color:#F79009; color:#7A2E0E; font-weight:800;
        }
        #footerSummary { color:#667085; font-size:10.5pt; font-weight:700; }
        #detailsClose, #detailsAction {
            color:#FFFFFF; background:#0B4A82; border:0; border-radius:4px;
            min-width:110px; min-height:30px; font-weight:800;
        }
        #detailsAction { background:#3D5A80; }
        #detailsClose:hover { background:#0A3F70; }
        #detailsAction:hover { background:#2F4A6D; }
        """

    # ---- geriye dönük yardımcılar ------------------------------------

    def _fit_table_columns(self) -> None:
        for grid in self.grids:
            grid.fit_columns()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt imzası
        super().showEvent(event)
        self._fit_table_columns()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt imzası
        super().resizeEvent(event)
        self._fit_table_columns()


# Geriye dönük ad
WorkflowDetailsDialog = RecordDetailsDialog
