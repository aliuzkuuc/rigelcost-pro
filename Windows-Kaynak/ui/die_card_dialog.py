"""KALIP KART — fabrika ERP düzeninde kalıp kartı ve veri dolu alt sekmeleri.

Kartın alt sekmeleri tek bir kalıp kimliği etrafında bağlıdır: kalıp → pres
fişleri → iş emri → sipariş satırı → müşteri ve stok hareketi. Alttaki tarih
aralığı bütün hareket sekmelerini birlikte süzer, böylece bir sekmedeki fiş
sayısı diğer sekmedeki hareketle aynı dönemi gösterir.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from PySide6.QtCore import QDate, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.column_filter_bar import FilterRowTable, normalize_tr
from ui.corporate_theme import stylesheet

# (anahtar, başlık, tip, genişlik) — tip hücre hizası ve biçimini belirler.
Column = tuple[str, str, str, int]

GROUP_HINT = "Gruplamak için bir sütun başlığını buraya sürükleyin"

QUICK_RANGES: tuple[tuple[str, str], ...] = (
    ("TARİH ARALIĞI", "custom"),
    ("BUGÜN", "today"),
    ("BU HAFTA", "week"),
    ("BU AY", "month"),
    ("SON 3 AY", "quarter"),
    ("BU YIL", "year"),
    ("TÜMÜ", "all"),
)

PRESS_COLUMNS: tuple[Column, ...] = (
    ("slip_no", "FİŞ NO", "text", 96),
    ("production_type", "ÜRETİM\nTİPİ", "text", 92),
    ("press_status", "PRES\nDURUM", "text", 88),
    ("saw_status", "TESTERE\nDURUM", "text", 92),
    ("station", "İSTASYON", "text", 80),
    ("operator_username", "OPERATÖR", "text", 88),
    ("shift", "VARDİYA", "text", 84),
    ("order_ref", "SİPARİŞ\nREF", "text", 92),
    ("work_order_no", "İŞ EMRİ\nNO", "text", 92),
    ("customer_name", "MÜŞTERİ", "text", 180),
    ("record_date", "TARİH", "datetime", 128),
    ("quantity", "ADET", "int", 72),
    ("net_kg", "NET KG", "num", 88),
    ("gross_kg", "BRÜT KG", "num", 88),
    ("metre", "METRE", "num", 88),
    ("fire_pct", "FİRE %", "num1", 70),
    ("tenefer_no", "TENEFER\nNO", "text", 84),
    ("lot_no", "LOT NO", "text", 92),
    ("test_result", "TEST\nSONUCU", "text", 90),
    ("die_problem", "KALIP\nPROBLEMİ", "text", 118),
)

TENEFER_DEFINITION_COLUMNS: tuple[Column, ...] = (
    ("tenefer_no", "TENEFER\nNO", "int", 92),
    ("operator_label", "OPERATÖR", "text", 100),
    ("limit_m", "ÖMÜR\nMETRE", "num1", 108),
)

TENEFER_USAGE_COLUMNS: tuple[Column, ...] = (
    ("tenefer_no", "TENEFER\nNO", "text", 92),
    ("limit_m", "ÖMÜR M", "num1", 96),
    ("used_m", "KULLANIM M", "num1", 108),
    ("remaining_m", "KALAN M", "num1", 100),
)

MOVEMENT_COLUMNS: tuple[Column, ...] = (
    ("record_date", "TARİH", "datetime", 128),
    ("movement_type", "HAREKET\nTİPİ", "text", 124),
    ("company", "FİRMA", "text", 170),
    ("quantity", "MİKTAR", "num", 84),
    ("unit", "BİRİM", "text", 70),
    ("location_from", "NEREDEN", "text", 110),
    ("location_to", "NEREYE", "text", 110),
    ("tenefer_no", "TENEFER\nNO", "text", 86),
    ("net_kg", "NET KG", "num", 88),
    ("metre", "METRE", "num", 88),
    ("note", "AÇIKLAMA", "text", 220),
    ("created_by", "KULLANICI", "text", 96),
)

SIBLING_COLUMNS: tuple[Column, ...] = (
    ("die_code", "KALIP\nKODU", "text", 100),
    ("spare_no", "YEDEK\nNO", "int", 74),
    ("status", "DURUM", "text", 94),
    ("figure_count", "FİGÜR", "int", 68),
    ("tenefer_no", "TENEFER\nNO", "text", 84),
    ("tenefer_type", "KALIP\nCİNSİ", "text", 112),
    ("tenefer_limit_m", "ÖMÜR M", "num1", 88),
    ("tenefer_used_m", "BASILAN M", "num1", 96),
    ("tenefer_remaining_m", "KALAN M", "num1", 90),
    ("life_limit_kg", "ÖMÜR KG", "num", 92),
    ("used_kg", "KULLANILAN\nKG", "num", 104),
    ("supplier_name", "TEDARİKÇİ", "text", 150),
    ("location", "RAF /\nKONUM", "text", 104),
)

STATION_COLUMNS: tuple[Column, ...] = (
    ("station_code", "İSTASYON\nKODU", "text", 124),
    ("station_name", "İSTASYON\nADI", "text", 200),
)

DOCUMENT_COLUMNS: tuple[Column, ...] = (
    ("document_type", "BELGE\nTİPİ", "text", 112),
    ("file_name", "DOSYA ADI", "text", 260),
    ("size_bytes", "BOYUT (B)", "int", 96),
    ("source_system", "KAYNAK", "text", 110),
    ("created_at", "TARİH", "datetime", 128),
)

PROBLEM_COLUMNS: tuple[Column, ...] = (
    ("problem_no", "PROBLEM\nNO", "text", 104),
    ("record_date", "TARİH", "datetime", 128),
    ("problem_type", "PROBLEM\nTİPİ", "text", 148),
    ("description", "AÇIKLAMA", "text", 260),
    ("status", "DURUM", "text", 118),
    ("source", "KAYNAK", "text", 118),
    ("slip_no", "FİŞ NO", "text", 96),
    ("station", "İSTASYON", "text", 88),
    ("operator_username", "OPERATÖR", "text", 92),
    ("created_by", "KULLANICI", "text", 96),
)

ORDER_LINE_COLUMNS: tuple[Column, ...] = (
    ("order_no", "SİPARİŞ\nNO", "text", 104),
    ("line_no", "SATIR", "int", 62),
    ("record_date", "TARİH", "date", 96),
    ("delivery_date", "TERMİN", "date", 96),
    ("customer_name", "MÜŞTERİ", "text", 180),
    ("profile_code", "PROFİL\nKODU", "text", 98),
    ("surface", "YÜZEY", "text", 92),
    ("color", "RENK", "text", 78),
    ("alloy", "ALAŞIM", "text", 80),
    ("production_length_mm", "BOY\n(mm)", "int", 76),
    ("ordered_quantity", "SİP.\nADET", "int", 80),
    ("ordered_kg", "SİP. KG", "num", 90),
    ("produced_quantity", "ÜRETİLEN\nADET", "int", 98),
    ("produced_kg", "ÜRETİLEN\nKG", "num", 98),
    ("shipped_quantity", "SEVK\nADET", "int", 84),
    ("shipped_kg", "SEVK KG", "num", 90),
    ("status", "DURUM", "text", 98),
)

STOCK_MOVEMENT_COLUMNS: tuple[Column, ...] = (
    ("record_date", "TARİH", "datetime", 128),
    ("movement_type", "HAREKET\nTİPİ", "text", 126),
    ("direction_label", "YÖN", "text", 70),
    ("stock_code", "STOK\nKODU", "text", 112),
    ("stock_name", "STOK ADI", "text", 190),
    ("warehouse_name", "AMBAR", "text", 130),
    ("quantity", "MİKTAR", "num", 92),
    ("unit", "BİRİM", "text", 68),
    ("lot_no", "LOT NO", "text", 96),
    ("work_order_no", "İŞ EMRİ\nNO", "text", 96),
    ("order_ref", "SİPARİŞ\nREF", "text", 92),
    ("customer_name", "MÜŞTERİ", "text", 170),
    ("document_no", "BELGE NO", "text", 104),
    ("created_by", "KULLANICI", "text", 96),
)

NUMERIC_KINDS = frozenset({"int", "num", "num1", "num3"})


def format_number(value: float, decimals: int) -> str:
    """Binlik ayırıcı nokta, ondalık virgül — fabrika çıktılarıyla aynı."""
    return f"{value:,.{decimals}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def format_cell(kind: str, value: Any) -> str:
    """Hücre metnini sütun tipine göre üretir; boş değer tire olarak görünür."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return ""
    if kind == "int":
        return format_number(_to_float(value), 0)
    if kind == "num":
        return format_number(_to_float(value), 2)
    if kind == "num1":
        return format_number(_to_float(value), 1)
    if kind == "num3":
        return format_number(_to_float(value), 3)
    if kind in {"date", "datetime"}:
        raw = str(value).strip().replace("T", " ")
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            day = f"{raw[8:10]}.{raw[5:7]}.{raw[0:4]}"
            if kind == "datetime" and len(raw) >= 16:
                return f"{day} {raw[11:16]}"
            return day
        return raw
    return str(value)


class ErpGrid(QWidget):
    """Gruplama şeridi, filtre satırı ve kayıt sayacı olan tam ERP gridi."""

    rowActivated = Signal(dict)

    def __init__(
        self,
        columns: Sequence[Column],
        *,
        title: str = "",
        show_group_bar: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("erpGrid")
        self._columns: list[Column] = list(columns)
        self._kinds = {key: kind for key, _label, kind, _w in self._columns}
        self._rows: list[dict[str, Any]] = []
        self._visible: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if title:
            caption = QLabel(title)
            caption.setObjectName("erpGridTitle")
            root.addWidget(caption)

        self.group_bar: QFrame | None = None
        if show_group_bar:
            self.group_bar = QFrame()
            self.group_bar.setObjectName("erpGroupBar")
            self.group_bar.setFixedHeight(24)
            group_layout = QHBoxLayout(self.group_bar)
            group_layout.setContentsMargins(8, 1, 6, 1)
            group_layout.setSpacing(6)
            hint = QLabel(GROUP_HINT)
            hint.setObjectName("erpGroupHint")
            group_layout.addWidget(hint)
            group_layout.addStretch(1)
            self.search = QLineEdit()
            self.search.setObjectName("erpGridSearch")
            self.search.setPlaceholderText("Ara…")
            self.search.setClearButtonEnabled(True)
            self.search.setFixedSize(190, 18)
            self.search.textChanged.connect(self._apply_filters)
            group_layout.addWidget(self.search)
            root.addWidget(self.group_bar)
        else:
            self.search = QLineEdit()
            self.search.setVisible(False)

        self.table = FilterRowTable()
        self.table.setObjectName("erpGridTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(21)
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        root.addWidget(self.table, 1)

        self.filter_bar = self.table.filter_bar
        self.filter_bar.set_idle_caption("=")
        self.filter_bar.set_value_formatter(self._format_for_filter)
        self.filter_bar.filtersChanged.connect(self._apply_filters)

        self.footer = QLabel("0")
        self.footer.setObjectName("erpGridFooter")
        self.footer.setAlignment(Qt.AlignCenter)
        root.addWidget(self.footer)

        self._configure_columns()
        self.table.itemDoubleClicked.connect(self._on_double_click)

    # ---- kurulum -----------------------------------------------------

    def _configure_columns(self) -> None:
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels(
            [label for _k, label, _t, _w in self._columns]
        )
        for index, (_key, _label, _kind, width) in enumerate(self._columns):
            self.table.setColumnWidth(index, width)
            item = self.table.horizontalHeaderItem(index)
            if item is not None:
                item.setTextAlignment(Qt.AlignCenter)
        # Filtre düğmesi tek satırlıktır; iki satırlı başlık orada sığmaz.
        self.filter_bar.configure(
            [(key, " ".join(label.split())) for key, label, _t, _w in self._columns]
        )

    def _format_for_filter(self, key: str, value: Any) -> str:
        return format_cell(self._kinds.get(key, "text"), value)

    # ---- veri --------------------------------------------------------

    def set_rows(self, rows: Iterable[dict[str, Any]]) -> None:
        self._rows = [dict(row) for row in rows]
        self.filter_bar.update_distinct_values(self._rows)
        self._apply_filters()

    def source_rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def visible_rows(self) -> list[dict[str, Any]]:
        return list(self._visible)

    def row_count(self) -> int:
        return len(self._visible)

    def column_keys(self) -> list[str]:
        return [key for key, _label, _kind, _width in self._columns]

    def column_labels(self) -> list[str]:
        return [label for _key, label, _kind, _width in self._columns]

    def column_kinds(self) -> dict[str, str]:
        return dict(self._kinds)

    def selected_row(self) -> dict[str, Any] | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._visible):
            return dict(self._visible[index])
        return None

    def _matches_search(self, row: dict[str, Any]) -> bool:
        needle = normalize_tr(self.search.text().strip()) if self.search else ""
        if not needle:
            return True
        for key, _label, kind, _width in self._columns:
            if needle in normalize_tr(format_cell(kind, row.get(key))):
                return True
        return False

    def _apply_filters(self) -> None:
        self._visible = [
            row for row in self._rows
            if self._matches_search(row) and self.filter_bar.row_matches(row)
        ]
        self._render()

    def _render(self) -> None:
        self.table.setRowCount(len(self._visible))
        for row_index, row in enumerate(self._visible):
            for column_index, (key, _label, kind, _width) in enumerate(self._columns):
                item = QTableWidgetItem(format_cell(kind, row.get(key)))
                if kind in NUMERIC_KINDS:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row_index, column_index, item)
        total = len(self._rows)
        shown = len(self._visible)
        self.footer.setText(
            format_number(shown, 0) if shown == total
            else f"{format_number(shown, 0)} / {format_number(total, 0)}"
        )

    def _on_double_click(self, _item: QTableWidgetItem) -> None:
        row = self.selected_row()
        if row is not None:
            self.rowActivated.emit(row)


class _TotalsStrip(QFrame):
    """TOP. BRÜT / TOP. NET / TOP. METRE / TOP. KULLANIM şeridi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dieTotalsStrip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._values: dict[str, QLabel] = {}
        for key, caption in (
            ("total_gross_kg", "TOP. BRÜT"),
            ("total_net_kg", "TOP. NET"),
            ("total_metre", "TOP. METRE"),
            ("total_usage", "TOP. KULLANIM"),
        ):
            cell = QFrame()
            cell.setObjectName("dieTotalCell")
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(8, 2, 8, 2)
            cell_layout.setSpacing(6)
            title = QLabel(f"{caption} :")
            title.setObjectName("dieTotalKey")
            value = QLabel("0")
            value.setObjectName("dieTotalValue")
            cell_layout.addWidget(title)
            cell_layout.addWidget(value)
            cell_layout.addStretch(1)
            layout.addWidget(cell, 1)
            self._values[key] = value

    def apply(self, header: dict[str, Any]) -> None:
        self._values["total_gross_kg"].setText(
            format_number(_to_float(header.get("total_gross_kg")), 2)
        )
        self._values["total_net_kg"].setText(
            format_number(_to_float(header.get("total_net_kg")), 2)
        )
        self._values["total_metre"].setText(
            format_number(_to_float(header.get("total_metre")), 2)
        )
        self._values["total_usage"].setText(
            format_number(_to_float(header.get("total_usage")), 0)
        )


class DieCardDialog(QDialog):
    """KALIP KART — başlık, ömür kutusu, toplam şeridi ve altı alt sekme."""

    TAB_KEYS = (
        "die_info",
        "tenefer",
        "movements",
        "press",
        "problems",
        "orders",
    )
    TAB_TITLES = (
        "KALIP BİLGİLERİ",
        "TENEFER BİLGİLERİ",
        "HAREKETLER",
        "PRES ÜRETİM BİLGİLERİ",
        "KALIBIN PROBLEMLERİ",
        "SİPARİŞ/STOK HAREKETLERİ",
    )

    def __init__(
        self,
        service: Any,
        die_id: int,
        *,
        username: str = "",
        can_edit: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.die_id = int(die_id)
        self.username = username
        self.can_edit = bool(can_edit)
        self.header_data: dict[str, Any] = service.die_card_header(self.die_id)

        self.setObjectName("dieCardDialog")
        self.setWindowTitle("KALIP KART")
        self.setSizeGripEnabled(True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.resize(1460, 880)
        self.setMinimumSize(1120, 660)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        root.addWidget(self._build_header())
        self.totals = _TotalsStrip()
        root.addWidget(self.totals)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("dieCardTabs")
        self.tabs.setDocumentMode(True)
        self.grids: dict[str, ErpGrid] = {}
        self._build_die_info_tab()
        self._build_tenefer_tab()
        self._build_movements_tab()
        self._build_press_tab()
        self._build_problems_tab()
        self._build_orders_tab()
        root.addWidget(self.tabs, 1)

        root.addWidget(self._build_footer())
        self.setStyleSheet(self._stylesheet())
        self.reload()

    # ---- başlık ------------------------------------------------------

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dieFieldCaption")
        return label

    def _read_only(self, value: Any, *, decimals: int | None = None) -> QLineEdit:
        text = (
            format_number(_to_float(value), decimals)
            if decimals is not None
            else ("" if value is None else str(value))
        )
        editor = QLineEdit(text)
        editor.setReadOnly(True)
        editor.setObjectName("dieReadOnly")
        return editor

    def _build_header(self) -> QWidget:
        data = self.header_data
        frame = QFrame()
        frame.setObjectName("dieHeader")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        self.profile_date = QDateEdit()
        self.profile_date.setDisplayFormat("dd.MM.yyyy")
        self.profile_date.setCalendarPopup(True)
        self.profile_date.setReadOnly(True)
        created = str(data.get("profile_created_at") or "")[:10]
        if len(created) == 10:
            self.profile_date.setDate(QDate.fromString(created, "yyyy-MM-dd"))
        else:
            self.profile_date.setDate(QDate.currentDate())
        self.customer_specific = QCheckBox()
        self.customer_specific.setChecked(bool(data.get("is_customer_specific")))
        self.customer_specific.setEnabled(False)

        entries: tuple[tuple[str, QWidget, int, int], ...] = (
            ("PROFİL KODU", self._read_only(data.get("profile_code")), 0, 0),
            ("TARİH", self.profile_date, 0, 1),
            (
                "BİRİM AĞIRLIK (Kg/m)",
                self._read_only(data.get("unit_weight_kg_m"), decimals=3),
                3,
                0,
            ),
            ("PROFİL GRUBU", self._read_only(data.get("profile_group")), 3, 1),
            (
                "MAX. BR. AĞIRLIK",
                self._read_only(
                    _to_float(data.get("unit_weight_kg_m")) * 1.05, decimals=3
                ),
                4,
                0,
            ),
            (
                "ÇEVRE (mm)",
                self._read_only(data.get("perimeter_mm"), decimals=3),
                4,
                1,
            ),
            (
                "MIN. BR. AĞIRLIK",
                self._read_only(
                    _to_float(data.get("unit_weight_kg_m")) * 0.90, decimals=3
                ),
                5,
                0,
            ),
            (
                "ALAN (mm²)",
                self._read_only(data.get("area_mm2"), decimals=3),
                5,
                1,
            ),
            ("KALIP CİNSİ", self._read_only(data.get("tenefer_type")), 6, 0),
        )
        for label, editor, row, column in entries:
            grid.addWidget(self._caption(label), row, column * 2)
            grid.addWidget(editor, row, column * 2 + 1)
        # Profil adı ve firma satırı iki sütunu birden kaplar.
        grid.addWidget(self._caption("PROFİL ADI"), 1, 0)
        grid.addWidget(self._read_only(data.get("profile_name")), 1, 1, 1, 3)
        grid.addWidget(self._caption("FİRMAYA ÖZEL"), 2, 0)
        owner = QHBoxLayout()
        owner.setSpacing(6)
        owner.addWidget(self.customer_specific)
        owner.addWidget(self._read_only(data.get("owner_customer_name")), 1)
        grid.addLayout(owner, 2, 1, 1, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(3, 2)
        layout.addLayout(grid, 5)

        life = QFrame()
        life.setObjectName("dieLifeBox")
        life_layout = QGridLayout(life)
        life_layout.setContentsMargins(8, 4, 8, 4)
        life_layout.setHorizontalSpacing(6)
        life_layout.setVerticalSpacing(2)
        self.life_labels: dict[str, QLabel] = {}
        life_rows = (
            ("spare_no", "YEDEK NO"),
            ("tenefer_no", "TENEFER NO"),
            ("tenefer_limit_m", "ÖMÜR (M)"),
            ("tenefer_used_m", "BASILAN (M)"),
            ("tenefer_remaining_m", "KALAN (M)"),
        )
        for index, (key, caption) in enumerate(life_rows):
            title = QLabel(f"{caption} :")
            title.setObjectName("dieLifeKey")
            value = QLabel("0")
            value.setObjectName("dieLifeValue")
            life_layout.addWidget(title, index, 0)
            life_layout.addWidget(value, index, 1)
            self.life_labels[key] = value
        # Referans: TEST SAYISI yanında üç renkli kutu (toplam / başarılı / başarısız).
        test_caption = QLabel("TEST SAYISI :")
        test_caption.setObjectName("dieLifeKey")
        self.test_total_label = QLabel("0")
        self.test_total_label.setObjectName("dieTestTotal")
        self.test_pass_label = QLabel("0")
        self.test_pass_label.setObjectName("dieTestPass")
        self.test_fail_label = QLabel("0")
        self.test_fail_label.setObjectName("dieTestFail")
        test_row = QHBoxLayout()
        test_row.setSpacing(4)
        test_row.addWidget(self.test_total_label)
        test_row.addWidget(self.test_pass_label)
        test_row.addWidget(self.test_fail_label)
        test_row.addStretch(1)
        life_layout.addWidget(test_caption, len(life_rows), 0)
        life_layout.addLayout(test_row, len(life_rows), 1, 1, 2)
        life_layout.setColumnStretch(1, 1)
        layout.addWidget(life, 2)

        self.drawing = QLabel()
        self.drawing.setObjectName("dieDrawing")
        self.drawing.setAlignment(Qt.AlignCenter)
        self.drawing.setMinimumSize(190, 130)
        self.drawing.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.drawing, 2)
        return frame

    # ---- alt sekmeler -------------------------------------------------

    def _register(self, key: str, grid: ErpGrid) -> ErpGrid:
        self.grids[key] = grid
        return grid

    @staticmethod
    def _section(title: str, widget: QWidget) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        caption = QLabel(title)
        caption.setObjectName("erpGridTitle")
        layout.addWidget(caption)
        layout.addWidget(widget, 1)
        return host

    def _build_die_info_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        data = self.header_data
        form_frame = QFrame()
        form_frame.setObjectName("dieEditCard")
        form = QFormLayout(form_frame)
        form.setContentsMargins(8, 8, 8, 8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        self.figure_count = QSpinBox()
        self.figure_count.setRange(1, 32)
        self.figure_count.setValue(max(1, int(data.get("figure_count") or 1)))
        self.life_limit_kg = QDoubleSpinBox()
        self.life_limit_kg.setDecimals(0)
        self.life_limit_kg.setRange(0, 1_000_000_000)
        self.life_limit_kg.setValue(_to_float(data.get("life_limit_kg")))
        self.tenefer_no_edit = QLineEdit(str(data.get("tenefer_no") or ""))
        self.tenefer_type_edit = QLineEdit(str(data.get("tenefer_type") or ""))
        self.tenefer_limit_edit = QDoubleSpinBox()
        self.tenefer_limit_edit.setDecimals(0)
        self.tenefer_limit_edit.setRange(0, 1_000_000_000)
        self.tenefer_limit_edit.setValue(_to_float(data.get("tenefer_limit_m")))
        self.supplier_edit = QLineEdit(str(data.get("supplier_name") or ""))
        self.location_edit = QLineEdit(str(data.get("location") or ""))
        self.note_edit = QPlainTextEdit(str(data.get("note") or ""))
        self.note_edit.setMaximumHeight(64)

        for caption, editor in (
            ("KALIP KODU", self._read_only(data.get("die_code"))),
            ("YEDEK NO", self._read_only(data.get("spare_no"), decimals=0)),
            ("DURUM", self._read_only(data.get("status"))),
            ("FİGÜR ADET", self.figure_count),
            ("ÖMÜR LİMİTİ (kg)", self.life_limit_kg),
            ("KULLANILAN (kg)", self._read_only(data.get("used_kg"), decimals=2)),
            ("TENEFER NO", self.tenefer_no_edit),
            ("KALIP CİNSİ", self.tenefer_type_edit),
            ("TENEFER ÖMRÜ (m)", self.tenefer_limit_edit),
            ("TEDARİKÇİ", self.supplier_edit),
            ("RAF / KONUM", self.location_edit),
            ("NOT", self.note_edit),
        ):
            form.addRow(self._caption(caption), editor)
        self.editable_fields = (
            self.figure_count,
            self.life_limit_kg,
            self.tenefer_no_edit,
            self.tenefer_type_edit,
            self.tenefer_limit_edit,
            self.supplier_edit,
            self.location_edit,
            self.note_edit,
        )
        for editor in self.editable_fields:
            editor.setEnabled(self.can_edit)
        form_frame.setMaximumWidth(380)
        layout.addWidget(form_frame)

        right = QSplitter(Qt.Vertical)
        right.addWidget(
            self._section(
                "PROFİLE BAĞLI KALIPLAR",
                self._register("die_info", ErpGrid(SIBLING_COLUMNS)),
            )
        )
        bottom = QSplitter(Qt.Horizontal)
        bottom.addWidget(
            self._section(
                "İSTASYON UYUMLULUĞU",
                self._register(
                    "die_stations", ErpGrid(STATION_COLUMNS, show_group_bar=False)
                ),
            )
        )
        bottom.addWidget(
            self._section(
                "BAĞLI DÖKÜMANLAR",
                self._register(
                    "die_documents", ErpGrid(DOCUMENT_COLUMNS, show_group_bar=False)
                ),
            )
        )
        bottom.setSizes([320, 640])
        right.addWidget(bottom)
        right.setSizes([420, 240])
        layout.addWidget(right, 1)
        self.tabs.addTab(page, self.TAB_TITLES[0])

    def _build_tenefer_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(
            self._section(
                "Ömür Tanımları",
                self._register(
                    "tenefer",
                    ErpGrid(TENEFER_DEFINITION_COLUMNS, show_group_bar=False),
                ),
            )
        )
        split.addWidget(
            self._section(
                "Kullanım",
                self._register(
                    "tenefer_usage",
                    ErpGrid(TENEFER_USAGE_COLUMNS, show_group_bar=False),
                ),
            )
        )
        split.setSizes([420, 560])
        layout.addWidget(split, 1)
        self.tabs.addTab(page, self.TAB_TITLES[1])

    def _build_movements_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.addWidget(self._register("movements", ErpGrid(MOVEMENT_COLUMNS)), 1)
        self.tabs.addTab(page, self.TAB_TITLES[2])

    def _build_press_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        self.press_tabs = QTabWidget()
        self.press_tabs.setObjectName("dieCardInnerTabs")
        self.press_tabs.setDocumentMode(True)
        for key, title in (
            ("press", "PRES ÜRETİM BİLGİLERİ"),
            ("press_test", "TEST ÜRETİMLERİ"),
        ):
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(2, 2, 2, 2)
            inner_layout.setSpacing(0)
            inner_layout.addWidget(self._register(key, ErpGrid(PRESS_COLUMNS)), 1)
            self.press_tabs.addTab(inner, title)
        layout.addWidget(self.press_tabs, 1)
        self.tabs.addTab(page, self.TAB_TITLES[3])

    def _build_problems_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.addWidget(self._register("problems", ErpGrid(PROBLEM_COLUMNS)), 1)
        self.tabs.addTab(page, self.TAB_TITLES[4])

    def _build_orders_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        self.order_tabs = QTabWidget()
        self.order_tabs.setObjectName("dieCardInnerTabs")
        self.order_tabs.setDocumentMode(True)
        for key, title, columns in (
            ("orders", "SİPARİŞ HAREKETLERİ", ORDER_LINE_COLUMNS),
            ("stock_movements", "STOK HAREKETLERİ", STOCK_MOVEMENT_COLUMNS),
        ):
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(2, 2, 2, 2)
            inner_layout.setSpacing(0)
            inner_layout.addWidget(self._register(key, ErpGrid(columns)), 1)
            self.order_tabs.addTab(inner, title)
        layout.addWidget(self.order_tabs, 1)
        self.tabs.addTab(page, self.TAB_TITLES[5])

    # ---- alt şerit ----------------------------------------------------

    def _build_footer(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("dieFooter")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        layout.addWidget(self._caption("Tarih Aralığı"))
        layout.addWidget(self._caption("Başlangıç"))
        self.date_from = QDateEdit()
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(QDate.currentDate().year() - 4, 1, 1))
        layout.addWidget(self.date_from)
        layout.addWidget(self._caption("Bitiş"))
        self.date_to = QDateEdit()
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        layout.addWidget(self.date_to)
        layout.addWidget(self._caption("Hızlı Seçim"))
        self.quick_range = QComboBox()
        for label, key in QUICK_RANGES:
            self.quick_range.addItem(label, key)
        self.quick_range.setMinimumWidth(140)
        layout.addWidget(self.quick_range)

        layout.addSpacing(10)
        self.print_button = QPushButton("YAZDIR")
        self.documents_button = QPushButton("DÖKÜMANLAR")
        self.profile_documents_button = QPushButton("PROFİL DÖKÜMANLARI")
        layout.addWidget(self.print_button)
        layout.addWidget(self.documents_button)
        layout.addWidget(self.profile_documents_button)
        layout.addStretch(1)
        self.close_button = QPushButton("KAPAT")
        self.close_button.setObjectName("dieClose")
        self.save_button = QPushButton("KAYDET")
        self.save_button.setObjectName("dieSave")
        self.save_button.setEnabled(self.can_edit)
        layout.addWidget(self.close_button)
        layout.addWidget(self.save_button)

        self.date_from.dateChanged.connect(self._on_date_changed)
        self.date_to.dateChanged.connect(self._on_date_changed)
        self.quick_range.currentIndexChanged.connect(self._apply_quick_range)
        self.print_button.clicked.connect(self.print_card)
        self.documents_button.clicked.connect(lambda: self.open_documents("DIE"))
        self.profile_documents_button.clicked.connect(
            lambda: self.open_documents("PROFILE")
        )
        self.close_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)
        return frame

    def _on_date_changed(self, *_args: object) -> None:
        if getattr(self, "_applying_range", False):
            return
        self.reload_movement_tabs()

    def _apply_quick_range(self, _index: int) -> None:
        key = self.quick_range.currentData()
        today = QDate.currentDate()
        if key == "custom":
            return
        if key == "today":
            start, end = today, today
        elif key == "week":
            start, end = today.addDays(-(today.dayOfWeek() - 1)), today
        elif key == "month":
            start, end = QDate(today.year(), today.month(), 1), today
        elif key == "quarter":
            start, end = today.addMonths(-3), today
        elif key == "year":
            start, end = QDate(today.year(), 1, 1), today
        else:
            start, end = QDate(2000, 1, 1), today.addYears(5)
        self._applying_range = True
        self.date_from.setDate(start)
        self.date_to.setDate(end)
        self._applying_range = False
        self.reload_movement_tabs()

    def date_range(self) -> tuple[str, str]:
        return (
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
        )

    # ---- veri yükleme -------------------------------------------------

    def reload(self) -> None:
        """Kartın tamamını yeniden okur — başlık, toplamlar ve altı sekme."""
        self.header_data = self.service.die_card_header(self.die_id)
        data = self.header_data
        self.totals.apply(data)
        self.life_labels["spare_no"].setText(
            format_number(_to_float(data.get("spare_no")), 0)
        )
        self.life_labels["tenefer_no"].setText(str(data.get("tenefer_no") or "—"))
        self.life_labels["tenefer_limit_m"].setText(
            format_number(_to_float(data.get("tenefer_limit_m")), 0)
        )
        self.life_labels["tenefer_used_m"].setText(
            format_number(_to_float(data.get("tenefer_used_m")), 1)
        )
        self.life_labels["tenefer_remaining_m"].setText(
            format_number(_to_float(data.get("tenefer_remaining_signed_m")), 1)
        )
        self.test_total_label.setText(
            format_number(_to_float(data.get("test_count")), 0)
        )
        self.test_pass_label.setText(
            format_number(_to_float(data.get("test_pass_count")), 0)
        )
        self.test_fail_label.setText(
            format_number(_to_float(data.get("test_fail_count")), 0)
        )

        self.grids["die_info"].set_rows(self.service.list_die_siblings(self.die_id))
        self.grids["die_stations"].set_rows(
            self.service.list_die_station_compatibility(self.die_id)
        )
        self.grids["die_documents"].set_rows(
            self.service.list_attachments("DIE", self.die_id)
        )
        tenefer = self.service.die_card_tenefer_life(self.die_id)
        self.grids["tenefer"].set_rows(tenefer["definitions"])
        self.grids["tenefer_usage"].set_rows(tenefer["usage"])
        self.grids["orders"].set_rows(self.service.list_die_order_lines(self.die_id))
        self._load_drawing()
        self.reload_movement_tabs()

    def reload_movement_tabs(self) -> None:
        """Tarih aralığına bağlı sekmeler — pres, hareket, problem, stok."""
        date_from, date_to = self.date_range()
        entries = self.service.list_die_press_entries(
            self.die_id, date_from=date_from, date_to=date_to
        )
        is_test = self.service.is_test_press_entry
        self.grids["press"].set_rows([row for row in entries if not is_test(row)])
        self.grids["press_test"].set_rows([row for row in entries if is_test(row)])
        self.grids["movements"].set_rows(
            self.service.list_die_movements(
                self.die_id, date_from=date_from, date_to=date_to
            )
        )
        self.grids["problems"].set_rows(
            self.service.list_die_problems(
                self.die_id, date_from=date_from, date_to=date_to
            )
        )
        self.grids["stock_movements"].set_rows(
            self.service.list_die_stock_movements(
                self.die_id, date_from=date_from, date_to=date_to
            )
        )

    def _load_drawing(self) -> None:
        """Profil görseli varsa kartın sağ üst kutusuna basılır."""
        for entity, entity_id in (
            ("DIE", self.die_id),
            ("PROFILE", int(self.header_data.get("profile_id") or 0)),
        ):
            if not entity_id:
                continue
            for attachment in self.service.list_attachments(entity, entity_id):
                content_type = str(attachment.get("content_type") or "")
                if not content_type.startswith("image/"):
                    continue
                pixmap = QPixmap(str(attachment.get("file_path") or ""))
                if pixmap.isNull():
                    continue
                self.drawing.setPixmap(
                    pixmap.scaled(
                        self.drawing.minimumWidth(),
                        self.drawing.minimumHeight(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                return
        self.drawing.setText(
            f"{self.header_data.get('profile_code') or ''}\nPROFİL RESMİ YOK"
        )

    # ---- eylemler ------------------------------------------------------

    def values(self) -> dict[str, Any]:
        return {
            "figure_count": self.figure_count.value(),
            "life_limit_kg": self.life_limit_kg.value(),
            "tenefer_no": self.tenefer_no_edit.text().strip(),
            "tenefer_type": self.tenefer_type_edit.text().strip(),
            "tenefer_limit_m": self.tenefer_limit_edit.value(),
            "supplier_name": self.supplier_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def open_documents(self, entity_type: str) -> list[dict[str, Any]]:
        entity_id = (
            self.die_id if entity_type == "DIE"
            else int(self.header_data.get("profile_id") or 0)
        )
        attachments = self.service.list_attachments(entity_type, entity_id)
        if not attachments:
            QMessageBox.information(
                self,
                "Bağlı belge yok",
                "Bu karta bağlı PDF veya görsel bulunmuyor.",
            )
            return []
        missing = [
            str(item.get("file_name") or "")
            for item in attachments
            if not QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(item.get("file_path") or ""))
            )
        ]
        if missing:
            QMessageBox.warning(self, "Bazı belgeler açılamadı", "\n".join(missing))
        return attachments

    def printable_rows(self) -> list[list[str]]:
        """Aktif sekmedeki görünür satırların yazdırılabilir dökümü."""
        grid = self.current_grid()
        if grid is None:
            return []
        keys = grid.column_keys()
        kinds = grid.column_kinds()
        return [
            [format_cell(kinds[key], row.get(key)) for key in keys]
            for row in grid.visible_rows()
        ]

    def current_grid(self) -> ErpGrid | None:
        index = self.tabs.currentIndex()
        key = self.TAB_KEYS[index] if 0 <= index < len(self.TAB_KEYS) else ""
        if key == "press":
            key = "press" if self.press_tabs.currentIndex() == 0 else "press_test"
        elif key == "orders":
            key = "orders" if self.order_tabs.currentIndex() == 0 else "stock_movements"
        return self.grids.get(key)

    def print_card(self) -> None:
        grid = self.current_grid()
        rows = self.printable_rows()
        if grid is None or not rows:
            QMessageBox.information(
                self, "Yazdırılacak satır yok", "Seçili sekmede görünür kayıt yok."
            )
            return
        QMessageBox.information(
            self,
            "Yazdırma hazır",
            f"{self.tabs.tabText(self.tabs.currentIndex())} — "
            f"{format_number(len(rows), 0)} satır yazdırmaya gönderildi.",
        )

    def accept(self) -> None:
        if not self.can_edit:
            super().accept()
            return
        try:
            self.service.update_die(
                self.die_id, username=self.username, **self.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kalıp kartı kaydedilemedi", str(error))
            return
        super().accept()

    # ---- görünüm -------------------------------------------------------

    @staticmethod
    def _stylesheet() -> str:
        return stylesheet(
            """
            #dieCardDialog { background:#EEF2F6; color:#1D2939; }
            #dieHeader, #dieFooter, #dieEditCard {
                background:#FFFFFF; border:1px solid #C5D0DE; border-radius:0;
            }
            #dieFieldCaption { color:#475467; font-size:10.5pt; font-weight:700; }
            #dieReadOnly { background:#F2F5F9; color:#101828; font-weight:700; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {
                border:1px solid #BFCDE0; border-radius:2px; padding:1px 4px;
                min-height:22px; background:#FFFFFF; color:#101828;
            }
            #dieLifeBox { background:#FFFFFF; border:2px solid #101828; }
            #dieLifeKey { color:#101828; font-size:11pt; font-weight:800; }
            #dieLifeValue { color:#101828; font-size:11pt; font-weight:800; }
            #dieTestTotal { color:#B42318; font-size:11pt; font-weight:800;
                            border:1px solid #B42318; padding:0 5px; min-width:18px; }
            #dieTestPass { color:#027A48; font-size:11pt; font-weight:800;
                           border:1px solid #027A48; padding:0 5px; min-width:18px; }
            #dieTestFail { color:#027A48; font-size:11pt; font-weight:800;
                           border:1px solid #027A48; padding:0 5px; min-width:18px; }
            #dieDrawing { background:#FFFFFF; border:1px solid #101828;
                          color:#98A2B3; font-size:10pt; font-weight:700; }
            #dieTotalCell { background:#FFFFFF; border:1px solid #101828; }
            #dieTotalKey { color:#101828; font-size:11pt; font-weight:800; }
            #dieTotalValue { color:#101828; font-size:11pt; font-weight:800; }
            #dieCardTabs::pane, #dieCardInnerTabs::pane {
                border:1px solid #C5D0DE; background:#FFFFFF; top:-1px;
            }
            #dieCardTabs QTabBar::tab, #dieCardInnerTabs QTabBar::tab {
                background:#E8EEF5; color:#1E3A5F; border:1px solid #C5D0DE;
                border-bottom:0; padding:3px 12px; margin-right:1px;
                font-size:10.5pt; font-weight:700; min-height:20px;
            }
            #dieCardTabs QTabBar::tab:selected, #dieCardInnerTabs QTabBar::tab:selected {
                background:#FFFFFF; color:#0B437C;
                border-bottom:2px solid #0B74BE;
            }
            #erpGridTitle {
                background:#E8EEF5; color:#0B437C; border:1px solid #C5D0DE;
                border-bottom:0; padding:2px 8px;
                font-size:10.5pt; font-weight:800;
            }
            #erpGroupBar {
                background:#F8FAFC; border:1px solid #C5D0DE; border-bottom:0;
            }
            #erpGroupHint { color:#667085; font-size:10pt; font-style:italic; }
            #erpGridSearch { min-height:16px; padding:0 4px; font-size:10pt; }
            #erpGridTable {
                background:#FFFFFF; alternate-background-color:#F7FAFC;
                gridline-color:#D6DEE8; border:1px solid #C5D0DE;
                selection-background-color:#0B437C; selection-color:#FFFFFF;
                font-size:11pt;
            }
            #erpGridTable QHeaderView::section {
                background:#0B437C; color:#FFFFFF; border:1px solid #083562;
                padding:3px 5px; font-size:11pt; font-weight:700;
            }
            #erpGridTable QScrollBar:vertical { width:11px; background:#F2F5F9; }
            #erpGridTable QScrollBar:horizontal { height:11px; background:#F2F5F9; }
            #erpGridTable QScrollBar::handle {
                background:#B7C7DB; border-radius:5px; min-height:24px; min-width:24px;
            }
            #erpGridTable QScrollBar::add-line, #erpGridTable QScrollBar::sub-line {
                width:0; height:0;
            }
            #erpGridFooter {
                background:#EAF3FC; border:1px solid #B7D1EC; border-top:0;
                color:#1E3A5F; font-size:10.5pt; font-weight:700; max-height:20px;
            }
            #columnFilterBar {
                background:#EEF2F7; border:0; border-bottom:1px solid #BFCDE0;
            }
            #columnFilterInner { background:#EEF2F7; }
            #columnFilterBar QToolButton#columnFilterButton {
                color:#101828; background:#FFFFFF; border:1px solid #C5D0DE;
                border-radius:0; padding:0 4px; font-size:10pt;
                min-height:20px; text-align:left;
            }
            #columnFilterBar QToolButton#columnFilterButton[filterActive="true"] {
                background:#DBEAFE; border-color:#3B82F6; font-weight:700;
            }
            #dieSave { color:#FFFFFF; background:#0B5A9C; border-color:#0B437C;
                       min-width:100px; font-weight:800; }
            #dieClose { color:#FFFFFF; background:#B42318; border-color:#912018;
                        min-width:100px; font-weight:800; }
            """
        )
