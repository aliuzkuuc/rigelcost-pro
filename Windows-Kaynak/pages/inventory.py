from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.inventory import InventoryService
from ui.corporate_theme import font_family_css, stylesheet


def format_number(value: float, decimals: int = 2) -> str:
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


class StockItemDialog(QDialog):
    def __init__(self, service: InventoryService, parent: QWidget) -> None:
        super().__init__(parent)
        self.service = service
        self.created_item_id: int | None = None
        self.setWindowTitle("Yeni Stok Kartı")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        title = QLabel("YENİ STOK KARTI")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        form = QFormLayout()
        self.code = QLineEdit()
        self.code.setPlaceholderText("Örn. BLT-6063-7")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Örn. 6063 billet 7 inç")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(service.CATEGORIES)
        self.unit = QComboBox()
        self.unit.addItems(service.UNITS)
        self.minimum = self.make_quantity_spinbox()
        self.opening = self.make_quantity_spinbox()
        self.opening_cost = self.make_quantity_spinbox(
            maximum=1_000_000_000,
            suffix=" TL/birim",
        )

        form.addRow("Stok kodu", self.code)
        form.addRow("Stok adı", self.name)
        form.addRow("Kategori", self.category)
        form.addRow("Birim", self.unit)
        form.addRow("Minimum stok", self.minimum)
        form.addRow("Açılış miktarı", self.opening)
        form.addRow("Açılış birim maliyeti", self.opening_cost)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        cancel = QPushButton("VAZGEÇ")
        cancel.setObjectName("dialogSecondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("STOK KARTINI OLUŞTUR")
        save.setObjectName("dialogPrimary")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel, 1)
        buttons.addWidget(save, 2)
        layout.addLayout(buttons)
        self.setStyleSheet(stylesheet(DIALOG_STYLE))

    @staticmethod
    def make_quantity_spinbox(
        *,
        maximum: float = 1_000_000_000,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0, maximum)
        spinbox.setDecimals(3)
        spinbox.setGroupSeparatorShown(True)
        spinbox.setSuffix(suffix)
        return spinbox

    def save(self) -> None:
        try:
            self.created_item_id = self.service.add_item(
                self.code.text(),
                self.name.text(),
                self.category.currentText(),
                self.unit.currentText(),
                min_quantity=self.minimum.value(),
                opening_quantity=self.opening.value(),
                opening_unit_cost=self.opening_cost.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Stok kartı oluşturulamadı", str(exc))
            return
        self.accept()


class StockMovementDialog(QDialog):
    def __init__(
        self,
        service: InventoryService,
        parent: QWidget,
        *,
        selected_item_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.items = service.list_items()
        self.setWindowTitle("Stok Hareketi")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        title = QLabel("STOK GİRİŞ / ÇIKIŞ / SAYIM")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        form = QFormLayout()
        self.item = QComboBox()
        selected_index = 0
        for index, item in enumerate(self.items):
            self.item.addItem(
                f"{item['code']} — {item['name']}  "
                f"({format_number(item['current_quantity'], 3)} {item['unit']})",
                int(item["id"]),
            )
            if int(item["id"]) == selected_item_id:
                selected_index = index
        self.item.setCurrentIndex(selected_index)

        self.movement_type = QComboBox()
        self.movement_type.addItems(service.MOVEMENT_TYPES)
        self.quantity = StockItemDialog.make_quantity_spinbox()
        self.unit_cost = StockItemDialog.make_quantity_spinbox(
            maximum=1_000_000_000,
            suffix=" TL/birim",
        )
        self.movement_date = QDateEdit(QDate.currentDate())
        self.movement_date.setCalendarPopup(True)
        self.movement_date.setDisplayFormat("dd.MM.yyyy")
        self.document_no = QLineEdit()
        self.document_no.setPlaceholderText("İrsaliye, fiş veya sipariş no")
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(75)

        form.addRow("Stok kartı", self.item)
        form.addRow("Hareket tipi", self.movement_type)
        form.addRow("Miktar / yeni sayım", self.quantity)
        form.addRow("Birim maliyet", self.unit_cost)
        form.addRow("Hareket tarihi", self.movement_date)
        form.addRow("Belge no", self.document_no)
        form.addRow("Açıklama", self.note)
        layout.addLayout(form)

        self.hint = QLabel(
            "Girişte miktar stoğa eklenir; çıkışta düşülür. Sayım seçildiğinde "
            "girilen değer yeni mevcut stok olur."
        )
        self.hint.setObjectName("dialogHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        buttons = QHBoxLayout()
        cancel = QPushButton("VAZGEÇ")
        cancel.setObjectName("dialogSecondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("HAREKETİ KAYDET")
        save.setObjectName("dialogPrimary")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel, 1)
        buttons.addWidget(save, 2)
        layout.addLayout(buttons)

        self.movement_type.currentTextChanged.connect(self.update_cost_state)
        self.update_cost_state(self.movement_type.currentText())
        self.setStyleSheet(stylesheet(DIALOG_STYLE))

    def update_cost_state(self, movement_type: str) -> None:
        enabled = movement_type == "GİRİŞ"
        self.unit_cost.setEnabled(enabled)
        if not enabled:
            self.unit_cost.setValue(0)

    def save(self) -> None:
        if self.item.currentIndex() < 0:
            QMessageBox.warning(
                self,
                "Stok kartı yok",
                "Önce en az bir stok kartı oluşturmalısınız.",
            )
            return
        try:
            self.service.record_movement(
                int(self.item.currentData()),
                self.movement_type.currentText(),
                self.quantity.value(),
                unit_cost=self.unit_cost.value(),
                document_no=self.document_no.text(),
                note=self.note.toPlainText(),
                movement_date=self.movement_date.date().toString("yyyy-MM-dd"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Hareket kaydedilemedi", str(exc))
            return
        self.accept()


class InventoryPage(QWidget):
    """Ekstrüzyon işletmesi için stok kartı ve hareket takip ekranı."""

    def __init__(self, service: InventoryService | None = None) -> None:
        super().__init__()
        self.service = service or InventoryService()
        self.build_ui()
        self.apply_style()
        self.refresh_data()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("stockHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title_layout = QVBoxLayout()
        title = QLabel("STOK TAKİBİ")
        title.setObjectName("stockTitle")
        subtitle = QLabel(
            "Billet, profil, hurda-fire, ambalaj, sarf ve yedek parça yönetimi"
        )
        subtitle.setObjectName("stockSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout, 1)

        self.new_item_button = QPushButton("YENİ STOK KARTI")
        self.new_item_button.setObjectName("stockSecondaryButton")
        self.new_item_button.clicked.connect(self.open_new_item)
        self.movement_button = QPushButton("STOK HAREKETİ")
        self.movement_button.setObjectName("stockPrimaryButton")
        self.movement_button.clicked.connect(self.open_movement)
        header_layout.addWidget(self.new_item_button)
        header_layout.addWidget(self.movement_button)
        layout.addWidget(header)

        summary_layout = QGridLayout()
        self.item_count_value = self.add_summary_card(
            summary_layout, 0, "STOK KARTI", "0"
        )
        self.low_count_value = self.add_summary_card(
            summary_layout, 1, "KRİTİK STOK", "0"
        )
        self.kg_stock_value = self.add_summary_card(
            summary_layout, 2, "KG BAZLI STOK", "0,00 kg"
        )
        self.stock_value_value = self.add_summary_card(
            summary_layout, 3, "TAHMİNİ STOK DEĞERİ", "0,00 TL"
        )
        for column in range(4):
            summary_layout.setColumnStretch(column, 1)
        layout.addLayout(summary_layout)

        filter_bar = QFrame()
        filter_bar.setObjectName("stockFilterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 9, 12, 9)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Stok kodu veya adına göre ara…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_items)
        self.category = QComboBox()
        self.category.addItem("Tümü")
        self.category.addItems(self.service.CATEGORIES)
        self.category.currentTextChanged.connect(self.refresh_items)
        all_movements = QPushButton("TÜM HAREKETLER")
        all_movements.setObjectName("stockSmallButton")
        all_movements.clicked.connect(self.show_all_movements)
        refresh = QPushButton("YENİLE")
        refresh.setObjectName("stockSmallButton")
        refresh.clicked.connect(self.refresh_data)
        filter_layout.addWidget(QLabel("Ara"))
        filter_layout.addWidget(self.search, 2)
        filter_layout.addWidget(QLabel("Kategori"))
        filter_layout.addWidget(self.category, 1)
        filter_layout.addWidget(all_movements)
        filter_layout.addWidget(refresh)
        layout.addWidget(filter_bar)

        splitter = QSplitter(Qt.Vertical)
        self.items_table = QTableWidget()
        self.items_table.setObjectName("stockTable")
        self.items_table.setColumnCount(9)
        self.items_table.setHorizontalHeaderLabels(
            [
                "Stok Kodu",
                "Stok Adı",
                "Kategori",
                "Birim",
                "Mevcut",
                "Minimum",
                "Ort. Maliyet",
                "Stok Değeri",
                "Durum",
            ]
        )
        self.configure_table(self.items_table)
        self.items_table.itemSelectionChanged.connect(
            self.refresh_selected_movements
        )
        splitter.addWidget(self.items_table)

        movement_container = QFrame()
        movement_container.setObjectName("movementContainer")
        movement_layout = QVBoxLayout(movement_container)
        movement_layout.setContentsMargins(0, 8, 0, 0)
        self.movement_title = QLabel("SON STOK HAREKETLERİ")
        self.movement_title.setObjectName("stockSectionTitle")
        movement_layout.addWidget(self.movement_title)
        self.movements_table = QTableWidget()
        self.movements_table.setObjectName("movementTable")
        self.movements_table.setColumnCount(9)
        self.movements_table.setHorizontalHeaderLabels(
            [
                "Tarih",
                "Stok Kodu",
                "Stok Adı",
                "Hareket",
                "Miktar",
                "Bakiye",
                "Birim Maliyet",
                "Belge No",
                "Açıklama",
            ]
        )
        self.configure_table(self.movements_table)
        movement_layout.addWidget(self.movements_table)
        splitter.addWidget(movement_container)
        splitter.setSizes([400, 260])
        layout.addWidget(splitter, 1)

    def set_access(self, *, can_create: bool) -> None:
        self.can_create = bool(can_create)
        self.new_item_button.setVisible(self.can_create)
        self.movement_button.setVisible(self.can_create)

    @staticmethod
    def configure_table(table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

    @staticmethod
    def add_summary_card(
        layout: QGridLayout,
        column: int,
        title: str,
        initial: str,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("stockSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        title_label = QLabel(title)
        title_label.setObjectName("stockSummaryTitle")
        value_label = QLabel(initial)
        value_label.setObjectName("stockSummaryValue")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, 0, column)
        return value_label

    def refresh_data(self) -> None:
        self.refresh_summary()
        self.refresh_items()
        self.refresh_movements()

    def refresh_summary(self) -> None:
        summary = self.service.summary()
        self.item_count_value.setText(format_number(summary["item_count"], 0))
        self.low_count_value.setText(format_number(summary["low_count"], 0))
        self.kg_stock_value.setText(
            f"{format_number(summary['kg_stock'], 2)} kg"
        )
        self.stock_value_value.setText(
            f"{format_number(summary['stock_value'], 2)} TL"
        )

    def refresh_items(self) -> None:
        items = self.service.list_items(
            search=self.search.text(),
            category=self.category.currentText(),
        )
        self.items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            is_low = bool(item["is_low"]) and float(item["min_quantity"]) > 0
            is_empty = float(item["current_quantity"]) <= 0
            status = "TÜKENDİ" if is_empty else ("KRİTİK" if is_low else "NORMAL")
            values = [
                item["code"],
                item["name"],
                item["category"],
                item["unit"],
                format_number(item["current_quantity"], 3),
                format_number(item["min_quantity"], 3),
                format_number(item["average_cost"], 2),
                format_number(item["stock_value"], 2),
                status,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 0:
                    cell.setData(Qt.UserRole, int(item["id"]))
                if column >= 4 and column <= 7:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if is_low or is_empty:
                    cell.setBackground(QColor("#FEE2E2"))
                    cell.setForeground(QColor("#991B1B"))
                self.items_table.setItem(row, column, cell)
        self.movement_button.setEnabled(bool(items))

    def selected_item_id(self) -> int | None:
        row = self.items_table.currentRow()
        if row < 0:
            return None
        item = self.items_table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item is not None else None

    def refresh_selected_movements(self) -> None:
        item_id = self.selected_item_id()
        if item_id is None:
            return
        code_item = self.items_table.item(self.items_table.currentRow(), 0)
        code = code_item.text() if code_item is not None else ""
        self.movement_title.setText(f"STOK HAREKETLERİ — {code}")
        self.refresh_movements(item_id)

    def show_all_movements(self) -> None:
        self.items_table.clearSelection()
        self.items_table.setCurrentItem(None)
        self.movement_title.setText("SON STOK HAREKETLERİ")
        self.refresh_movements()

    def refresh_movements(self, item_id: int | None = None) -> None:
        movements = self.service.list_movements(item_id=item_id)
        self.movements_table.setRowCount(len(movements))
        for row, movement in enumerate(movements):
            delta = float(movement["quantity_delta"])
            values = [
                movement["movement_date"],
                movement["code"],
                movement["name"],
                movement["movement_type"],
                f"{'+' if delta > 0 else ''}{format_number(delta, 3)} "
                f"{movement['unit']}",
                f"{format_number(movement['balance_after'], 3)} "
                f"{movement['unit']}",
                format_number(movement["unit_cost"], 2),
                movement["document_no"],
                movement["note"],
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column in {4, 5, 6}:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column == 4:
                    cell.setForeground(
                        QColor("#047857" if delta >= 0 else "#B42318")
                    )
                self.movements_table.setItem(row, column, cell)

    def open_new_item(self) -> None:
        if not getattr(self, "can_create", True):
            return
        dialog = StockItemDialog(self.service, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def open_movement(self) -> None:
        if not getattr(self, "can_create", True):
            return
        if not self.service.list_items():
            QMessageBox.information(
                self,
                "Stok kartı yok",
                "Önce bir stok kartı oluşturmalısınız.",
            )
            return
        dialog = StockMovementDialog(
            self.service,
            self,
            selected_item_id=self.selected_item_id(),
        )
        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            InventoryPage { background: #EEF2F6; color: #1F2937; }
            #stockHeader, #stockFilterBar, #stockSummaryCard {
                background: #FFFFFF;
                border: 1px solid #D5DDE7;
                border-radius: 9px;
            }
            #stockTitle {
                color: #163A70;
                font-size: 22px;
                font-weight: 700;
            }
            #stockSubtitle { color: #667085; font-size: 11px; }
            #stockSummaryTitle {
                color: #667085;
                font-size: 10px;
                font-weight: 600;
            }
            #stockSummaryValue {
                color: #163A70;
                font-size: 19px;
                font-weight: 700;
            }
            #stockPrimaryButton, #stockSecondaryButton, #stockSmallButton {
                border-radius: 6px;
                padding: 9px 13px;
                font-weight: 700;
            }
            #stockPrimaryButton {
                background: #163A70;
                color: #FFFFFF;
                border: 1px solid #163A70;
            }
            #stockSecondaryButton, #stockSmallButton {
                background: #FFFFFF;
                color: #163A70;
                border: 1px solid #9EB1C8;
            }
            #stockTable, #movementTable {
                background: #FFFFFF;
                alternate-background-color: #F8FAFC;
                border: 1px solid #D5DDE7;
                gridline-color: #E4E7EC;
                selection-background-color: #DCEBFA;
                selection-color: #163A70;
            }
            QHeaderView::section {
                background: #E6EDF5;
                color: #163A70;
                border: 0;
                border-right: 1px solid #CBD5E1;
                padding: 7px;
                font-weight: 700;
            }
            #stockSectionTitle {
                color: #163A70;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit, QComboBox {
                min-height: 31px;
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0 8px;
            }
            """
        ))


DIALOG_STYLE = """
    QDialog { background: #F4F7FB; }
    #dialogTitle { color: #163A70; font-size: 19px; font-weight: 700; }
    #dialogHint { color: #667085; font-size: 10px; }
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {
        min-height: 32px;
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 0 8px;
    }
    #dialogPrimary, #dialogSecondary {
        min-height: 38px;
        border-radius: 6px;
        font-weight: 700;
    }
    #dialogPrimary {
        background: #163A70; color: #FFFFFF; border: 0;
    }
    #dialogSecondary {
        background: #FFFFFF; color: #344054; border: 1px solid #CBD5E1;
    }
"""
