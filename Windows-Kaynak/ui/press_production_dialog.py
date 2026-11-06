"""Pres üretim fişi giriş ekranı.

Fişin üç dökümü birbirine bağlıdır: brüt kilogram billet satırlarından,
net kilogram ve adet sepet satırlarından gelir, fire ise ikisinin farkıdır ve
hurda kırılımıyla örtüşmek zorundadır. Toplamlar canlı hesaplanır.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.corporate_theme import stylesheet, title_style

DIE_PROBLEMS = (
    "",
    "GÖRÜNTÜ BOZUK",
    "ÖLÇÜ DIŞI",
    "ÇATLAK / KAYIK",
    "AKIŞ DENGESİZ",
    "KALIP KIRILDI",
    "YÜZEY ÇİZİK",
)
SCRAP_REASONS = ("HURDA", "ARA İŞ", "BAŞLANGIÇ FİRESİ", "KISA BOY", "TEST")

BILLET_COLUMNS = (
    ("billet_length_mm", "BİLLET BOY", 0),
    ("billet_count", "BİLLET ADET", 0),
    ("length_count", "BOY ADEDİ", 0),
    ("total_length_count", "TOPLAM BOY", 0),
    ("gross_kg", "BRÜT KG", 2),
    ("raw_material_stock", "HAMMADDE", None),
    ("lot_no", "LOT NO", None),
    ("dummy_length_mm", "DÜPÇİK BOY", 0),
    ("press_speed_m_s", "BASKI ZAM. (m/sn)", 1),
    ("container_temp_c", "KOVAN °C", 0),
    ("die_temp_c", "KALIP °C", 0),
    ("billet_temp_c", "BİLLET °C", 0),
    ("exit_temp_c", "ÇIKIŞ °C", 0),
    ("note", "AÇIKLAMA", None),
)
BASKET_COLUMNS = (
    ("basket_no", "SEPET NO", None),
    ("length_mm", "BOY (mm)", 0),
    ("quantity", "ADET", 0),
    ("net_kg", "KG", 2),
    ("work_order_no", "İŞ EMRİ NO", None),
)
SCRAP_COLUMNS = (
    ("scrap_reason", "HURDA SEBEBİ", None),
    ("quantity", "ADET", 0),
    ("kg", "KG", 2),
)


def _to_number(text: str) -> float:
    raw = str(text or "").strip().replace(" ", "")
    if not raw:
        return 0.0
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
        return 0.0


def _format(value: float, decimals: int) -> str:
    return f"{value:,.{decimals}f}".replace(",", "#").replace(".", ",").replace("#", ".")


class EditableGrid(QTableWidget):
    """Son satıra yazılınca kendiliğinden yeni satır açan giriş tablosu."""

    def __init__(
        self,
        columns: tuple[tuple[str, str, int | None], ...],
        *,
        rows: int = 3,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(rows, len(columns))
        self.columns = columns
        self._on_change = on_change
        self.setHorizontalHeaderLabels([label for _key, label, _dec in columns])
        self.verticalHeader().setDefaultSectionSize(26)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        for index, (_key, _label, decimals) in enumerate(columns):
            self.setColumnWidth(index, 104 if decimals is None else 86)
        self.cellChanged.connect(self._handle_change)

    def _handle_change(self, row: int, _column: int) -> None:
        if row == self.rowCount() - 1 and self.row_values(row):
            self.blockSignals(True)
            self.insertRow(self.rowCount())
            self.blockSignals(False)
        if self._on_change is not None:
            self._on_change()

    def row_values(self, row: int) -> dict[str, Any] | None:
        """Dolu satırı sözlüğe çevirir; tamamen boş satır için None döner."""
        values: dict[str, Any] = {}
        filled = False
        for index, (key, _label, decimals) in enumerate(self.columns):
            item = self.item(row, index)
            text = item.text().strip() if item else ""
            if text:
                filled = True
            values[key] = text if decimals is None else _to_number(text)
        return values if filled else None

    def values(self) -> list[dict[str, Any]]:
        rows = []
        for row in range(self.rowCount()):
            payload = self.row_values(row)
            if payload is not None:
                rows.append(payload)
        return rows

    def column_total(self, key: str) -> float:
        index = next(
            (i for i, (name, _l, _d) in enumerate(self.columns) if name == key), None
        )
        if index is None:
            return 0.0
        total = 0.0
        for row in range(self.rowCount()):
            item = self.item(row, index)
            if item:
                total += _to_number(item.text())
        return total

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.blockSignals(True)
        self.setRowCount(max(len(rows) + 1, 3))
        for row_index, payload in enumerate(rows):
            for index, (key, _label, decimals) in enumerate(self.columns):
                value = payload.get(key)
                text = (
                    str(value or "")
                    if decimals is None
                    else _format(float(value or 0), decimals)
                )
                item = QTableWidgetItem(text)
                if decimals is not None:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(row_index, index, item)
        self.blockSignals(False)
        if self._on_change is not None:
            self._on_change()

    def add_row(self) -> None:
        self.insertRow(self.rowCount())
        self.setCurrentCell(self.rowCount() - 1, 0)

    def remove_current_row(self) -> None:
        row = self.currentRow()
        if row >= 0 and self.rowCount() > 1:
            self.removeRow(row)
            if self._on_change is not None:
                self._on_change()


class PressProductionDialog(QDialog):
    """Pres üretim fişinin tüm bölümlerini içeren giriş ekranı."""

    def __init__(
        self,
        work_order: dict[str, Any],
        *,
        username: str,
        slip_no: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.work_order = work_order
        self.username = username
        # Bölümler sırayla kurulurken tablolar birbirini tetikler; hesap ancak
        # tüm parçalar hazır olunca çalışmalıdır.
        self._ready = False
        self.setWindowTitle("PRES ÜRETİM")
        self.setSizeGripEnabled(True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.resize(1420, 880)
        self.setMinimumSize(1080, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        heading = QLabel("PRES ÜRETİM FİŞİ")
        heading.setStyleSheet(title_style(px=16, weight=900))
        root.addWidget(heading)
        self.slip_label = QLabel(
            f"FİŞ NO {slip_no or '—'}   ·   İŞ EMRİ {work_order.get('work_order_no', '')}"
            f"   ·   {work_order.get('customer_name', '')}"
            f"   ·   {work_order.get('profile_code', '')}"
        )
        self.slip_label.setStyleSheet("color:#475467;font-weight:700;")
        root.addWidget(self.slip_label)

        body = QHBoxLayout()
        body.setSpacing(8)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(8)
        body.addLayout(left, 4)
        body.addWidget(self._build_side_panel(), 1)

        left.addWidget(self._build_header_section())
        left.addWidget(self._build_billet_section(), 1)
        left.addWidget(self._build_output_section(), 1)
        left.addWidget(self._build_totals_bar())

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("KAYDET")
        buttons.button(QDialogButtonBox.Cancel).setText("KAPAT")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setStyleSheet(stylesheet(
            """
            QDialog { background:#F3F6FA; color:#1D2939; }
            QLabel, QCheckBox { color:#1D2939; }
            QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
                color:#101828; background:white; border:1px solid #BFCDE0;
                border-radius:4px; padding:4px 6px; min-height:24px;
            }
            QLineEdit[readOnly="true"] { background:#EEF2F7; color:#344054; font-weight:800; }
            QTableWidget { color:#101828; background:white; gridline-color:#D6DEE8; }
            QHeaderView::section { color:white; background:#0B4A82; padding:5px;
                                   font-weight:800; font-size:10.5pt; }
            QPushButton { color:#123C68; background:white; border:1px solid #AFC3DC;
                          border-radius:4px; min-height:26px; padding:2px 10px; font-weight:800; }
            QDialogButtonBox QPushButton { min-width:120px; min-height:32px; }
            QFrame#section { background:white; border:1px solid #D6DEE8; border-radius:6px; }
            QLabel#sectionTitle { background:#E8EFF7; color:#0B4A82; font-weight:900;
                                  padding:5px 8px; border-radius:4px; letter-spacing:.5px; }
            QLabel#totalKey { color:#475467; font-weight:700; }
            QLabel#totalValue { color:#0B4A82; font-weight:900; font-size:14px; }
            """
        ))
        self._ready = True
        self.recalculate()

    # ---- bölümler ----------------------------------------------------

    @staticmethod
    def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        return frame, layout

    def _build_header_section(self) -> QFrame:
        work_order = self.work_order
        frame, layout = self._section("ÜRETİM BİLGİLERİ")

        self.operator = QLineEdit(self.username)
        self.qc_username = QLineEdit()
        self.qc_username.setPlaceholderText("Kalite kontrol kullanıcısı")
        self.production_type = QComboBox()
        self.production_type.addItems(
            ("PLANLI ÜRETİM", "PLANSIZ ÜRETİM", "TEST", "KISA BOY", "NUMUNE")
        )
        self.shift = QComboBox()
        self.shift.addItems(("1.VARDİYA", "2.VARDİYA", "3.VARDİYA"))
        self.station = QLineEdit(str(work_order.get("station") or ""))
        self.station.setReadOnly(True)
        self.die_code = QLineEdit(str(work_order.get("die_code") or ""))
        self.die_code.setReadOnly(True)
        self.spare_no = QSpinBox()
        self.spare_no.setRange(0, 999)
        self.spare_no.setValue(int(work_order.get("spare_no") or 0))
        self.figure_count = QSpinBox()
        self.figure_count.setRange(0, 999)
        self.figure_count.setValue(int(work_order.get("figure_count") or 0))
        self.tenefer_no = QLineEdit(str(work_order.get("tenefer_no") or ""))
        self.raw_material_stock = QLineEdit(
            str(work_order.get("raw_material_stock") or "AL. BİLLET")
        )

        now = QDateTime.currentDateTime()
        self.started_at = QDateTimeEdit(now.addSecs(-1800))
        self.ended_at = QDateTimeEdit(now)
        for editor in (self.started_at, self.ended_at):
            editor.setDisplayFormat("dd.MM.yyyy HH:mm")
            editor.setCalendarPopup(True)
            editor.dateTimeChanged.connect(self.recalculate)
        self.duration_min = QLineEdit()
        self.duration_min.setReadOnly(True)
        self.preparation_min = QSpinBox()
        self.preparation_min.setRange(0, 10_000)
        self.preparation_min.setValue(5)

        self.theoretical_weight = QLineEdit(
            _format(float(work_order.get("unit_weight_kg_m") or 0), 3)
        )
        self.theoretical_weight.setReadOnly(True)
        self.real_weight = QLineEdit()
        self.real_weight.setReadOnly(True)
        self.result_length = QSpinBox()
        self.result_length.setRange(0, 50_000)
        self.result_length.setValue(int(float(work_order.get("production_length_mm") or 0)))
        self.result_length.valueChanged.connect(self.recalculate)

        self.press_status = QComboBox()
        self.press_status.addItems(("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI"))
        self.press_status.setCurrentText("TAMAMLANDI")
        self.saw_status = QComboBox()
        self.saw_status.addItems(("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI"))
        self.saw_status.setCurrentText("TAMAMLANDI")
        self.test_result = QComboBox()
        self.test_result.addItems(("", "BAŞARILI", "BAŞARISIZ"))
        self.die_problem = QComboBox()
        self.die_problem.addItems(DIE_PROBLEMS)
        self.die_problem_note = QLineEdit()
        self.die_problem_note.setPlaceholderText("Kalıp problemi açıklaması")
        self.note = QLineEdit()
        self.note.setPlaceholderText("Operatör notu")
        self.lot = QLineEdit()
        self.lot.setPlaceholderText("Üretim lot / şarj no")
        self.complete = QCheckBox("İş emrini tamamla ve sonraki istasyonu aç")
        self.complete.setChecked(True)

        # Etiketler alanların solundadır; form düzeni hem aynı
        # görünümü verir hem de dar alanda etiketi alana bindirmez.
        columns = (
            (
                ("OPERATÖR", self.operator),
                ("KK KULLANICISI", self.qc_username),
                ("ÜRETİM TİPİ", self.production_type),
                ("VARDİYA", self.shift),
                ("İSTASYON", self.station),
                ("LOT / ŞARJ NO", self.lot),
            ),
            (
                ("BAŞ. TARİHİ", self.started_at),
                ("BİTİŞ TARİHİ", self.ended_at),
                ("ÇALIŞMA DK", self.duration_min),
                ("KALIP HAZIRLIK DK", self.preparation_min),
                ("ÇIKAN BOY mm", self.result_length),
                ("HAMMADDE STOK", self.raw_material_stock),
            ),
            (
                ("KALIP", self.die_code),
                ("YEDEK NO", self.spare_no),
                ("FİGÜR ADET", self.figure_count),
                ("TENEFER NO", self.tenefer_no),
                ("TEO. GRAMAJ kg/m", self.theoretical_weight),
                ("GERÇEK GRAMAJ kg/m", self.real_weight),
            ),
            (
                ("ÜRETİM DURUMU", self.press_status),
                ("TESTERE DURUMU", self.saw_status),
                ("TEST SONUCU", self.test_result),
                ("KALIP PROBLEMİ", self.die_problem),
                ("KALIP PROBLEM AÇIK.", self.die_problem_note),
                ("AÇIKLAMA", self.note),
            ),
        )
        row = QHBoxLayout()
        row.setSpacing(14)
        for block in columns:
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(5)
            for label, editor in block:
                caption = QLabel(label)
                caption.setStyleSheet("color:#475467;font-weight:700;font-size:10.5pt;")
                form.addRow(caption, editor)
            row.addLayout(form, 1)
        layout.addLayout(row)
        layout.addWidget(self.complete)
        # Alt tablolar esnerken başlık ezilmesin diye kendi yüksekliğinde kalır.
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return frame

    def _grid_toolbar(self, grid: EditableGrid) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)
        add = QPushButton("+ SATIR EKLE")
        add.clicked.connect(grid.add_row)
        remove = QPushButton("SATIR SİL")
        remove.clicked.connect(grid.remove_current_row)
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch(1)
        return bar

    def _build_billet_section(self) -> QFrame:
        frame, layout = self._section("BİLLET BOYLARI")
        self.billet_grid = EditableGrid(BILLET_COLUMNS, on_change=self.recalculate)
        default_stock = str(self.work_order.get("raw_material_stock") or "AL. BİLLET")
        self.billet_grid.set_rows(
            [{"raw_material_stock": default_stock, "press_speed_m_s": 4.4}]
        )
        self.billet_grid.setMinimumHeight(150)
        layout.addLayout(self._grid_toolbar(self.billet_grid))
        layout.addWidget(self.billet_grid, 1)
        self.billet_summary = QLabel()
        self.billet_summary.setStyleSheet("color:#0B4A82;font-weight:800;")
        layout.addWidget(self.billet_summary)
        return frame

    def _build_output_section(self) -> QFrame:
        frame, layout = self._section("NET ADETLER")
        columns = QHBoxLayout()
        columns.setSpacing(10)

        basket_side = QVBoxLayout()
        basket_title = QLabel("SEPET VERİLERİ")
        basket_title.setStyleSheet("color:#475467;font-weight:800;font-size:10.5pt;")
        basket_side.addWidget(basket_title)
        self.basket_grid = EditableGrid(BASKET_COLUMNS, on_change=self.recalculate)
        self.basket_grid.set_rows(
            [{
                "basket_no": "",
                "length_mm": float(self.work_order.get("production_length_mm") or 0),
                "work_order_no": str(self.work_order.get("work_order_no") or ""),
            }]
        )
        self.basket_grid.setMinimumHeight(150)
        basket_side.addLayout(self._grid_toolbar(self.basket_grid))
        basket_side.addWidget(self.basket_grid, 1)
        self.basket_summary = QLabel()
        self.basket_summary.setStyleSheet("color:#0B4A82;font-weight:800;")
        basket_side.addWidget(self.basket_summary)

        scrap_side = QVBoxLayout()
        scrap_title = QLabel("HURDA VERİLERİ")
        scrap_title.setStyleSheet("color:#475467;font-weight:800;font-size:10.5pt;")
        scrap_side.addWidget(scrap_title)
        self.scrap_grid = EditableGrid(SCRAP_COLUMNS, on_change=self.recalculate)
        self.scrap_grid.set_rows([{"scrap_reason": "HURDA"}])
        self.scrap_grid.setMinimumHeight(150)
        scrap_side.addLayout(self._grid_toolbar(self.scrap_grid))
        scrap_side.addWidget(self.scrap_grid, 1)
        self.scrap_summary = QLabel()
        self.scrap_summary.setStyleSheet("color:#B54708;font-weight:800;")
        scrap_side.addWidget(self.scrap_summary)

        columns.addLayout(basket_side, 3)
        columns.addLayout(scrap_side, 2)
        layout.addLayout(columns, 1)
        return frame

    def _build_totals_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("section")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(18)
        self.total_labels: dict[str, QLabel] = {}
        for key, caption in (
            ("gross", "BRÜT KG"),
            ("net", "NET KG"),
            ("quantity", "NET ADET"),
            ("scrap", "FİRE KG"),
            ("fire_pct", "FİRE %"),
            ("remaining", "KALAN ADET"),
        ):
            block = QVBoxLayout()
            block.setSpacing(0)
            title = QLabel(caption)
            title.setObjectName("totalKey")
            value = QLabel("0")
            value.setObjectName("totalValue")
            block.addWidget(title)
            block.addWidget(value)
            layout.addLayout(block)
            self.total_labels[key] = value
        layout.addStretch(1)
        self.consistency = QLabel()
        self.consistency.setWordWrap(True)
        self.consistency.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.consistency, 2)
        return frame

    def _build_side_panel(self) -> QWidget:
        work_order = self.work_order
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        blocks = (
            (
                "PROFİL BİLGİLERİ",
                (
                    ("PROFİL KOD", work_order.get("profile_code")),
                    ("PROFİL AD", work_order.get("profile_name")),
                    ("ALAŞIM", work_order.get("alloy")),
                    ("TEO. GRAMAJ", work_order.get("unit_weight_kg_m")),
                ),
            ),
            (
                "KALIP BİLGİLERİ",
                (
                    ("KALIP KOD", work_order.get("die_code")),
                    ("YEDEK NO", work_order.get("spare_no")),
                    ("FİGÜR ADET", work_order.get("figure_count")),
                    ("TENEFER NO", work_order.get("tenefer_no")),
                    ("TENEFER KALAN m", work_order.get("tenefer_remaining_m")),
                ),
            ),
            (
                "İŞ EMRİ BİLGİLERİ",
                (
                    ("İŞ EMRİ NO", work_order.get("work_order_no")),
                    ("ÜRETİM EMRİ", work_order.get("production_order_no")),
                    ("OPERASYON", work_order.get("operation")),
                    ("PLAN ADET", work_order.get("planned_quantity")),
                    ("PLAN KG", work_order.get("planned_kg")),
                    ("ÜRET. BOY", work_order.get("production_length_mm")),
                ),
            ),
            (
                "SİPARİŞ BİLGİLERİ",
                (
                    ("SİPARİŞ REF", work_order.get("order_line_ref") or work_order.get("order_no")),
                    ("MÜŞTERİ", work_order.get("customer_name")),
                    ("YÜZEY", work_order.get("surface")),
                    ("SİP. ADET", work_order.get("ordered_quantity")),
                    ("SİP. KG", work_order.get("ordered_kg")),
                ),
            ),
        )
        for title, rows in blocks:
            frame, block_layout = self._section(title)
            grid = QGridLayout()
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(3)
            for index, (label, value) in enumerate(rows):
                caption = QLabel(label)
                caption.setStyleSheet("color:#667085;font-weight:700;font-size:9.5pt;")
                if isinstance(value, float):
                    shown = _format(value, 3)
                else:
                    shown = str(value) if value not in (None, "") else "—"
                content = QLabel(shown)
                content.setStyleSheet("color:#101828;font-weight:800;font-size:11pt;")
                content.setWordWrap(True)
                grid.addWidget(caption, index, 0)
                grid.addWidget(content, index, 1)
            grid.setColumnStretch(1, 1)
            block_layout.addLayout(grid)
            layout.addWidget(frame)
        layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        container.setMinimumWidth(230)
        container.setMaximumWidth(320)
        return container

    # ---- hesap -------------------------------------------------------

    def recalculate(self) -> None:
        if not self._ready:
            return
        gross = self.billet_grid.column_total("gross_kg")
        billet_count = self.billet_grid.column_total("billet_count")
        net = self.basket_grid.column_total("net_kg")
        quantity = self.basket_grid.column_total("quantity")
        scrap_kg = self.scrap_grid.column_total("kg")
        scrap_qty = self.scrap_grid.column_total("quantity")
        fire = max(0.0, gross - net)
        fire_pct = (fire / gross * 100) if gross > 0 else 0.0
        planned = float(self.work_order.get("planned_quantity") or 0)

        self.total_labels["gross"].setText(_format(gross, 2))
        self.total_labels["net"].setText(_format(net, 2))
        self.total_labels["quantity"].setText(_format(quantity, 0))
        self.total_labels["scrap"].setText(_format(fire, 2))
        self.total_labels["fire_pct"].setText(_format(fire_pct, 1))
        self.total_labels["remaining"].setText(_format(max(0.0, planned - quantity), 0))

        self.billet_summary.setText(
            f"Billet adet: {_format(billet_count, 0)}   ·   "
            f"Brüt: {_format(gross, 2)} kg"
        )
        self.basket_summary.setText(
            f"Sepet: {len(self.basket_grid.values())}   ·   "
            f"Adet: {_format(quantity, 0)}   ·   Net: {_format(net, 2)} kg"
        )
        self.scrap_summary.setText(
            f"Hurda adet: {_format(scrap_qty, 0)}   ·   "
            f"Hurda: {_format(scrap_kg, 2)} kg"
        )

        length_m = self.result_length.value() / 1000
        if quantity > 0 and length_m > 0:
            self.real_weight.setText(_format(net / (quantity * length_m), 4))
        else:
            self.real_weight.setText("0,0000")

        seconds = self.started_at.dateTime().secsTo(self.ended_at.dateTime())
        self.duration_min.setText(_format(max(0.0, seconds / 60), 0))

        problems = []
        if gross <= 0:
            problems.append("Billet brüt kilogramı girilmedi.")
        if net <= 0:
            problems.append("Sepet net kilogramı girilmedi.")
        if net > gross > 0:
            problems.append("Net kilogram brütü aşamaz.")
        if self.scrap_grid.values() and abs(scrap_kg - fire) > max(0.05, fire * 0.001):
            problems.append(
                f"Hurda kırılımı {_format(scrap_kg, 2)} kg, fire {_format(fire, 2)} kg — eşit olmalı."
            )
        if problems:
            self.consistency.setText("  ".join(problems))
            self.consistency.setStyleSheet(
                "color:#B42318;background:#FEF3F2;border:1px solid #FDA29B;"
                "border-radius:4px;padding:4px 8px;font-weight:800;"
            )
        else:
            self.consistency.setText(
                "Fiş tutarlı: brüt billetten, net sepetten geliyor, fire hurda kırılımıyla örtüşüyor."
            )
            self.consistency.setStyleSheet(
                "color:#067647;background:#ECFDF3;border:1px solid #A6F4C5;"
                "border-radius:4px;padding:4px 8px;font-weight:800;"
            )

    # ---- çıktı -------------------------------------------------------

    def values(self) -> dict[str, Any]:
        gross = self.billet_grid.column_total("gross_kg")
        net = self.basket_grid.column_total("net_kg")
        quantity = self.basket_grid.column_total("quantity")
        planned = float(self.work_order.get("planned_quantity") or 0)
        length_m = self.result_length.value() / 1000
        real_weight = net / (quantity * length_m) if quantity > 0 and length_m > 0 else 0.0
        billet_rows = self.billet_grid.values()
        return {
            "quantity": quantity,
            "gross_kg": gross,
            "net_kg": net,
            "metre": quantity * length_m,
            "lot_no": self.lot.text().strip().upper(),
            "shift": self.shift.currentText(),
            "complete": self.complete.isChecked(),
            "production_type": self.production_type.currentText(),
            "press_status": self.press_status.currentText(),
            "saw_status": self.saw_status.currentText(),
            "real_weight_kg_m": real_weight,
            "theoretical_weight_kg_m": _to_number(self.theoretical_weight.text()),
            "billet_count": int(self.billet_grid.column_total("billet_count")),
            "billet_length_mm": (
                billet_rows[0].get("billet_length_mm", 0) if billet_rows else 0
            ),
            "basket_count": len(self.basket_grid.values()),
            "result_length_mm": float(self.result_length.value()),
            "preparation_min": float(self.preparation_min.value()),
            "duration_min": _to_number(self.duration_min.text()),
            "note": self.note.text().strip(),
            "qc_username": self.qc_username.text().strip(),
            "test_result": self.test_result.currentText(),
            "die_problem": self.die_problem.currentText(),
            "die_problem_note": self.die_problem_note.text().strip(),
            "spare_no": self.spare_no.value(),
            "figure_count": self.figure_count.value(),
            "tenefer_no": self.tenefer_no.text().strip(),
            "raw_material_stock": self.raw_material_stock.text().strip(),
            "remaining_quantity": max(0.0, planned - quantity),
            "started_at": self.started_at.dateTime().toPython().isoformat(timespec="seconds"),
            "ended_at": self.ended_at.dateTime().toPython().isoformat(timespec="seconds"),
            "billets": billet_rows,
            "baskets": self.basket_grid.values(),
            "scraps": self.scrap_grid.values(),
        }

    def accept(self) -> None:
        gross = self.billet_grid.column_total("gross_kg")
        net = self.basket_grid.column_total("net_kg")
        quantity = self.basket_grid.column_total("quantity")
        if not self.billet_grid.values():
            QMessageBox.warning(
                self, "Billet dökümü eksik",
                "En az bir billet satırı girilmeden pres fişi kaydedilemez.",
            )
            return
        if gross <= 0:
            QMessageBox.warning(
                self, "Brüt kilogram eksik",
                "Billet satırlarında brüt kilogram sıfırdan büyük olmalıdır.",
            )
            return
        if net <= 0 or quantity <= 0:
            QMessageBox.warning(
                self, "Sepet dökümü eksik",
                "Sepet satırlarında net kilogram ve adet girilmelidir.",
            )
            return
        if net > gross:
            QMessageBox.warning(
                self, "Giren–çıkan hesabı geçersiz",
                "Net kilogram brüt kilogramı aşamaz.",
            )
            return
        fire = gross - net
        scrap_rows = self.scrap_grid.values()
        if scrap_rows:
            scrap_kg = self.scrap_grid.column_total("kg")
            if abs(scrap_kg - fire) > max(0.05, fire * 0.001):
                QMessageBox.warning(
                    self, "Hurda kırılımı uyuşmuyor",
                    f"Hurda toplamı {_format(scrap_kg, 2)} kg, fire {_format(fire, 2)} kg. "
                    "İkisi eşit olmalıdır.",
                )
                return
        if self.ended_at.dateTime() < self.started_at.dateTime():
            QMessageBox.warning(
                self, "Tarih hatalı", "Bitiş tarihi başlangıçtan önce olamaz."
            )
            return
        super().accept()
