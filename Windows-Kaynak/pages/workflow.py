from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from PySide6.QtCore import QDate, QPoint, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.local_workflow import LocalWorkflowService
from pages.department import AttachmentPicker
from ui.column_filter_bar import ColumnFilterBar
from ui.corporate_theme import stylesheet, title_style, voucher_no_style
from ui.record_details_dialog import RecordDetailsDialog, WorkflowDetailsDialog
from ui.workflow_side_panel import WorkflowSidePanel


def number_box(*, decimals: int = 2, maximum: float = 1_000_000_000) -> QDoubleSpinBox:
    editor = QDoubleSpinBox()
    editor.setDecimals(decimals)
    editor.setRange(0, maximum)
    editor.setGroupSeparatorShown(True)
    editor.setAlignment(Qt.AlignRight)
    return editor


class WorkflowDialog(QDialog):
    def finish(self, layout: QVBoxLayout) -> None:
        self.setSizeGripEnabled(True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setMinimumSize(480, 340)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("KAYDET")
        buttons.button(QDialogButtonBox.Cancel).setText("VAZGEÇ")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(stylesheet(
            """
            QDialog { background:#F3F6FA; color:#1D2939; }
            QLabel, QCheckBox { color:#1D2939; }
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                color:#101828; background:white; border:1px solid #BFCDE0;
                border-radius:4px; padding:6px; min-height:27px;
            }
            QTableWidget { color:#101828; background:white; gridline-color:#D6DEE8; }
            QHeaderView::section { color:white; background:#0B4A82; padding:7px; font-weight:800; }
            QPushButton { color:#123C68; background:white; border:1px solid #AFC3DC;
                border-radius:4px; min-height:32px; padding:3px 12px; font-weight:800; }
            QDialogButtonBox QPushButton { min-width:110px; }
            """
        ))


class StockItemDialog(WorkflowDialog):
    """Relational material card used by purchase, production and warehouses."""

    def __init__(
        self,
        parent: QWidget | None = None,
        record: dict[str, Any] | None = None,
        *,
        service: LocalWorkflowService | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.record = record or {}
        editing = bool(record)
        self.setWindowTitle("Stok Kartını Düzenle" if editing else "Yeni Stok Kartı")
        self.resize(720, 520)
        root = QVBoxLayout(self)
        title = QLabel("STOK KARTINI DÜZENLE" if editing else "YENİ STOK KARTI")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.addItems(("HAMMADDE", "YARI MAMUL", "MAMUL", "AMBALAJ", "SARF", "HİZMET"))
        self.unit = QComboBox()
        self.unit.setEditable(True)
        self.unit.addItems(("KG", "ADET", "METRE", "M2", "M3", "LİTRE", "PAKET"))
        self.minimum = number_box(decimals=3)
        self.unit_set = QComboBox()
        self.unit_set.addItem("Birim seti yok", None)
        if service is not None:
            for row in service.list_unit_sets():
                self.unit_set.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.tracks_lot = QCheckBox("Lot / şarj takibi zorunlu")
        self.active = QCheckBox("Kart aktif")
        self.active.setChecked(True)
        form.addRow("Stok kodu *", self.code)
        form.addRow("Stok adı *", self.name)
        form.addRow("Stok grubu *", self.group)
        form.addRow("Ana birim *", self.unit)
        form.addRow("Birim seti", self.unit_set)
        form.addRow("Minimum stok", self.minimum)
        form.addRow("İzlenebilirlik", self.tracks_lot)
        form.addRow("Durum", self.active)
        root.addLayout(form)
        note = QLabel(
            "Bu kart satın alma, reçete, üretim fişi ve ambar hareketlerinde aynı "
            "kimlikle kullanılır; ekranlar arasında yeniden yazılmaz."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        root.addStretch(1)
        if record:
            self.code.setText(str(record.get("code") or ""))
            self.name.setText(str(record.get("name") or ""))
            self.group.setCurrentText(str(record.get("stock_group") or "SARF"))
            self.unit.setCurrentText(str(record.get("unit") or "ADET"))
            self.minimum.setValue(float(record.get("minimum_quantity") or 0))
            if record.get("unit_set_id") is not None:
                index = self.unit_set.findData(int(record["unit_set_id"]))
                if index >= 0:
                    self.unit_set.setCurrentIndex(index)
            self.tracks_lot.setChecked(bool(record.get("tracks_lot")))
            self.active.setChecked(bool(record.get("active", 1)))
        self.finish(root)

    def values(self) -> dict[str, object]:
        return {
            "code": self.code.text(), "name": self.name.text(),
            "stock_group": self.group.currentText(), "unit": self.unit.currentText(),
            "minimum_quantity": self.minimum.value(),
            "unit_set_id": self.unit_set.currentData(),
            "tracks_lot": self.tracks_lot.isChecked(), "active": self.active.isChecked(),
        }

    def accept(self) -> None:
        if not self.code.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "Eksik bilgi", "Stok kodu ve stok adı zorunludur.")
            return
        super().accept()


class SupplierDialog(WorkflowDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        record: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record or {}
        editing = bool(record)
        self.setWindowTitle("Tedarikçi Kartını Düzenle" if editing else "Yeni Tedarikçi")
        self.resize(760, 590)
        root = QVBoxLayout(self)
        title = QLabel("TEDARİKÇİ KARTINI DÜZENLE" if editing else "YENİ TEDARİKÇİ / FASONCU KARTI")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.kind = QComboBox(); self.kind.addItems(("TEDARİKÇİ", "FASONCU", "HİZMET VEREN"))
        self.tax_office = QLineEdit(); self.tax_number = QLineEdit()
        self.contact = QLineEdit(); self.phone = QLineEdit(); self.email = QLineEdit()
        self.city = QLineEdit(); self.address = QPlainTextEdit(); self.address.setMaximumHeight(90)
        self.currency = QComboBox(); self.currency.addItems(("TRY", "USD", "EUR"))
        self.active = QCheckBox("Kart aktif"); self.active.setChecked(True)
        for label, editor in (
            ("Tedarikçi kodu *", self.code), ("Ticari unvan *", self.name),
            ("Kart tipi", self.kind), ("Vergi dairesi", self.tax_office),
            ("Vergi numarası", self.tax_number), ("İlgili kişi", self.contact),
            ("Telefon", self.phone), ("E-posta", self.email), ("Şehir", self.city),
            ("Adres", self.address), ("Varsayılan döviz", self.currency),
            ("Durum", self.active),
        ):
            form.addRow(label, editor)
        root.addLayout(form)
        if record:
            self.code.setText(str(record.get("code") or ""))
            self.name.setText(str(record.get("name") or ""))
            self.kind.setCurrentText(str(record.get("supplier_type") or "TEDARİKÇİ"))
            self.tax_office.setText(str(record.get("tax_office") or ""))
            self.tax_number.setText(str(record.get("tax_number") or ""))
            self.contact.setText(str(record.get("contact_name") or ""))
            self.phone.setText(str(record.get("phone") or ""))
            self.email.setText(str(record.get("email") or ""))
            self.city.setText(str(record.get("city") or ""))
            self.address.setPlainText(str(record.get("address") or ""))
            self.currency.setCurrentText(str(record.get("currency") or "TRY"))
            self.active.setChecked(bool(record.get("active", 1)))
        self.finish(root)

    def values(self) -> dict[str, object]:
        return {
            "code": self.code.text(), "name": self.name.text(),
            "supplier_type": self.kind.currentText(), "tax_office": self.tax_office.text(),
            "tax_number": self.tax_number.text(), "contact_name": self.contact.text(),
            "phone": self.phone.text(), "email": self.email.text(),
            "city": self.city.text(), "address": self.address.toPlainText(),
            "currency": self.currency.currentText(),
            "active": self.active.isChecked(),
        }


class PurchaseRequestDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.rows: list[dict[str, object]] = []
        self.setWindowTitle("Yeni Satın Alma Talebi")
        self.resize(1080, 720)
        root = QVBoxLayout(self)
        title = QLabel("SATIN ALMA TALEP FİŞİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        head = QHBoxLayout()
        self.request_date = QDateEdit(QDate.currentDate()); self.request_date.setCalendarPopup(True)
        self.description = QLineEdit()
        head.addWidget(QLabel("Talep tarihi")); head.addWidget(self.request_date)
        head.addWidget(QLabel("Açıklama")); head.addWidget(self.description, 1)
        root.addLayout(head)
        entry = QGridLayout()
        self.stock = QComboBox(); self.stock.addItem("Stok kartı seçin…", None)
        for row in service.list_stock_items():
            self.stock.addItem(f"{row['code']} — {row['name']} [{row['unit']}]", row["id"])
        self.warehouse = QComboBox()
        for row in service.list_warehouses():
            self.warehouse.addItem(f"{row['name']} [{row['code']}]", row["id"])
        self.required_date = QDateEdit(QDate.currentDate().addDays(7)); self.required_date.setCalendarPopup(True)
        self.quantity = number_box(decimals=3)
        self.reason = QLineEdit()
        add = QPushButton("＋ SATIR EKLE"); add.clicked.connect(self.add_line)
        fields = (("Stok kartı *", self.stock), ("Ambar *", self.warehouse),
                  ("İstenen tarih", self.required_date), ("Miktar *", self.quantity),
                  ("Talep sebebi", self.reason))
        for column, (label, editor) in enumerate(fields):
            entry.addWidget(QLabel(label), 0, column); entry.addWidget(editor, 1, column)
        entry.addWidget(add, 1, len(fields))
        root.addLayout(entry)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(("Stok", "Ambar", "Tarih", "Miktar", "Birim", "Sebep"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, 1)
        remove = QPushButton("SEÇİLİ SATIRI SİL"); remove.clicked.connect(self.remove_line)
        root.addWidget(remove, 0, Qt.AlignLeft)
        self.finish(root)

    def add_line(self) -> None:
        stock_id = self.stock.currentData()
        if stock_id is None or self.quantity.value() <= 0:
            QMessageBox.warning(self, "Eksik bilgi", "Stok kartı ve miktar zorunludur.")
            return
        stock = next(row for row in self.service.list_stock_items() if row["id"] == stock_id)
        values = {
            "stock_item_id": stock_id, "warehouse_id": self.warehouse.currentData(),
            "required_date": self.required_date.date().toString("yyyy-MM-dd"),
            "quantity": self.quantity.value(), "reason": self.reason.text(),
        }
        self.rows.append(values)
        row_index = self.table.rowCount(); self.table.insertRow(row_index)
        display = (stock["code"] + " — " + stock["name"], self.warehouse.currentText(),
                   self.required_date.date().toString("dd.MM.yyyy"), self.quantity.value(),
                   stock["unit"], self.reason.text())
        for column, value in enumerate(display):
            self.table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.quantity.setValue(0); self.reason.clear()

    def remove_line(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row); self.rows.pop(row)

    def accept(self) -> None:
        if not self.rows:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir talep satırı ekleyin.")
            return
        super().accept()


class PurchaseOrderDialog(WorkflowDialog):
    def __init__(
        self,
        service: LocalWorkflowService,
        parent: QWidget | None = None,
        *,
        request_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.request_id = request_id
        self.requests = [
            row for row in service.list_purchase_requests()
            if row["approval_status"] == "ONAYLANDI"
            and float(row["approved_quantity"] or 0) > float(row["ordered_quantity"] or 0) + 0.0005
        ]
        self.setWindowTitle("Talebi Satın Alma Siparişine Çevir")
        self.resize(1000, 680)
        root = QVBoxLayout(self)
        title = QLabel("SATIN ALMA SİPARİŞİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.request = QComboBox(); self.request.addItem("Onaylı talep seçin…", None)
        for row in self.requests:
            self.request.addItem(f"{row['request_no']} — {row['requested_by']} — {row['requested_quantity']:.3f}", row["id"])
        self.supplier = QComboBox(); self.supplier.addItem("Tedarikçi seçin…", None)
        for row in service.list_suppliers(): self.supplier.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.order_date = QDateEdit(QDate.currentDate()); self.order_date.setCalendarPopup(True)
        self.delivery_date = QDateEdit(QDate.currentDate().addDays(7)); self.delivery_date.setCalendarPopup(True)
        self.currency = QComboBox(); self.currency.addItems(("TRY", "USD", "EUR"))
        self.exchange_rate = number_box(decimals=4); self.exchange_rate.setValue(1)
        self.document_no = QLineEdit(); self.note = QLineEdit()
        for label, editor in (("Onaylı talep *", self.request), ("Tedarikçi *", self.supplier),
                              ("Sipariş tarihi", self.order_date), ("Teslim tarihi", self.delivery_date),
                              ("Döviz", self.currency), ("Kur", self.exchange_rate),
                              ("Tedarikçi belge no", self.document_no), ("Not", self.note)):
            form.addRow(label, editor)
        root.addLayout(form)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(("Talep Satırı", "Stok", "Ambar", "Miktar", "Birim", "Birim Fiyat", "Toplam"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        self.request.currentIndexChanged.connect(self.load_lines)
        self.table.itemChanged.connect(self.refresh_totals)
        self.finish(root)
        if request_id is not None:
            index = self.request.findData(int(request_id))
            if index >= 0:
                self.request.setCurrentIndex(index)

    def load_lines(self, *_args: object) -> None:
        self.table.blockSignals(True); self.table.setRowCount(0)
        request_id = self.request.currentData()
        if request_id is not None:
            for line in self.service.list_purchase_request_lines(int(request_id)):
                remaining = float(line["approved_quantity"]) - float(line["ordered_quantity"])
                if remaining <= 0.0005: continue
                row = self.table.rowCount(); self.table.insertRow(row)
                values = (line["id"], line["stock_code"] + " — " + line["stock_name"],
                          line["warehouse_name"], remaining, line["unit"], 0, 0)
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value));
                    if column != 5: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, column, item)
        self.table.blockSignals(False)

    def refresh_totals(self, item: QTableWidgetItem) -> None:
        if item.column() != 5: return
        try: price = float(item.text().strip().replace(",", "."))
        except ValueError: price = 0
        quantity = float(self.table.item(item.row(), 3).text())
        self.table.item(item.row(), 6).setText(f"{quantity * price:.2f}")

    def unit_prices(self) -> dict[int, float]:
        result: dict[int, float] = {}
        for row in range(self.table.rowCount()):
            line_id = int(self.table.item(row, 0).text())
            try: price = float(self.table.item(row, 5).text().strip().replace(",", "."))
            except ValueError: price = 0
            result[line_id] = price
        return result

    def accept(self) -> None:
        if self.request.currentData() is None or self.supplier.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Onaylı talep ve tedarikçi seçilmelidir.")
            return
        super().accept()


class GoodsReceiptDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Satın Alma Mal Kabul")
        self.resize(980, 650)
        root = QVBoxLayout(self)
        title = QLabel("SATIN ALMA İRSALİYESİ / MAL KABUL")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.order = QComboBox(); self.order.addItem("Açık satın alma siparişi seçin…", None)
        for row in service.list_purchase_orders():
            if row["status"] != "TAMAMLANDI":
                self.order.addItem(f"{row['purchase_order_no']} — {row['supplier_name']}", row["id"])
        self.receipt_date = QDateEdit(QDate.currentDate()); self.receipt_date.setCalendarPopup(True)
        self.dispatch_no = QLineEdit(); self.lot_no = QLineEdit(); self.note = QLineEdit()
        for label, editor in (("Satın alma siparişi *", self.order), ("Kabul tarihi", self.receipt_date),
                              ("İrsaliye no", self.dispatch_no), ("Lot / şarj no", self.lot_no),
                              ("Not", self.note)):
            form.addRow(label, editor)
        root.addLayout(form)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(("Satır", "Stok", "Ambar", "Sipariş", "Alınan", "Kalan", "Bu Kabul"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        self.order.currentIndexChanged.connect(self.load_lines)
        self.finish(root)

    def load_lines(self, *_args: object) -> None:
        self.table.setRowCount(0)
        order_id = self.order.currentData()
        if order_id is None: return
        for line in self.service.list_purchase_order_lines(int(order_id)):
            remaining = float(line["quantity"]) - float(line["received_quantity"])
            if remaining <= 0.0005: continue
            row = self.table.rowCount(); self.table.insertRow(row)
            values = (line["id"], line["stock_code"] + " — " + line["stock_name"],
                      line["warehouse_name"], line["quantity"], line["received_quantity"], remaining, remaining)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column != 6: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, column, item)

    def quantities(self) -> dict[int, float]:
        result: dict[int, float] = {}
        for row in range(self.table.rowCount()):
            try: value = float(self.table.item(row, 6).text().strip().replace(",", "."))
            except ValueError: value = 0
            result[int(self.table.item(row, 0).text())] = value
        return result

    def accept(self) -> None:
        if self.order.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Satın alma siparişi seçilmelidir.")
            return
        super().accept()


class UnitSetDialog(WorkflowDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[dict[str, object]] = []
        self.setWindowTitle("Yeni Birim Seti")
        self.resize(760, 620)
        root = QVBoxLayout(self)
        title = QLabel("BİRİM SETİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.base_unit = QComboBox()
        self.base_unit.addItems(("KG", "ADET", "METRE", "TON"))
        form.addRow("Set kodu *", self.code)
        form.addRow("Set adı *", self.name)
        form.addRow("Ana birim *", self.base_unit)
        root.addLayout(form)
        entry = QHBoxLayout()
        self.unit_code = QComboBox()
        self.unit_code.setEditable(True)
        self.unit_code.addItems(("KG", "ADET", "METRE", "TON", "PAKET"))
        self.factor = number_box(decimals=6)
        self.factor.setValue(1.0)
        self.description = QLineEdit()
        add = QPushButton("＋ BİRİM SATIRI EKLE")
        add.clicked.connect(self.add_line)
        entry.addWidget(QLabel("Birim"))
        entry.addWidget(self.unit_code)
        entry.addWidget(QLabel("Çarpan"))
        entry.addWidget(self.factor)
        entry.addWidget(QLabel("Açıklama"))
        entry.addWidget(self.description, 1)
        entry.addWidget(add)
        root.addLayout(entry)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(("Birim", "Çarpan", "Açıklama"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, 1)
        remove = QPushButton("SEÇİLİ SATIRI SİL")
        remove.clicked.connect(self.remove_line)
        root.addWidget(remove, 0, Qt.AlignLeft)
        info = QLabel(
            "Ana birime dönüşüm: miktar × çarpan. Örn. ana birim KG iken ADET=0.01 "
            "demek 1 adet = 0.01 kg anlamına gelir."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.finish(root)

    def add_line(self) -> None:
        unit_code = self.unit_code.currentText().strip().upper()
        factor = self.factor.value()
        if not unit_code or factor <= 0:
            QMessageBox.warning(self, "Eksik bilgi", "Birim kodu ve çarpan zorunludur.")
            return
        values = {
            "unit_code": unit_code,
            "factor": factor,
            "description": self.description.text().strip(),
        }
        self.rows.append(values)
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        for column, value in enumerate((unit_code, factor, values["description"])):
            self.table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.description.clear()

    def remove_line(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.rows.pop(row)

    def accept(self) -> None:
        if not self.code.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "Eksik bilgi", "Set kodu ve adı zorunludur.")
            return
        if not self.rows:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir birim satırı ekleyin.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "code": self.code.text(),
            "name": self.name.text(),
            "base_unit": self.base_unit.currentText(),
            "lines": self.rows,
        }


class BranchDialog(WorkflowDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Şube")
        self.resize(650, 470)
        root = QVBoxLayout(self)
        title = QLabel("ŞUBE KARTI")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.code = QLineEdit(); self.name = QLineEdit(); self.city = QLineEdit()
        self.address = QPlainTextEdit(); self.address.setMaximumHeight(100)
        self.active = QCheckBox("Şube aktif"); self.active.setChecked(True)
        for label, editor in (("Şube kodu *", self.code), ("Şube adı *", self.name),
                              ("Şehir", self.city), ("Adres", self.address),
                              ("Durum", self.active)):
            form.addRow(label, editor)
        root.addLayout(form)
        self.finish(root)

    def values(self) -> dict[str, Any]:
        return {"code": self.code.text(), "name": self.name.text(),
                "city": self.city.text(), "address": self.address.toPlainText(),
                "active": self.active.isChecked()}


class MaintenanceInstructionDialog(WorkflowDialog):
    """Periyodik bakım talimatı kartı."""

    DEFAULT_PERIOD_DAYS = 30

    def __init__(
        self,
        service: LocalWorkflowService,
        parent: QWidget | None = None,
        record: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record or {}
        editing = bool(self.record)
        self.setWindowTitle("Bakım Talimatı" if editing else "Yeni Bakım Talimatı")
        self.resize(700, 560)
        root = QVBoxLayout(self)
        title = QLabel("BAKIM TALİMAT KARTI")
        title.setStyleSheet(title_style())
        root.addWidget(title)

        if editing:
            no_label = QLabel(
                f"Talimat No: {self.record.get('instruction_no') or '—'}"
            )
            no_label.setStyleSheet("font-weight:800; color:#0B437C;")
            root.addWidget(no_label)

        form = QFormLayout()
        self.instruction_type = QComboBox()
        self.instruction_type.addItems(
            LocalWorkflowService.MAINTENANCE_INSTRUCTION_TYPES
        )
        self.instruction_type.setCurrentText(
            str(self.record.get("instruction_type") or "PERİYODİK")
        )
        self.name = QLineEdit(str(self.record.get("name") or ""))
        self.name.setPlaceholderText("Örn. Pres hidrolik yağ seviyesi kontrolü")

        self.operation = QComboBox()
        self.operation.setEditable(True)
        self.operation.addItem("")
        self.station = QComboBox()
        self.station.setEditable(True)
        self.station.addItem("")
        try:
            stations = service.list_stations()
        except Exception:
            stations = []
        for operation_name in sorted(
            {str(row.get("operation_name") or "").strip() for row in stations}
        ):
            if operation_name:
                self.operation.addItem(operation_name)
        for station_name in sorted(
            {str(row.get("name") or "").strip() for row in stations}
        ):
            if station_name:
                self.station.addItem(station_name)
        self.operation.setCurrentText(str(self.record.get("operation") or ""))
        self.station.setCurrentText(str(self.record.get("station") or ""))

        self.period_days = QSpinBox()
        self.period_days.setRange(0, 3650)
        self.period_days.setSuffix(" gün")
        self.period_days.setValue(int(self.record.get("period_days") or 0))

        self.description = QPlainTextEdit(str(self.record.get("description") or ""))
        self.description.setMaximumHeight(120)
        self.description.setPlaceholderText(
            "Yapılacak işlem adımları, kullanılacak malzeme ve iş güvenliği notları"
        )

        self.active = QCheckBox("Talimat aktif")
        self.active.setChecked(bool(self.record.get("active", True)))

        for label, editor in (
            ("Talimat tipi *", self.instruction_type),
            ("Talimat adı *", self.name),
            ("Operasyon", self.operation),
            ("İstasyon", self.station),
            ("Periyot", self.period_days),
            ("Açıklama", self.description),
            ("Durum", self.active),
        ):
            form.addRow(label, editor)
        root.addLayout(form)

        info = QLabel(
            "PERİYODİK talimatlarda periyot zorunludur; bakım emri periyot kadar "
            "ileri tarihe planlanır. ARİZİ talimatlarda periyot 0 bırakılabilir."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.instruction_type.currentTextChanged.connect(self._sync_period_requirement)
        self._sync_period_requirement(self.instruction_type.currentText())
        self.finish(root)

    def _sync_period_requirement(self, kind: str) -> None:
        periodic = kind.strip().upper() == "PERİYODİK"
        # Minimum'u yükseltmek değeri kendiliğinden ittireceği için önce okunur.
        current = self.period_days.value()
        self.period_days.setMinimum(1 if periodic else 0)
        if periodic and current <= 0:
            self.period_days.setValue(self.DEFAULT_PERIOD_DAYS)

    def accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Eksik bilgi", "Bakım talimatı adını girin.")
            self.name.setFocus()
            return
        if (
            self.instruction_type.currentText().strip().upper() == "PERİYODİK"
            and self.period_days.value() <= 0
        ):
            QMessageBox.warning(
                self, "Eksik bilgi",
                "Periyodik talimatlarda gün cinsinden periyot girilmelidir.",
            )
            self.period_days.setFocus()
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "instruction_type": self.instruction_type.currentText(),
            "name": self.name.text(),
            "operation": self.operation.currentText(),
            "station": self.station.currentText(),
            "period_days": self.period_days.value(),
            "description": self.description.toPlainText(),
            "active": self.active.isChecked(),
        }


class MaintenanceOrderDialog(WorkflowDialog):
    """Bakım emri kartı — talimattan veya sıfırdan açılabilir."""

    def __init__(
        self,
        service: LocalWorkflowService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Bakım Emri")
        self.resize(700, 540)
        root = QVBoxLayout(self)
        title = QLabel("BAKIM EMRİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)

        form = QFormLayout()
        self.instruction = QComboBox()
        self.instruction.addItem("Talimatsız (serbest bakım)", None)
        try:
            instructions = service.list_maintenance_instructions(
                include_inactive=False
            )
        except Exception:
            instructions = []
        for row in instructions:
            self.instruction.addItem(
                f"{row['instruction_no']} — {row['name']}", int(row["id"])
            )

        self.order_type = QComboBox()
        self.order_type.addItems(
            LocalWorkflowService.MAINTENANCE_INSTRUCTION_TYPES
        )
        self.name = QLineEdit()
        self.operation = QLineEdit()
        self.station = QLineEdit()
        self.station_section = QLineEdit()
        self.planned_start = QDateEdit(QDate.currentDate())
        self.planned_start.setCalendarPopup(True)
        self.planned_start.setDisplayFormat("dd.MM.yyyy")
        self.planned_end = QDateEdit(QDate.currentDate().addDays(1))
        self.planned_end.setCalendarPopup(True)
        self.planned_end.setDisplayFormat("dd.MM.yyyy")
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(110)

        for label, editor in (
            ("Bakım talimatı", self.instruction),
            ("Bakım tipi *", self.order_type),
            ("Bakım adı *", self.name),
            ("Operasyon", self.operation),
            ("İstasyon", self.station),
            ("İstasyon bölümü", self.station_section),
            ("Planlanan başlangıç", self.planned_start),
            ("Planlanan bitiş", self.planned_end),
            ("Açıklama", self.description),
        ):
            form.addRow(label, editor)
        root.addLayout(form)

        self._instructions = {int(row["id"]): row for row in instructions}
        self.instruction.currentIndexChanged.connect(self._apply_instruction)
        self.finish(root)

    def _apply_instruction(self) -> None:
        instruction_id = self.instruction.currentData()
        if instruction_id is None:
            return
        row = self._instructions.get(int(instruction_id))
        if not row:
            return
        self.order_type.setCurrentText(str(row.get("instruction_type") or "PERİYODİK"))
        self.name.setText(str(row.get("name") or ""))
        self.operation.setText(str(row.get("operation") or ""))
        self.station.setText(str(row.get("station") or ""))
        self.description.setPlainText(str(row.get("description") or ""))
        period = int(row.get("period_days") or 0)
        if period > 0:
            self.planned_end.setDate(self.planned_start.date().addDays(period))

    def accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Eksik bilgi", "Bakım adını girin.")
            self.name.setFocus()
            return
        if self.planned_end.date() < self.planned_start.date():
            QMessageBox.warning(
                self, "Tarih hatası",
                "Planlanan bitiş, başlangıç tarihinden önce olamaz.",
            )
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "instruction_id": self.instruction.currentData(),
            "order_type": self.order_type.currentText(),
            "name": self.name.text(),
            "operation": self.operation.text(),
            "station": self.station.text(),
            "station_section": self.station_section.text(),
            "planned_start": self.planned_start.date().toString("yyyy-MM-dd"),
            "planned_end": self.planned_end.date().toString("yyyy-MM-dd"),
            "description": self.description.toPlainText(),
        }


class WarehouseDialog(WorkflowDialog):
    def __init__(
        self, service: LocalWorkflowService, parent: QWidget | None = None,
        record: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record or {}
        self.setWindowTitle("Ambar Kartı")
        self.resize(700, 520)
        root = QVBoxLayout(self)
        title = QLabel("AMBAR KARTI VE STOK POLİTİKASI")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.code = QLineEdit(str(self.record.get("code") or ""))
        self.name = QLineEdit(str(self.record.get("name") or ""))
        self.warehouse_type = QComboBox()
        self.warehouse_type.addItems(("HAMMADDE", "YARI MAMUL", "MAMUL", "HURDA", "SARF", "FASON"))
        self.warehouse_type.setCurrentText(str(self.record.get("warehouse_type") or "YARI MAMUL"))
        self.branch = QComboBox(); self.branch.addItem("Şube seçin…", None)
        for row in service.list_branches():
            self.branch.addItem(f"{row['code']} — {row['name']}", row["id"])
            if int(row["id"]) == int(self.record.get("branch_id") or 0):
                self.branch.setCurrentIndex(self.branch.count() - 1)
        self.policy = QComboBox(); self.policy.addItems(("ENGELLE", "UYAR", "İZİN"))
        self.policy.setCurrentText(str(self.record.get("negative_stock_policy") or "İZİN"))
        self.mixed_lots = QCheckBox("Aynı stok için farklı lotlar bulunabilir")
        self.mixed_lots.setChecked(bool(self.record.get("allow_mixed_lots", True)))
        self.active = QCheckBox("Ambar aktif"); self.active.setChecked(bool(self.record.get("active", True)))
        for label, editor in (("Ambar kodu *", self.code), ("Ambar adı *", self.name),
                              ("Ambar tipi", self.warehouse_type), ("Şube *", self.branch),
                              ("Negatif stok", self.policy), ("Lot politikası", self.mixed_lots),
                              ("Durum", self.active)):
            form.addRow(label, editor)
        root.addLayout(form)
        info = QLabel(
            "ENGELLE: bakiye altına çıkış kaydedilmez.  UYAR: negatif kayıt listede görünür.  "
            "İZİN: kontrol kullanıcı sorumluluğundadır."
        )
        info.setWordWrap(True); root.addWidget(info)
        if self.record:
            self.code.setReadOnly(True); self.name.setReadOnly(True)
            self.warehouse_type.setEnabled(False)
        self.finish(root)

    def accept(self) -> None:
        if self.branch.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Ambarın bağlı olduğu şubeyi seçin.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "code": self.code.text(), "name": self.name.text(),
            "warehouse_type": self.warehouse_type.currentText(),
            "branch_id": int(self.branch.currentData()),
            "negative_stock_policy": self.policy.currentText(),
            "allow_mixed_lots": self.mixed_lots.isChecked(),
            "active": self.active.isChecked(),
        }


class StockDocumentDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.rows: list[dict[str, Any]] = []
        self.setWindowTitle("Stok Fişi")
        self.resize(1050, 720)
        root = QVBoxLayout(self)
        title = QLabel("STOK GİRİŞ / ÇIKIŞ / TRANSFER FİŞİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        header = QGridLayout()
        self.document_type = QComboBox(); self.document_type.addItems(("TRANSFER", "GİRİŞ", "ÇIKIŞ"))
        self.document_date = QDateEdit(QDate.currentDate()); self.document_date.setCalendarPopup(True)
        self.source = QComboBox(); self.source.addItem("Kaynak ambar seçin…", None)
        self.target = QComboBox(); self.target.addItem("Hedef ambar seçin…", None)
        for warehouse in service.list_warehouses():
            label = f"{warehouse['branch_name']} / {warehouse['name']} [{warehouse['code']}]"
            self.source.addItem(label, warehouse["id"]); self.target.addItem(label, warehouse["id"])
        self.reference = QLineEdit(); self.note = QLineEdit()
        for row, (label, editor) in enumerate((
            ("Fiş tipi", self.document_type), ("Fiş tarihi", self.document_date),
            ("Kaynak ambar", self.source), ("Hedef ambar", self.target),
            ("Referans no", self.reference), ("Not", self.note),
        )):
            header.addWidget(QLabel(label), row // 2, (row % 2) * 2)
            header.addWidget(editor, row // 2, (row % 2) * 2 + 1)
        root.addLayout(header)
        line = QHBoxLayout()
        self.stock = QComboBox(); self.stock.addItem("Stok kartı seçin…", None)
        for row in service.list_stock_items():
            self.stock.addItem(f"{row['code']} — {row['name']} ({row['unit']})", row["id"])
        self.quantity = number_box(decimals=3); self.quantity.setPrefix("Miktar: ")
        self.lot = QLineEdit(); self.lot.setPlaceholderText("Lot / şarj")
        self.line_note = QLineEdit(); self.line_note.setPlaceholderText("Satır notu")
        add = QPushButton("＋ SATIR EKLE"); add.clicked.connect(self.add_line)
        line.addWidget(self.stock, 2); line.addWidget(self.quantity)
        line.addWidget(self.lot); line.addWidget(self.line_note); line.addWidget(add)
        root.addLayout(line)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Stok", "Miktar", "Birim", "Lot / Şarj", "Not"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        remove = QPushButton("SEÇİLİ SATIRI SİL"); remove.clicked.connect(self.remove_line)
        root.addWidget(remove, 0, Qt.AlignLeft)
        self.document_type.currentTextChanged.connect(self.sync_type)
        self.sync_type()
        self.finish(root)

    def sync_type(self, *_args: object) -> None:
        kind = self.document_type.currentText()
        self.source.setEnabled(kind in {"ÇIKIŞ", "TRANSFER"})
        self.target.setEnabled(kind in {"GİRİŞ", "TRANSFER"})

    def add_line(self) -> None:
        stock_id = self.stock.currentData()
        if stock_id is None or self.quantity.value() <= 0:
            QMessageBox.warning(self, "Eksik satır", "Stok kartı ve sıfırdan büyük miktar girin.")
            return
        stock = next(row for row in self.service.list_stock_items() if row["id"] == stock_id)
        values = {"stock_item_id": int(stock_id), "quantity": self.quantity.value(),
                  "lot_no": self.lot.text(), "note": self.line_note.text()}
        self.rows.append(values)
        row_index = self.table.rowCount(); self.table.insertRow(row_index)
        display = (f"{stock['code']} — {stock['name']}", self.quantity.value(),
                   stock["unit"], self.lot.text(), self.line_note.text())
        for column, value in enumerate(display):
            self.table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.quantity.setValue(0); self.lot.clear(); self.line_note.clear()

    def remove_line(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row); self.rows.pop(row)

    def accept(self) -> None:
        kind = self.document_type.currentText()
        if kind in {"ÇIKIŞ", "TRANSFER"} and self.source.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Kaynak ambarı seçin."); return
        if kind in {"GİRİŞ", "TRANSFER"} and self.target.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Hedef ambarı seçin."); return
        if not self.rows:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir stok satırı ekleyin."); return
        super().accept()


class CustomerDialog(WorkflowDialog):
    def __init__(self, parent: QWidget | None = None, record: dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.record = record or {}
        editing = bool(record)
        self.setWindowTitle("Müşteri Kartını Düzenle" if editing else "Yeni Müşteri Kartı")
        self.resize(900, 760)
        root = QVBoxLayout(self)
        title = QLabel("MÜŞTERİ KARTINI DÜZENLE" if editing else "YENİ MÜŞTERİ KARTI")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        tabs = QTabWidget()
        self.tabs = tabs
        tab_container = QWidget()
        tab_container.setMinimumSize(760, 560)
        tab_container_layout = QVBoxLayout(tab_container)
        tab_container_layout.setContentsMargins(0, 0, 0, 0)
        tab_container_layout.addWidget(tabs)
        tab_scroll = QScrollArea()
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setFrameShape(QFrame.NoFrame)
        tab_scroll.setWidget(tab_container)
        root.addWidget(tab_scroll, 1)

        company_tab = QWidget()
        form = QFormLayout(company_tab)
        self.code = QLineEdit()
        self.code.setPlaceholderText("Örn. MUS-001")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Firma unvanı")
        self.short_name = QLineEdit()
        self.sector = QLineEdit()
        self.sales_representative = QLineEdit()
        self.currency = QComboBox()
        self.currency.addItems(("TRY", "USD", "EUR"))
        self.is_supplier = QCheckBox("Aynı zamanda tedarikçi")
        self.is_subcontractor = QCheckBox("Aynı zamanda fasoncu")
        form.addRow("Müşteri kodu *", self.code)
        form.addRow("Ticari unvan *", self.name)
        form.addRow("Kısa ad", self.short_name)
        form.addRow("Sektör", self.sector)
        form.addRow("İç satış temsilcisi", self.sales_representative)
        form.addRow("Varsayılan döviz", self.currency)
        form.addRow("Firma türü", self.is_supplier)
        form.addRow("", self.is_subcontractor)
        tabs.addTab(company_tab, "Firma")

        address_tab = QWidget()
        address_layout = QVBoxLayout(address_tab)
        address_form = QFormLayout()
        self.tax_office = QLineEdit()
        self.tax_number = QLineEdit()
        self.address = QPlainTextEdit()
        self.address.setMaximumHeight(100)
        self.city = QLineEdit()
        self.district = QLineEdit()
        self.postal_code = QLineEdit()
        self.country = QLineEdit()
        self.country.setText("TÜRKİYE")
        address_form.addRow("Vergi dairesi", self.tax_office)
        address_form.addRow("Vergi / T.C. no", self.tax_number)
        address_form.addRow("Ülke", self.country)
        address_form.addRow("Şehir", self.city)
        address_form.addRow("İlçe", self.district)
        address_form.addRow("Posta kodu", self.postal_code)
        address_form.addRow("Merkez adresi", self.address)
        address_layout.addLayout(address_form)
        address_help = QLabel(
            "Merkez dışında fabrika, depo ve sevk adreslerini ayrı kart olarak tanımlayın. "
            "Satış siparişinde teslim adresi bu listeden seçilir."
        )
        address_help.setWordWrap(True)
        address_layout.addWidget(address_help)
        self.addresses = QTableWidget(0, 8)
        self.addresses.setHorizontalHeaderLabels(
            ("Adres Adı", "Ülke", "Şehir", "İlçe", "Adres", "Posta Kodu", "Vergi Dairesi", "Vergi No")
        )
        self.addresses.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.addresses.horizontalHeader().setStretchLastSection(True)
        self.addresses.setMinimumHeight(180)
        address_layout.addWidget(self.addresses, 1)
        address_buttons = QHBoxLayout()
        add_address = QPushButton("＋ ADRES EKLE")
        remove_address = QPushButton("SEÇİLİ ADRESİ SİL")
        add_address.clicked.connect(self.add_address_row)
        remove_address.clicked.connect(self.remove_address_row)
        address_buttons.addWidget(add_address)
        address_buttons.addWidget(remove_address)
        address_buttons.addStretch(1)
        address_layout.addLayout(address_buttons)
        tabs.addTab(address_tab, "Vergi ve Adres")

        communication_tab = QWidget()
        communication_form = QFormLayout(communication_tab)
        self.phone = QLineEdit()
        self.phone2 = QLineEdit()
        self.fax = QLineEdit()
        self.email = QLineEdit()
        self.email2 = QLineEdit()
        for label, editor in (
            ("Telefon 1", self.phone), ("Telefon 2", self.phone2),
            ("Faks", self.fax), ("E-posta 1", self.email),
            ("E-posta 2", self.email2),
        ):
            communication_form.addRow(label, editor)
        tabs.addTab(communication_tab, "İletişim")

        contacts_tab = QWidget()
        contacts_layout = QVBoxLayout(contacts_tab)
        contacts_help = QLabel("Firmadaki satın alma, muhasebe, kalite ve sevkiyat ilgililerini ayrı satırlar halinde tanımlayın.")
        contacts_help.setWordWrap(True)
        contacts_layout.addWidget(contacts_help)
        self.contacts = QTableWidget(0, 5)
        self.contacts.setHorizontalHeaderLabels(("Ad Soyad", "Görev", "Telefon 1", "Telefon 2", "E-posta"))
        self.contacts.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        contacts_layout.addWidget(self.contacts, 1)
        contact_buttons = QHBoxLayout()
        add_contact = QPushButton("＋ İLGİLİ KİŞİ EKLE")
        remove_contact = QPushButton("SEÇİLİ KİŞİYİ SİL")
        add_contact.clicked.connect(self.add_contact_row)
        remove_contact.clicked.connect(self.remove_contact_row)
        contact_buttons.addWidget(add_contact)
        contact_buttons.addWidget(remove_contact)
        contact_buttons.addStretch(1)
        contacts_layout.addLayout(contact_buttons)
        tabs.addTab(contacts_tab, "İlgili Kişiler")

        commercial_tab = QWidget()
        commercial_form = QFormLayout(commercial_tab)
        self.accounting_code = QLineEdit()
        self.bank_name = QLineEdit()
        self.notes = QPlainTextEdit()
        self.order_note = QPlainTextEdit()
        self.production_note = QPlainTextEdit()
        self.general_warning = QPlainTextEdit()
        for editor in (self.notes, self.order_note, self.production_note, self.general_warning):
            editor.setMaximumHeight(70)
        commercial_form.addRow("Muhasebe kodu", self.accounting_code)
        commercial_form.addRow("Banka", self.bank_name)
        commercial_form.addRow("Genel not", self.notes)
        commercial_form.addRow("Sipariş notu", self.order_note)
        commercial_form.addRow("Üretim notu", self.production_note)
        commercial_form.addRow("Genel uyarı", self.general_warning)
        tabs.addTab(commercial_tab, "Ticari ve Notlar")

        if record:
            for key in (
                "code", "name", "short_name", "sector", "tax_office", "tax_number",
                "phone", "phone2", "fax", "email", "email2", "city", "district",
                "postal_code", "country", "sales_representative", "accounting_code",
                "bank_name",
            ):
                getattr(self, key).setText(str(record.get(key) or ""))
            self.address.setPlainText(str(record.get("address") or ""))
            for key in ("notes", "order_note", "production_note", "general_warning"):
                getattr(self, key).setPlainText(str(record.get(key) or ""))
            self.is_supplier.setChecked(bool(record.get("is_supplier")))
            self.is_subcontractor.setChecked(bool(record.get("is_subcontractor")))
            currency_index = self.currency.findText(str(record.get("currency") or "TRY"))
            self.currency.setCurrentIndex(max(0, currency_index))
            for contact in record.get("contacts", []):
                self.add_contact_row(contact)
            for address_record in record.get("addresses", []):
                is_main_duplicate = (
                    str(address_record.get("name") or "").strip().upper() == "MERKEZ"
                    and str(address_record.get("address") or "").strip()
                    == str(record.get("address") or "").strip()
                )
                if not is_main_duplicate:
                    self.add_address_row(address_record)
        self.finish(root)

    def add_contact_row(self, contact: dict[str, Any] | None = None) -> None:
        row = self.contacts.rowCount()
        self.contacts.insertRow(row)
        contact = contact or {}
        for column, key in enumerate(("name", "role", "phone1", "phone2", "email")):
            self.contacts.setItem(row, column, QTableWidgetItem(str(contact.get(key) or "")))

    def remove_contact_row(self) -> None:
        row = self.contacts.currentRow()
        if row >= 0:
            self.contacts.removeRow(row)

    def contact_values(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        keys = ("name", "role", "phone1", "phone2", "email")
        for row in range(self.contacts.rowCount()):
            values = {
                key: (self.contacts.item(row, column).text().strip() if self.contacts.item(row, column) else "")
                for column, key in enumerate(keys)
            }
            if values["name"]:
                rows.append(values)
        return rows

    def add_address_row(self, address: dict[str, Any] | None = None) -> None:
        row = self.addresses.rowCount()
        self.addresses.insertRow(row)
        address = address or {"name": "FABRİKA", "country": "TÜRKİYE"}
        for column, key in enumerate(
            ("name", "country", "city", "district", "address", "postal_code", "tax_office", "tax_number")
        ):
            self.addresses.setItem(
                row, column, QTableWidgetItem(str(address.get(key) or ""))
            )

    def remove_address_row(self) -> None:
        row = self.addresses.currentRow()
        if row >= 0:
            self.addresses.removeRow(row)

    def address_values(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if self.address.toPlainText().strip():
            rows.append(
                {
                    "name": "MERKEZ",
                    "country": self.country.text().strip(),
                    "city": self.city.text().strip(),
                    "district": self.district.text().strip(),
                    "address": self.address.toPlainText().strip(),
                    "postal_code": self.postal_code.text().strip(),
                    "tax_office": self.tax_office.text().strip(),
                    "tax_number": self.tax_number.text().strip(),
                }
            )
        keys = (
            "name", "country", "city", "district", "address", "postal_code",
            "tax_office", "tax_number",
        )
        for row in range(self.addresses.rowCount()):
            values = {
                key: (
                    self.addresses.item(row, column).text().strip()
                    if self.addresses.item(row, column)
                    else ""
                )
                for column, key in enumerate(keys)
            }
            if values["address"]:
                rows.append(values)
        return rows

    def values(self) -> dict[str, Any]:
        return {
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "tax_office": self.tax_office.text().strip(),
            "tax_number": self.tax_number.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "address": self.address.toPlainText().strip(),
            "city": self.city.text().strip(),
            "district": self.district.text().strip(),
            "postal_code": self.postal_code.text().strip(),
            "country": self.country.text().strip(),
            "sales_representative": self.sales_representative.text().strip(),
            "currency": self.currency.currentText(),
            "short_name": self.short_name.text().strip(),
            "sector": self.sector.text().strip(),
            "phone2": self.phone2.text().strip(),
            "fax": self.fax.text().strip(),
            "email2": self.email2.text().strip(),
            "accounting_code": self.accounting_code.text().strip(),
            "bank_name": self.bank_name.text().strip(),
            "notes": self.notes.toPlainText().strip(),
            "order_note": self.order_note.toPlainText().strip(),
            "production_note": self.production_note.toPlainText().strip(),
            "general_warning": self.general_warning.toPlainText().strip(),
            "is_supplier": self.is_supplier.isChecked(),
            "is_subcontractor": self.is_subcontractor.isChecked(),
            "contacts": self.contact_values(),
            "addresses": self.address_values(),
        }


class ProfileRouteDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Profil + Kalıp (eski toplu kayıt)")
        self.resize(820, 760)
        root = QVBoxLayout(self)
        title = QLabel("PROFİL + KALIP (ESKİ TOPLU KAYIT)")
        title.setStyleSheet(title_style())
        help_text = QLabel(
            "Profil kartını, kullanılacak kalıbı ve sipariş onaylandığında açılacak "
            "istasyon sırasını tanımlayın."
        )
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)

        form_container = QWidget()
        form_container.setMinimumSize(690, 930)
        form = QFormLayout(form_container)
        self.organization = QLineEdit(service.organization_name())
        self.organization.setReadOnly(True)
        self.organization.setToolTip(
            "Profil kartı müşteriye değil, programın kurulu olduğu fabrikaya aittir."
        )
        self.profile_code = QLineEdit()
        self.profile_name = QLineEdit()
        self.unit_weight = number_box(decimals=4)
        self.alloy = QComboBox()
        self.alloy.addItems(("6060B", "6063B", "6060", "6063", "6082"))
        self.temper = QComboBox()
        self.temper.addItems(("T5", "T6", "T4", "T66"))
        self.die_code = QLineEdit()
        self.spare_no = QSpinBox()
        self.spare_no.setRange(0, 99)
        self.figure_count = QSpinBox()
        self.figure_count.setRange(1, 32)
        self.figure_count.setValue(1)
        self.life_limit = number_box(decimals=0)
        self.tenefer_no = QComboBox()
        self.tenefer_no.setEditable(True)
        self.tenefer_no.addItems(("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"))
        self.tenefer_no.setCurrentText("1")
        self.tenefer_type = QLineEdit("STANDART")
        self.tenefer_limit = number_box(decimals=0)
        self.tenefer_limit.setValue(2000)
        self.press_station = QComboBox()
        self.press_station.addItems(("PRES 1", "PRES 2", "PRES 3"))
        self.has_thermal = QCheckBox("Termik işlemi rotaya dahil et")
        self.has_thermal.setChecked(True)
        self.surface = QComboBox()
        self.surface.addItems(("YOK", "ELOKSAL", "BOYA"))
        self.raw_material = QComboBox()
        self.raw_material.addItem("Hammadde stok kartı seçin…", "")
        for row in service.list_stock_items():
            if str(row.get("stock_group") or "").upper() == "HAMMADDE":
                self.raw_material.addItem(
                    f"{row['code']} — {row['name']}", row["code"]
                )
        if self.raw_material.count() > 1:
            self.raw_material.setCurrentIndex(1)
        self.create_recipe = QCheckBox("Profil kaydından sonra ana reçeteyi de oluştur")
        self.create_recipe.setChecked(False)
        self.route_steps = QTableWidget(0, 4)
        self.route_steps.setHorizontalHeaderLabels(
            ("Operasyon", "İstasyon", "Giriş Ambarı", "Çıkış Ambarı")
        )
        self.route_steps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        step_buttons = QHBoxLayout()
        add_step = QPushButton("＋ Adım Ekle")
        remove_step = QPushButton("－ Seçili Adımı Sil")
        rebuild_steps = QPushButton("Şablondan Doldur")
        add_step.clicked.connect(self.add_route_step_row)
        remove_step.clicked.connect(self.remove_route_step_row)
        rebuild_steps.clicked.connect(self.fill_route_template)
        step_buttons.addWidget(add_step)
        step_buttons.addWidget(remove_step)
        step_buttons.addWidget(rebuild_steps)
        step_buttons.addStretch(1)
        self.profile_pdf = AttachmentPicker(
            file_kind="file_pdf", department="Kalıphane", module="Profil Kartları"
        )
        self.profile_image = AttachmentPicker(
            file_kind="file_image", department="Kalıphane", module="Profil Kartları"
        )
        self.die_pdf = AttachmentPicker(
            file_kind="file_pdf", department="Kalıphane", module="Kalıp Kartları"
        )
        self.die_image = AttachmentPicker(
            file_kind="file_image", department="Kalıphane", module="Kalıp Kartları"
        )

        form.addRow("Profil sahibi işletme", self.organization)
        form.addRow("Profil kodu *", self.profile_code)
        form.addRow("Profil adı *", self.profile_name)
        form.addRow("Teorik ağırlık (kg/m) *", self.unit_weight)
        form.addRow("Alaşım", self.alloy)
        form.addRow("Sertlik", self.temper)
        form.addRow("Kalıp kodu *", self.die_code)
        form.addRow("Yedek no", self.spare_no)
        form.addRow("Figür adet *", self.figure_count)
        form.addRow("Kalıp ömür limiti (kg)", self.life_limit)
        form.addRow("Tenefer no *", self.tenefer_no)
        form.addRow("Tenefer cinsi", self.tenefer_type)
        form.addRow("Tenefer ömrü (m) *", self.tenefer_limit)
        form.addRow("Pres istasyonu", self.press_station)
        form.addRow("Termik", self.has_thermal)
        form.addRow("Yüzey işlemi", self.surface)
        form.addRow("Pres hammadde stok kartı *", self.raw_material)
        form.addRow("Üretim rotası adımları", self.route_steps)
        form.addRow("", self._wrap_layout(step_buttons))
        form.addRow("", self.create_recipe)
        form.addRow("Profil teknik PDF", self.profile_pdf)
        form.addRow("Profil JPG / PNG", self.profile_image)
        form.addRow("Kalıp PDF", self.die_pdf)
        form.addRow("Kalıp JPG / PNG", self.die_image)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.NoFrame)
        form_scroll.setWidget(form_container)
        root.addWidget(form_scroll, 1)
        self.finish(root)
        self.has_thermal.toggled.connect(self.fill_route_template)
        self.surface.currentIndexChanged.connect(self.fill_route_template)
        self.press_station.currentIndexChanged.connect(self.fill_route_template)
        self.tenefer_no.currentTextChanged.connect(self._apply_tenefer_standard_limit)
        self.fill_route_template()
        self._apply_tenefer_standard_limit()

    def _apply_tenefer_standard_limit(self, *_args: object) -> None:
        """Tenefer no değişince standart ömrü öner (1→2000, 2→3000…)."""
        text = self.tenefer_no.currentText().strip()
        if not text.isdigit():
            return
        standards = {
            1: 2000, 2: 3000, 3: 4500, 4: 6000, 5: 8000,
            6: 2000, 7: 3000, 8: 4500, 9: 6000, 10: 8000,
        }
        suggested = standards.get(int(text))
        if suggested:
            self.tenefer_limit.setValue(suggested)

    @staticmethod
    def _wrap_layout(layout: QHBoxLayout) -> QWidget:
        container = QWidget()
        container.setLayout(layout)
        return container

    def add_route_step_row(
        self,
        operation: str = "",
        station: str = "",
        input_wh: str = "HAMMADDE",
        output_wh: str = "PRES",
    ) -> None:
        row = self.route_steps.rowCount()
        self.route_steps.insertRow(row)
        for column, value in enumerate((operation, station, input_wh, output_wh)):
            self.route_steps.setItem(row, column, QTableWidgetItem(value))

    def remove_route_step_row(self) -> None:
        row = self.route_steps.currentRow()
        if row >= 0:
            self.route_steps.removeRow(row)

    def fill_route_template(self, *_args: object) -> None:
        self.route_steps.setRowCount(0)
        press = self.press_station.currentText()
        steps: list[tuple[str, str, str, str]] = [
            ("PRES ÜRETİM", press, "HAMMADDE", "PRES"),
        ]
        previous = "PRES"
        if self.has_thermal.isChecked():
            steps.extend(
                [
                    ("TERMİK GİRİŞ", "TERMİK 1", previous, "TERMIK_ON"),
                    ("TERMİK ÇIKIŞ", "TERMİK 1", "TERMIK_ON", "TERMIK"),
                ]
            )
            previous = "TERMIK"
        surface = self.surface.currentText()
        if surface != "YOK":
            steps.append((surface, f"{surface} 1", previous, "YUZEY"))
            previous = "YUZEY"
        if steps:
            steps[-1] = (
                steps[-1][0],
                steps[-1][1],
                steps[-1][2],
                "SEVK_ON",
            )
        for operation, station, input_wh, output_wh in steps:
            self.add_route_step_row(operation, station, input_wh, output_wh)

    def route_step_values(self) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        for row in range(self.route_steps.rowCount()):
            values = []
            for column in range(4):
                item = self.route_steps.item(row, column)
                values.append(item.text().strip().upper() if item else "")
            operation, station, input_wh, output_wh = values
            if not operation or not station:
                raise ValueError(
                    f"{row + 1}. rota adımında operasyon ve istasyon zorunludur."
                )
            steps.append(
                {
                    "operation": operation,
                    "station": station,
                    "input_warehouse": input_wh or "HAMMADDE",
                    "output_warehouse": output_wh or "SEVK_ON",
                }
            )
        if not steps:
            raise ValueError("Üretim rotasında en az bir operasyon adımı tanımlayın.")
        return steps

    def create_records(self, *, username: str) -> tuple[int, int]:
        if not self.profile_code.text().strip() or not self.profile_name.text().strip():
            raise ValueError("Profil kodu ve adı zorunludur.")
        if self.unit_weight.value() <= 0:
            raise ValueError("Teorik profil ağırlığı sıfırdan büyük olmalıdır.")
        if not self.die_code.text().strip():
            raise ValueError("Kalıp kodu zorunludur.")
        if not str(self.raw_material.currentData() or "").strip():
            raise ValueError("Pres üretiminde düşülecek hammadde stok kartını seçin.")
        profile_id = self.service.create_profile(
            self.profile_code.text(),
            self.profile_name.text(),
            unit_weight_kg_m=self.unit_weight.value(),
            customer_id=None,
            alloy=self.alloy.currentText(),
            temper=self.temper.currentText(),
            username=username,
        )
        die_id = self.service.create_die(
            profile_id,
            self.die_code.text(),
            spare_no=self.spare_no.value(),
            figure_count=self.figure_count.value(),
            life_limit_kg=self.life_limit.value(),
            tenefer_no=self.tenefer_no.currentText(),
            tenefer_type=self.tenefer_type.text(),
            tenefer_limit_m=self.tenefer_limit.value(),
            compatible_stations=[self.press_station.currentText()],
            username=username,
        )
        steps = self.route_step_values()
        route_id = self.service.create_route(
            profile_id,
            f"R-{self.profile_code.text().strip()}",
            f"{self.profile_name.text().strip()} üretim rotası",
            steps,
            username=username,
            surface=self.surface.currentText(),
            alloy=self.alloy.currentText(),
            temper=self.temper.currentText(),
        )
        if self.create_recipe.isChecked():
            raw_code = str(self.raw_material.currentData() or "").strip().upper()
            self.service.create_recipe(
                profile_id,
                route_id,
                f"RC-{self.profile_code.text().strip()}",
                f"{self.profile_name.text().strip()} ana reçetesi",
                [
                    {
                        "operation": str(step["operation"]),
                        "station": str(step["station"]),
                        "route_sequence_no": sequence,
                        "numerator": 1,
                        "denominator": 1,
                        "warehouse_code": str(step.get("output_warehouse") or ""),
                        "unit_code": "KG",
                        "stock_code": raw_code if sequence == 1 else "",
                    }
                    for sequence, step in enumerate(steps, start=1)
                ],
                username=username,
                raw_material_stock_code=raw_code,
            )
        for entity_type, entity_id, document_type, picker in (
            ("PROFILE", profile_id, "PROFİL PDF", self.profile_pdf),
            ("PROFILE", profile_id, "PROFİL GÖRSELİ", self.profile_image),
            ("DIE", die_id, "KALIP PDF", self.die_pdf),
            ("DIE", die_id, "KALIP GÖRSELİ", self.die_image),
        ):
            if picker.value():
                self.service.add_attachment(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    document_type=document_type,
                    file_path=picker.value(),
                    username=username,
                )
        return profile_id, die_id


class RouteEditDialog(WorkflowDialog):
    def __init__(
        self,
        service: LocalWorkflowService,
        route_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.route_id = int(route_id)
        route = next(
            (row for row in service.list_routes() if int(row["id"]) == self.route_id),
            None,
        )
        if route is None:
            raise ValueError("Üretim rotası bulunamadı.")
        self.route = route
        self.setWindowTitle("Üretim Rotası Düzenle")
        self.resize(760, 620)
        root = QVBoxLayout(self)
        title = QLabel(f"ROTA: {route['code']} — {route['profile_code']}")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.name = QLineEdit(str(route.get("name") or ""))
        self.recipe_name = QLineEdit(str(route.get("recipe_name") or ""))
        self.production_length = number_box(decimals=0, maximum=100_000)
        self.production_length.setValue(float(route.get("production_length_mm") or 0))
        self.surface = QComboBox()
        self.surface.addItems(("YOK", "ELOKSAL", "BOYA", "PRES"))
        current_surface = str(route.get("surface") or "YOK").upper()
        index = self.surface.findText(current_surface)
        if index >= 0:
            self.surface.setCurrentIndex(index)
        self.alloy = QLineEdit(str(route.get("alloy") or ""))
        self.temper = QLineEdit(str(route.get("temper") or ""))
        form.addRow("Rota adı *", self.name)
        form.addRow("Reçete adı", self.recipe_name)
        form.addRow("Üretim boyu (mm)", self.production_length)
        form.addRow("Yüzey", self.surface)
        form.addRow("Alaşım", self.alloy)
        form.addRow("Sertlik", self.temper)
        root.addLayout(form)
        self.route_steps = QTableWidget(0, 4)
        self.route_steps.setHorizontalHeaderLabels(
            ("Operasyon", "İstasyon", "Giriş Ambarı", "Çıkış Ambarı")
        )
        self.route_steps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for step in service.list_route_steps(self.route_id):
            row = self.route_steps.rowCount()
            self.route_steps.insertRow(row)
            for column, key in enumerate(
                ("operation", "default_station", "input_warehouse_code", "output_warehouse_code")
            ):
                self.route_steps.setItem(
                    row, column, QTableWidgetItem(str(step.get(key) or ""))
                )
        root.addWidget(self.route_steps, 1)
        step_buttons = QHBoxLayout()
        add_step = QPushButton("＋ Adım Ekle")
        remove_step = QPushButton("－ Seçili Adımı Sil")
        add_step.clicked.connect(self._add_step_row)
        remove_step.clicked.connect(self._remove_step_row)
        step_buttons.addWidget(add_step)
        step_buttons.addWidget(remove_step)
        step_buttons.addStretch(1)
        root.addLayout(step_buttons)
        self.finish(root)

    def _add_step_row(self) -> None:
        row = self.route_steps.rowCount()
        self.route_steps.insertRow(row)
        for column in range(4):
            self.route_steps.setItem(row, column, QTableWidgetItem(""))

    def _remove_step_row(self) -> None:
        row = self.route_steps.currentRow()
        if row >= 0:
            self.route_steps.removeRow(row)

    def route_step_values(self) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        for row in range(self.route_steps.rowCount()):
            values = []
            for column in range(4):
                item = self.route_steps.item(row, column)
                values.append(item.text().strip().upper() if item else "")
            operation, station, input_wh, output_wh = values
            if not operation or not station:
                raise ValueError(
                    f"{row + 1}. rota adımında operasyon ve istasyon zorunludur."
                )
            steps.append(
                {
                    "operation": operation,
                    "station": station,
                    "input_warehouse": input_wh or "HAMMADDE",
                    "output_warehouse": output_wh or "SEVK_ON",
                }
            )
        if not steps:
            raise ValueError("Üretim rotasında en az bir operasyon adımı tanımlayın.")
        return steps

    def save(self, *, username: str) -> None:
        self.service.update_route(
            self.route_id,
            name=self.name.text(),
            steps=self.route_step_values(),
            recipe_name=self.recipe_name.text(),
            production_length_mm=int(self.production_length.value()),
            surface=self.surface.currentText(),
            alloy=self.alloy.text(),
            temper=self.temper.text(),
            username=username,
        )


class SalesOrderDialog(WorkflowDialog):
    def __init__(
        self,
        service: LocalWorkflowService,
        parent: QWidget | None = None,
        *,
        order_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.order_id = order_id
        self.lines: list[dict[str, object]] = []
        self.profile_rows = {row["id"]: row for row in service.list_profiles()}
        editing = order_id is not None
        self.setWindowTitle("Satış Siparişi Düzenle" if editing else "Yeni Satış Siparişi")
        self.resize(1180, 780)
        root = QVBoxLayout(self)
        title = QLabel("SATIŞ SİPARİŞİ DÜZENLE" if editing else "YENİ SATIŞ SİPARİŞİ")
        title.setStyleSheet(title_style(px=20, weight=900))
        root.addWidget(title)

        voucher = QFrame()
        voucher.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        voucher_layout = QGridLayout(voucher)
        self.voucher_no = QLineEdit(
            "" if editing else service.peek_next_no("R")
        )
        self.voucher_no.setReadOnly(True)
        self.voucher_no.setStyleSheet(voucher_no_style())
        self.revision_no = QLineEdit("00")
        self.revision_no.setReadOnly(True)
        self.voucher_date = QLineEdit(QDate.currentDate().toString("dd.MM.yyyy HH:mm"))
        self.voucher_date.setReadOnly(True)
        voucher_layout.addWidget(QLabel("FİŞ NO *"), 0, 0)
        voucher_layout.addWidget(self.voucher_no, 0, 1)
        voucher_layout.addWidget(QLabel("REV. NO"), 0, 2)
        voucher_layout.addWidget(self.revision_no, 0, 3)
        voucher_layout.addWidget(QLabel("TARİH"), 0, 4)
        voucher_layout.addWidget(self.voucher_date, 0, 5)
        root.addWidget(voucher)

        tabs = QTabWidget()
        tab_general = QWidget()
        general_layout = QVBoxLayout(tab_general)

        customer_frame = QFrame()
        customer_frame.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        customer_grid = QGridLayout(customer_frame)
        self.customer = QComboBox()
        for row in service.list_customers():
            self.customer.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.contact_name = QLineEdit()
        self.contact_name.setPlaceholderText("Yetkili / muhatap")
        self.document_no = QLineEdit()
        self.document_no.setPlaceholderText("Müşteri sipariş no")
        self.payment_method = QComboBox()
        self.payment_method.addItems((
            "PEŞİN", "VADELİ", "ÇEK", "SENET", "HAVALE/EFT", "KREDİ KARTI",
        ))
        self.maturity_days = QSpinBox()
        self.maturity_days.setRange(0, 3650)
        self.maturity_days.setSuffix(" gün")
        self.order_date = QDateEdit(QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.delivery_date = QDateEdit(QDate.currentDate().addDays(14))
        self.delivery_date.setCalendarPopup(True)
        self.delivery_address = QComboBox()
        self.delivery_address.setMinimumWidth(320)
        self.msp = QLineEdit()
        self.msp.setPlaceholderText("MSP")
        self.representative = QLineEdit()
        self.representative.setPlaceholderText("Satış temsilcisi")
        customer_fields = (
            ("Müşteri *", self.customer),
            ("Yetkili", self.contact_name),
            ("Müşteri sip. no", self.document_no),
            ("Ödeme", self.payment_method),
            ("Vade", self.maturity_days),
            ("Sipariş tarihi", self.order_date),
            ("Teslim tarihi", self.delivery_date),
            ("MSP", self.msp),
            ("Temsilci", self.representative),
        )
        for index, (label, editor) in enumerate(customer_fields):
            row, column = divmod(index, 3)
            customer_grid.addWidget(QLabel(label), row, column * 2)
            customer_grid.addWidget(editor, row, column * 2 + 1)
        customer_grid.addWidget(QLabel("Sevk adresi"), 3, 0)
        customer_grid.addWidget(self.delivery_address, 3, 1, 1, 5)
        general_layout.addWidget(QLabel("MÜŞTERİ BİLGİLERİ"))
        general_layout.addWidget(customer_frame)

        fis_frame = QFrame()
        fis_frame.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        fis_grid = QGridLayout(fis_frame)
        self.branch = QComboBox()
        self.branch.addItem("Şube seçin…", None)
        for row in service.list_branches():
            self.branch.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.warehouse = QComboBox()
        self.warehouse.addItem("Ambar seçin…", None)
        for row in service.list_warehouses():
            if not row.get("active", 1):
                continue
            self.warehouse.addItem(
                f"{row['branch_code']} / {row['code']} — {row['name']}", row["id"]
            )
        self.currency = QComboBox()
        self.currency.addItems(("TRY", "USD", "EUR"))
        fis_grid.addWidget(QLabel("Şube"), 0, 0)
        fis_grid.addWidget(self.branch, 0, 1)
        fis_grid.addWidget(QLabel("Ambar"), 0, 2)
        fis_grid.addWidget(self.warehouse, 0, 3)
        fis_grid.addWidget(QLabel("Döviz"), 0, 4)
        fis_grid.addWidget(self.currency, 0, 5)
        general_layout.addWidget(QLabel("FİŞ BİLGİLERİ"))
        general_layout.addWidget(fis_frame)

        lme_frame = QFrame()
        lme_frame.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        lme_grid = QGridLayout(lme_frame)
        self.usd_rate = number_box(decimals=4)
        self.eur_rate = number_box(decimals=4)
        self.lme_usd_ton = number_box(decimals=2)
        self.premium_usd_ton = number_box(decimals=2)
        lme_fields = (
            ("USD kuru", self.usd_rate),
            ("EUR kuru", self.eur_rate),
            ("LME (USD/ton)", self.lme_usd_ton),
            ("Prim (USD/ton)", self.premium_usd_ton),
        )
        for index, (label, editor) in enumerate(lme_fields):
            lme_grid.addWidget(QLabel(label), 0, index * 2)
            lme_grid.addWidget(editor, 0, index * 2 + 1)
        general_layout.addWidget(QLabel("KUR / LME"))
        general_layout.addWidget(lme_frame)
        general_layout.addStretch(1)
        tabs.addTab(tab_general, "Genel Bilgiler")

        tab_lines = QWidget()
        lines_layout = QVBoxLayout(tab_lines)
        line_frame = QFrame()
        line_frame.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        line_layout = QGridLayout(line_frame)
        self.profile = QComboBox()
        self.profile.addItem("Profil kartı seçin…", None)
        for row in self.profile_rows.values():
            marker = "" if row["has_route"] else " [ROTA YOK]"
            self.profile.addItem(
                f"{row['profile_code']} — {row['profile_name']}{marker}", row["id"]
            )
        self.die = QComboBox()
        self.length = QSpinBox()
        self.length.setRange(1, 50_000)
        self.length.setValue(6000)
        self.surface = QComboBox()
        self.surface.addItems(("PRES", "ELOKSAL", "BOYALI", "HAM"))
        self.quantity = number_box(decimals=0)
        self.kg = number_box(decimals=3)
        self.kg.setReadOnly(True)
        self.kg.setToolTip("Adet × boy (m) × profil kartındaki teorik kg/m")
        self.unit_price = number_box(decimals=4)
        self.add_line_button = QPushButton("＋ SATIR EKLE")
        entries = (
            ("Profil *", self.profile), ("Kalıp", self.die),
            ("Boy (mm)", self.length), ("Yüzey", self.surface),
            ("Adet", self.quantity), ("Teorik KG", self.kg),
            ("Birim fiyat", self.unit_price),
        )
        for index, (label, editor) in enumerate(entries):
            line_layout.addWidget(QLabel(label), 0, index)
            line_layout.addWidget(editor, 1, index)
        line_layout.addWidget(self.add_line_button, 1, len(entries))
        lines_layout.addWidget(line_frame)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            (
                "Sıra", "Profil Kod", "Profil Ad", "Adet", "Boy",
                "Yüzey", "kg/m", "KG", "Birim Fiyat", "Tutar",
            )
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lines_layout.addWidget(self.table, 1)
        remove = QPushButton("SEÇİLİ SATIRI SİL")
        remove.clicked.connect(self.remove_line)
        lines_layout.addWidget(remove, 0, Qt.AlignLeft)
        tabs.addTab(tab_lines, "Satır Detayları")

        tab_notes = QWidget()
        notes_layout = QVBoxLayout(tab_notes)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Sipariş notu / özel açıklama")
        self.note.setMinimumHeight(120)
        notes_layout.addWidget(QLabel("NOT / AÇIKLAMA"))
        notes_layout.addWidget(self.note)
        totals_frame = QFrame()
        totals_frame.setStyleSheet(
            "QFrame{background:#E8F0F8;border:1px solid #C7D5E5;border-radius:6px;}"
        )
        totals_grid = QGridLayout(totals_frame)
        self.total_quantity = QLabel("0")
        self.total_kg = QLabel("0,000")
        self.total_amount = QLabel("0,00")
        self.total_currency = QLabel("TRY")
        for index, (label, widget) in enumerate(
            (
                ("Toplam adet", self.total_quantity),
                ("Toplam KG", self.total_kg),
                ("Toplam tutar", self.total_amount),
                ("Döviz", self.total_currency),
            )
        ):
            totals_grid.addWidget(QLabel(label), 0, index * 2)
            widget.setStyleSheet("font-weight:800;font-size:14px;")
            totals_grid.addWidget(widget, 0, index * 2 + 1)
        notes_layout.addWidget(QLabel("TOPLAMLAR"))
        notes_layout.addWidget(totals_frame)
        notes_layout.addStretch(1)
        tabs.addTab(tab_notes, "Notlar & Toplamlar")

        root.addWidget(tabs, 1)
        self.profile.currentIndexChanged.connect(self.refresh_dies)
        self.profile.currentIndexChanged.connect(self.recalculate_kg)
        self.length.valueChanged.connect(self.recalculate_kg)
        self.quantity.valueChanged.connect(self.recalculate_kg)
        self.add_line_button.clicked.connect(self.add_line)
        self.customer.currentIndexChanged.connect(self.refresh_addresses)
        self.currency.currentTextChanged.connect(self.refresh_totals)
        self.finish(root)
        self.refresh_dies()
        self.refresh_addresses()
        if editing:
            self.load_order(int(order_id))

    def header_values(self) -> dict[str, object]:
        return {
            "customer_id": int(self.customer.currentData()),
            "order_date": self.order_date.date().toString("yyyy-MM-dd"),
            "delivery_date": self.delivery_date.date().toString("yyyy-MM-dd"),
            "customer_document_no": self.document_no.text(),
            "msp": self.msp.text(),
            "currency": self.currency.currentText(),
            "delivery_address_id": self.delivery_address.currentData(),
            "payment_method": self.payment_method.currentText(),
            "maturity_days": self.maturity_days.value(),
            "contact_name": self.contact_name.text(),
            "representative": self.representative.text(),
            "note": self.note.toPlainText(),
            "usd_rate": self.usd_rate.value(),
            "eur_rate": self.eur_rate.value(),
            "lme_usd_ton": self.lme_usd_ton.value(),
            "premium_usd_ton": self.premium_usd_ton.value(),
            "branch_id": self.branch.currentData(),
            "warehouse_id": self.warehouse.currentData(),
        }

    def load_order(self, order_id: int) -> None:
        progress = self.service.order_progress(order_id)
        order = progress["order"]
        self.voucher_no.setText(str(order["order_no"]))
        self.revision_no.setText(f"{int(order.get('revision_no') or 0):02d}")
        self.voucher_date.setText(str(order.get("created_at") or "")[:16].replace("T", " "))
        index = self.customer.findData(int(order["customer_id"]))
        if index >= 0:
            self.customer.setCurrentIndex(index)
        self.refresh_addresses()
        self.contact_name.setText(str(order.get("contact_name") or ""))
        self.document_no.setText(str(order.get("customer_document_no") or ""))
        payment = str(order.get("payment_method") or "")
        if payment:
            pay_index = self.payment_method.findText(payment)
            if pay_index >= 0:
                self.payment_method.setCurrentIndex(pay_index)
        self.maturity_days.setValue(int(order.get("maturity_days") or 0))
        self.order_date.setDate(QDate.fromString(str(order["order_date"]), "yyyy-MM-dd"))
        self.delivery_date.setDate(QDate.fromString(str(order["delivery_date"]), "yyyy-MM-dd"))
        self.msp.setText(str(order.get("msp") or ""))
        self.representative.setText(str(order.get("representative") or ""))
        self.note.setPlainText(str(order.get("note") or ""))
        self.usd_rate.setValue(float(order.get("usd_rate") or 0))
        self.eur_rate.setValue(float(order.get("eur_rate") or 0))
        self.lme_usd_ton.setValue(float(order.get("lme_usd_ton") or 0))
        self.premium_usd_ton.setValue(float(order.get("premium_usd_ton") or 0))
        currency = str(order.get("currency") or "TRY")
        cur_index = self.currency.findText(currency)
        if cur_index >= 0:
            self.currency.setCurrentIndex(cur_index)
        if order.get("branch_id") is not None:
            branch_index = self.branch.findData(int(order["branch_id"]))
            if branch_index >= 0:
                self.branch.setCurrentIndex(branch_index)
        if order.get("warehouse_id") is not None:
            wh_index = self.warehouse.findData(int(order["warehouse_id"]))
            if wh_index >= 0:
                self.warehouse.setCurrentIndex(wh_index)
        if order.get("delivery_address_id") is not None:
            addr_index = self.delivery_address.findData(int(order["delivery_address_id"]))
            if addr_index >= 0:
                self.delivery_address.setCurrentIndex(addr_index)
        self.lines.clear()
        self.table.setRowCount(0)
        for row in progress["lines"]:
            profile = self.profile_rows.get(int(row["profile_id"]), {})
            unit_weight = float(profile.get("unit_weight_kg_m") or 0)
            die_text = "—"
            if row.get("die_id"):
                dies = self.service.list_dies(int(row["profile_id"]))
                for die in dies:
                    if int(die["id"]) == int(row["die_id"]):
                        die_text = f"{die['die_code']} / Yedek {die['spare_no']}"
                        break
            values: dict[str, object] = {
                "profile_id": int(row["profile_id"]),
                "profile_code": row.get("profile_code"),
                "profile_name": row.get("profile_name"),
                "die_id": row.get("die_id"),
                "die_text": die_text,
                "length_mm": int(row["stock_length_mm"]),
                "surface": row["surface"],
                "quantity": float(row["ordered_quantity"]),
                "kg": float(row["ordered_kg"]),
                "unit_weight_kg_m": unit_weight,
                "unit_price": float(row["unit_price"]),
            }
            self.lines.append(values)
            self._append_table_row(len(self.lines), values)
        self.refresh_totals()

    def refresh_totals(self, *_args: object) -> None:
        total_qty = sum(float(line.get("quantity") or 0) for line in self.lines)
        total_kg = sum(float(line.get("kg") or 0) for line in self.lines)
        total_amount = sum(
            float(line.get("kg") or 0) * float(line.get("unit_price") or 0)
            for line in self.lines
        )
        self.total_quantity.setText(f"{total_qty:,.0f}".replace(",", "."))
        self.total_kg.setText(f"{total_kg:,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.total_amount.setText(
            f"{total_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        self.total_currency.setText(self.currency.currentText())

    def _append_table_row(self, line_no: int, values: dict[str, object]) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        amount = float(values.get("kg") or 0) * float(values.get("unit_price") or 0)
        display = (
            line_no,
            values.get("profile_code"),
            values.get("profile_name"),
            values.get("quantity"),
            values.get("length_mm"),
            values.get("surface"),
            f"{float(values.get('unit_weight_kg_m') or 0):.3f}",
            values.get("kg"),
            values.get("unit_price"),
            f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        for column, value in enumerate(display):
            self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def refresh_addresses(self, *_args: object) -> None:
        selected = self.delivery_address.currentData()
        self.delivery_address.clear()
        self.delivery_address.addItem("Müşteri merkez adresi", None)
        customer_id = self.customer.currentData()
        if customer_id is not None:
            for row in self.service.list_customer_contacts(int(customer_id)):
                if not self.contact_name.text().strip() and row.get("name"):
                    self.contact_name.setText(str(row["name"]))
                    break
            for row in self.service.list_customer_addresses(int(customer_id)):
                label = " — ".join(
                    value for value in (
                        str(row["name"]), str(row["city"]), str(row["district"]),
                        str(row["address"]),
                    ) if value
                )
                self.delivery_address.addItem(label, row["id"])
        if selected is not None:
            index = self.delivery_address.findData(selected)
            if index >= 0:
                self.delivery_address.setCurrentIndex(index)

    def recalculate_kg(self, *_args: object) -> None:
        profile = self.profile_rows.get(self.profile.currentData())
        unit_weight = float(profile.get("unit_weight_kg_m") or 0) if profile else 0.0
        theoretical_kg = (
            self.quantity.value() * (self.length.value() / 1000.0) * unit_weight
        )
        self.kg.setValue(round(theoretical_kg, 3))

    def refresh_dies(self) -> None:
        current = self.die.currentData()
        self.die.clear()
        self.die.addItem("Kalıp seçin…", None)
        profile_id = self.profile.currentData()
        if profile_id:
            for row in self.service.list_dies(int(profile_id)):
                self.die.addItem(
                    f"{row['die_code']} / Yedek {row['spare_no']}", row["id"]
                )
        if current is not None:
            index = self.die.findData(current)
            if index >= 0:
                self.die.setCurrentIndex(index)

    def add_line(self) -> None:
        profile_id = self.profile.currentData()
        profile = self.profile_rows.get(profile_id)
        if profile is None:
            QMessageBox.warning(self, "Eksik bilgi", "Önce profil kartını seçin.")
            return
        if not profile["has_route"]:
            QMessageBox.warning(self, "Rota yok", "Bu profil için üretim rotası tanımlı değil.")
            return
        if self.quantity.value() <= 0:
            QMessageBox.warning(self, "Eksik miktar", "Sipariş adedini girin.")
            return
        if float(profile.get("unit_weight_kg_m") or 0) <= 0:
            QMessageBox.warning(
                self, "Profil gramajı eksik",
                "Profil kartındaki teorik ağırlık (kg/m) sıfır olamaz.",
            )
            return
        values: dict[str, object] = {
            "profile_id": profile_id,
            "profile_code": profile["profile_code"],
            "profile_name": profile["profile_name"],
            "die_id": self.die.currentData(),
            "die_text": self.die.currentText() if self.die.currentData() else "—",
            "length_mm": self.length.value(),
            "surface": self.surface.currentText(),
            "quantity": self.quantity.value(),
            "kg": self.kg.value(),
            "unit_weight_kg_m": float(profile.get("unit_weight_kg_m") or 0),
            "unit_price": self.unit_price.value(),
        }
        self.lines.append(values)
        self._append_table_row(len(self.lines), values)
        self.quantity.setValue(0)
        self.refresh_totals()

    def remove_line(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.lines.pop(row)
            self.table.setRowCount(0)
            for index, line in enumerate(self.lines, start=1):
                self._append_table_row(index, line)
            self.refresh_totals()

    def accept(self) -> None:
        if self.customer.currentData() is None:
            QMessageBox.warning(self, "Eksik bilgi", "Müşteri kartını seçin.")
            return
        if not self.lines:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir sipariş satırı ekleyin.")
            return
        super().accept()


class RecipeDialog(WorkflowDialog):
    def __init__(
        self,
        service: LocalWorkflowService,
        parent: QWidget | None = None,
        *,
        recipe_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.recipe_id = int(recipe_id) if recipe_id is not None else None
        self.profile_rows = {row["id"]: row for row in service.list_profiles()}
        self.stock_rows = {
            row["code"]: row for row in service.list_stock_items(include_inactive=False)
        }
        editing = self.recipe_id is not None
        self.setWindowTitle("Reçete Düzenle" if editing else "Yeni Üretim Reçetesi")
        self.resize(1080, 760)
        root = QVBoxLayout(self)
        title = QLabel("PROFİL REÇETESİ VE OPERASYON ORANLARI")
        title.setStyleSheet(title_style())
        info = QLabel(
            "Profil rotasını seçin. Pres operasyonunda düşülecek hammadde stok kartını "
            "belirleyin. Her operasyon satırında stok, ambar ve pay/payda oranlarını "
            "Sistemdeki gibi tanımlayın."
        )
        info.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(info)
        form = QGridLayout()
        self.profile = QComboBox()
        self.profile.addItem("Profil kartı seçin…", None)
        for row in self.profile_rows.values():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.route = QComboBox()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.raw_material = QComboBox()
        self.raw_material.addItem("Pres hammadde stok kartı seçin…", "")
        for row in self.stock_rows.values():
            if str(row.get("stock_group") or "").upper() == "HAMMADDE":
                self.raw_material.addItem(f"{row['code']} — {row['name']}", row["code"])
        self.production_length = number_box(decimals=0, maximum=100_000)
        self.saw_allowance = number_box(decimals=2, maximum=10_000)
        self.hanger_allowance = number_box(decimals=2, maximum=10_000)
        fields = (
            ("Profil *", self.profile), ("Rota *", self.route),
            ("Reçete kodu *", self.code), ("Reçete adı *", self.name),
            ("Pres hammadde stok kartı *", self.raw_material),
            ("Üretim boyu (mm)", self.production_length),
            ("Testere payı (mm)", self.saw_allowance),
            ("Askı payı (mm)", self.hanger_allowance),
        )
        for index, (label, editor) in enumerate(fields):
            row, column = divmod(index, 2)
            form.addWidget(QLabel(label), row, column * 2)
            form.addWidget(editor, row, column * 2 + 1)
        root.addLayout(form)
        self.lines = QTableWidget(0, 9)
        self.lines.setHorizontalHeaderLabels(
            (
                "Sıra", "Operasyon", "İstasyon", "Giriş Ambarı", "Çıkış Ambarı",
                "Stok Kartı", "Birim", "Pay", "Payda",
            )
        )
        self.lines.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.lines.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.lines, 1)
        self.profile.currentIndexChanged.connect(self.refresh_routes)
        self.route.currentIndexChanged.connect(self.load_route_steps)
        self.raw_material.currentIndexChanged.connect(self.apply_raw_material_to_pres_line)
        self.finish(root)
        self.refresh_routes()
        if editing:
            self._load_recipe()

    def _load_recipe(self) -> None:
        assert self.recipe_id is not None
        recipe = self.service.get_recipe(self.recipe_id)
        profile_index = self.profile.findData(int(recipe["profile_id"]))
        if profile_index >= 0:
            self.profile.setCurrentIndex(profile_index)
        self.refresh_routes()
        route_index = self.route.findData(int(recipe["route_id"]))
        if route_index >= 0:
            self.route.setCurrentIndex(route_index)
        self.code.setText(str(recipe["recipe_code"]))
        self.name.setText(str(recipe["recipe_name"]))
        self.production_length.setValue(float(recipe.get("production_length_mm") or 0))
        self.saw_allowance.setValue(float(recipe.get("saw_allowance_mm") or 0))
        self.hanger_allowance.setValue(float(recipe.get("hanger_allowance_mm") or 0))
        raw_code = str(recipe.get("raw_material_stock_external_id") or "")
        raw_index = self.raw_material.findData(raw_code)
        if raw_index >= 0:
            self.raw_material.setCurrentIndex(raw_index)
        self.profile.setEnabled(False)
        self.route.setEnabled(False)
        self.code.setReadOnly(True)
        self.lines.setRowCount(0)
        for line in self.service.list_recipe_lines(self.recipe_id):
            row = self.lines.rowCount()
            self.lines.insertRow(row)
            stock_code = str(line.get("stock_code") or "")
            values = (
                line["route_sequence_no"], line["operation_name"], line["station_name"],
                "", line.get("warehouse_code") or "",
                stock_code, line.get("unit_code") or "KG",
                line.get("numerator") or 1, line.get("denominator") or 1,
            )
            for column, value in enumerate(values):
                if column == 5:
                    self.lines.setCellWidget(
                        row, column, self._stock_combo(default_code=stock_code)
                    )
                else:
                    self.lines.setItem(row, column, QTableWidgetItem(str(value or "")))

    def apply_raw_material_to_pres_line(self, *_args: object) -> None:
        raw_code = str(self.raw_material.currentData() or "").strip()
        if not raw_code:
            return
        for row in range(self.lines.rowCount()):
            operation_item = self.lines.item(row, 1)
            if operation_item and "PRES" in operation_item.text().upper():
                stock_combo = self.lines.cellWidget(row, 5)
                if isinstance(stock_combo, QComboBox):
                    index = stock_combo.findData(raw_code)
                    if index >= 0:
                        stock_combo.setCurrentIndex(index)

    def _stock_combo(self, *, default_code: str = "") -> QComboBox:
        combo = QComboBox()
        combo.addItem("— profil stok kartı —", "")
        for code, row in sorted(self.stock_rows.items()):
            combo.addItem(f"{code} — {row['name']}", code)
        if default_code:
            index = combo.findData(default_code)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def refresh_routes(self, *_args: object) -> None:
        self.route.clear()
        self.route.addItem("Üretim rotası seçin…", None)
        profile_id = self.profile.currentData()
        if profile_id is not None:
            for row in self.service.list_routes(int(profile_id)):
                self.route.addItem(f"{row['code']} — {row['name']}", row["id"])

    def load_route_steps(self, *_args: object) -> None:
        route_id = self.route.currentData()
        self.lines.setRowCount(0)
        if route_id is None:
            return
        raw_code = str(self.raw_material.currentData() or "").strip()
        for step in self.service.list_route_steps(int(route_id)):
            row = self.lines.rowCount()
            self.lines.insertRow(row)
            operation = str(step.get("operation") or "")
            stock_code = raw_code if "PRES" in operation.upper() else ""
            values = (
                step["sequence_no"], operation, step["default_station"],
                step["input_warehouse_code"], step["output_warehouse_code"],
                stock_code, "KG", 1, 1,
            )
            for column, value in enumerate(values):
                if column == 5:
                    self.lines.setCellWidget(row, column, self._stock_combo(default_code=str(value)))
                else:
                    self.lines.setItem(row, column, QTableWidgetItem(str(value or "")))
        profile = self.profile_rows.get(self.profile.currentData())
        if profile and not self.code.text().strip():
            self.code.setText(f"RC-{profile['profile_code']}")
            self.name.setText(f"{profile['profile_name']} üretim reçetesi")

    def create_record(self, *, username: str) -> int:
        if self.profile.currentData() is None or self.route.currentData() is None:
            raise ValueError("Profil ve üretim rotası seçilmelidir.")
        raw_code = str(self.raw_material.currentData() or "").strip().upper()
        if not raw_code:
            raise ValueError("Pres operasyonunda düşülecek hammadde stok kartı seçilmelidir.")
        lines: list[dict[str, object]] = []
        for row in range(self.lines.rowCount()):
            text = lambda column: (
                self.lines.item(row, column).text().strip()
                if self.lines.item(row, column) else ""
            )
            stock_combo = self.lines.cellWidget(row, 5)
            stock_code = ""
            if isinstance(stock_combo, QComboBox):
                stock_code = str(stock_combo.currentData() or "").strip().upper()
            operation = text(1)
            if "PRES" in operation.upper() and not stock_code:
                stock_code = raw_code
            lines.append(
                {
                    "route_sequence_no": int(float(text(0) or row + 1)),
                    "operation": operation, "station": text(2),
                    "warehouse_code": text(4),
                    "stock_code": stock_code,
                    "unit_code": text(6) or "KG",
                    "numerator": float(text(7).replace(",", ".") or 1),
                    "denominator": float(text(8).replace(",", ".") or 1),
                }
            )
        return self.service.create_recipe(
            int(self.profile.currentData()), int(self.route.currentData()),
            self.code.text(), self.name.text(), lines,
            production_length_mm=self.production_length.value(),
            saw_allowance_mm=self.saw_allowance.value(),
            hanger_allowance_mm=self.hanger_allowance.value(),
            raw_material_stock_code=raw_code,
            username=username,
        )

    def update_record(self, *, username: str) -> None:
        if self.recipe_id is None:
            raise ValueError("Düzenlenecek reçete seçilmedi.")
        raw_code = str(self.raw_material.currentData() or "").strip().upper()
        if not raw_code:
            raise ValueError("Pres operasyonunda düşülecek hammadde stok kartı seçilmelidir.")
        lines: list[dict[str, object]] = []
        for row in range(self.lines.rowCount()):
            text = lambda column: (
                self.lines.item(row, column).text().strip()
                if self.lines.item(row, column) else ""
            )
            stock_combo = self.lines.cellWidget(row, 5)
            stock_code = ""
            if isinstance(stock_combo, QComboBox):
                stock_code = str(stock_combo.currentData() or "").strip().upper()
            operation = text(1)
            if "PRES" in operation.upper() and not stock_code:
                stock_code = raw_code
            lines.append(
                {
                    "route_sequence_no": int(float(text(0) or row + 1)),
                    "operation": operation, "station": text(2),
                    "warehouse_code": text(4),
                    "stock_code": stock_code,
                    "unit_code": text(6) or "KG",
                    "numerator": float(text(7).replace(",", ".") or 1),
                    "denominator": float(text(8).replace(",", ".") or 1),
                }
            )
        self.service.update_recipe(
            self.recipe_id,
            recipe_name=self.name.text(),
            lines=lines,
            production_length_mm=self.production_length.value(),
            saw_allowance_mm=self.saw_allowance.value(),
            hanger_allowance_mm=self.hanger_allowance.value(),
            raw_material_stock_code=raw_code,
            username=username,
        )


class SalesQuoteDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.profile_rows = {row["id"]: row for row in service.list_profiles()}
        self.setWindowTitle("Yeni Satış Teklifi")
        self.resize(960, 640)
        root = QVBoxLayout(self)
        title = QLabel("SATIŞ TEKLİFİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QGridLayout()
        self.customer = QComboBox()
        self.customer.addItem("Müşteri seçin…", None)
        for row in service.list_customers():
            self.customer.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.quote_date = QDateEdit(QDate.currentDate())
        self.quote_date.setCalendarPopup(True)
        self.valid_until = QDateEdit(QDate.currentDate().addDays(30))
        self.valid_until.setCalendarPopup(True)
        self.currency = QComboBox()
        self.currency.addItems(("EUR", "USD", "TRY"))
        self.exchange_rate = number_box(decimals=4, maximum=1_000)
        self.exchange_rate.setValue(1.0)
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(60)
        fields = (
            ("Müşteri *", self.customer), ("Teklif tarihi", self.quote_date),
            ("Geçerlilik", self.valid_until), ("Döviz", self.currency),
            ("Kur", self.exchange_rate),
        )
        for index, (label, editor) in enumerate(fields):
            row, column = divmod(index, 2)
            form.addWidget(QLabel(label), row, column * 2)
            form.addWidget(editor, row, column * 2 + 1)
        root.addLayout(form)
        root.addWidget(QLabel("Not"))
        root.addWidget(self.note)
        self.lines = QTableWidget(0, 7)
        self.lines.setHorizontalHeaderLabels(
            ("Profil", "Boy mm", "Adet", "KG", "Birim Fiyat", "Yüzey", "Alaşım/Sertlik")
        )
        self.lines.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.lines, 1)
        buttons = QHBoxLayout()
        add_line = QPushButton("＋ Satır Ekle")
        remove_line = QPushButton("－ Satır Sil")
        add_line.clicked.connect(self.add_line_row)
        remove_line.clicked.connect(self.remove_line_row)
        buttons.addWidget(add_line)
        buttons.addWidget(remove_line)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.finish(root)
        self.add_line_row()

    def _profile_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem("Profil seçin…", None)
        for row in self.profile_rows.values():
            combo.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        return combo

    def add_line_row(self) -> None:
        row = self.lines.rowCount()
        self.lines.insertRow(row)
        self.lines.setCellWidget(row, 0, self._profile_combo())
        for column, default in ((1, "6000"), (2, "100"), (3, "500"), (4, "4.5"), (5, "PRES"), (6, "6060B/T5")):
            self.lines.setItem(row, column, QTableWidgetItem(default))

    def remove_line_row(self) -> None:
        row = self.lines.currentRow()
        if row >= 0:
            self.lines.removeRow(row)

    def create_record(self, *, username: str) -> int:
        if self.customer.currentData() is None:
            raise ValueError("Müşteri seçilmelidir.")
        lines: list[dict[str, object]] = []
        for row in range(self.lines.rowCount()):
            profile_combo = self.lines.cellWidget(row, 0)
            profile_id = profile_combo.currentData() if isinstance(profile_combo, QComboBox) else None
            if profile_id is None:
                continue
            text = lambda col: (
                self.lines.item(row, col).text().strip()
                if self.lines.item(row, col) else ""
            )
            alloy_temper = text(6).split("/")
            lines.append(
                {
                    "profile_id": int(profile_id),
                    "length_mm": float(text(1).replace(",", ".") or 0),
                    "quantity": float(text(2).replace(",", ".") or 0),
                    "kg": float(text(3).replace(",", ".") or 0),
                    "unit_price": float(text(4).replace(",", ".") or 0),
                    "surface": text(5),
                    "alloy": alloy_temper[0] if alloy_temper else "",
                    "temper": alloy_temper[1] if len(alloy_temper) > 1 else "",
                }
            )
        if not lines:
            raise ValueError("En az bir teklif satırı girin.")
        return self.service.create_sales_quote(
            int(self.customer.currentData()),
            quote_date=self.quote_date.date().toString("yyyy-MM-dd"),
            valid_until=self.valid_until.date().toString("yyyy-MM-dd"),
            lines=lines,
            currency=self.currency.currentText(),
            exchange_rate=self.exchange_rate.value(),
            note=self.note.toPlainText(),
            username=username,
        )


class ProductionPlanDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._eligible: list[dict[str, Any]] = []
        self.rows = {
            row["id"]: row for row in service.list_order_lines_for_planning()
            if float(row["remaining_quantity"] or 0) > 0.001
            or float(row["remaining_kg"] or 0) > 0.001
        }
        self.setWindowTitle("Üretim Emri")
        self.resize(920, 640)
        root = QVBoxLayout(self)
        title = QLabel("ÜRETİM EMRİ — REÇETE / ROTA / HAMMADDE")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        info = QLabel(
            "Sipariş satırı için reçete, rota ve hammadde seçerek üretim emri açın. "
            "Bu seçimler Kalıphane kartlarında değil; üretim planlamasında yapılır."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        form = QFormLayout()
        self.order_line = QComboBox()
        self.order_line.addItem("Planlanacak sipariş satırını seçin…", None)
        for row in self.rows.values():
            self.order_line.addItem(
                f"{row['order_no']} / {row['customer_name']} / {row['profile_code']} — "
                f"Kalan {row['remaining_quantity']:.0f} adet, {row['remaining_kg']:.3f} kg",
                row["id"],
            )
        self.recipe = QComboBox()
        self.route = QComboBox()
        self.raw_material = QComboBox()
        self.quantity = number_box(decimals=0)
        self.kg = number_box(decimals=3)
        self.planned_start = QDateEdit(QDate.currentDate())
        self.planned_start.setCalendarPopup(True)
        self.remaining = QLabel("Sipariş satırı seçilmedi")
        self.remaining.setWordWrap(True)
        self.stations = QTableWidget(0, 3)
        self.stations.setHorizontalHeaderLabels(("Sıra", "Operasyon", "İstasyon"))
        self.stations.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stations.setMaximumHeight(180)
        form.addRow("Sipariş satırı *", self.order_line)
        form.addRow("REÇETE *", self.recipe)
        form.addRow("ROTA *", self.route)
        form.addRow("HAMMADDE", self.raw_material)
        form.addRow("Plan adedi", self.quantity)
        form.addRow("Plan kg", self.kg)
        form.addRow("Plan başlangıcı", self.planned_start)
        form.addRow("Kalan", self.remaining)
        form.addRow("İstasyonlar", self.stations)
        root.addLayout(form)
        root.addStretch(1)
        self.order_line.currentIndexChanged.connect(self.refresh_line)
        self.recipe.currentIndexChanged.connect(self._sync_from_recipe)
        self.route.currentIndexChanged.connect(self._sync_from_route)
        self.finish(root)
        self.refresh_line()

    def refresh_line(self, *_args: object) -> None:
        record = self.rows.get(self.order_line.currentData())
        self._eligible = []
        self.recipe.blockSignals(True)
        self.route.blockSignals(True)
        self.raw_material.blockSignals(True)
        self.recipe.clear()
        self.route.clear()
        self.raw_material.clear()
        self.stations.setRowCount(0)
        self.recipe.addItem("Reçete seçin…", None)
        self.route.addItem("Rota seçin…", None)
        self.raw_material.addItem("Hammadde (reçeteden)", "")
        if record is None:
            self.quantity.setValue(0)
            self.kg.setValue(0)
            self.remaining.setText("Sipariş satırı seçilmedi")
            self.recipe.blockSignals(False)
            self.route.blockSignals(False)
            self.raw_material.blockSignals(False)
            return
        self._eligible = self.service.list_eligible_routes_for_line(int(record["id"]))
        seen_recipes: set[int] = set()
        for item in self._eligible:
            recipe_id = item.get("recipe_id")
            if recipe_id and int(recipe_id) not in seen_recipes:
                seen_recipes.add(int(recipe_id))
                self.recipe.addItem(
                    f"{item['recipe_code']} — {item['recipe_name']}",
                    int(recipe_id),
                )
            self.route.addItem(
                f"{item['code']} — {item['name']}",
                int(item["id"]),
            )
            raw = str(item.get("raw_material_code") or "").strip()
            if raw and self.raw_material.findData(raw) < 0:
                label = raw
                for stock in self.service.list_stock_items():
                    if str(stock.get("code") or "").upper() == raw:
                        label = f"{stock['code']} — {stock['name']}"
                        break
                self.raw_material.addItem(label, raw)
        if not self._eligible:
            self.recipe.addItem("Uygun reçete bulunamadı", None)
            self.route.addItem("Uygun rota bulunamadı", None)
        elif self.route.count() == 2:
            self.route.setCurrentIndex(1)
            self._sync_from_route()
        self.quantity.setValue(float(record["remaining_quantity"] or 0))
        self.kg.setValue(float(record["remaining_kg"] or 0))
        self.remaining.setText(
            f"Kalan: {float(record['remaining_quantity'] or 0):.0f} adet / "
            f"{float(record['remaining_kg'] or 0):.3f} kg — Teslim {record['delivery_date']}"
        )
        self.recipe.blockSignals(False)
        self.route.blockSignals(False)
        self.raw_material.blockSignals(False)

    def _sync_from_recipe(self, *_args: object) -> None:
        recipe_id = self.recipe.currentData()
        if recipe_id is None:
            return
        match = next(
            (item for item in self._eligible if item.get("recipe_id") == int(recipe_id)),
            None,
        )
        if match is None:
            return
        self.route.blockSignals(True)
        idx = self.route.findData(int(match["id"]))
        if idx >= 0:
            self.route.setCurrentIndex(idx)
        self.route.blockSignals(False)
        self._apply_match(match)

    def _sync_from_route(self, *_args: object) -> None:
        route_id = self.route.currentData()
        if route_id is None:
            self.stations.setRowCount(0)
            return
        match = next(
            (item for item in self._eligible if int(item["id"]) == int(route_id)),
            None,
        )
        if match is None:
            return
        if match.get("recipe_id"):
            self.recipe.blockSignals(True)
            idx = self.recipe.findData(int(match["recipe_id"]))
            if idx >= 0:
                self.recipe.setCurrentIndex(idx)
            self.recipe.blockSignals(False)
        self._apply_match(match)

    def _apply_match(self, match: dict[str, Any]) -> None:
        raw = str(match.get("raw_material_code") or "").strip()
        if raw:
            self.raw_material.blockSignals(True)
            idx = self.raw_material.findData(raw)
            if idx < 0:
                self.raw_material.addItem(raw, raw)
                idx = self.raw_material.findData(raw)
            if idx >= 0:
                self.raw_material.setCurrentIndex(idx)
            self.raw_material.blockSignals(False)
        self.stations.setRowCount(0)
        try:
            steps = self.service.list_route_steps(int(match["id"]))
        except (ValueError, OSError):
            steps = []
        for step in steps:
            row = self.stations.rowCount()
            self.stations.insertRow(row)
            self.stations.setItem(
                row, 0, QTableWidgetItem(str(step.get("sequence_no") or row + 1))
            )
            self.stations.setItem(
                row, 1, QTableWidgetItem(str(step.get("operation") or ""))
            )
            self.stations.setItem(
                row, 2,
                QTableWidgetItem(
                    str(step.get("default_station") or step.get("station") or "")
                ),
            )

    def create_record(self, *, username: str) -> int:
        if self.order_line.currentData() is None or self.route.currentData() is None:
            raise ValueError("Sipariş satırı ve rota seçilmelidir.")
        if self.recipe.currentData() is None and self.recipe.count() > 2:
            raise ValueError("Reçete seçilmelidir.")
        return self.service.plan_sales_order_line(
            int(self.order_line.currentData()),
            planned_quantity=self.quantity.value(),
            planned_kg=self.kg.value(),
            route_id=int(self.route.currentData()),
            planned_start=self.planned_start.date().toString("yyyy-MM-dd"),
            username=username,
        )


class ProductionEntryDialog(WorkflowDialog):
    def __init__(self, work_order: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.work_order = work_order
        self.is_press = str(work_order["operation"] or "").upper().startswith("PRES")
        self.setWindowTitle("Operatör Üretim Fişi")
        self.resize(900, 780)
        root = QVBoxLayout(self)
        title = QLabel(f"ÜRETİM GİRİŞİ — {work_order['work_order_no']}")
        title.setStyleSheet(title_style(px=17, weight=900))
        root.addWidget(title)
        info = QLabel(
            f"{work_order['customer_name']} · {work_order['profile_code']} · "
            f"{work_order['operation']} / {work_order['station']}"
        )
        root.addWidget(info)

        content = QWidget()
        content.setMinimumSize(760, 790 if self.is_press else 390)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        form = QFormLayout()
        self.quantity = number_box(decimals=0)
        self.quantity.setValue(float(work_order["planned_quantity"] or 0))
        self.gross = number_box(decimals=3)
        self.gross.setValue(float(work_order["planned_kg"] or 0))
        self.net = number_box(decimals=3)
        self.net.setValue(float(work_order["planned_kg"] or 0))
        self.metre = number_box(decimals=2)
        self.lot = QLineEdit()
        self.shift = QComboBox()
        self.shift.addItems(("1.VARDİYA", "2.VARDİYA", "3.VARDİYA"))
        self.complete = QCheckBox("İş emrini tamamla ve sonraki istasyonu aç")
        self.complete.setChecked(True)
        for label, editor in (
            ("Üretilen adet", self.quantity), ("Brüt KG", self.gross),
            ("Net KG", self.net), ("Net metre", self.metre),
            ("Lot no", self.lot), ("Vardiya", self.shift),
            ("İş emri durumu", self.complete),
        ):
            form.addRow(label, editor)
        content_layout.addLayout(form)

        self.production_type = QComboBox()
        self.production_type.addItems(
            ("PLANLI ÜRETİM", "PLANSIZ ÜRETİM", "TEST", "KISA BOY", "NUMUNE")
        )
        self.press_status = QComboBox()
        self.press_status.addItems(("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI"))
        self.press_status.setCurrentText("TAMAMLANDI")
        self.saw_status = QComboBox()
        self.saw_status.addItems(("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI"))
        self.saw_status.setCurrentText("TAMAMLANDI")
        self.real_weight = number_box(decimals=4)
        self.real_weight.setValue(float(work_order.get("unit_weight_kg_m") or 0))
        self.real_weight.setReadOnly(self.is_press)
        self.theoretical_weight = number_box(decimals=4)
        self.theoretical_weight.setValue(float(work_order.get("unit_weight_kg_m") or 0))
        self.theoretical_weight.setReadOnly(True)
        self.billet_count = QSpinBox()
        self.billet_count.setRange(1, 100_000)
        self.billet_count.setValue(1)
        self.billet_length = number_box(decimals=0, maximum=50_000)
        self.billet_length.setReadOnly(True)
        self.billet_diameter = number_box(decimals=2, maximum=1_000)
        self.billet_diameter.setValue(152.40)
        self.billet_density = number_box(decimals=0, maximum=20_000)
        self.billet_density.setValue(2700)
        self.billet_weight = number_box(decimals=4, maximum=10_000)
        self.billet_weight.setReadOnly(True)
        self.press_fire = number_box(decimals=2, maximum=50)
        self.press_fire.setValue(3.0)
        self.theoretical_net = number_box(decimals=3)
        self.theoretical_net.setReadOnly(True)
        self.theoretical_billet = number_box(decimals=3)
        self.theoretical_billet.setReadOnly(True)
        self.basket_count = QSpinBox()
        self.basket_count.setRange(0, 10_000)
        self.result_length = number_box(decimals=0, maximum=50_000)
        default_length = float(
            work_order.get("production_length_mm") or work_order.get("production_length_mm") or 0
        )
        self.result_length.setValue(default_length)
        self.preparation_min = number_box(decimals=1, maximum=10_000)
        self.duration_min = number_box(decimals=1, maximum=100_000)
        self.missing_quantity = number_box(decimals=0)
        self.missing_reason = QLineEdit()
        self.missing_reason.setPlaceholderText("Örn. BOY KURTARMADI / HURDA")
        self.note = QLineEdit()
        self.note.setPlaceholderText("Operatör ve üretim notu")

        press_frame = QFrame()
        press_frame.setObjectName("pressDetails")
        press_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        press_grid = QGridLayout(press_frame)
        press_entries = (
            ("Üretim tipi", self.production_type),
            ("Pres durumu", self.press_status),
            ("Testere durumu", self.saw_status),
            ("Reel gramaj kg/m", self.real_weight),
            ("Teorik gramaj kg/m", self.theoretical_weight),
            ("Billet adedi", self.billet_count),
            ("Billet çapı mm", self.billet_diameter),
            ("Billet yoğunluğu kg/m³", self.billet_density),
            ("Billet teorik kg/m", self.billet_weight),
            ("Pres fire oranı %", self.press_fire),
            ("Billet boyu mm", self.billet_length),
            ("Teorik net profil kg", self.theoretical_net),
            ("Teorik brüt billet kg", self.theoretical_billet),
            ("Sepet adedi", self.basket_count),
            ("Çıkan boy mm", self.result_length),
            ("Hazırlık dk", self.preparation_min),
            ("Üretim süresi dk", self.duration_min),
            ("Eksik adet", self.missing_quantity),
            ("Eksik nedeni", self.missing_reason),
            ("Not", self.note),
        )
        for index, (label, editor) in enumerate(press_entries):
            row, block = divmod(index, 2)
            press_grid.addWidget(QLabel(label), row, block * 2)
            press_grid.addWidget(editor, row, block * 2 + 1)
        press_frame.setVisible(self.is_press)
        content_layout.addWidget(press_frame)
        self.theory_note = QLabel(
            "Giren billet ve çıkan profil birbiriyle bağlıdır: adet × boy × profil "
            "teorik gramajı net KG'yi; billet çapı, yoğunluğu ve fire oranı billet "
            "boyunu belirler. Hesaplanan alanlar elle değiştirilemez."
        )
        self.theory_note.setWordWrap(True)
        self.theory_note.setStyleSheet(
            "color:#475467;background:#EAF2FB;border:1px solid #B9D2EC;"
            "border-radius:4px;padding:8px;font-weight:600;"
        )
        self.theory_note.setVisible(self.is_press)
        content_layout.addWidget(self.theory_note)
        content_layout.addStretch(1)

        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.NoFrame)
        content_scroll.setWidget(content)
        root.addWidget(content_scroll, 1)

        if self.is_press:
            self.gross.setReadOnly(True)
            self.net.setReadOnly(True)
            self.metre.setReadOnly(True)
            for editor in (
                self.quantity, self.result_length, self.theoretical_weight,
                self.billet_count, self.billet_diameter, self.billet_density,
                self.press_fire,
            ):
                editor.valueChanged.connect(self.recalculate_press)
            self.recalculate_press()
        self.finish(root)

    def recalculate_press(self, *_args: object) -> None:
        if not self.is_press:
            return
        theory = LocalWorkflowService.calculate_press_theory(
            quantity=self.quantity.value(),
            result_length_mm=self.result_length.value(),
            profile_weight_kg_m=self.theoretical_weight.value(),
            billet_count=self.billet_count.value(),
            billet_diameter_mm=self.billet_diameter.value(),
            billet_density_kg_m3=self.billet_density.value(),
            fire_pct=self.press_fire.value(),
        )
        self.metre.setValue(theory["net_metre"])
        self.net.setValue(theory["theoretical_net_kg"])
        self.gross.setValue(theory["theoretical_billet_kg"])
        self.real_weight.setValue(self.theoretical_weight.value())
        self.billet_weight.setValue(theory["billet_weight_kg_m"])
        self.billet_length.setValue(theory["billet_length_mm"])
        self.theoretical_net.setValue(theory["theoretical_net_kg"])
        self.theoretical_billet.setValue(theory["theoretical_billet_kg"])

    def accept(self) -> None:
        if self.is_press:
            if self.quantity.value() <= 0:
                QMessageBox.warning(self, "Üretim kaydedilemez", "Üretilen adet sıfırdan büyük olmalıdır.")
                return
            if self.result_length.value() <= 0 or self.theoretical_weight.value() <= 0:
                QMessageBox.warning(
                    self,
                    "Profil kartı eksik",
                    "Profil teorik gramajı ve üretim boyu tanımlanmadan pres fişi kaydedilemez.",
                )
                return
            if self.billet_diameter.value() <= 0 or self.billet_density.value() <= 0:
                QMessageBox.warning(
                    self, "Billet bilgisi eksik",
                    "Billet çapı ve alüminyum yoğunluğu sıfırdan büyük olmalıdır.",
                )
                return
            if self.billet_length.value() <= 0 or self.gross.value() < self.net.value():
                QMessageBox.warning(
                    self, "Giren–çıkan hesabı geçersiz",
                    "Billet boyu, brüt billet KG ve net profil KG hesabını kontrol edin.",
                )
                return
        elif self.net.value() <= 0 or self.gross.value() < self.net.value():
            QMessageBox.warning(
                self, "Geçersiz miktar", "Üretim brüt ve net kilogramlarını kontrol edin."
            )
            return
        super().accept()


class PackageDialog(WorkflowDialog):
    def __init__(self, service: LocalWorkflowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows = service.list_packable_lines()
        self.setWindowTitle("Yeni Paket / Kasa")
        self.resize(660, 430)
        root = QVBoxLayout(self)
        title = QLabel("YENİ PAKET / KASA")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.line = QComboBox()
        self.line.addItem("Paketlenecek üretilmiş profil satırını seçin…", None)
        for row in self.rows:
            self.line.addItem(
                f"{row['order_no']} · {row['customer_name']} · {row['profile_code']} "
                f"· kalan {row['remaining_kg']:.2f} kg",
                row["id"],
            )
        self.quantity = number_box(decimals=0)
        self.net = number_box(decimals=3)
        self.gross = number_box(decimals=3)
        self.lot = QLineEdit()
        form.addRow("Sipariş / profil *", self.line)
        form.addRow("Paketlenen adet", self.quantity)
        form.addRow("Net KG *", self.net)
        form.addRow("Brüt KG *", self.gross)
        form.addRow("Lot no", self.lot)
        root.addLayout(form)
        self.line.currentIndexChanged.connect(self.apply_remaining)
        self.finish(root)

    def apply_remaining(self) -> None:
        line_id = self.line.currentData()
        row = next((item for item in self.rows if item["id"] == line_id), None)
        if row:
            self.quantity.setValue(float(row["remaining_quantity"] or 0))
            self.net.setValue(float(row["remaining_kg"] or 0))
            self.gross.setValue(float(row["remaining_kg"] or 0))

    def accept(self) -> None:
        if self.line.currentData() is None:
            QMessageBox.warning(self, "Profil seçilmedi", "Paketlenecek sipariş profilini seçin.")
            return
        if self.net.value() <= 0 or self.gross.value() < self.net.value():
            QMessageBox.warning(self, "Geçersiz miktar", "Paket net ve brüt kilogramlarını kontrol edin.")
            return
        super().accept()


class WeighingListDialog(WorkflowDialog):
    def __init__(self, packages: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.packages = [row for row in packages if row["status"] == "SEVK ÖN"]
        self.setWindowTitle("Yeni Çeki Listesi")
        self.resize(850, 570)
        root = QVBoxLayout(self)
        title = QLabel("YENİ ÇEKİ LİSTESİ")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Araç, teslim veya yükleme notu…")
        root.addWidget(self.note)
        self.table = QTableWidget(len(self.packages), 5)
        self.table.setHorizontalHeaderLabels(
            ("Paket No", "Müşteri", "Sipariş", "Net KG", "Brüt KG")
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_index, row in enumerate(self.packages):
            values = (
                row["package_no"], row["customer_name"], row["order_nos"],
                row["net_kg"], row["gross_kg"],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0:
                    item.setData(Qt.UserRole, row["id"])
                self.table.setItem(row_index, column, item)
        root.addWidget(QLabel("Aynı müşteriye ait SEVK ÖN paketlerini seçin:"))
        root.addWidget(self.table, 1)
        self.finish(root)

    def selected_package_ids(self) -> list[int]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [
            int(self.table.item(row, 0).data(Qt.UserRole))
            for row in rows
            if self.table.item(row, 0) is not None
        ]

    def accept(self) -> None:
        if not self.selected_package_ids():
            QMessageBox.warning(self, "Paket seçilmedi", "En az bir SEVK ÖN paketi seçin.")
            return
        super().accept()


class ShipmentDialog(WorkflowDialog):
    def __init__(self, packages: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.packages = [row for row in packages if row["status"] == "SEVK HAZIR"]
        self.setWindowTitle("Yeni Sevkiyat")
        self.resize(850, 570)
        root = QVBoxLayout(self)
        title = QLabel("YENİ SEVKİYAT")
        title.setStyleSheet(title_style())
        root.addWidget(title)
        form = QFormLayout()
        self.shipment_date = QDateEdit(QDate.currentDate())
        self.shipment_date.setCalendarPopup(True)
        self.plate = QLineEdit()
        form.addRow("Sevk tarihi", self.shipment_date)
        form.addRow("Araç plakası", self.plate)
        root.addLayout(form)
        self.table = QTableWidget(len(self.packages), 5)
        self.table.setHorizontalHeaderLabels(("Paket No", "Müşteri", "Sipariş", "Net KG", "Brüt KG"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_index, row in enumerate(self.packages):
            values = (row["package_no"], row["customer_name"], row["order_nos"], row["net_kg"], row["gross_kg"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0:
                    item.setData(Qt.UserRole, row["id"])
                self.table.setItem(row_index, column, item)
        root.addWidget(QLabel("Aynı müşteriye ait bir veya daha fazla hazır paketi seçin:"))
        root.addWidget(self.table, 1)
        self.finish(root)

    def selected_package_ids(self) -> list[int]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        result: list[int] = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is not None:
                result.append(int(item.data(Qt.UserRole)))
        return result

    def accept(self) -> None:
        if not self.selected_package_ids():
            QMessageBox.warning(self, "Paket seçilmedi", "En az bir hazır paket seçin.")
            return
        super().accept()


class InvoiceDialog(WorkflowDialog):
    def __init__(self, shipment: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Satış İrsaliyesini Faturala")
        self.resize(620, 470)
        root = QVBoxLayout(self)
        title = QLabel(f"FATURALANDIR — {shipment.get('dispatch_note_no') or shipment['shipment_no']}")
        title.setStyleSheet(title_style(weight=700))
        root.addWidget(title)
        form = QFormLayout()
        self.invoice_date = QDateEdit(QDate.currentDate())
        self.invoice_date.setCalendarPopup(True)
        self.currency = QComboBox()
        self.currency.addItems(("TRY", "USD", "EUR"))
        self.exchange_rate = number_box(decimals=4)
        self.exchange_rate.setValue(1)
        self.lme = number_box(decimals=2)
        self.premium = number_box(decimals=2)
        self.mode = QComboBox()
        self.mode.addItems(("BİRİM FİYAT", "LME + PRİM"))
        for label, editor in (
            ("Fatura tarihi", self.invoice_date),
            ("Fatura dövizi", self.currency),
            ("Döviz kuru", self.exchange_rate),
            ("LME USD/ton", self.lme),
            ("Prim USD/ton", self.premium),
            ("Fiyatlandırma", self.mode),
        ):
            form.addRow(label, editor)
        root.addLayout(form)
        info = QLabel(
            "Birim Fiyat seçilirse sipariş satırındaki fiyatlar; LME + Prim seçilirse "
            "sevk edilen net kg ve girilen metal fiyatı kullanılır."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.finish(root)


class WorkflowPage(QWidget):
    """Satıştan sevkiyata kadar tek yerel ilişkisel veri zincirini gösterir."""

    CONTEXT_VIEW = {
        ("Satış", "Müşteriler"): "customers",
        ("Satış", "Satış Siparişleri"): "orders",
        ("Satış", "Satış İrsaliyeleri"): "shipments",
        ("Satış", "Satış Faturaları"): "invoices",
        ("Satış", "Satış Sevk Miktarları"): "orders",
        ("Satış", "Bekleyen Siparişler"): "orders",
        ("Satış", "Bekleyen Siparişler Pivot"): "orders",
        ("Satış", "Sipariş Detay (Satış)"): "order_lines",
        ("Satış", "Satış Stok Hareketleri"): "stock_movements",
        ("Satış", "Teklifler"): "sales_quotes",
        ("Satış", "Sipariş Detay (Numune)"): "order_lines",
        ("Satış", "Profil Fiyat Listeleri"): "price_lists",
        ("Satış", "Şikayetler"): "complaints",
        ("Satın Alma", "Talep Sebepleri"): "request_reasons",
        ("Malzeme Yönetimi", "Stok Hareketleri"): "stock_movements",
        ("Malzeme Yönetimi", "Müşteri Ürün Kodları"): "customer_product_codes",
        ("Malzeme Yönetimi", "Tedarikçi Ürün Kodları"): "supplier_product_codes",
        ("Malzeme Yönetimi", "Hizmet Kartları"): "service_items",
        ("Malzeme Yönetimi", "Özellik Setleri"): "property_sets",
        ("Malzeme Yönetimi", "Özellikler"): "property_values",
        ("Malzeme Yönetimi", "Fasoncular"): "subcontractors",
        ("Kalıphane", "Kalıp Talepleri"): "die_tooling_requests",
        ("Kalıphane", "Kalıp İş Emirleri"): "die_tooling_work_orders",
        ("Kalıphane", "Bekleyen İş Emirleri"): "die_tooling_pending",
        ("Kalıphane", "Kalıp Fişleri"): "die_tooling_slips",
        ("Kalıphane", "Kalıp Problemleri"): "die_tooling_problems",
        ("Kalıphane", "Kalıp Verilmeyenler"): "die_unassigned",
        ("Satın Alma", "Satın Alma Stok Hareketleri"): "stock_movements",
        ("Satın Alma", "Tedarikçiler"): "suppliers",
        ("Satın Alma", "Talep Fişleri"): "purchase_requests",
        ("Satın Alma", "Bekleyen Talepler"): "purchase_requests",
        ("Satın Alma", "Talep Detay"): "purchase_requests",
        ("Satın Alma", "Satın Alma Siparişleri"): "purchase_orders",
        ("Satın Alma", "Bekleyen Siparişler"): "purchase_orders",
        ("Satın Alma", "Sipariş Detay"): "purchase_orders",
        ("Satın Alma", "Satın Alma Miktarları"): "purchase_orders",
        ("Satın Alma", "Satın Alma İrsaliyeleri"): "goods_receipts",
        ("Satın Alma", "Satın Alma Faturaları"): "purchase_invoices",
        ("Satın Alma", "Teklif Karşılaştırma"): "purchase_quotes",
        ("Malzeme Yönetimi", "Şubeler"): "branches",
        ("Malzeme Yönetimi", "Ambarlar"): "warehouses",
        ("Malzeme Yönetimi", "Stok Fişleri"): "stock_documents",
        ("Malzeme Yönetimi", "Stok Kartları"): "stock_items",
        ("Malzeme Yönetimi", "Birim Setleri"): "unit_sets",
        ("Malzeme Yönetimi", "Lotlar"): "warehouse_balances",
        ("Malzeme Yönetimi", "Kritik Stoklar"): "warehouse_balances",
        ("Malzeme Yönetimi", "Negatif Stoklar"): "warehouse_balances",
        ("Kalıphane", "Profil Kartları"): "profiles",
        ("Kalıphane", "Profil Katalog"): "profiles",
        ("Kalıphane", "Kalıp Kartları"): "dies",
        ("Kalıphane", "Kalıp Hareketleri"): "die_movements",
        ("Kalıphane", "İmalattaki Kalıplar"): "dies",
        ("Kalıphane", "Hurda Kalıplar"): "dies",
        ("Kalıphane", "Teneferi Yaklaşanlar"): "dies",
        ("Kalıphane", "Tedarik Bekleyen Kalıplar"): "dies",
        ("Üretim", "Üretim Siparişleri"): "orders",
        ("Üretim", "Üretim Siparişleri (Detay)"): "orders",
        ("Üretim", "Üretim Onayı Bekleyen Siparişler"): "orders",
        ("Üretim", "Üretim Planlama"): "planning",
        ("Üretim", "Planlama Takvimi"): "work_orders",
        ("Üretim", "Reçeteler"): "recipes",
        ("Üretim", "Üretim Emirleri"): "production",
        ("Üretim", "İş Emirleri"): "work_orders",
        ("Üretim", "İş Emri Miktarları"): "work_orders",
        ("Üretim", "İstasyon Yükleri"): "work_orders",
        ("Üretim", "Pres Üretim Fişleri"): "production_entries",
        ("Üretim", "Pres Üretim Miktarları"): "production_entries",
        ("Üretim", "Pres-Testere Takip"): "production_entries",
        ("Üretim", "Eloksal Fişleri"): "eloksal_slips",
        ("Üretim", "Eloksal Takip"): "eloksal_slips",
        ("Üretim", "Duruşlar"): "downtime_events",
        ("Üretim", "Üretim Fişleri"): "production_entries",
        ("Üretim", "Stok Miktarları"): "warehouse_balances",
        ("Üretim", "Ambar Yükleri"): "warehouse_balances",
        ("Üretim", "Stok Hareketleri"): "stock_movements",
        ("Malzeme Yönetimi", "Stok Hareketleri"): "stock_movements",
        ("Sevkiyat", "Kasalama Fişleri"): "packages",
        ("Sevkiyat", "Kasalama Fişleri (Detay)"): "packages",
        ("Sevkiyat", "Hazır Kasalar"): "packages",
        ("Sevkiyat", "Çeki Listeleri"): "weighing_lists",
        ("Sevkiyat", "Ambar Yükleri"): "warehouse_balances",
        ("Bakım", "Bakım Emirleri"): "maintenance_orders",
        ("Bakım", "Bakım Bekleyenler"): "maintenance_orders",
        ("Bakım", "Bakım Talimatları"): "maintenance_instructions",
    }

    COLUMNS = {
        "customers": (
            ("code", "MÜŞTERİ KOD"), ("name", "TİCARİ UNVAN"),
            ("short_name", "KISA AD"), ("sector", "SEKTÖR"),
            ("tax_office", "VERGİ DAİRESİ"), ("tax_number", "VERGİ NO"),
            ("contact_name", "İLGİLİ KİŞİ"), ("phone", "TELEFON"),
            ("email", "E-POSTA"), ("district", "İLÇE"), ("city", "ŞEHİR"),
            ("currency", "DÖVİZ"), ("sales_representative", "TEMSİLCİ"),
            ("active", "DURUM"),
        ),
        "stock_items": (("code", "Stok Kod"), ("name", "Stok Adı"), ("stock_group", "Grup"), ("profile_code", "Profil"), ("unit", "Birim"), ("tracks_lot", "Lot Takibi"), ("minimum_quantity", "Minimum"), ("balance", "Toplam Bakiye"), ("active", "Durum")),
        "unit_sets": (("code", "Set Kod"), ("name", "Birim Seti"), ("base_unit", "Ana Birim"), ("line_count", "Satır"), ("active", "Durum")),
        "suppliers": (("code", "Tedarikçi Kod"), ("name", "Ticari Unvan"), ("supplier_type", "Tip"), ("tax_office", "Vergi Dairesi"), ("tax_number", "Vergi No"), ("contact_name", "İlgili"), ("phone", "Telefon"), ("city", "Şehir"), ("currency", "Döviz"), ("active", "Durum")),
        "purchase_requests": (("request_no", "Talep No"), ("request_date", "Tarih"), ("requested_by", "Talep Eden"), ("line_count", "Satır"), ("requested_quantity", "Talep Miktarı"), ("approved_quantity", "Onaylanan"), ("ordered_quantity", "Siparişleşen"), ("approval_status", "Onay"), ("status", "Durum")),
        "purchase_orders": (("purchase_order_no", "Sipariş No"), ("request_no", "Talep No"), ("supplier_name", "Tedarikçi"), ("order_date", "Sipariş"), ("delivery_date", "Teslim"), ("line_count", "Satır"), ("ordered_quantity", "Sipariş Miktarı"), ("received_quantity", "Teslim Alınan"), ("total_amount", "Toplam"), ("currency", "Döviz"), ("status", "Durum")),
        "goods_receipts": (("receipt_no", "Mal Kabul No"), ("dispatch_note_no", "İrsaliye No"), ("receipt_date", "Tarih"), ("purchase_order_no", "Sipariş No"), ("supplier_name", "Tedarikçi"), ("line_count", "Satır"), ("received_quantity", "Kabul Miktarı"), ("created_by", "Kabul Eden")),
        "branches": (("code", "Şube Kod"), ("name", "Şube Adı"), ("city", "Şehir"), ("warehouse_count", "Ambar Sayısı"), ("active", "Durum")),
        "warehouses": (("code", "Ambar Kod"), ("name", "Ambar Adı"), ("branch_name", "Şube"), ("warehouse_type", "Ambar Tipi"), ("negative_stock_policy", "Negatif Stok"), ("allow_mixed_lots", "Karma Lot"), ("active", "Durum")),
        "stock_documents": (("document_no", "Fiş No"), ("document_type", "Fiş Tipi"), ("document_date", "Tarih"), ("source_warehouse_name", "Kaynak Ambar"), ("target_warehouse_name", "Hedef Ambar"), ("reference_no", "Referans"), ("line_count", "Satır"), ("total_quantity", "Toplam Miktar"), ("created_by", "Kullanıcı")),
        "profiles": (("profile_code", "Profil Kod"), ("profile_name", "Profil"), ("organization_name", "İşletme"), ("unit_weight_kg_m", "kg/m"), ("alloy", "Alaşım"), ("temper", "Sertlik"), ("has_route", "Rota"), ("attachment_count", "Belge")),
        "dies": (
            ("profile_code", "Profil Kod"), ("spare_no", "Yedek"), ("status", "Durum"),
            ("profile_name", "Profil Adı"), ("supplier_name", "Tedarikçi"),
            ("tenefer_remaining_m", "Kalan Tenefer m"), ("tenefer_limit_m", "Tenefer Ömrü m"),
            ("tenefer_used_m", "Tenefer Basılan m"), ("tenefer_no", "Tenefer No"),
            ("figure_count", "Figür"), ("used_kg", "Pres Net kg"),
            ("last_movement", "Son Hareket"), ("last_tenefer_company", "Firma"),
            ("external_company", "Dışarıda Firma"), ("location", "Raf/Konum"),
            ("die_code", "Kalıp Kod"), ("attachment_count", "Belge"),
        ),
        "dies_near_tenefer": (
            ("profile_code", "Profil"), ("spare_no", "Yedek"), ("tenefer_no", "Tenefer"),
            ("tenefer_remaining_m", "Kalan m"), ("tenefer_limit_m", "Ömür m"),
            ("tenefer_used_m", "Basılan m"), ("tenefer_usage_pct", "Doluluk %"),
            ("last_movement", "Son Hareket"), ("status", "Durum"),
        ),
        "dies_scrap": (
            ("die_code", "Kalıp Kod"), ("profile_code", "Profil"), ("used_kg", "Basılan kg"),
            ("tenefer_used_m", "Tenefer m"), ("status", "Durum"), ("location", "Son Konum"),
            ("last_movement", "Son Hareket"),
        ),
        "dies_in_production": (
            ("die_code", "Kalıp Kod"), ("profile_code", "Profil"), ("spare_no", "Yedek"),
            ("tenefer_no", "Tenefer"), ("figure_count", "Figür"), ("used_kg", "Basılan kg"),
            ("tenefer_used_m", "Tenefer m"), ("supplier_name", "Tedarikçi"),
            ("status", "Durum"),
        ),
        "orders": (("order_no", "Sipariş No"), ("customer_name", "Müşteri"), ("order_date", "Sipariş"), ("delivery_date", "Teslim"), ("line_count", "Satır"), ("ordered_kg", "Sipariş kg"), ("produced_kg", "Üretilen kg"), ("shipped_kg", "Sevk kg"), ("status", "Durum"), ("production_approval", "Üretim Onayı")),
        "orders_grid": (
            ("progress_pct", "%"),
            ("order_no", "FİŞ NO"),
            ("revision_display", "REV. NO"),
            ("customer_document_no", "BELGE NO"),
            ("msp", "MSP"),
            ("customer_name", "FİRMA"),
            ("order_date", "TARİH"),
            ("delivery_date", "TESLİM TARİHİ"),
            ("delivery_week", "TESLİM HFT."),
            ("delivery_year", "TESLİM YILI"),
            ("ordered_kg", "SİPARİŞ KG"),
            ("shipped_kg", "SEVK KG"),
            ("pending_kg", "BEKLEYEN KG"),
            ("total_amount", "TOPLAM"),
            ("foreign_total", "DÖVİZLİ TOPLAM"),
            ("currency_display", "DÖVİZ"),
            ("usd_total", "USD TOPLAM"),
            ("branch_name", "ŞUBE"),
            ("warehouse_name", "AMBAR"),
            ("created_by", "KULLANICI"),
            ("representative", "TEMSİLCİ"),
            ("order_approval", "ONAY"),
            ("production_approval_display", "ÜRETİM ONAY"),
            ("approval_note", "ONAY AÇIKLAMASI"),
            ("close_status", "KAPANMA DURUM"),
            ("order_status", "SİPARİŞ DURUM"),
        ),
        "order_lines_grid": (
            ("status_display", "DURUM"),
            ("order_approval", "ONAY"),
            ("production_approval_display", "ÜRETİM ONAY"),
            ("fulfillment_status", "KARŞILANMA"),
            ("customer_name", "FİRMA ADI"),
            ("order_no", "FİŞ NO"),
            ("customer_document_no", "BELGE NO"),
            ("msp", "MSP"),
            ("customer_code", "MÜŞTERİ"),
            ("order_date", "SİPARİŞ TARİHİ"),
            ("delivery_date", "SATIR TESLİM TARİHİ"),
            ("line_delivery_week", "SATIR TESLİM HAFTA"),
            ("profile_code", "PROFİL KOD"),
            ("production_length_mm", "BOY (mm)"),
            ("surface", "YÜZEY"),
            ("color", "RENK"),
            ("alloy", "ALAŞIM"),
            ("temper", "SERTLİK"),
            ("ordered_quantity", "SİPARİŞ ADET"),
            ("production_quantity", "ÜRETİM ADET"),
            ("shipped_quantity", "SEVK EDİLEN ADET"),
            ("pending_production_quantity", "ÜRETİM BEKLEYEN ADET"),
            ("field_quantity", "SAHADAKİ ADET"),
            ("ready_shipment_quantity", "SEVK BEKLEYEN ADET"),
            ("ordered_kg", "SİPARİŞ KG"),
            ("production_kg", "ÜRETİM KG"),
            ("pending_production_kg", "ÜRETİM BEKLEYEN KG"),
            ("field_kg", "SAHADAKİ KG"),
            ("shipped_kg", "SEVK EDİLEN KG"),
            ("ready_shipment_kg", "SEVK BEKLEYEN KG"),
            ("progress_pct", "%"),
            ("customer_region", "BÖLGE"),
            ("product_code", "ÜRÜN KOD"),
            ("last_shipment_date", "SON SEVK TARİH"),
            ("warehouses", "AMBARLAR"),
            ("plans", "PLANLAR"),
            ("unit_price", "BİRİM FİYAT"),
            ("line_amount", "TUTAR"),
            ("die_code", "KALIP"),
            ("merged_flag", "BİRLEŞMİŞ"),
            ("order_ref", "SİPARİŞ REF"),
            ("line_no", "SATIR"),
        ),
        "request_reasons": (
            ("code", "KOD"), ("name", "TALEP SEBEBİ"), ("description", "AÇIKLAMA"), ("active", "AKTİF"),
        ),
        "customer_product_codes": (
            ("party_name", "MÜŞTERİ"), ("external_code", "MÜŞTERİ ÜRÜN KOD"),
            ("external_name", "MÜŞTERİ ÜRÜN ADI"), ("stock_code", "STOK KOD"), ("active", "AKTİF"),
        ),
        "supplier_product_codes": (
            ("party_name", "TEDARİKÇİ"), ("external_code", "TEDARİKÇİ ÜRÜN KOD"),
            ("external_name", "TEDARİKÇİ ÜRÜN ADI"), ("stock_code", "STOK KOD"), ("active", "AKTİF"),
        ),
        "service_items": (
            ("code", "HİZMET KOD"), ("name", "HİZMET ADI"), ("unit", "BİRİM"), ("active", "AKTİF"),
        ),
        "property_sets": (
            ("code", "SET KOD"), ("name", "SET ADI"), ("property_kind", "TİP"),
            ("value_count", "DEĞER SAYISI"), ("active", "AKTİF"),
        ),
        "property_values": (
            ("set_code", "SET KOD"), ("set_name", "SET ADI"), ("property_kind", "TİP"),
            ("code", "DEĞER KOD"), ("name", "DEĞER"), ("active", "AKTİF"),
        ),
        "price_lists": (
            ("list_code", "LİSTE KOD"), ("list_name", "LİSTE ADI"), ("customer_name", "MÜŞTERİ"),
            ("currency", "DÖVİZ"), ("line_count", "SATIR"), ("valid_from", "BAŞLANGIÇ"),
            ("valid_until", "BİTİŞ"), ("active", "AKTİF"),
        ),
        "complaints": (
            ("complaint_no", "ŞİKAYET NO"), ("record_date", "TARİH"), ("customer_name", "MÜŞTERİ"),
            ("order_no", "SİPARİŞ"), ("profile_code", "PROFİL"), ("subject", "KONU"),
            ("status", "DURUM"),
        ),
        "subcontractors": (
            ("code", "FASON KOD"), ("name", "FASONCU"), ("supplier_type", "TİP"),
            ("phone", "TELEFON"), ("city", "ŞEHİR"), ("active", "AKTİF"),
        ),
        "die_tooling_requests": (
            ("request_no", "TALEP NO"), ("record_date", "TARİH"), ("profile_code", "PROFİL"),
            ("figure_no", "RESİM NO"), ("supplier_name", "TEDARİKÇİ"), ("status", "DURUM"),
        ),
        "die_tooling_work_orders": (
            ("work_order_no", "İŞ EMRİ NO"), ("record_date", "TARİH"), ("order_type", "TİP"),
            ("die_code", "KALIP"), ("profile_code", "PROFİL"), ("supplier_name", "TEDARİKÇİ"),
            ("planned_end", "PLAN BİTİŞ"), ("status", "DURUM"),
        ),
        "die_tooling_pending": (
            ("work_order_no", "İŞ EMRİ NO"), ("record_date", "TARİH"), ("order_type", "TİP"),
            ("die_code", "KALIP"), ("profile_code", "PROFİL"), ("status", "DURUM"),
        ),
        "die_tooling_slips": (
            ("slip_no", "FİŞ NO"), ("record_date", "TARİH"), ("slip_type", "FİŞ TİPİ"),
            ("die_code", "KALIP"), ("profile_code", "PROFİL"), ("used_kg", "KG"),
            ("location_from", "NEREDEN"), ("location_to", "NEREYE"),
        ),
        "die_tooling_problems": (
            ("problem_no", "PROBLEM NO"), ("record_date", "TARİH"), ("die_code", "KALIP"),
            ("profile_code", "PROFİL"), ("problem_type", "TİP"), ("status", "DURUM"),
        ),
        "die_unassigned": (
            ("order_no", "SİPARİŞ"), ("line_no", "SATIR"), ("customer_name", "MÜŞTERİ"),
            ("profile_code", "PROFİL"), ("ordered_kg", "SİPARİŞ KG"), ("status", "DURUM"),
        ),
        "purchase_requests_grid": (
            ("request_no", "FİŞ NO"), ("request_date", "TARİH"), ("requested_by", "TALEP EDEN"),
            ("description", "AÇIKLAMA"), ("line_count", "SATIR"), ("requested_quantity", "TALEP MİKTARI"),
            ("approved_quantity", "ONAYLANAN"), ("ordered_quantity", "SİPARİŞLEŞEN"),
            ("pending_quantity", "BEKLEYEN"), ("approval_display", "ONAY"), ("status", "DURUM"),
        ),
        "purchase_orders_grid": (
            ("purchase_order_no", "FİŞ NO"), ("request_no", "TALEP NO"), ("supplier_name", "TEDARİKÇİ"),
            ("order_date", "SİPARİŞ TARİHİ"), ("delivery_date", "TESLİM TARİHİ"), ("line_count", "SATIR"),
            ("ordered_quantity", "SİPARİŞ MİKTARI"), ("received_quantity", "TESLİM ALINAN"),
            ("pending_quantity", "BEKLEYEN"), ("total_amount", "TOPLAM"), ("currency_display", "DÖVİZ"),
            ("created_by", "KULLANICI"), ("status", "DURUM"),
        ),
        "goods_receipts_grid": (
            ("receipt_no", "FİŞ NO"), ("dispatch_note_no", "İRSALİYE NO"), ("receipt_date", "TARİH"),
            ("purchase_order_no", "SİPARİŞ NO"), ("supplier_name", "TEDARİKÇİ"), ("line_count", "SATIR"),
            ("received_quantity", "KABUL MİKTARI"), ("created_by", "KULLANICI"),
        ),
        "stock_items_grid": (
            ("code", "STOK KOD"), ("name", "STOK ADI"), ("stock_group", "GRUP"), ("profile_code", "PROFİL"),
            ("unit", "BİRİM"), ("unit_set_name", "BİRİM SETİ"), ("tracks_lot_display", "LOT TAKİBİ"),
            ("minimum_quantity", "MİNİMUM"), ("balance", "BAKİYE"), ("active_display", "DURUM"),
        ),
        "stock_documents_grid": (
            ("document_no", "FİŞ NO"), ("document_type", "FİŞ TİPİ"), ("document_date", "TARİH"),
            ("source_warehouse_name", "KAYNAK AMBAR"), ("target_warehouse_name", "HEDEF AMBAR"),
            ("reference_no", "REFERANS"), ("line_count", "SATIR"), ("total_quantity", "TOPLAM MİKTAR"),
            ("created_by", "KULLANICI"),
        ),
        "stock_movements_grid": (
            ("movement_at", "TARİH"), ("warehouse_name", "AMBAR"), ("stock_code", "STOK KOD"),
            ("stock_name", "STOK ADI"), ("lot_no", "LOT / ŞARJ"), ("movement_type", "HAREKET"),
            ("direction", "YÖN"), ("quantity", "MİKTAR"), ("order_no", "SİPARİŞ"),
            ("work_order_no", "İŞ EMRİ"), ("document_no", "BELGE"), ("created_by", "KULLANICI"),
        ),
        "warehouse_balances_grid": (
            ("selected", "SEÇİM"), ("image_path", "RESİM"),
            ("lot_no", "LOT NO"), ("stock_code", "KOD"), ("stock_name", "AD"),
            ("stock_group", "STOK GRUP"), ("sub_group", "ALT GRUP"),
            ("balance", "GERÇEK MİKTAR"), ("unit", "ANA BİRİM"),
            ("real_weight_kg_m", "REEL GRJ."), ("profile_code", "PROFİL KODU"),
            ("production_length_mm", "BOY (mm)"), ("stock_length_mm", "SİPARİŞ BOY(mm)"),
            ("surface", "YÜZEY"), ("color", "RENK"), ("temper", "SERTLİK"),
            ("alloy", "ALAŞIM"), ("quantity", "ADET"), ("metre", "METRE"),
            ("order_ref", "SİPARİŞ REF"), ("customer_name", "MÜŞTERİ"),
            ("order_stock", "SİPARİŞ STOK"),
            ("days_since_last_movement", "SON HAREKET GEÇEN GÜN"),
            ("warehouse_name", "AMBAR"),
        ),
        "warehouses_grid": (
            ("code", "AMBAR KOD"), ("name", "AMBAR ADI"), ("branch_name", "ŞUBE"),
            ("warehouse_type", "AMBAR TİPİ"), ("negative_stock_policy", "NEGATİF STOK"),
            ("allow_mixed_lots", "KARMA LOT"), ("active", "DURUM"),
        ),
        "branches_grid": (
            ("code", "ŞUBE KOD"), ("name", "ŞUBE ADI"), ("city", "ŞEHİR"),
            ("warehouse_count", "AMBAR SAYISI"), ("active", "DURUM"),
        ),
        "suppliers_grid": (
            ("code", "TEDARİKÇİ KOD"), ("name", "TİCARİ UNVAN"), ("supplier_type", "TİP"),
            ("contact_name", "İLGİLİ"), ("phone", "TELEFON"), ("city", "ŞEHİR"),
            ("currency", "DÖVİZ"), ("active", "DURUM"),
        ),
        "unit_sets_grid": (
            ("code", "SET KOD"), ("name", "SET ADI"), ("base_unit", "ANA BİRİM"),
            ("line_count", "SATIR"), ("active", "DURUM"),
        ),
        "planning": (("order_no", "Sipariş No"), ("line_no", "Satır"), ("customer_name", "Müşteri"), ("profile_code", "Profil"), ("die_code", "Kalıp"), ("delivery_date", "Teslim"), ("ordered_quantity", "Sipariş Adet"), ("ordered_kg", "Sipariş kg"), ("planned_quantity", "Plan Adet"), ("planned_kg", "Plan kg"), ("remaining_quantity", "Kalan Adet"), ("remaining_kg", "Kalan kg"), ("production_order_count", "Parti"), ("status", "Durum")),
        "recipes": (("recipe_code", "Reçete Kodu"), ("recipe_name", "Reçete"), ("profile_code", "Profil"), ("route_code", "Rota"), ("raw_material_code", "Hammadde"), ("production_length_mm", "Üretim Boyu"), ("saw_allowance_mm", "Testere Payı"), ("hanger_allowance_mm", "Askı Payı"), ("line_count", "Operasyon"), ("active", "Durum")),
        "production": (("production_order_no", "Üretim Emri"), ("order_no", "Sipariş"), ("customer_name", "Müşteri"), ("profile_code", "Profil"), ("route_code", "Rota"), ("planned_kg", "Plan kg"), ("produced_kg", "Üretilen kg"), ("completed_work_orders", "Biten İş"), ("work_order_count", "Toplam İş"), ("status", "Durum")),
        "work_orders": (("priority", "Öncelik"), ("work_order_no", "İş Emri"), ("production_order_no", "Üretim Emri"), ("order_no", "Sipariş"), ("customer_name", "Müşteri"), ("profile_code", "Profil"), ("operation", "Operasyon"), ("station", "İstasyon"), ("planned_kg", "Plan kg"), ("produced_kg", "Net kg"), ("scrap_kg", "Fire kg"), ("status", "Durum")),
        "work_orders_station": (
            ("selected", "SEÇİM"), ("priority", "ÖNCELİK"),
            ("production_note", "ÜRETİM AÇIKLAMASI"), ("sequence_no", "SIRA"),
            ("profile_name", "PROFİL AD"), ("production_pct", "ÜRETİM %"),
            ("work_order_no", "İŞ EMRİ NO"), ("order_line_ref", "SİPARİŞ REF"),
            ("customer_name", "MÜŞTERİ"), ("profile_code", "PROFİL KOD"),
            ("image_path", "RESİM"), ("production_length_mm", "ÜRETİM BOYU"),
            ("surface", "YÜZEY"), ("ordered_quantity", "SİPARİŞ ADET"),
            ("remaining_kg", "KALAN KG"), ("color", "RENK"),
            ("raw_material_stock", "HAMMADDE"), ("actual_start", "BAŞLANGIÇ"),
            ("actual_end", "BİTİŞ"), ("stock_length_mm", "SİPARİŞ BOYU"),
            ("order_surface", "SİPARİŞ YÜZEY"), ("order_color", "SİPARİŞ RENK"),
            ("planned_quantity", "PLAN ADET"), ("produced_quantity", "ÜRETİLEN ADET"),
            ("warehouse_quantity", "AMBAR ADET"), ("remaining_quantity", "KALAN ADET"),
            ("remaining_metre", "KALAN METRE"), ("ordered_kg", "SİPARİŞ KG"),
            ("planned_kg", "PLAN KG"), ("produced_kg", "ÜRETİLEN KG"),
            ("warehouse_kg", "AMBAR KG"), ("previous_station", "ÖNCEKİ İSTASYON"),
            ("next_station", "SONRAKİ İSTASYON"), ("operation", "OPERASYON"),
            ("station", "İSTASYON"), ("status", "DURUM"),
        ),
        "warehouse_balances": (("warehouse_name", "Ambar"), ("warehouse_type", "Ambar Tipi"), ("stock_code", "Stok Kod"), ("stock_name", "Stok Adı"), ("profile_code", "Profil"), ("lot_no", "Lot / Şarj"), ("balance", "Bakiye"), ("unit", "Birim"), ("last_movement_at", "Son Hareket"), ("movement_count", "Hareket")),
        "stock_movements": (("movement_at", "Tarih"), ("warehouse_name", "Ambar"), ("stock_code", "Stok Kod"), ("stock_name", "Stok Adı"), ("lot_no", "Lot / Şarj"), ("movement_type", "Hareket"), ("direction", "Yön"), ("quantity", "Miktar"), ("order_no", "Sipariş"), ("work_order_no", "İş Emri"), ("document_no", "Belge"), ("created_by", "Kullanıcı")),
        "packages": (("package_no", "Paket No"), ("customer_name", "Müşteri"), ("order_nos", "Sipariş"), ("profile_codes", "Profil"), ("net_kg", "Net kg"), ("gross_kg", "Brüt kg"), ("warehouse_name", "Ambar"), ("status", "Durum")),
        "weighing_lists": (("weighing_list_no", "Çeki Listesi"), ("created_at", "Tarih"), ("customer_name", "Müşteri"), ("package_count", "Paket"), ("net_kg", "Net kg"), ("gross_kg", "Brüt kg"), ("created_by", "Hazırlayan"), ("status", "Durum")),
        "shipments": (("dispatch_note_no", "İrsaliye No"), ("shipment_no", "Sevkiyat No"), ("shipment_date", "Tarih"), ("customer_name", "Müşteri"), ("weighing_list_no", "Çeki Listesi"), ("vehicle_plate", "Plaka"), ("package_count", "Paket"), ("net_kg", "Net kg"), ("gross_kg", "Brüt kg"), ("status", "Durum")),
        "invoices": (("invoice_no", "Fatura No"), ("invoice_date", "Tarih"), ("customer_name", "Müşteri"), ("dispatch_note_no", "İrsaliye"), ("pricing_mode", "Fiyatlandırma"), ("lme_usd_ton", "LME"), ("premium_usd_ton", "Prim"), ("total_amount", "Toplam"), ("currency", "Döviz"), ("status", "Durum")),
        "die_movements": (
            ("record_date", "TARİH"), ("die_code", "KALIP KOD"), ("spare_no", "YEDEK"),
            ("profile_code", "PROFİL"), ("movement_type", "HAREKET"), ("company", "FİRMA"),
            ("location_from", "NEREDEN"), ("location_to", "NEREYE"),
            ("quantity", "MİKTAR"), ("unit", "BİRİM"), ("note", "NOT"),
        ),
        "die_movements_grid": (
            ("record_date", "TARİH"), ("die_code", "KALIP KOD"), ("spare_no", "YEDEK NO"),
            ("profile_code", "PROFİL KOD"), ("movement_type", "HAREKET TİPİ"),
            ("location_from", "KAYNAK KONUM"), ("location_to", "HEDEF KONUM"),
            ("company", "FİRMA"), ("quantity", "MİKTAR"), ("created_by", "KULLANICI"),
        ),
        "eloksal_slips": (
            ("slip_no", "FİŞ NO"), ("hanger_no", "ASKI NO"), ("record_date", "ASKILAMA TARİH"),
            ("color_group", "RENK GRUP"), ("work_order_no", "İŞ EMRİ NO"), ("order_ref", "SİPARİŞ REF"),
            ("customer_name", "MÜŞTERİ"), ("profile_code", "PROFİL KOD"), ("order_color", "SİPARİŞ RENK"),
            ("eloksal_status", "ELOKSAL BİTTİ"), ("stripping_status", "SÖKME BİTTİ"),
            ("hanging_quantity", "ASKILAMA ADET"), ("hanging_kg", "ASKILAMA KG"),
            ("stripping_quantity", "SÖKME ADET"), ("stripping_kg", "SÖKME KG"),
            ("scrap_quantity", "HURDA ADET"), ("scrap_kg", "HURDA KG"),
        ),
        "downtime_events": (
            ("reason", "DURUŞ SEBEBİ"), ("sub_reason", "DURUŞ ALT SEBEBİ"),
            ("record_date", "BAŞLANGIÇ TARİHİ"), ("ended_at", "BİTİŞ TARİHİ"),
            ("duration_min", "SÜRE (dk)"), ("operation", "OPERASYON"), ("station", "İSTASYON"),
            ("station_section", "İSTASYON BÖLÜMÜ"), ("status", "DURUM"), ("note", "AÇIKLAMA"),
        ),
        "production_entries": (
            ("slip_no", "FİŞ NO"), ("production_type", "ÜRETİM TİPİ"),
            ("press_status", "PRES DURUM"), ("saw_status", "TESTERE DURUM"),
            ("station", "İSTASYON"), ("operator_username", "OPERATÖR"),
            ("shift", "VARDİYA"), ("order_ref", "SİPARİŞ REF"),
            ("work_order_no", "İŞ EMRİ NO"), ("customer_name", "MÜŞTERİ"),
            ("profile_code", "PROFİL KOD"), ("spare_no", "YEDEK NO"),
            ("figure_count", "FİGÜR"), ("real_weight_kg_m", "REEL GRAMAJ"),
            ("theoretical_weight_kg_m", "TEORİK GRAMAJ"),
            ("started_at", "BAŞLANGIÇ"), ("ended_at", "BİTİŞ"),
            ("duration_min", "ÜRETİM SÜRESİ"), ("preparation_min", "KALIP HAZIRLIK"),
            ("raw_material_stock", "HAMMADDE STOK"), ("lot_no", "LOT NO"),
            ("gross_kg", "BRÜT KG"), ("net_kg", "NET KG"),
            ("scrap_kg", "FİRE KG"), ("fire_pct", "FİRE %"),
            ("result_length_mm", "ÇIKAN BOYLAR"), ("kg_hour", "KG/SAAT"),
            ("quantity", "NET ADET"), ("metre", "NET M"),
            ("figure_gross_metre", "FİGÜR BRÜT M"), ("tenefer_no", "TENEFER NO"),
            ("die_problem_note", "KALIP PR. AÇIKLAMA"), ("billet_count", "BİLLET ADET"),
            ("average_billet_length_mm", "ORT. BİLLET BOY"),
            ("max_billet_length_mm", "MAX BİLLET BOY"),
            ("min_billet_length_mm", "MİN BİLLET BOY"),
            ("test_result", "TEST BAŞARILI"), ("surface", "SİPARİŞ YÜZEY"),
            ("color", "SİPARİŞ RENK"), ("customer_region", "BÖLGE"),
            ("note", "AÇIKLAMA"), ("die_supplier", "KALIP TEDARİKÇİ"),
        ),
        "maintenance_orders": (
            ("order_no", "FİŞ NO"), ("order_type", "TİP"), ("name", "AD"),
            ("description", "AÇIKLAMA"), ("status", "DURUM"), ("operation", "OPERASYON"),
            ("station", "İSTASYON"), ("station_section", "İSTASYON BÖLÜM"),
            ("record_date", "TARİH"), ("planned_start", "PLANLANAN BAŞ."),
            ("planned_end", "PLANLANAN BİT."), ("actual_start", "GERÇEKLEŞEN BAŞ."),
            ("actual_end", "GERÇEKLEŞEN BİT."), ("compliance_pct", "BAKIM UYUM ORANI"),
        ),
        "maintenance_instructions": (
            ("instruction_no", "TALİMAT NO"), ("instruction_type", "TİP"), ("name", "AD"),
            ("description", "AÇIKLAMA"), ("operation", "OPERASYON"), ("station", "İSTASYON"),
            ("period_days", "PERİYOT (gün)"), ("active", "AKTİF"),
        ),
        "purchase_invoices": (
            ("invoice_no", "FİŞ NO"), ("record_date", "TARİH"), ("supplier_name", "TEDARİKÇİ"),
            ("purchase_order_no", "SİPARİŞ NO"), ("goods_receipt_no", "MAL KABUL NO"),
            ("subtotal", "ARA TOPLAM"), ("tax_amount", "KDV"), ("total_amount", "TOPLAM"),
            ("currency", "DÖVİZ"), ("status", "DURUM"),
        ),
        "purchase_quotes": (
            ("request_no", "TALEP NO"), ("supplier_name", "TEDARİKÇİ"), ("quote_no", "TEKLİF NO"),
            ("record_date", "TARİH"), ("delivery_date", "TESLİM"), ("unit_price", "BİRİM FİYAT"),
            ("quantity", "MİKTAR"), ("total_amount", "TOPLAM"), ("currency", "DÖVİZ"),
            ("selected", "SEÇİLDİ"),
        ),
        "sales_quotes": (
            ("quote_no", "TEKLİF NO"), ("record_date", "TARİH"), ("customer_name", "MÜŞTERİ"),
            ("valid_until", "GEÇERLİLİK"), ("total_amount", "TOPLAM"), ("currency", "DÖVİZ"),
            ("line_count", "SATIR"), ("status", "DURUM"),
        ),
    }

    _MENU_TAIL: list[dict[str, Any]] = [
        {"separator": True},
        {"label": "Kayıt Bilgisi", "action": "show_audit_history"},
        {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
        {"label": "Listeyi Excel'e Aktar", "action": "export_current_table", "needs_selection": False},
        {"label": "Listeyi PDF'e Aktar", "action": "export_current_table_pdf", "needs_selection": False},
        {"label": "Yazdır / Önizle", "action": "preview_current_table", "needs_selection": False},
        {"label": "Sütun Dizilimleri", "action": "save_column_layout"},
        {"label": "Sütunları Sıfırla", "action": "reset_columns", "needs_selection": False},
    ]

    # Her sekmenin sağ tık menüsü işleve göre farklıdır.
    CONTEXT_MENUS: dict[str, list[dict[str, Any]]] = {
        "order_lines": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Siparişe Git", "action": "open_order_line_order", "perm": "edit"},
            {"label": "Profil Kartı", "action": "open_order_line_profile"},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "orders": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_sales_order", "perm": "edit"},
            {"label": "Sil", "action": "delete_sales_order", "perm": "delete"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Sipariş Onay", "action": "confirm_sales_order", "perm": "approve"},
            {"label": "Üretim Onay", "action": "approve_order_for_production", "perm": "approve"},
            {"label": "Sipariş Durumu", "action": "show_order_status"},
            {"label": "Yazdır", "action": "print_sales_order"},
            {"label": "Sipariş Kapatma", "action": "close_sales_order", "perm": "approve"},
            {"separator": True},
            {"label": "Sipariş Ekstre Raporu", "action": "print_order_statement"},
            {"label": "Müşteri Ekstre Raporu", "action": "open_customer_orders"},
            {"label": "Entegrasyon", "action": "open_integration_hub"},
            {"label": "Revizyonlar", "action": "show_audit_history"},
            {"label": "Bağlı Çeki Listeleri", "action": "open_linked_weighing_lists"},
            {"separator": True},
            {"label": "Kopyasını Oluştur", "action": "copy_sales_order", "perm": "create"},
            {"label": "Karşı Sipariş Oluştur", "action": "create_counter_purchase_request", "perm": "create"},
            {"label": "Alt Malzemelerden Sipariş Oluştur", "action": "create_recipe_material_request", "perm": "create"},
            {"label": "Vade Farkına Göre Güncelle", "action": "apply_maturity_pricing", "perm": "edit"},
            {"label": "Fiyat Listesine Göre Güncelle", "action": "apply_price_list_to_order", "perm": "edit"},
            {"separator": True},
            {"label": "KK Hareketleri", "action": "navigate_quality_movements"},
            {"label": "Şikayetler", "action": "navigate_complaints"},
            {"label": "Malzeme Bul", "action": "navigate_stock_search"},
            {"label": "Dokümanlar", "action": "open_order_documents"},
            {"label": "Üretim Revizyon Bilgisi", "action": "show_production_revision_info"},
            {"label": "Malzeme Yönetim Fişi Oluştur", "action": "navigate_stock_documents"},
            {"label": "İrsaliye Oluştur", "action": "navigate_shipments_for_order"},
        ],
        "profiles": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_profile", "perm": "edit"},
            {"label": "Sil / Pasife Al", "action": "deactivate_profile", "perm": "delete"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Profil Kartı", "action": "show_record_details"},
            {"label": "Sipariş Hareketleri", "action": "open_profile_orders"},
            {"label": "Stok Hareketleri", "action": "open_profile_stock_movements"},
            {"label": "Stok Kartı", "action": "open_profile_stock_card"},
            {"label": "Kalıp Kartları", "action": "open_profile_dies"},
            {"label": "Üretim Rotası (Üretim)", "action": "edit_profile_route", "perm": "edit"},
            {"separator": True},
            {"label": "Belge Ekle", "action": "add_selected_attachment", "perm": "create"},
            {"label": "Dokümanlar", "action": "run_secondary"},
        ],
        "dies": [
            {"label": "Kalıp Kartı", "action": "open_die_card"},
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_die", "perm": "edit"},
            {"label": "Sil", "action": "delete_die", "perm": "delete"},
            {"label": "Hurdaya Ayır", "action": "scrap_die", "perm": "delete"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Kalıp Hareketi Gir", "action": "add_die_movement", "perm": "create"},
            {"label": "Kalıp Hareketleri", "action": "open_die_card"},
            {"label": "Üretim Geçmişi", "action": "open_die_production_history"},
            {"label": "Tenefer Bilgisi", "action": "open_die_card"},
            {"separator": True},
            {"label": "Belge Ekle", "action": "add_selected_attachment", "perm": "create"},
            {"label": "Dokümanlar", "action": "run_secondary"},
        ],
        "planning": [
            {"label": "Üretim Partisi Planla", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Sipariş Satırı Detayı", "action": "show_record_details"},
            {"label": "Siparişe Git", "action": "open_planning_order"},
            {"label": "Üretim Emirleri", "action": "open_planning_production_orders"},
        ],
        "production": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Sipariş Durumu", "action": "open_production_order_progress"},
            {"label": "İş Emirleri", "action": "open_production_work_orders"},
            {"label": "Stok Hareketleri", "action": "open_production_stock_movements"},
        ],
        "work_orders": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Operatör Üretim Fişi", "action": "run_primary", "perm": "create"},
            {"label": "Öncelik Değiştir", "action": "change_priority", "perm": "edit"},
            {"label": "Üretim Geçmişi", "action": "show_record_details"},
            {"label": "Stok Hareketleri", "action": "open_work_order_stock_movements"},
            {"label": "Sipariş Durumu", "action": "open_work_order_order"},
            {"label": "İş Emri Yazdır", "action": "print_work_order"},
        ],
        "packages": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Çeki Listesi Oluştur", "action": "create_weighing_list_from_packages", "perm": "create"},
            {"label": "İrsaliye Oluştur", "action": "create_shipment_from_packages", "perm": "create"},
            {"label": "Stok Hareketleri", "action": "open_package_stock_movements"},
            {"label": "Etiket Yazdır", "action": "print_package_label"},
        ],
        "weighing_lists": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "İrsaliye Oluştur", "action": "create_shipment_from_list", "perm": "create"},
            {"label": "Yazdır", "action": "print_weighing_list"},
        ],
        "shipments": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Faturala", "action": "create_invoice", "perm": "create"},
            {"label": "Yazdır", "action": "print_shipment"},
            {"label": "Bağlı Çeki Listesi", "action": "open_shipment_weighing_list"},
        ],
        "customers": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_customer", "perm": "edit"},
            {"label": "Sil", "action": "delete_customer", "perm": "delete"},
            {"label": "Pasife Al / Aktifleştir", "action": "toggle_customer_active", "perm": "delete"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Müşteri Kartı", "action": "show_record_details"},
            {"label": "Sipariş Hareketleri", "action": "open_customer_orders"},
            {"label": "Müşteri Ekstre Raporu", "action": "open_customer_orders"},
        ],
        "stock_items": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_stock_item", "perm": "edit"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Stok Hareketleri", "action": "open_stock_item_movements"},
            {"label": "Ambar Bakiyeleri", "action": "open_stock_item_balances"},
            {"label": "Malzeme Bul", "action": "show_record_details"},
        ],
        "purchase_requests": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Talebi Onayla", "action": "run_secondary", "perm": "approve"},
            {"label": "Siparişe Çevir", "action": "convert_purchase_request_to_order", "perm": "create"},
        ],
        "purchase_orders": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Mal Kabul", "action": "open_goods_receipt_for_order", "perm": "create"},
            {"label": "Satın Alma Stok Hareketleri", "action": "navigate_purchase_stock_movements"},
        ],
        "recipes": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_recipe", "perm": "edit"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"separator": True},
            {"label": "Reçete Detayı", "action": "show_record_details"},
            {"label": "Profil Kartı", "action": "open_recipe_profile"},
        ],
        "stock_movements": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "warehouse_balances": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
            {"label": "Stok Hareketleri", "action": "open_balance_stock_movements"},
        ],
        "stock_documents": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "branches": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "warehouses": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_warehouse", "perm": "edit"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "unit_sets": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "suppliers": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_supplier", "perm": "edit"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "goods_receipts": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
            {"label": "Satın Alma Faturası Oluştur", "action": "create_invoice_from_receipt", "perm": "create"},
        ],
        "die_movements": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
            {"label": "Kalıp Kartına Git", "action": "open_die_from_movement"},
        ],
        "eloksal_slips": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Eloksal Tamamla", "action": "complete_eloksal_hanging", "perm": "edit"},
            {"label": "Sökme Tamamla", "action": "complete_eloksal_stripping", "perm": "edit"},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "downtime_events": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Duruşu Kapat", "action": "close_selected_downtime", "perm": "edit"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "production_entries": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
            {"label": "Pres Üretim Fişi Yazdır", "action": "print_press_slip"},
            {"label": "İş Emrine Git", "action": "open_entry_work_order"},
        ],
        "maintenance_orders": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "maintenance_instructions": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Değiştir", "action": "edit_maintenance_instruction", "perm": "edit"},
            {"separator": True},
            {"label": "Bakım Emri Aç", "action": "open_order_from_instruction", "perm": "create"},
            {"label": "Aktif / Pasif", "action": "toggle_maintenance_instruction", "perm": "edit"},
            {"separator": True},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "purchase_invoices": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "purchase_quotes": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Teklifi Seç", "action": "select_purchase_quote_row", "perm": "approve"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "sales_quotes": [
            {"label": "Ekle", "action": "run_primary", "perm": "create", "needs_selection": False},
            {"label": "Siparişe Dönüştür", "action": "convert_sales_quote", "perm": "create"},
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
        "invoices": [
            {"label": "Yenile", "action": "refresh_data", "needs_selection": False},
            {"label": "Görüntüle", "action": "show_record_details"},
        ],
    }

    def __init__(self, *, username: str, service: LocalWorkflowService | None = None) -> None:
        super().__init__()
        self.username = username or "sistem"
        self.service = service or LocalWorkflowService()
        self.department = "Satış"
        self.module = "Satış Siparişleri"
        self.view = "orders"
        self.records: list[dict[str, Any]] = []
        self.can_create = True
        self.can_edit = True
        self.can_delete = True
        self.can_approve = True
        self.build_ui()
        self.apply_style()
        self.set_context(self.department, self.module)

    @classmethod
    def handles_context(cls, department: str, module: str) -> bool:
        return (department, module) in cls.CONTEXT_VIEW

    def set_access(
        self, *, can_create: bool, can_approve: bool,
        can_edit: bool = True, can_delete: bool = True,
    ) -> None:
        self.can_create = bool(can_create)
        self.can_approve = bool(can_approve)
        self.can_edit = bool(can_edit)
        self.can_delete = bool(can_delete)
        self.apply_context()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        # Tam ekranda grid'e yer: ince chrome, az boşluk
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(3)

        # Tek satır başlık (eski 3 satırlık header + tab birleşik)
        self.rigel_tab_bar = QFrame()
        self.rigel_tab_bar.setObjectName("rigelTabBar")
        tab_layout = QHBoxLayout(self.rigel_tab_bar)
        tab_layout.setContentsMargins(8, 2, 8, 2)
        tab_layout.setSpacing(8)
        self.department_label = QLabel("SATIŞ")
        self.department_label.setObjectName("workflowDepartment")
        self.module_label = QLabel("Satış Siparişleri")
        self.module_label.setObjectName("workflowModule")
        self.rigel_tab_title = QLabel("SATIŞ SİPARİŞLERİ")
        self.rigel_tab_title.setObjectName("rigelTabTitle")
        self.description = QLabel("Siparişten sevkiyata bağlı yerel operasyon verisi")
        self.description.setObjectName("workflowDescription")
        self.description.setVisible(False)
        tab_layout.addWidget(self.department_label)
        tab_layout.addWidget(QLabel("·"))
        tab_layout.addWidget(self.module_label)
        tab_layout.addStretch(1)
        tab_layout.addWidget(self.rigel_tab_title)
        root.addWidget(self.rigel_tab_bar)

        # Grup çubuğu kapalı — dikey yer kaplamasın
        self.rigel_group_bar = QLabel(
            "Gruplamak için bir sütun başlığını buraya sürükleyin"
        )
        self.rigel_group_bar.setObjectName("rigelGroupBar")
        self.rigel_group_bar.setVisible(False)
        root.addWidget(self.rigel_group_bar)

        # KPI: ince yatay şerit
        kpis = QHBoxLayout()
        kpis.setContentsMargins(0, 0, 0, 0)
        kpis.setSpacing(4)
        self.kpi_values: list[QLabel] = []
        for title in ("KAYIT", "AÇIK / HAZIR", "TOPLAM KG", "VERİ"):
            card = QFrame()
            card.setObjectName("workflowKpi")
            layout = QHBoxLayout(card)
            layout.setContentsMargins(8, 2, 8, 2)
            layout.setSpacing(6)
            label = QLabel(title)
            label.setObjectName("workflowKpiTitle")
            value = QLabel("0")
            value.setObjectName("workflowKpiValue")
            layout.addWidget(label)
            layout.addWidget(value)
            layout.addStretch(1)
            kpis.addWidget(card, 1)
            self.kpi_values.append(value)
        root.addLayout(kpis)

        controls = QFrame()
        controls.setObjectName("workflowControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(6, 3, 6, 3)
        controls_layout.setSpacing(4)
        self.primary = QPushButton("YENİ")
        self.primary.setObjectName("workflowPrimary")
        self.secondary = QPushButton("İŞLEM")
        self.secondary.setObjectName("workflowSecondary")
        self.danger = QPushButton("ÇIKART")
        self.danger.setObjectName("workflowDanger")
        self.show_inactive = QCheckBox("Pasif")
        self.refresh = QPushButton("YENİLE")
        self.export_excel = QPushButton("EXCEL")
        self.export_pdf = QPushButton("PDF")
        self.print_preview = QPushButton("YAZDIR")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara…")
        self.clear_column_filters = QPushButton("FİLTRE TEMİZLE")
        self.clear_column_filters.setToolTip(
            "Sütun başlıklarının altındaki çoklu seçim filtrelerini temizler"
        )
        controls_layout.addWidget(self.primary)
        controls_layout.addWidget(self.secondary)
        controls_layout.addWidget(self.danger)
        controls_layout.addWidget(self.refresh)
        controls_layout.addWidget(self.export_excel)
        controls_layout.addWidget(self.export_pdf)
        controls_layout.addWidget(self.print_preview)
        controls_layout.addWidget(self.show_inactive)
        controls_layout.addWidget(self.clear_column_filters)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.search, 1)
        root.addWidget(controls)

        # Tarih / ambar — grid üstünde ince şerit (dikey yer tasarrufu, kaydırma yok)
        self.station_filter_bar = QFrame()
        self.station_filter_bar.setObjectName("workflowFilters")
        station_filter_layout = QHBoxLayout(self.station_filter_bar)
        station_filter_layout.setContentsMargins(6, 1, 6, 1)
        station_filter_layout.setSpacing(4)
        station_filter_layout.addWidget(QLabel("TARİH"))
        self.date_from = QDateEdit()
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        today = QDate.currentDate()
        self.date_from.setDate(QDate(today.year(), today.month(), 1))
        self.date_to = QDateEdit()
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(today)
        station_filter_layout.addWidget(self.date_from)
        station_filter_layout.addWidget(QLabel("—"))
        station_filter_layout.addWidget(self.date_to)
        station_filter_layout.addSpacing(8)
        station_filter_layout.addWidget(QLabel("AMBAR"))
        self.warehouse_filter = QComboBox()
        self.warehouse_filter.addItem("TÜM AMBARLAR", "")
        for warehouse in self.service.list_warehouses():
            self.warehouse_filter.addItem(
                f"{warehouse['name']}  [{warehouse['code']}]", warehouse["code"]
            )
        self.warehouse_filter.setMinimumWidth(180)
        station_filter_layout.addWidget(self.warehouse_filter)
        station_filter_layout.addStretch(1)
        clear_filters = QPushButton("BU AY")
        clear_filters.clicked.connect(self.reset_station_filters)
        station_filter_layout.addWidget(clear_filters)
        root.addWidget(self.station_filter_bar)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.column_filter_bar = ColumnFilterBar()
        self.column_filter_bar.set_value_formatter(self.format_value)
        self.column_filter_bar.attach_table(self.table)
        grid_host = QWidget()
        grid_layout = QVBoxLayout(grid_host)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)
        grid_layout.addWidget(self.column_filter_bar)
        grid_layout.addWidget(self.table, 1)
        self.content_split = QSplitter(Qt.Horizontal)
        self.content_split.addWidget(grid_host)
        self.side_panel = WorkflowSidePanel(self)
        self.side_panel.setVisible(False)
        self.content_split.addWidget(self.side_panel)
        self.content_split.setStretchFactor(0, 1)
        self.content_split.setStretchFactor(1, 0)
        self.content_split.setSizes([1000, 0])
        root.addWidget(self.content_split, 1)

        self.rigel_footer = QLabel("0 kayıt")
        self.rigel_footer.setObjectName("rigelFooter")
        self.rigel_footer.setContentsMargins(8, 1, 8, 1)
        root.addWidget(self.rigel_footer)

        self.status = QLabel("")
        self.status.setObjectName("workflowStatus")
        self.status.setVisible(False)
        root.addWidget(self.status)

        self.primary.clicked.connect(self.run_primary)
        self.secondary.clicked.connect(self.run_secondary)
        self.danger.clicked.connect(self.run_danger)
        self.refresh.clicked.connect(self.refresh_data)
        self.export_excel.clicked.connect(self.export_current_table)
        self.export_pdf.clicked.connect(self.export_current_table_pdf)
        self.print_preview.clicked.connect(self.preview_current_table)
        self.search.textChanged.connect(self.refresh_data)
        self.clear_column_filters.clicked.connect(self.column_filter_bar.clear_filters)
        self.column_filter_bar.filtersChanged.connect(self.refresh_data)
        self.show_inactive.toggled.connect(self.refresh_data)
        self.date_from.dateChanged.connect(self.refresh_data)
        self.date_to.dateChanged.connect(self.refresh_data)
        self.warehouse_filter.currentIndexChanged.connect(self.refresh_data)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.itemSelectionChanged.connect(self.update_side_panel)
        self.table.itemDoubleClicked.connect(
            lambda _item: (
                self.edit_customer() if self.view == "customers" and self.can_edit
                else self.edit_stock_item() if self.view == "stock_items" and self.can_edit
                else self.edit_warehouse() if self.view == "warehouses" and self.can_edit
                else self.open_die_card() if self.view == "dies"
                else self.show_record_details()
            )
        )

    def set_context(self, department: str, module: str) -> None:
        if not self.handles_context(department, module):
            raise KeyError(f"Bağlı iş akışı ekranı yok: {department} / {module}")
        self.department = department
        self.module = module
        self.view = self.CONTEXT_VIEW[(department, module)]
        self.apply_context()

    def apply_context(self) -> None:
        self.department_label.setText(self.department.upper())
        self.module_label.setText(self.module)
        self.rigel_tab_title.setText(self.module.upper())
        descriptions = {
            "orders": "Satış siparişi onaylandığında profil rotasına göre üretim ve iş emirleri otomatik açılır.",
            "planning": "Sipariş satırlarını kalan miktara göre bir veya daha fazla üretim partisine bölün.",
            "recipes": "Profil rotasındaki her operasyonun stok, istasyon ve pay/payda miktar ilişkileri.",
            "production": "Siparişten otomatik oluşan üretim emirleri ve tamamlanan operasyonlar.",
            "work_orders": "Yalnız sırası gelen iş emrine üretim girilir; sonraki istasyon otomatik açılır.",
            "warehouse_balances": "Hareket defterinden hesaplanan ambar, stok ve lot bazlı canlı bakiye.",
            "stock_movements": "Üretim, ara ambar, çeki listesi ve sevkiyatın değiştirilemez stok hareketleri.",
            "packages": "Üretimi biten profiller kasalanır ve önce Sevk Ön ambarında bekler.",
            "weighing_lists": "Sevk Ön kasaları çeki listesine bağlanınca Sevk Hazır ambarına aktarılır.",
            "shipments": "Hazır paketler sevk edilince sipariş miktarı ve mamul stoku otomatik güncellenir.",
            "invoices": "Sevk edilmiş satış irsaliyeleri birim fiyat veya LME + prim yöntemiyle faturalanır.",
            "customers": "Siparişlerde seçilecek gerçek müşteri kartları.",
            "stock_items": "Satın alma, reçete, üretim ve ambarlarda ortak kullanılan stok kartları.",
            "unit_sets": "KG, adet, metre ve paket dönüşümleri reçete tüketim hareketlerine uygulanır.",
            "suppliers": "Talep, sipariş, mal kabul ve faturada aynı kimlikle kullanılan tedarikçi kartları.",
            "purchase_requests": "Bölüm talebi onaylandıktan sonra tedarikçi siparişine dönüştürülür.",
            "purchase_orders": "Onaylı talepten doğan ve teslim alınan miktarı izlenen tedarikçi siparişleri.",
            "goods_receipts": "İrsaliye mal kabulü aynı stok kartı ve hedef ambara giriş hareketi üretir.",
            "branches": "Ambarların bağlı olduğu fabrika, depo ve diğer fiziksel işletme noktaları.",
            "warehouses": "Her ambar bir şubeye bağlıdır; negatif stok ENGELLE, UYAR veya İZİN olarak yönetilir.",
            "stock_documents": "Giriş, çıkış ve ambar transferleri tek fişle lot bazlı stok hareketlerine işlenir.",
            "profiles": "Profil ana kartları (kg/m, alaşım, sertlik). Rota ve reçete Üretim modülündedir.",
            "dies": "Kalıp ömrü, tenefer ve tedarikçi kayıtları. Rota/reçete bu ekranda yoktur.",
            "order_lines": "Sipariş detay satır görünümü — durum, onay, profil, boy ve miktar.",
        }
        self.description.setText(descriptions.get(self.view, "Operasyon ekranı"))
        primary_text = {
            "customers": "＋ YENİ MÜŞTERİ",
            "stock_items": "＋ YENİ STOK KARTI",
            "suppliers": "＋ YENİ TEDARİKÇİ",
            "purchase_requests": "＋ YENİ TALEP FİŞİ",
            "purchase_orders": "＋ TALEBİ SİPARİŞE ÇEVİR",
            "goods_receipts": "＋ MAL KABUL",
            "branches": "＋ YENİ ŞUBE",
            "warehouses": "＋ YENİ AMBAR",
            "stock_documents": "＋ YENİ STOK FİŞİ",
            "unit_sets": "＋ YENİ BİRİM SETİ",
            "profiles": "＋ PROFİL",
            "dies": "＋ KALIP",
            "orders": "＋ YENİ SATIŞ SİPARİŞİ",
            "planning": "＋ ÜRETİM PARTİSİ PLANLA",
            "recipes": "＋ YENİ REÇETE",
            "production": "＋ ÜRETİM EMRİ",
            "work_orders": "ÜRETİM GİRİŞİ",
            "warehouse_balances": "YENİLE",
            "stock_movements": "YENİLE",
            "packages": "＋ YENİ PAKET",
            "weighing_lists": "＋ ÇEKİ LİSTESİ OLUŞTUR",
            "shipments": "＋ SEVKİYAT OLUŞTUR",
            "invoices": "YENİLE",
            "die_movements": "YENİLE",
            "eloksal_slips": "＋ ELOKSAL FİŞİ",
            "downtime_events": "＋ DURUŞ KAYDI",
            "production_entries": "YENİLE",
            "maintenance_orders": "＋ BAKIM EMRİ",
            "maintenance_instructions": "＋ YENİ BAKIM TALİMATI",
            "purchase_invoices": "＋ SATIN ALMA FATURASI",
            "purchase_quotes": "＋ TEKLİF GİR",
            "sales_quotes": "＋ YENİ TEKLİF",
            "request_reasons": "＋ TALEP SEBEBİ",
            "complaints": "＋ ŞİKAYET",
            "price_lists": "＋ FİYAT LİSTESİ",
            "die_tooling_requests": "＋ KALIP TALEBİ",
            "die_tooling_work_orders": "＋ KALIP İŞ EMRİ",
            "die_tooling_pending": "＋ KALIP İŞ EMRİ",
            "service_items": "＋ HİZMET KARTI",
            "die_tooling_slips": "＋ KALIP FİŞİ",
            "die_tooling_problems": "＋ KALIP PROBLEMİ",
            "customer_product_codes": "＋ ÜRÜN KODU",
            "supplier_product_codes": "＋ ÜRÜN KODU",
            "property_sets": "＋ ÖZELLİK SETİ",
            "property_values": "＋ ÖZELLİK DEĞERİ",
            "subcontractors": "＋ FASONCU",
        }
        self.primary.setText(primary_text.get(self.view, "YENİLE"))
        if self.department == "Sevkiyat" and self.module == "Ambar Yükleri":
            self.primary.setText("＋ YENİ PAKET")
        self.primary.setVisible(self.can_create)
        self.secondary.setText(
            "DÜZENLE" if self.view in {"customers", "stock_items", "warehouses"}
            else "BELGELERİ AÇ" if self.view in {"profiles", "dies"}
            else "TALEBİ ONAYLA" if self.view == "purchase_requests"
            else "ÜRETİME ONAYLA"
        )
        self.secondary.setVisible(
            (self.view in {"customers", "stock_items", "warehouses"} and self.can_edit)
            or self.view in {"profiles", "dies"}
            or (self.view == "purchase_requests" and self.can_approve)
            or (self.view == "orders" and self.can_approve)
        )
        self.danger.setText("SİL")
        self.danger.setVisible(
            self.view in {"customers", "dies", "profiles"} and self.can_delete
        )
        self.show_inactive.setText(
            "Pasif stokları göster" if self.view == "stock_items"
            else "Pasif müşterileri göster"
        )
        self.show_inactive.setVisible(self.view in {"customers", "stock_items"})
        self.station_filter_bar.setVisible(
            self.module in {
                "Satış Siparişleri", "Satış Sevk Miktarları", "Bekleyen Siparişler",
                "Sipariş Detay (Satış)", "Satış Stok Hareketleri",
                "Üretim Siparişleri", "Üretim Onayı Bekleyen Siparişler",
                "Reçeteler", "Üretim Emirleri", "İş Emirleri", "Pres Üretim Fişleri",
                "Pres Üretim Miktarları", "Üretim Fişleri", "Stok Miktarları",
                "İstasyon Yükleri", "Ambar Yükleri", "Stok Hareketleri", "Stok Fişleri",
                "Satın Alma Stok Hareketleri", "Lotlar", "Kritik Stoklar", "Negatif Stoklar",
                "Kasalama Fişleri", "Hazır Kasalar", "Çeki Listeleri",
                "Satın Alma Siparişleri", "Satın Alma İrsaliyeleri",
            }
        )
        self.table.setSelectionMode(
            QAbstractItemView.ExtendedSelection
            if self.view in {"work_orders", "packages"}
            else QAbstractItemView.SingleSelection
        )
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.configure_table()
        self.refresh_data()

    def active_columns_key(self) -> str:
        if self.view == "order_lines":
            return "order_lines_grid"
        if self.view == "orders" and self.module in {
            "Satış Siparişleri", "Satış Sevk Miktarları", "Bekleyen Siparişler",
            "Üretim Siparişleri", "Üretim Onayı Bekleyen Siparişler",
            "Sipariş Detay (Satış)",
        }:
            return "orders_grid"
        if self.view == "purchase_requests" and self.module in {
            "Talep Fişleri", "Bekleyen Talepler", "Talep Detay",
        }:
            return "purchase_requests_grid"
        if self.view == "purchase_orders" and self.module in {
            "Satın Alma Siparişleri", "Bekleyen Siparişler",
            "Sipariş Detay", "Satın Alma Miktarları",
        }:
            return "purchase_orders_grid"
        if self.view == "goods_receipts":
            return "goods_receipts_grid"
        if self.view == "stock_items":
            return "stock_items_grid"
        if self.view == "stock_documents":
            return "stock_documents_grid"
        if self.view == "stock_movements":
            return "stock_movements_grid"
        if self.view == "warehouse_balances":
            return "warehouse_balances_grid"
        if self.view == "warehouses":
            return "warehouses_grid"
        if self.view == "branches":
            return "branches_grid"
        if self.view == "suppliers":
            return "suppliers_grid"
        if self.view == "unit_sets":
            return "unit_sets_grid"
        if self.view == "work_orders" and self.module == "İstasyon Yükleri":
            return "work_orders_station"
        if self.view == "die_movements":
            return "die_movements_grid"
        if self.view == "dies":
            if self.module == "Teneferi Yaklaşanlar":
                return "dies_near_tenefer"
            if self.module == "Hurda Kalıplar":
                return "dies_scrap"
            if self.module == "İmalattaki Kalıplar":
                return "dies_in_production"
        return self.view

    def _list_dies_for_module(self) -> list[dict[str, Any]]:
        if self.module == "Hurda Kalıplar":
            return self.service.list_dies_filtered(scrap_only=True)
        if self.module == "İmalattaki Kalıplar":
            return self.service.list_dies_filtered(status="İMALATTA")
        if self.module == "Teneferi Yaklaşanlar":
            return self.service.list_dies_filtered(tenefer_near_limit=True)
        if self.module == "Tedarik Bekleyen Kalıplar":
            return self.service.list_dies_filtered(status="TEDARİK BEKLİYOR")
        return self.service.list_dies()

    def _list_eloksal_for_module(self) -> list[dict[str, Any]]:
        tracking = self.module == "Eloksal Takip"
        return self.service.list_eloksal_slips(tracking_only=tracking)

    def _list_maintenance_for_module(self) -> list[dict[str, Any]]:
        pending = self.module == "Bakım Bekleyenler"
        return self.service.list_maintenance_orders(pending_only=pending)

    def _list_work_orders_for_module(self) -> list[dict[str, Any]]:
        records = self.service.list_work_orders()
        if self.module == "İstasyon Yükleri":
            return [row for row in records if str(row.get("status")) == "HAZIR"]
        if self.module == "Pres Üretim Fişleri":
            return [
                row for row in records
                if str(row.get("operation") or "").upper().startswith("PRES")
            ]
        if self.module == "Pres Üretim Miktarları":
            return [
                row for row in records
                if str(row.get("operation") or "").upper().startswith("PRES")
                and float(row.get("produced_kg") or 0) > 0
            ]
        if self.module == "Planlama Takvimi":
            return [
                row for row in records
                if str(row.get("status")) in {"HAZIR", "BEKLİYOR", "ÜRETİLİYOR"}
            ]
        if self.module == "Pres-Testere Takip":
            return [
                row for row in records
                if str(row.get("operation") or "").upper().startswith("PRES")
                and str(row.get("status")) in {"ÜRETİLİYOR", "TAMAMLANDI", "HAZIR"}
            ]
        return records

    def _list_production_entries_for_module(self) -> list[dict[str, Any]]:
        records = self.service.list_all_production_entries()
        if self.module in {
            "Pres Üretim Fişleri", "Pres Üretim Miktarları", "Pres-Testere Takip",
        }:
            records = [
                row for row in records
                if str(row.get("operation") or "").upper().startswith("PRES")
            ]
        if self.module == "Pres Üretim Miktarları":
            records = [row for row in records if float(row.get("net_kg") or 0) > 0]
        if self.module == "Pres-Testere Takip":
            records = [
                row for row in records
                if str(row.get("saw_status") or "").upper()
                not in {"", "TAMAMLANDI", "BİTTİ"}
            ]
        return records

    def _list_purchase_requests_for_module(self) -> list[dict[str, Any]]:
        records = self.service.list_purchase_requests()
        if self.module != "Bekleyen Talepler":
            return records
        return [
            row for row in records
            if str(row.get("status")) == "AÇIK"
            and (
                str(row.get("approval_status")) != "ONAYLANDI"
                or float(row.get("ordered_quantity") or 0)
                < float(row.get("requested_quantity") or 0) - 0.0005
            )
        ]

    def _list_purchase_orders_for_module(self) -> list[dict[str, Any]]:
        records = self.service.list_purchase_orders()
        if self.module not in {"Bekleyen Siparişler", "Satın Alma Miktarları"}:
            return records
        return [
            row for row in records
            if str(row.get("status")) not in {"TAMAMLANDI", "İPTAL"}
            and float(row.get("pending_quantity") or 0) > 0.0005
        ]

    def _list_stock_movements_for_module(self) -> list[dict[str, Any]]:
        if self.module == "Satın Alma Stok Hareketleri":
            return self.service.list_stock_movements(
                movement_types=["SATIN ALMA MAL KABUL"],
            )
        if self.module == "Üretim Stok Hareketleri":
            return [
                row for row in self.service.list_stock_movements()
                if str(row.get("movement_type") or "").upper() != "SATIN ALMA MAL KABUL"
                and (
                    row.get("work_order_no")
                    or row.get("order_no")
                    or "ÜRET" in str(row.get("movement_type") or "").upper()
                )
            ]
        return self.service.list_stock_movements()

    def configure_table(self) -> None:
        columns = self.COLUMNS[self.active_columns_key()]
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in columns])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        for index in range(len(columns)):
            self.table.setColumnWidth(index, 135)
        # Sütun filtre satırı her görünür sütun için bir hücre (ERP tarzı)
        self.column_filter_bar.configure(columns, preserve=False)
        self.column_filter_bar.setVisible(True)

    @staticmethod
    def _sum_first_available(
        records: list[dict[str, Any]], keys: tuple[str, ...]
    ) -> float:
        """Her kayıtta sırayla ilk dolu alanı toplar.

        Sekmeler farklı alan adları döndürür (sipariş ordered_kg, çeki listesi
        net_kg, ambar balance gibi); özet satırı hepsinde aynı çalışmalıdır.
        """
        total = 0.0
        for row in records:
            for key in keys:
                value = row.get(key)
                if value in (None, ""):
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if number:
                    total += number
                    break
        return total

    @classmethod
    def total_kg(cls, records: list[dict[str, Any]]) -> float:
        return cls._sum_first_available(
            records,
            (
                "ordered_kg", "planned_kg", "net_kg", "balance",
                "total_quantity", "received_quantity", "quantity",
            ),
        )

    @classmethod
    def total_quantity(cls, records: list[dict[str, Any]]) -> float:
        return cls._sum_first_available(
            records,
            (
                "ordered_quantity", "planned_quantity", "requested_quantity",
                "received_quantity", "quantity", "package_count", "line_count",
            ),
        )

    @staticmethod
    def format_value(key: str, value: object) -> str:
        if value is None:
            return ""
        if key == "direction":
            return "GİRİŞ" if int(value) > 0 else "ÇIKIŞ"
        if key in {"tracks_lot", "allow_mixed_lots"}:
            return "EVET" if bool(value) else "HAYIR"
        if key == "active":
            return "AKTİF" if bool(value) else "PASİF"
        if key == "has_route":
            return "TANIMLI" if bool(value) else "ROTA YOK"
        if key in {"progress_pct", "production_pct"}:
            try:
                return f"{int(value)}%"
            except (TypeError, ValueError):
                return str(value)
        if key in {"total_amount", "foreign_total", "usd_total"}:
            try:
                text = f"{float(value):,.2f}"
                return text.replace(",", "_").replace(".", ",").replace("_", ".")
            except (TypeError, ValueError):
                return str(value)
        if key in {"delivery_week", "delivery_year"}:
            if value in {None, ""}:
                return ""
            return str(int(value))
        if key.endswith("_kg") or key in {
            "unit_weight_kg_m", "planned_kg", "net_kg", "gross_kg", "balance",
            "quantity", "total_quantity", "requested_quantity", "approved_quantity",
            "ordered_quantity", "received_quantity", "pending_quantity", "minimum_quantity",
        }:
            try:
                text = f"{float(value):,.3f}"
                return text.replace(",", "_").replace(".", ",").replace("_", ".")
            except (TypeError, ValueError):
                return str(value)
        if key.endswith("_date") or key.endswith("_at"):
            try:
                return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")
            except ValueError:
                return str(value)[:16].replace("T", " ")
        return str(value)

    def source_records(self) -> list[dict[str, Any]]:
        return {
            "customers": lambda: self.service.list_customers(
                include_inactive=self.show_inactive.isChecked()
            ),
            "stock_items": lambda: self.service.list_stock_items(
                include_inactive=self.show_inactive.isChecked()
            ),
            "unit_sets": self.service.list_unit_sets,
            "suppliers": self.service.list_suppliers,
            "purchase_requests": self._list_purchase_requests_for_module,
            "purchase_orders": self._list_purchase_orders_for_module,
            "goods_receipts": self.service.list_goods_receipts,
            "branches": self.service.list_branches,
            "warehouses": self.service.list_warehouses,
            "stock_documents": self.service.list_stock_documents,
            "profiles": self.service.list_profiles,
            "dies": self._list_dies_for_module,
            "die_movements": self.service.list_all_die_movements,
            "eloksal_slips": self._list_eloksal_for_module,
            "downtime_events": self.service.list_downtime_events,
            "production_entries": self._list_production_entries_for_module,
            "maintenance_orders": self._list_maintenance_for_module,
            "maintenance_instructions": self.service.list_maintenance_instructions,
            "purchase_invoices": self.service.list_purchase_invoices,
            "purchase_quotes": self.service.list_purchase_quotes,
            "sales_quotes": self.service.list_sales_quotes,
            "order_lines": self.service.list_sales_order_lines_detail,
            "request_reasons": self.service.list_request_reasons,
            "customer_product_codes": self.service.list_customer_product_codes,
            "supplier_product_codes": self.service.list_supplier_product_codes,
            "service_items": self.service.list_service_items_master,
            "property_sets": self.service.list_property_sets,
            "property_values": self.service.list_property_values,
            "price_lists": self.service.list_sales_price_lists,
            "complaints": self.service.list_customer_complaints,
            "subcontractors": self.service.list_subcontractors,
            "die_tooling_requests": self.service.list_die_tooling_requests,
            "die_tooling_work_orders": self.service.list_die_tooling_work_orders,
            "die_tooling_pending": lambda: self.service.list_die_tooling_work_orders(pending_only=True),
            "die_tooling_slips": self.service.list_die_tooling_slips,
            "die_tooling_problems": self.service.list_die_tooling_problems,
            "die_unassigned": self.service.list_profiles_missing_die,
            "orders": self.service.list_sales_orders,
            "planning": self.service.list_order_lines_for_planning,
            "recipes": self.service.list_recipes,
            "production": self.service.list_production_orders,
            "work_orders": self._list_work_orders_for_module,
            "warehouse_balances": self.service.list_warehouse_balances,
            "stock_movements": self._list_stock_movements_for_module,
            "packages": self.service.list_packages,
            "weighing_lists": self.service.list_weighing_lists,
            "shipments": self.service.list_shipments,
            "invoices": self.service.list_sales_invoices,
        }[self.view]()

    def refresh_data(self, *_args: object) -> None:
        if self.view == "order_lines":
            try:
                self.service.recalculate_all_order_line_status()
            except OSError:
                pass
        records = self.source_records()
        if self.module == "Kritik Stoklar":
            records = [
                row for row in records
                if 0 <= float(row.get("balance") or 0)
                <= float(row.get("minimum_quantity") or 0)
                and float(row.get("minimum_quantity") or 0) > 0
            ]
        elif self.module == "Negatif Stoklar":
            records = [row for row in records if float(row.get("balance") or 0) < 0]
        elif self.module in {"Hazır Kasalar", "Ambar Yükleri"} and self.view == "packages":
            records = [
                row for row in records
                if str(row.get("status") or "") in {"SEVK ÖN", "SEVK HAZIR"}
            ]
        if not self.station_filter_bar.isHidden():
            start = self.date_from.date().toString("yyyy-MM-dd")
            end = self.date_to.date().toString("yyyy-MM-dd")
            warehouse_code = str(self.warehouse_filter.currentData() or "")
            filtered: list[dict[str, Any]] = []
            for row in records:
                record_date = str(
                    row.get("record_date") or row.get("movement_at")
                    or row.get("document_date")
                    or row.get("last_movement_at") or row.get("packed_at")
                    or row.get("order_date") or ""
                )[:10]
                if record_date and not (start <= record_date <= end):
                    continue
                if warehouse_code and warehouse_code not in {
                    str(row.get("input_warehouse_code") or ""),
                    str(row.get("output_warehouse_code") or ""),
                    str(row.get("warehouse_code") or ""),
                    str(row.get("source_warehouse_code") or ""),
                    str(row.get("target_warehouse_code") or ""),
                }:
                    continue
                filtered.append(row)
            records = filtered
        search = self.search.text().strip().casefold()
        if search:
            records = [
                row for row in records
                if search in " ".join(str(value) for value in row.values()).casefold()
            ]
        # Sütun filtrelerinden önce benzersiz değerleri besle (Excel AutoFilter)
        self.column_filter_bar.update_distinct_values(
            records, format_value=self.format_value
        )
        if self.column_filter_bar.has_active_filters():
            records = [
                row for row in records
                if self.column_filter_bar.row_matches(
                    row, format_value=self.format_value
                )
            ]
        self.records = records
        columns = self.COLUMNS[self.active_columns_key()]
        self.table.setRowCount(len(records))
        total_kg = self.total_kg(records)
        total_qty = self.total_quantity(records)
        filter_note = (
            "  |  sütun filtreli"
            if self.column_filter_bar.has_active_filters()
            else ""
        )
        self.rigel_footer.setText(
            f"{len(records)} kayıt  |  "
            f"toplam adet: {total_qty:,.0f}  |  "
            f"toplam kg: {total_kg:,.3f}{filter_note}"
        )
        for row_index, row in enumerate(records):
            for column, (key, _label) in enumerate(columns):
                item = QTableWidgetItem(self.format_value(key, row.get(key)))
                if column == 0:
                    item.setData(Qt.UserRole, row["id"])
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if key == "active":
                    item.setForeground(
                        QColor("#067647") if bool(row.get(key)) else QColor("#B42318")
                    )
                if key == "status":
                    item.setForeground(
                        QColor("#067647") if row.get(key) in {"HAZIR", "SEVK HAZIR", "TAMAMLANDI", "SEVK EDİLDİ"}
                        else QColor("#B54708")
                    )
                if (
                    key == "progress_pct"
                    and self.active_columns_key() == "orders_grid"
                ):
                    pct = max(0, min(100, int(row.get("progress_pct") or 0)))
                    if pct >= 100:
                        item.setBackground(QColor("#22895E"))
                        item.setForeground(QColor("#FFFFFF"))
                    elif pct > 0:
                        shade = 220 - int(pct * 0.9)
                        item.setBackground(QColor(shade, 239, shade - 20))
                if key == "close_status":
                    item.setForeground(
                        QColor("#067647") if row.get(key) == "AÇIK" else QColor("#667085")
                    )
                if key in {"order_approval", "production_approval_display", "approval_display"}:
                    item.setForeground(
                        QColor("#067647") if row.get(key) == "KABUL" else QColor("#B54708")
                    )
                self.table.setItem(row_index, column, item)
        statuses = ("HAZIR", "AÇIK", "BEKLİYOR", "ÜRETİLİYOR", "ONAY BEKLİYOR", "ÜRETİMDE")
        open_count = sum(1 for row in records if row.get("status") in statuses)
        self.kpi_values[0].setText(str(len(records)))
        self.kpi_values[1].setText(str(open_count))
        self.kpi_values[2].setText(self.format_value("net_kg", total_kg) + " kg")
        self.kpi_values[3].setText("YEREL")
        self.status.setText(
            f"{self.department} / {self.module}: {len(records)} kayıt."
        )
        self.load_column_layout()
        self.column_filter_bar.sync_widths()
        self.update_side_panel()

    def update_side_panel(self) -> None:
        record = self.selected_record()
        # Varsayılan kapalı — sadece satır seçilince aç (grid'e yer kalsın)
        if record is None:
            self.side_panel.setVisible(False)
            return
        if self.view in {"order_lines", "orders", "planning"}:
            self.side_panel.setVisible(True)
            self.side_panel.show_record(
                title="Sipariş Bilgileri" if self.view != "planning" else "Plan Satırı",
                record=record,
            )
        elif self.view in {"work_orders", "production"}:
            self.side_panel.setVisible(True)
            self.side_panel.show_record(title="İş Emri / Üretim Emri", record=record)
        elif self.view in {"profiles", "dies"}:
            self.side_panel.setVisible(True)
            self.side_panel.show_record(title="Profil / Kalıp Kartı", record=record)
        elif self.view in {"recipes", "packages", "shipments", "weighing_lists"}:
            self.side_panel.setVisible(True)
            titles = {
                "recipes": "Reçete Detayı",
                "packages": "Paket Bilgisi",
                "shipments": "Sevkiyat Bilgisi",
                "weighing_lists": "Çeki Listesi",
            }
            self.side_panel.show_record(title=titles.get(self.view, "Kayıt"), record=record)
        else:
            self.side_panel.setVisible(False)

    def reset_station_filters(self) -> None:
        today = QDate.currentDate()
        self.date_from.setDate(QDate(today.year(), today.month(), 1))
        self.date_to.setDate(today)
        self.warehouse_filter.setCurrentIndex(0)
        self.refresh_data()

    def selected_record(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        record_id = int(item.data(Qt.UserRole))
        return next((record for record in self.records if int(record["id"]) == record_id), None)

    def warn_select(self) -> None:
        QMessageBox.warning(self, "Kayıt seçilmedi", "İşlem yapılacak satırı seçin.")

    def create_package_from_ready_product(self) -> None:
        """Open the package card from both package and live warehouse screens."""
        dialog = PackageDialog(self.service, self)
        if not dialog.rows:
            QMessageBox.information(
                self,
                "Paketlenecek ürün yok",
                "Üretimi tamamlanmış ve paketlenmemiş profil bulunmuyor.",
            )
            return
        if dialog.exec() == QDialog.Accepted:
            self.service.create_package(
                int(dialog.line.currentData()),
                quantity=dialog.quantity.value(),
                net_kg=dialog.net.value(),
                gross_kg=dialog.gross.value(),
                lot_no=dialog.lot.text(),
                username=self.username,
            )
            self.refresh_data()

    def run_primary(self) -> None:
        try:
            if self.view == "customers":
                dialog = CustomerDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_customer(**dialog.values(), username=self.username)
            elif self.view == "stock_items":
                dialog = StockItemDialog(self, service=self.service)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_stock_item(**dialog.values(), username=self.username)
            elif self.view == "suppliers":
                dialog = SupplierDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_supplier(**dialog.values(), username=self.username)
            elif self.view == "purchase_requests":
                dialog = PurchaseRequestDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_purchase_request(
                        request_date=dialog.request_date.date().toString("yyyy-MM-dd"),
                        description=dialog.description.text(), lines=dialog.rows,
                        username=self.username,
                    )
            elif self.view == "purchase_orders":
                dialog = PurchaseOrderDialog(self.service, self)
                if not dialog.requests:
                    QMessageBox.information(self, "Onaylı talep yok", "Önce bir satın alma talebini onaylayın.")
                    return
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_purchase_order_from_request(
                        int(dialog.request.currentData()), int(dialog.supplier.currentData()),
                        order_date=dialog.order_date.date().toString("yyyy-MM-dd"),
                        delivery_date=dialog.delivery_date.date().toString("yyyy-MM-dd"),
                        currency=dialog.currency.currentText(), exchange_rate=dialog.exchange_rate.value(),
                        supplier_document_no=dialog.document_no.text(), note=dialog.note.text(),
                        unit_prices=dialog.unit_prices(), username=self.username,
                    )
            elif self.view == "goods_receipts":
                dialog = GoodsReceiptDialog(self.service, self)
                if dialog.order.count() <= 1:
                    QMessageBox.information(self, "Açık sipariş yok", "Mal kabul yapılacak satın alma siparişi bulunmuyor.")
                    return
                if dialog.exec() == QDialog.Accepted:
                    self.service.receive_purchase_order(
                        int(dialog.order.currentData()),
                        receipt_date=dialog.receipt_date.date().toString("yyyy-MM-dd"),
                        dispatch_note_no=dialog.dispatch_no.text(), lot_no=dialog.lot_no.text(),
                        note=dialog.note.text(), quantities=dialog.quantities(), username=self.username,
                    )
            elif self.view == "branches":
                dialog = BranchDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_branch(**dialog.values(), username=self.username)
            elif self.view == "warehouses":
                dialog = WarehouseDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_warehouse(**dialog.values(), username=self.username)
            elif self.view == "stock_documents":
                dialog = StockDocumentDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_stock_document(
                        document_type=dialog.document_type.currentText(),
                        document_date=dialog.document_date.date().toString("yyyy-MM-dd"),
                        source_warehouse_id=(
                            int(dialog.source.currentData())
                            if dialog.source.isEnabled() and dialog.source.currentData() is not None
                            else None
                        ),
                        target_warehouse_id=(
                            int(dialog.target.currentData())
                            if dialog.target.isEnabled() and dialog.target.currentData() is not None
                            else None
                        ),
                        reference_no=dialog.reference.text(), note=dialog.note.text(),
                        lines=dialog.rows, username=self.username,
                    )
            elif self.view == "unit_sets":
                dialog = UnitSetDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_unit_set(**dialog.values(), username=self.username)
            elif self.view == "profiles":
                from ui.master_data_dialogs import ProfileCreateDialog
                dialog = ProfileCreateDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    values = dialog.values()
                    self.service.create_profile(
                        values["profile_code"],
                        values["profile_name"],
                        unit_weight_kg_m=values["unit_weight_kg_m"],
                        alloy=values["alloy"],
                        temper=values["temper"],
                        username=self.username,
                    )
            elif self.view == "dies":
                from ui.master_data_dialogs import DieCreateDialog
                if not self.service.list_profiles():
                    QMessageBox.information(
                        self, "Profil yok",
                        "Kalıp eklemek için önce Profil Kartları ekranından profil tanımlayın.",
                    )
                    return
                dialog = DieCreateDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_die(**dialog.values(), username=self.username)
            elif self.view == "orders":
                dialog = SalesOrderDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    payload = dialog.header_values()
                    customer_id = int(payload.pop("customer_id"))
                    self.service.create_sales_order(
                        customer_id,
                        lines=dialog.lines,
                        username=self.username,
                        **payload,
                    )
            elif self.view == "planning":
                dialog = ProductionPlanDialog(self.service, self)
                if not dialog.rows:
                    QMessageBox.information(
                        self, "Planlanacak miktar yok",
                        "Bütün açık sipariş satırları üretim partilerine dağıtılmış."
                    )
                    return
                if dialog.exec() == QDialog.Accepted:
                    dialog.create_record(username=self.username)
            elif self.view == "recipes":
                dialog = RecipeDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    dialog.create_record(username=self.username)
            elif self.view == "sales_quotes":
                if not self.service.list_customers():
                    QMessageBox.information(
                        self, "Müşteri yok", "Önce müşteri kartı tanımlayın."
                    )
                    return
                if not self.service.list_profiles():
                    QMessageBox.information(
                        self, "Profil yok", "Önce profil kartı tanımlayın."
                    )
                    return
                dialog = SalesQuoteDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    dialog.create_record(username=self.username)
            elif self.view == "production":
                dialog = ProductionPlanDialog(self.service, self)
                if not dialog.rows:
                    QMessageBox.information(
                        self, "Planlanacak miktar yok",
                        "Üretim emri açmak için önce üretime onaylı ve kalan miktarı olan "
                        "sipariş satırı olmalıdır.",
                    )
                    return
                if dialog.exec() == QDialog.Accepted:
                    dialog.create_record(username=self.username)
            elif self.view == "warehouse_balances":
                if self.department == "Sevkiyat" and self.module == "Ambar Yükleri":
                    self.create_package_from_ready_product()
                else:
                    self.refresh_data()
                return
            elif self.view == "stock_movements":
                self.refresh_data()
                return
            elif self.view == "work_orders":
                record = self.selected_record()
                if record is None:
                    self.warn_select()
                    return
                if str(record.get("operation") or "").upper().startswith("PRES"):
                    self.open_press_production(record)
                    return
                dialog = ProductionEntryDialog(record, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.record_work_order_output(
                        record["id"],
                        quantity=dialog.quantity.value(),
                        gross_kg=dialog.gross.value(),
                        net_kg=dialog.net.value(),
                        metre=dialog.metre.value(),
                        die_id=record.get("die_id") if record["operation"].startswith("PRES") else None,
                        lot_no=dialog.lot.text(),
                        shift=dialog.shift.currentText(),
                        username=self.username,
                        complete=dialog.complete.isChecked(),
                        production_type=dialog.production_type.currentText(),
                        press_status=dialog.press_status.currentText(),
                        saw_status=dialog.saw_status.currentText(),
                        real_weight_kg_m=dialog.real_weight.value(),
                        theoretical_weight_kg_m=dialog.theoretical_weight.value(),
                        billet_count=dialog.billet_count.value(),
                        billet_length_mm=dialog.billet_length.value(),
                        billet_diameter_mm=dialog.billet_diameter.value(),
                        billet_density_kg_m3=dialog.billet_density.value(),
                        billet_weight_kg_m=dialog.billet_weight.value(),
                        theoretical_net_kg=dialog.theoretical_net.value(),
                        theoretical_billet_kg=dialog.theoretical_billet.value(),
                        press_fire_pct=dialog.press_fire.value(),
                        basket_count=dialog.basket_count.value(),
                        result_length_mm=dialog.result_length.value(),
                        preparation_min=dialog.preparation_min.value(),
                        duration_min=dialog.duration_min.value(),
                        missing_quantity=dialog.missing_quantity.value(),
                        missing_reason=dialog.missing_reason.text(),
                        note=dialog.note.text(),
                    )
            elif self.view == "packages":
                self.create_package_from_ready_product()
            elif self.view == "weighing_lists":
                dialog = WeighingListDialog(self.service.list_packages(), self)
                if not dialog.packages:
                    QMessageBox.information(
                        self,
                        "Sevk Ön paketi yok",
                        "Çeki listesine alınacak SEVK ÖN paketi bulunmuyor.",
                    )
                    return
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_weighing_list(
                        dialog.selected_package_ids(),
                        note=dialog.note.text(),
                        username=self.username,
                    )
            elif self.view == "shipments":
                dialog = ShipmentDialog(self.service.list_packages(), self)
                if not dialog.packages:
                    QMessageBox.information(self, "Hazır paket yok", "Sevke hazır paket bulunmuyor.")
                    return
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_shipment(
                        dialog.selected_package_ids(),
                        shipment_date=dialog.shipment_date.date().toString("yyyy-MM-dd"),
                        vehicle_plate=dialog.plate.text(),
                        username=self.username,
                    )
            elif self.view == "invoices":
                self.refresh_data()
                return
            elif self.view == "eloksal_slips" and self.module == "Eloksal Fişleri":
                work_orders = [
                    row for row in self.service.list_work_orders()
                    if "ELOKSAL" in str(row.get("operation") or "").upper()
                    and str(row.get("status")) in {"HAZIR", "ÜRETİLİYOR"}
                ]
                if not work_orders:
                    QMessageBox.information(
                        self, "Eloksal iş emri yok",
                        "Askıya alınacak hazır eloksal iş emri bulunmuyor.",
                    )
                    return
                labels = [
                    f"{row['work_order_no']} | {row['order_line_ref']} | {row['profile_code']}"
                    for row in work_orders[:50]
                ]
                label, ok = QInputDialog.getItem(
                    self, "Eloksal fişi", "İş emri seçin", labels, 0, False,
                )
                if not ok:
                    return
                work_id = work_orders[labels.index(label)]["id"]
                hanger, ok = QInputDialog.getText(self, "Askı no", "Askı numarası:")
                if not ok:
                    return
                color, ok = QInputDialog.getText(self, "Renk grubu", "Renk grubu:")
                if not ok:
                    return
                qty, ok = QInputDialog.getDouble(self, "Askılama adet", "Adet:", 0, 0, 1_000_000, 0)
                if not ok:
                    return
                kg, ok = QInputDialog.getDouble(self, "Askılama kg", "KG:", 0, 0, 1_000_000, 3)
                if not ok:
                    return
                self.service.create_eloksal_slip(
                    work_order_id=int(work_id),
                    hanger_no=hanger,
                    color_group=color,
                    hanging_quantity=qty,
                    hanging_kg=kg,
                    username=self.username,
                )
            elif self.view == "downtime_events":
                reason, ok = QInputDialog.getText(self, "Duruş kaydı", "Duruş sebebi:")
                if not ok or not reason.strip():
                    return
                station, ok = QInputDialog.getText(self, "İstasyon", "İstasyon:")
                if not ok:
                    return
                self.service.create_downtime_event(
                    reason=reason,
                    station=station,
                    username=self.username,
                )
            elif self.view == "maintenance_orders":
                dialog = MaintenanceOrderDialog(self.service, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                values = dialog.values()
                values.pop("instruction_id", None)
                self.service.create_maintenance_order(
                    username=self.username, **values
                )
            elif self.view == "maintenance_instructions":
                dialog = MaintenanceInstructionDialog(self.service, self)
                if dialog.exec() != QDialog.Accepted:
                    return
                self.service.create_maintenance_instruction(
                    username=self.username, **dialog.values()
                )
            elif self.view == "purchase_invoices":
                receipts = self.service.list_goods_receipts()
                if not receipts:
                    QMessageBox.information(self, "Mal kabul yok", "Faturalandırılacak mal kabul fişi bulunmuyor.")
                    return
                labels = [
                    f"{row['receipt_no']} | {row.get('supplier_name', '')} | {row.get('purchase_order_no', '')}"
                    for row in receipts[:50]
                ]
                label, ok = QInputDialog.getItem(
                    self, "Satın alma faturası", "Mal kabul fişi seçin", labels, 0, False,
                )
                if not ok:
                    return
                receipt_id = receipts[labels.index(label)]["id"]
                self.service.create_purchase_invoice_from_receipt(
                    int(receipt_id), username=self.username,
                )
            elif self.view == "purchase_quotes":
                requests = self._list_purchase_requests_for_module()
                if not requests:
                    QMessageBox.information(self, "Talep yok", "Teklif girilecek satın alma talebi bulunmuyor.")
                    return
                req_labels = [f"{row['request_no']} | {row.get('description', '')}" for row in requests[:50]]
                req_label, ok = QInputDialog.getItem(
                    self, "Teklif", "Talep seçin", req_labels, 0, False,
                )
                if not ok:
                    return
                request_id = requests[req_labels.index(req_label)]["id"]
                suppliers = self.service.list_suppliers()
                if not suppliers:
                    QMessageBox.information(self, "Tedarikçi yok", "Önce tedarikçi kartı tanımlayın.")
                    return
                sup_labels = [f"{row['code']} | {row['name']}" for row in suppliers[:50]]
                sup_label, ok = QInputDialog.getItem(
                    self, "Teklif", "Tedarikçi seçin", sup_labels, 0, False,
                )
                if not ok:
                    return
                supplier_id = suppliers[sup_labels.index(sup_label)]["id"]
                price, ok = QInputDialog.getDouble(
                    self, "Teklif", "Birim fiyat:", 0, 0, 1_000_000, 4,
                )
                if not ok:
                    return
                qty, ok = QInputDialog.getDouble(
                    self, "Teklif", "Miktar:", 1, 0, 1_000_000, 3,
                )
                if not ok:
                    return
                self.service.create_purchase_quote(
                    request_id=int(request_id),
                    supplier_id=int(supplier_id),
                    unit_price=price,
                    quantity=qty,
                    username=self.username,
                )
            elif self.view == "request_reasons":
                from ui.master_data_dialogs import RequestReasonDialog

                dialog = RequestReasonDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_request_reason(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "complaints":
                from ui.master_data_dialogs import ComplaintDialog

                customers = self.service.list_customers()
                if not customers:
                    QMessageBox.information(self, "Müşteri yok", "Önce müşteri kartı tanımlayın.")
                    return
                dialog = ComplaintDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_customer_complaint(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "die_tooling_requests":
                from ui.master_data_dialogs import DieToolingRequestDialog

                if not self.service.list_profiles():
                    QMessageBox.information(self, "Profil yok", "Önce profil kartı tanımlayın.")
                    return
                dialog = DieToolingRequestDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_die_tooling_request(
                        username=self.username, **dialog.values()
                    )
            elif self.view in {"die_tooling_work_orders", "die_tooling_pending"}:
                from ui.master_data_dialogs import DieToolingWorkOrderDialog

                if not self.service.list_profiles():
                    QMessageBox.information(self, "Profil yok", "Önce profil kartı tanımlayın.")
                    return
                dialog = DieToolingWorkOrderDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_die_tooling_work_order(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "service_items":
                from ui.master_data_dialogs import ServiceItemDialog

                dialog = ServiceItemDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_service_item_master(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "die_tooling_slips":
                from ui.master_data_dialogs import DieToolingSlipDialog

                if not self.service.list_dies():
                    QMessageBox.information(self, "Kalıp yok", "Önce kalıp kartı tanımlayın.")
                    return
                dialog = DieToolingSlipDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_die_tooling_slip(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "die_tooling_problems":
                from ui.master_data_dialogs import DieToolingProblemDialog

                if not self.service.list_dies():
                    QMessageBox.information(self, "Kalıp yok", "Önce kalıp kartı tanımlayın.")
                    return
                dialog = DieToolingProblemDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    if not dialog.values()["description"].strip():
                        QMessageBox.warning(self, "Eksik bilgi", "Problem açıklaması zorunludur.")
                        return
                    self.service.create_die_tooling_problem(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "customer_product_codes":
                from ui.master_data_dialogs import PartyProductCodeDialog

                dialog = PartyProductCodeDialog(
                    self.service, party_type="CUSTOMER", parent=self
                )
                if dialog.exec() == QDialog.Accepted:
                    values = dialog.values()
                    if not values.get("profile_id"):
                        QMessageBox.warning(self, "Eksik bilgi", "Profil seçin.")
                        return
                    self.service.create_party_product_code(
                        username=self.username, **values
                    )
            elif self.view == "supplier_product_codes":
                from ui.master_data_dialogs import PartyProductCodeDialog

                dialog = PartyProductCodeDialog(
                    self.service, party_type="SUPPLIER", parent=self
                )
                if dialog.exec() == QDialog.Accepted:
                    values = dialog.values()
                    if not values.get("profile_id"):
                        QMessageBox.warning(self, "Eksik bilgi", "Profil seçin.")
                        return
                    self.service.create_party_product_code(
                        username=self.username, **values
                    )
            elif self.view == "property_sets":
                from ui.master_data_dialogs import PropertySetDialog

                dialog = PropertySetDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_property_set_master(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "property_values":
                from ui.master_data_dialogs import PropertyValueDialog

                if not self.service.list_property_sets():
                    QMessageBox.information(self, "Set yok", "Önce özellik seti tanımlayın.")
                    return
                dialog = PropertyValueDialog(self.service, self)
                if dialog.exec() == QDialog.Accepted:
                    self.service.create_property_set_value(
                        username=self.username, **dialog.values()
                    )
            elif self.view == "subcontractors":
                from ui.master_data_dialogs import SubcontractorDialog

                dialog = SubcontractorDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    values = dialog.values()
                    self.service.create_subcontractor(
                        values["code"], values["name"],
                        phone=values["phone"], city=values["city"],
                        username=self.username,
                    )
            elif self.view == "price_lists":
                record = self.selected_record()
                if record is not None:
                    from ui.master_data_dialogs import PriceListLineDialog

                    dialog = PriceListLineDialog(self.service, int(record["id"]), self)
                    if dialog.exec() == QDialog.Accepted:
                        self.service.create_sales_price_list_line(
                            username=self.username, **dialog.values()
                        )
                else:
                    from ui.master_data_dialogs import SalesPriceListDialog

                    dialog = SalesPriceListDialog(self.service, self)
                    if dialog.exec() == QDialog.Accepted:
                        self.service.create_sales_price_list(
                            username=self.username, **dialog.values()
                        )
            else:
                return
        except (ValueError, OSError, sqlite3.IntegrityError) as error:
            message = str(error)
            if "NEGATIVE_STOCK_BLOCKED" in message:
                message = "Ambar politikası bu işlemde negatif stok oluşmasına izin vermiyor."
            QMessageBox.warning(self, "İşlem tamamlanamadı", message)
            return
        self.refresh_data()

    def run_secondary(self) -> None:
        if self.view == "customers":
            self.edit_customer()
            return
        if self.view == "stock_items":
            self.edit_stock_item()
            return
        if self.view == "warehouses":
            self.edit_warehouse()
            return
        if self.view == "purchase_requests" and self.can_approve:
            record = self.selected_record()
            if record is None:
                self.warn_select(); return
            try:
                self.service.approve_purchase_request(int(record["id"]), username=self.username)
            except ValueError as error:
                QMessageBox.warning(self, "Talep onaylanamadı", str(error)); return
            self.refresh_data(); return
        if self.view in {"profiles", "dies"}:
            record = self.selected_record()
            if record is None:
                self.warn_select()
                return
            entity_type = "PROFILE" if self.view == "profiles" else "DIE"
            attachments = self.service.list_attachments(entity_type, record["id"])
            if not attachments:
                QMessageBox.information(
                    self, "Bağlı belge yok", "Seçili karta bağlı PDF veya görsel bulunmuyor."
                )
                return
            missing: list[str] = []
            for attachment in attachments:
                path = str(attachment["file_path"])
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                    missing.append(str(attachment["file_name"]))
            if missing:
                QMessageBox.warning(
                    self,
                    "Bazı belgeler açılamadı",
                    "\n".join(missing),
                )
            return
        if self.view != "orders" or not self.can_approve:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Üretime onayla",
            "Seçili sipariş üretime onaylansın mı?\n\n"
            "Onay sonrası planlama ayrı yapılır. "
            "Üretim emri oluşturmak için Üretim → Üretim Planlama ekranını kullanın.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            approved_lines = self.service.approve_sales_order(record["id"], username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş onaylanamadı", str(error))
            return
        self.refresh_data()
        QMessageBox.information(
            self,
            "Sipariş üretime onaylandı",
            f"{len(approved_lines)} sipariş satırı planlamaya hazır.\n"
            "Üretim emri açmak için Üretim Planlama ekranına geçin.",
        )

    def selected_records(self) -> list[dict[str, Any]]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        result: list[dict[str, Any]] = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is None:
                continue
            record_id = int(item.data(Qt.UserRole))
            record = next(
                (value for value in self.records if int(value["id"]) == record_id),
                None,
            )
            if record is not None:
                result.append(record)
        return result

    def context_menu_specs(self) -> list[dict[str, Any]]:
        specs = list(self.CONTEXT_MENUS.get(self.view, [
            {"label": "Görüntüle", "action": "show_record_details"},
        ]))
        if self.department == "Sevkiyat" and self.module == "Ambar Yükleri":
            specs.insert(0, {
                "label": "Paket Oluştur",
                "action": "create_package_from_ready_product",
                "perm": "create",
                "needs_selection": False,
            })
        specs.extend(self._MENU_TAIL)
        return specs

    def context_action_texts(self) -> list[str]:
        return [
            spec["label"] for spec in self.context_menu_specs()
            if not spec.get("separator")
        ]

    def _context_item_enabled(self, spec: dict[str, Any]) -> bool:
        if spec.get("separator"):
            return False
        perm = spec.get("perm")
        if perm == "create" and not self.can_create:
            return False
        if perm == "edit" and not self.can_edit:
            return False
        if perm == "delete" and not self.can_delete:
            return False
        if perm == "approve" and not self.can_approve:
            return False
        if spec.get("needs_selection", True) and self.selected_record() is None:
            return False
        return True

    def show_feature_pending(self, feature: str = "") -> None:
        QMessageBox.information(
            self,
            "ERP uyumu",
            f"{feature or 'Bu işlem'} bir sonraki sürümde eklenecek.\n"
            "Menü yapısı korunuyor; işlevler adım adım bağlanıyor.",
        )

    def navigate_to(self, department: str, module: str, *, search: str = "") -> None:
        if not self.handles_context(department, module):
            QMessageBox.warning(
                self, "Ekran bulunamadı",
                f"{department} / {module} ekranı henüz bağlı değil.",
            )
            return
        self.set_context(department, module)
        if search:
            self.search.setText(search)
        else:
            self.refresh_data()

    def reset_columns(self) -> None:
        self.configure_table()
        self.refresh_data()

    def selected_search_token(self, *keys: str) -> str:
        record = self.selected_record()
        if record is None:
            return ""
        for key in keys:
            value = record.get(key)
            if value not in {None, ""}:
                return str(value)
        return ""

    def approve_order_for_production(self) -> None:
        self.run_secondary()

    def open_customer_orders(self) -> None:
        token = self.selected_search_token("customer_name", "order_no")
        self.navigate_to("Satış", "Satış Siparişleri", search=token)

    def open_linked_weighing_lists(self) -> None:
        token = self.selected_search_token("order_no", "customer_name")
        self.navigate_to("Sevkiyat", "Çeki Listeleri", search=token)

    def open_order_documents(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        attachments = self.service.list_attachments("SALES_ORDER", int(record["id"]))
        if not attachments:
            QMessageBox.information(
                self, "Doküman yok", "Seçili siparişe bağlı doküman bulunmuyor."
            )
            return
        missing: list[str] = []
        for attachment in attachments:
            path = str(attachment["file_path"])
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                missing.append(str(attachment["file_name"]))
        if missing:
            QMessageBox.warning(self, "Bazı belgeler açılamadı", "\n".join(missing))

    def show_production_revision_info(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        rows = self.service.audit_history("SALES_ORDER", int(record["id"]))
        production_rows = [
            row for row in rows
            if row.get("entity_type") in {"PRODUCTION_ORDER", "WORK_ORDER", "SALES_ORDER"}
            or "PLAN" in str(row.get("action") or "")
            or "APPROVE" in str(row.get("action") or "")
        ]
        table_rows = [
            [
                row.get("created_at"),
                row.get("username"),
                row.get("action"),
                row.get("after_json") or "",
            ]
            for row in production_rows
        ]
        RecordDetailsDialog(
            "Üretim Revizyon Bilgisi",
            fields=[
                ("Sipariş No", record.get("order_no")),
                ("Firma", record.get("customer_name")),
            ],
            tables=[
                {
                    "title": "Revizyon / Onay Geçmişi",
                    "headers": ["Tarih", "Kullanıcı", "İşlem", "Detay"],
                    "rows": table_rows,
                }
            ],
            parent=self,
        ).exec()


    def navigate_stock_search(self) -> None:
        self.navigate_to("Malzeme Yönetimi", "Stok Kartları")

    def navigate_stock_documents(self) -> None:
        self.run_primary() if self.view == "stock_documents" else self.navigate_to(
            "Malzeme Yönetimi", "Stok Fişleri"
        )

    def navigate_shipments_for_order(self) -> None:
        token = self.selected_search_token("order_no", "customer_name")
        self.navigate_to("Satış", "Satış İrsaliyeleri", search=token)

    def navigate_quality_movements(self) -> None:
        self.navigate_to("Malzeme Yönetimi", "Stok Hareketleri", search="KALITE")

    def create_counter_purchase_request(self) -> None:
        if self.view != "orders" or not self.can_create:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            request_id = self.service.create_purchase_request_from_sales_order(
                int(record["id"]), username=self.username
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Karşı talep", str(error))
            return
        QMessageBox.information(
            self, "Talep oluşturuldu",
            f"Satın alma talebi oluşturuldu (ID: {request_id}).",
        )
        self.navigate_to("Satın Alma", "Satın Alma Talepleri")

    def create_recipe_material_request(self) -> None:
        if self.view != "orders" or not self.can_create:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            request_id = self.service.create_purchase_request_from_recipe_materials(
                int(record["id"]), username=self.username
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Alt malzeme talebi", str(error))
            return
        QMessageBox.information(
            self, "Talep oluşturuldu",
            f"Hammadde talebi oluşturuldu (ID: {request_id}).",
        )
        self.navigate_to("Satın Alma", "Satın Alma Talepleri")

    def apply_maturity_pricing(self) -> None:
        if self.view != "orders" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        rate, ok = QInputDialog.getDouble(
            self, "Vade farkı", "Yıllık vade oranı (%):", 12.0, 0, 100, 2
        )
        if not ok:
            return
        try:
            updated = self.service.apply_maturity_pricing_to_order(
                int(record["id"]), annual_rate_pct=rate, username=self.username
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Vade farkı", str(error))
            return
        QMessageBox.information(self, "Güncellendi", f"{updated} satır fiyatı güncellendi.")
        self.refresh_data()

    def show_order_status(self) -> None:
        if self.view != "orders":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        progress = self.service.order_progress(int(record["id"]))
        order = progress["order"]
        lines: list[str] = [
            f"Fiş: {order.get('order_no')}  Rev: {order.get('revision_no', 0):02d}",
            f"Müşteri: {order.get('customer_name')}",
            f"Durum: {order.get('status')}  |  Üretim Onay: {order.get('production_approval')}",
            f"Tarih: {order.get('order_date')}  Teslim: {order.get('delivery_date')}",
            "",
            "SATIR DURUMLARI",
        ]
        detail_rows = [
            row for row in self.service.list_sales_order_lines_detail()
            if int(row.get("sales_order_id") or 0) == int(record["id"])
        ]
        if detail_rows:
            for row in detail_rows:
                lines.append(
                    f"  {row.get('line_no')}. {row.get('profile_code')} | "
                    f"sipariş {float(row.get('ordered_kg') or 0):,.3f} kg | "
                    f"üretim {float(row.get('produced_kg') or 0):,.3f} kg | "
                    f"sevk {float(row.get('shipped_kg') or 0):,.3f} kg | "
                    f"{row.get('fulfillment_status') or row.get('line_status')}"
                )
        else:
            for row in progress["lines"]:
                lines.append(
                    f"  {row.get('line_no')}. {row.get('profile_code')} | "
                    f"durum {row.get('status')}"
                )
        QMessageBox.information(self, "Sipariş Durumu", "\n".join(lines))

    def print_order_statement(self) -> None:
        if self.view != "orders":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        progress = self.service.order_progress(int(record["id"]))
        order = progress["order"]
        headers = ("Satır", "Profil", "Sipariş kg", "Üretim kg", "Sevk kg", "Birim Fiyat", "Tutar", "Durum")
        rows: list[list[str]] = []
        total_kg = 0.0
        total_amount = 0.0
        for row in progress["lines"]:
            kg = float(row.get("ordered_kg") or 0)
            amount = kg * float(row.get("unit_price") or 0)
            total_kg += kg
            total_amount += amount
            rows.append([
                str(row.get("line_no") or ""),
                str(row.get("profile_code") or ""),
                f"{kg:,.3f}",
                f"{float(row.get('produced_kg') or 0):,.3f}",
                f"{float(row.get('shipped_kg') or 0):,.3f}",
                f"{float(row.get('unit_price') or 0):,.4f}",
                f"{amount:,.2f}",
                str(row.get("status") or ""),
            ])
        rows.append(["", "TOPLAM", f"{total_kg:,.3f}", "", "", "", f"{total_amount:,.2f}", ""])
        subtitle = (
            f"Müşteri: {order.get('customer_name')}  |  "
            f"Tarih: {order.get('order_date')}  |  "
            f"Döviz: {order.get('currency')}"
        )
        from ui.document_preview import preview_grid_document

        preview_grid_document(
            self,
            title=f"SİPARİŞ EKSTRESİ — {order.get('order_no')}",
            subtitle=subtitle,
            headers=list(headers),
            rows=rows,
        )

    def open_integration_hub(self) -> None:
        path = self.service.factory_config_path()
        QMessageBox.information(
            self,
            "Entegrasyon",
            "Paylaşım ve dış sistem bağlantıları:\n\n"
            f"• rigel.config: {path}\n"
            f"• Veritabanı: {self.service.database_path}\n"
            "• Excel/PDF dışa aktarım: tablo araç çubuğu EXCEL / PDF\n"
            "• Eski veri aktarımı: Dosya menüsünden eski veri içe aktarım",
        )

    def save_column_layout(self) -> None:
        from PySide6.QtCore import QSettings

        settings = QSettings("RigelCost", "WorkflowColumns")
        key = f"{self.department}/{self.module}"
        widths = [
            self.table.columnWidth(column)
            for column in range(self.table.columnCount())
        ]
        settings.setValue(key, widths)
        QMessageBox.information(
            self, "Sütun dizilimi",
            f"{self.module} ekranı için sütun genişlikleri kaydedildi.",
        )

    def load_column_layout(self) -> None:
        from PySide6.QtCore import QSettings

        settings = QSettings("RigelCost", "WorkflowColumns")
        key = f"{self.department}/{self.module}"
        widths = settings.value(key)
        if not isinstance(widths, list):
            return
        for column, width in enumerate(widths):
            if column >= self.table.columnCount():
                break
            try:
                self.table.setColumnWidth(column, int(width))
            except (TypeError, ValueError):
                continue

    def navigate_complaints(self) -> None:
        self.navigate_to("Satış", "Şikayetler")

    def navigate_purchase_stock_movements(self) -> None:
        self.navigate_to("Satın Alma", "Satın Alma Stok Hareketleri")

    def open_profile_orders(self) -> None:
        token = self.selected_search_token("profile_code", "profile_name")
        self.navigate_to("Satış", "Satış Siparişleri", search=token)

    def open_profile_stock_movements(self) -> None:
        token = self.selected_search_token("profile_code")
        self.navigate_to("Malzeme Yönetimi", "Stok Hareketleri", search=token)

    def open_profile_stock_card(self) -> None:
        token = self.selected_search_token("profile_code")
        self.navigate_to("Malzeme Yönetimi", "Stok Kartları", search=token)

    def open_profile_dies(self) -> None:
        token = self.selected_search_token("profile_code")
        self.navigate_to("Kalıphane", "Kalıp Kartları", search=token)

    def open_die_production_history(self) -> None:
        token = self.selected_search_token("die_code", "profile_code")
        self.navigate_to("Üretim", "Pres Üretim Fişleri", search=token)

    def open_planning_order(self) -> None:
        token = self.selected_search_token("order_no", "profile_code")
        self.navigate_to("Satış", "Satış Siparişleri", search=token)

    def open_planning_production_orders(self) -> None:
        token = self.selected_search_token("order_no", "profile_code")
        self.navigate_to("Üretim", "Üretim Emirleri", search=token)

    def open_production_order_progress(self) -> None:
        token = self.selected_search_token("order_no", "production_order_no")
        self.navigate_to("Satış", "Satış Siparişleri", search=token.split()[0] if token else "")

    def open_production_work_orders(self) -> None:
        token = self.selected_search_token("production_order_no", "order_no")
        self.navigate_to("Üretim", "İş Emirleri", search=token)

    def open_production_stock_movements(self) -> None:
        token = self.selected_search_token("order_no", "production_order_no")
        self.navigate_to("Üretim", "Stok Hareketleri", search=token)

    def open_work_order_stock_movements(self) -> None:
        token = self.selected_search_token("work_order_no", "order_no")
        self.navigate_to("Üretim", "Stok Hareketleri", search=token)

    def open_work_order_order(self) -> None:
        token = self.selected_search_token("order_no")
        self.navigate_to("Satış", "Satış Siparişleri", search=token)

    def open_package_stock_movements(self) -> None:
        token = self.selected_search_token("package_no", "order_nos")
        self.navigate_to("Malzeme Yönetimi", "Stok Hareketleri", search=token)

    def open_shipment_weighing_list(self) -> None:
        token = self.selected_search_token("weighing_list_no")
        self.navigate_to("Sevkiyat", "Çeki Listeleri", search=token)

    def open_stock_item_movements(self) -> None:
        token = self.selected_search_token("code", "name")
        self.navigate_to("Malzeme Yönetimi", "Stok Hareketleri", search=token)

    def open_stock_item_balances(self) -> None:
        token = self.selected_search_token("code", "name")
        self.navigate_to("Malzeme Yönetimi", "Lotlar", search=token)

    def open_balance_stock_movements(self) -> None:
        token = self.selected_search_token("stock_code", "lot_no")
        self.navigate_to("Malzeme Yönetimi", "Stok Hareketleri", search=token)

    def open_recipe_profile(self) -> None:
        token = self.selected_search_token("profile_code")
        self.navigate_to("Kalıphane", "Profil Kartları", search=token)

    def open_goods_receipt_for_order(self) -> None:
        self.navigate_to("Satın Alma", "Satın Alma İrsaliyeleri")

    def dispatch_context_action(self, spec: dict[str, Any]) -> None:
        action = str(spec.get("action") or "")
        if action == "pending":
            self.show_feature_pending(str(spec.get("feature") or spec.get("label") or ""))
            return
        handler = getattr(self, action, None)
        if handler is None:
            self.show_feature_pending(action)
            return
        handler()

    def open_context_menu(self, position: QPoint) -> None:
        index = self.table.indexAt(position)
        if index.isValid() and index.row() not in {
            selected.row() for selected in self.table.selectionModel().selectedRows()
        }:
            self.table.selectRow(index.row())
        menu = QMenu(self)
        for spec in self.context_menu_specs():
            if spec.get("separator"):
                if menu.actions() and not menu.actions()[-1].isSeparator():
                    menu.addSeparator()
                continue
            action = QAction(spec["label"], menu)
            action.setEnabled(self._context_item_enabled(spec))
            action.triggered.connect(lambda checked=False, item=spec: self.dispatch_context_action(item))
            menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def edit_sales_order(self) -> None:
        if self.view != "orders" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        dialog = SalesOrderDialog(self.service, self, order_id=int(record["id"]))
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.header_values()
        customer_id = int(payload.pop("customer_id"))
        try:
            self.service.update_sales_order(
                int(record["id"]),
                customer_id,
                lines=dialog.lines,
                username=self.username,
                **payload,
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş güncellenemedi", str(error))
            return
        self.refresh_data()

    def delete_sales_order(self) -> None:
        if self.view != "orders" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Siparişi sil",
            f"{record['order_no']} numaralı sipariş kalıcı olarak silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.delete_sales_order(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş silinemedi", str(error))
            return
        self.refresh_data()

    def copy_sales_order(self) -> None:
        if self.view != "orders" or not self.can_create:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            new_id = self.service.copy_sales_order(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş kopyalanamadı", str(error))
            return
        self.refresh_data()
        progress = self.service.order_progress(new_id)
        QMessageBox.information(
            self,
            "Sipariş kopyalandı",
            f"Yeni sipariş no: {progress['order']['order_no']}",
        )

    def confirm_sales_order(self) -> None:
        if self.view != "orders" or not self.can_approve:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Sipariş onayı",
            f"{record['order_no']} ticari olarak onaylansın mı?\n\n"
            "Üretim onayı ayrı adımda verilir.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.confirm_sales_order(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş onaylanamadı", str(error))
            return
        self.refresh_data()
        QMessageBox.information(self, "Sipariş onaylandı", "Sipariş durumu AÇIK olarak güncellendi.")

    def close_sales_order(self) -> None:
        if self.view != "orders" or not self.can_approve:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Sipariş kapatma",
            f"{record['order_no']} kapatılsın mı?\n\nAçık satırlar KAPALI durumuna alınır.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.close_sales_order(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş kapatılamadı", str(error))
            return
        self.refresh_data()

    def print_sales_order(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        progress = self.service.order_progress(int(record["id"]))
        order = progress["order"]
        headers = (
            "Satır", "Profil", "Boy mm", "Adet", "kg", "Yüzey", "Alaşım", "Sertlik", "Durum"
        )
        rows: list[list[str]] = []
        for row in progress["lines"]:
            rows.append(
                [
                    str(row.get("line_no") or ""),
                    f"{row.get('profile_code')} {row.get('profile_name')}",
                    str(row.get("stock_length_mm") or row.get("production_length_mm") or ""),
                    f"{float(row.get('ordered_quantity') or 0):,.0f}",
                    f"{float(row.get('ordered_kg') or 0):,.3f}",
                    str(row.get("surface") or ""),
                    str(row.get("alloy") or ""),
                    str(row.get("temper") or ""),
                    str(row.get("status") or ""),
                ]
            )
        subtitle = (
            f"Fiş No: {order.get('order_no')}  |  "
            f"Müşteri: {order.get('customer_name')}  |  "
            f"Tarih: {order.get('order_date')}  |  "
            f"Teslim: {order.get('delivery_date')}  |  "
            f"Durum: {order.get('status')}  |  "
            f"Üretim Onay: {order.get('production_approval')}"
        )
        from ui.document_preview import preview_grid_document

        preview_grid_document(
            self,
            title=f"SATIŞ SİPARİŞİ — {order.get('order_no')}",
            subtitle=subtitle,
            headers=list(headers),
            rows=rows,
        )

    def print_weighing_list(self) -> None:
        if self.view != "weighing_lists":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            document = self.service.weighing_list_document(int(record["id"]))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Çeki listesi", str(error))
            return
        from reports.shipment_documents import weighing_list_html
        from ui.document_preview import preview_html_document

        preview_html_document(
            self,
            title=f"Çeki Listesi — {document['header'].get('weighing_list_no')}",
            html_content=weighing_list_html(document["header"], document["lines"]),
        )

    def print_shipment(self) -> None:
        if self.view != "shipments":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            document = self.service.shipment_document(int(record["id"]))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sevkiyat", str(error))
            return
        from reports.shipment_documents import shipment_dispatch_html
        from ui.document_preview import preview_html_document

        preview_html_document(
            self,
            title=f"Sevk İrsaliyesi — {document['header'].get('shipment_no')}",
            html_content=shipment_dispatch_html(document["header"], document["lines"]),
        )

    def print_package_label(self) -> None:
        if self.view != "packages":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            document = self.service.package_label_document(int(record["id"]))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Paket etiketi", str(error))
            return
        from reports.shipment_documents import package_label_html
        from ui.document_preview import preview_html_document

        preview_html_document(
            self,
            title=f"Paket Etiketi — {document['header'].get('package_no')}",
            html_content=package_label_html(document["header"], document["lines"]),
        )

    def open_press_production(self, record: dict[str, Any]) -> None:
        """Pres iş emirlerini ayrıntılı pres üretim fişi ekranıyla açar."""
        from ui.press_production_dialog import PressProductionDialog

        context = dict(record)
        try:
            context.update(self.service.press_entry_context(int(record["id"])))
        except (ValueError, sqlite3.Error):
            pass
        dialog = PressProductionDialog(
            context,
            username=self.username,
            slip_no=self.service.peek_next_no("PF"),
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.values()
        try:
            entry_id = self.service.record_work_order_output(
                int(record["id"]),
                die_id=record.get("die_id"),
                username=self.username,
                **payload,
            )
        except (ValueError, OSError, sqlite3.IntegrityError) as error:
            QMessageBox.warning(self, "Pres fişi kaydedilemedi", str(error))
            return
        self.refresh_data()
        if QMessageBox.question(
            self,
            "Pres üretim fişi kaydedildi",
            "Fiş kaydedildi. Çıktısını şimdi görmek ister misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        ) == QMessageBox.Yes:
            self.show_press_slip(entry_id)

    def show_press_slip(self, production_entry_id: int) -> None:
        try:
            document = self.service.press_slip_document(int(production_entry_id))
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Pres üretim fişi", str(error))
            return
        from reports.production_documents import press_slip_html
        from ui.document_preview import preview_html_document

        preview_html_document(
            self,
            title=f"Pres Üretim Fişi — {document['header'].get('slip_no')}",
            html_content=press_slip_html(document),
        )

    def print_press_slip(self) -> None:
        """Üretim Fişleri ekranından seçili pres fişinin çıktısını açar."""
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        self.show_press_slip(int(record["id"]))

    def print_work_order(self) -> None:
        if self.view != "work_orders":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            header = self.service.work_order_document(int(record["id"]))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "İş emri", str(error))
            return
        from reports.shipment_documents import work_order_slip_html
        from ui.document_preview import preview_html_document

        preview_html_document(
            self,
            title=f"İş Emri — {header.get('work_order_no')}",
            html_content=work_order_slip_html(header),
        )

    def edit_profile(self) -> None:
        if self.view != "profiles" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        from ui.master_data_dialogs import ProfileEditDialog

        dialog = ProfileEditDialog(self.service, int(record["id"]), self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_profile(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Profil güncellenemedi", str(error))
            return
        self.refresh_data()

    def edit_recipe(self) -> None:
        if self.view != "recipes" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            dialog = RecipeDialog(self.service, self, recipe_id=int(record["id"]))
        except ValueError as error:
            QMessageBox.warning(self, "Reçete açılamadı", str(error))
            return
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            dialog.update_record(username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Reçete güncellenemedi", str(error))
            return
        self.refresh_data()

    def convert_sales_quote(self) -> None:
        if self.view != "sales_quotes" or not self.can_create:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        if str(record.get("status") or "").upper() == "SİPARİŞE DÖNÜŞTÜ":
            QMessageBox.information(
                self, "Teklif kullanıldı", "Bu teklif zaten siparişe dönüştürülmüş."
            )
            return
        order_date = QDate.currentDate().toString("yyyy-MM-dd")
        delivery_date = QDate.currentDate().addDays(14).toString("yyyy-MM-dd")
        try:
            order_id = self.service.convert_sales_quote_to_order(
                int(record["id"]),
                order_date=order_date,
                delivery_date=delivery_date,
                username=self.username,
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş oluşturulamadı", str(error))
            return
        progress = self.service.order_progress(order_id)
        QMessageBox.information(
            self,
            "Sipariş oluşturuldu",
            f"Teklif {record['quote_no']} → sipariş {progress['order']['order_no']} olarak açıldı.",
        )
        self.refresh_data()

    def edit_profile_route(self) -> None:
        if self.view != "profiles" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        routes = self.service.list_routes(int(record["id"]))
        if not routes:
            QMessageBox.information(
                self, "Rota yok", "Bu profil için tanımlı üretim rotası bulunmuyor."
            )
            return
        route_id = int(routes[0]["id"])
        if len(routes) > 1:
            labels = [f"{row['code']} — {row['name']}" for row in routes]
            choice, ok = QInputDialog.getItem(
                self, "Rota seçin", "Düzenlenecek üretim rotasını seçin:", labels, 0, False
            )
            if not ok:
                return
            route_id = int(routes[labels.index(choice)]["id"])
        try:
            dialog = RouteEditDialog(self.service, route_id, self)
        except ValueError as error:
            QMessageBox.warning(self, "Rota açılamadı", str(error))
            return
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            dialog.save(username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Rota güncellenemedi", str(error))
            return
        self.refresh_data()

    def deactivate_profile(self) -> None:
        if self.view != "profiles" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Profili pasife al",
            f"{record['profile_code']} profil kartı pasife alınsın mı?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.deactivate_profile(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Profil pasife alınamadı", str(error))
            return
        self.refresh_data()

    def open_die_card(self) -> None:
        """KALIP KART — kalıbın bütün alt sekmelerini tek pencerede açar."""
        if self.view != "dies":
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        from ui.die_card_dialog import DieCardDialog

        try:
            dialog = DieCardDialog(
                self.service,
                int(record["id"]),
                username=self.username,
                can_edit=self.can_edit,
                parent=self,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Kalıp kartı açılamadı", str(error))
            return
        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def edit_die(self) -> None:
        if self.view != "dies" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        from ui.master_data_dialogs import DieEditDialog

        dialog = DieEditDialog(self.service, int(record["id"]), self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_die(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kalıp güncellenemedi", str(error))
            return
        self.refresh_data()

    def scrap_die(self) -> None:
        if self.view != "dies" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Kalıbı hurdaya ayır",
            f"{record['die_code']} kalıbı hurdaya ayrılsın mı?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.scrap_die(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kalıp hurdaya ayrılamadı", str(error))
            return
        self.refresh_data()

    def apply_price_list_to_order(self) -> None:
        if self.view != "orders" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            from ui.master_data_dialogs import PriceListPickerDialog

            dialog = PriceListPickerDialog(self.service, self)
        except ValueError as error:
            QMessageBox.information(self, "Fiyat listesi", str(error))
            return
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            updated = self.service.apply_price_list_to_order(
                int(record["id"]),
                dialog.price_list_id(),
                username=self.username,
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Fiyat güncellenemedi", str(error))
            return
        QMessageBox.information(
            self, "Fiyat listesi uygulandı", f"{updated} sipariş satırı güncellendi."
        )
        self.refresh_data()

    def edit_customer(self) -> None:
        if self.view != "customers" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        customer = self.service.customer(int(record["id"]))
        customer["contacts"] = self.service.list_customer_contacts(int(record["id"]))
        customer["addresses"] = self.service.list_customer_addresses(int(record["id"]))
        dialog = CustomerDialog(self, customer)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_customer(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Müşteri güncellenemedi", str(error))
            return
        self.refresh_data()

    def edit_supplier(self) -> None:
        if self.view != "suppliers" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        dialog = SupplierDialog(self, self.service.supplier(int(record["id"])))
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_supplier(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Tedarikçi güncellenemedi", str(error))
            return
        self.refresh_data()

    def convert_purchase_request_to_order(self) -> None:
        if self.view != "purchase_requests" or not self.can_create:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        if str(record.get("approval_status")) != "ONAYLANDI":
            QMessageBox.warning(
                self, "Talep onaysız",
                "Siparişe çevirmek için önce talebi onaylayın.",
            )
            return
        dialog = PurchaseOrderDialog(self.service, self, request_id=int(record["id"]))
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_purchase_order_from_request(
                int(dialog.request.currentData()), int(dialog.supplier.currentData()),
                order_date=dialog.order_date.date().toString("yyyy-MM-dd"),
                delivery_date=dialog.delivery_date.date().toString("yyyy-MM-dd"),
                currency=dialog.currency.currentText(), exchange_rate=dialog.exchange_rate.value(),
                supplier_document_no=dialog.document_no.text(), note=dialog.note.text(),
                unit_prices=dialog.unit_prices(), username=self.username,
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Sipariş oluşturulamadı", str(error))
            return
        self.refresh_data()

    def edit_stock_item(self) -> None:
        if self.view != "stock_items" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        dialog = StockItemDialog(self, self.service.stock_item(int(record["id"])), service=self.service)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_stock_item(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Stok kartı güncellenemedi", str(error))
            return
        self.refresh_data()

    def edit_warehouse(self) -> None:
        if self.view != "warehouses" or not self.can_edit:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        dialog = WarehouseDialog(self.service, self, record)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update_warehouse_policy(
                int(record["id"]), branch_id=int(values["branch_id"]),
                negative_stock_policy=str(values["negative_stock_policy"]),
                allow_mixed_lots=bool(values["allow_mixed_lots"]),
                active=bool(values["active"]), username=self.username,
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Ambar güncellenemedi", str(error))
            return
        self.refresh_data()

    def run_danger(self) -> None:
        if self.view == "customers":
            self.delete_customer()
        elif self.view == "dies":
            self.delete_die()
        elif self.view == "profiles":
            self.deactivate_profile()

    def delete_customer(self) -> None:
        if self.view != "customers" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Müşteriyi sil",
            (
                f"{record['code']} — {record['name']} kalıcı olarak silinsin mi?\n\n"
                "Bağlı sipariş veya teklif varsa silme engellenir."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.delete_customer(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Müşteri silinemedi", str(error))
            return
        self.refresh_data()

    def delete_die(self) -> None:
        if self.view != "dies" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        answer = QMessageBox.question(
            self,
            "Kalıbı sil",
            (
                f"{record['die_code']} kalıp kartı kalıcı olarak silinsin mi?\n\n"
                "Bağlı sipariş veya hareket varsa silme engellenir; o durumda hurdaya ayırın."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.delete_die(int(record["id"]), username=self.username)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kalıp silinemedi", str(error))
            return
        self.refresh_data()

    def toggle_customer_active(self) -> None:
        if self.view != "customers" or not self.can_delete:
            return
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        activate = not bool(record.get("active"))
        verb = "aktifleştirilsin" if activate else "pasife alınsın"
        answer = QMessageBox.question(
            self, "Müşteri durumunu değiştir",
            f"{record['code']} — {record['name']} {verb} mı?\n\n"
            "Pasife alma, eski sipariş ve profil bağlantılarını silmez.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.service.set_customer_active(
            int(record["id"]), activate, username=self.username
        )
        self.refresh_data()

    # Detay fişinin sağ MİKTARLAR paneli: DURUM / ADET / KG dökümü.
    DETAIL_STAT_ROWS: tuple[tuple[str, str, str], ...] = (
        ("SİPARİŞ", "ordered_quantity", "ordered_kg"),
        ("PLAN", "planned_quantity", "planned_kg"),
        ("ÜRETİM", "produced_quantity", "produced_kg"),
        ("HURDA", "", "scrap_kg"),
        ("PAKET", "package_count", "net_kg"),
        ("BRÜT", "", "gross_kg"),
        ("SEVK", "shipped_quantity", "shipped_kg"),
        ("KABUL", "received_quantity", ""),
        ("BAKİYE", "balance", ""),
        ("TUTAR", "", "total_amount"),
    )
    # Fiş değil kart olan sekmelerde üst blok başlığı değişir.
    DETAIL_CARD_VIEWS = frozenset({
        "customers", "suppliers", "stock_items", "profiles", "dies", "recipes",
        "routes", "branches", "warehouses", "unit_sets", "price_lists",
        "property_sets", "maintenance_instructions", "subcontractors",
        "customer_product_codes", "supplier_product_codes", "service_items",
    })

    @staticmethod
    def voucher_number(value: object, decimals: int = 0) -> str:
        """Fiş panellerinde kullanılan Türkçe biçimli sayı."""
        if value in {None, ""}:
            return ""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        text = f"{number:,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")

    @classmethod
    def record_stat_rows(cls, record: dict[str, Any]) -> list[list[Any]]:
        """Kayıttaki miktar alanlarını sağ panel satırlarına çevirir."""
        rows: list[list[Any]] = []
        for label, quantity_key, kg_key in cls.DETAIL_STAT_ROWS:
            quantity = record.get(quantity_key) if quantity_key else None
            kg = record.get(kg_key) if kg_key else None
            if quantity in {None, ""} and kg in {None, ""}:
                continue
            rows.append([
                label,
                cls.voucher_number(quantity, 0),
                cls.voucher_number(kg, 2),
            ])
        return rows

    @staticmethod
    def record_subtitle(record: dict[str, Any]) -> str:
        """Başlık çubuğunda kaydı tanıtan kısa metin."""
        parts: list[str] = []
        for key in (
            "customer_name", "supplier_name", "profile_code", "stock_code",
            "die_code", "warehouse_name",
        ):
            value = record.get(key)
            if value not in {None, ""} and str(value) not in parts:
                parts.append(str(value))
            if len(parts) >= 2:
                break
        return "   ·   ".join(parts)

    def detail_header_title(self) -> str:
        return "KART BİLGİSİ" if self.view in self.DETAIL_CARD_VIEWS else "FİŞ BİLGİSİ"

    def planning_line_for_production(self, record: dict[str, Any]) -> dict[str, Any]:
        """Üretim emrini açan sipariş satırı — satır başına tek emir vardır."""
        order_no = str(record.get("order_no") or "")
        profile_code = str(record.get("profile_code") or "")
        production_no = str(record.get("production_order_no") or "")
        candidates = [
            line
            for line in self.service.list_order_lines_for_planning()
            if str(line.get("order_no") or "") == order_no
            and str(line.get("profile_code") or "") == profile_code
        ]
        for line in candidates:
            for order in self.service.production_orders_for_line(int(line["id"])):
                if str(order.get("production_order_no") or "") == production_no:
                    return line
        return candidates[0] if candidates else {}

    def production_order_voucher(
        self, record: dict[str, Any]
    ) -> tuple[list[tuple[str, Any]], list[dict[str, Any]], list[list[Any]]]:
        """Üretim emri fişi: başlık alanları, alt sekme ızgaraları ve miktarlar."""
        line = self.planning_line_for_production(record)
        profile_id = int(line.get("profile_id") or 0)
        route_code = str(record.get("route_code") or "")
        recipes = self.service.list_recipes(profile_id) if profile_id else []
        recipe = next(
            (row for row in recipes if str(row.get("route_code") or "") == route_code),
            recipes[0] if recipes else {},
        )
        recipe_lines = (
            self.service.list_recipe_lines(int(recipe["id"])) if recipe else []
        )
        work_orders = self.service.work_orders_for_production(int(record["id"]))
        dies = self.service.list_dies(profile_id) if profile_id else []
        profile_code = str(record.get("profile_code") or "")
        balances = [
            row
            for row in self.service.list_warehouse_balances()
            if str(row.get("profile_code") or "") == profile_code
        ]
        raw_material = next(
            (
                f"{row.get('stock_code')} — {row.get('description') or 'HAMMADDE'}"
                for row in recipe_lines
                if row.get("stock_code")
                and (
                    "HAMMADDE" in str(row.get("warehouse_code") or "").upper()
                    or str(row.get("process_type") or "").upper().startswith("GİRDİ")
                )
            ),
            str(recipe.get("raw_material_code") or "") or "TANIMSIZ",
        )
        production_length = (
            recipe.get("production_length_mm") or line.get("production_length_mm") or 0
        )

        fields: list[tuple[str, Any]] = [
            ("FİŞ NO", record.get("production_order_no")),
            ("TARİH", self.format_value("order_date", line.get("order_date"))),
            (
                "SİPARİŞ",
                f"{record.get('order_no')}-{line.get('line_no')}"
                if line else record.get("order_no"),
            ),
            ("MÜŞTERİ", record.get("customer_name")),
            ("STOK KOD", record.get("profile_code")),
            ("STOK AD", record.get("profile_name")),
            (
                "REÇETE",
                f"{recipe.get('recipe_code')} — {recipe.get('recipe_name')}"
                if recipe else "REÇETE YOK",
            ),
            (
                "ROTA",
                f"{record.get('route_code')} — {recipe.get('route_name') or ''}".strip(" —"),
            ),
            ("HAMMADDE", raw_material),
            ("MİKTAR", self.voucher_number(record.get("planned_quantity"), 0)),
            ("PLAN KG", self.voucher_number(record.get("planned_kg"), 2)),
            ("ÜRETİM BOY", f"{self.voucher_number(production_length, 0)} mm"),
            ("SİPARİŞ BOY", f'{self.voucher_number(line.get("production_length_mm"), 0)} mm'),
            ("UÇ KESİM PAYI", f'{self.voucher_number(recipe.get("hanger_allowance_mm"), 0)} mm'),
            ("TESTERE PAYI", f'{self.voucher_number(recipe.get("saw_allowance_mm"), 0)} mm'),
            ("YÜZEY", line.get("surface")),
            ("ALAŞIM", line.get("alloy")),
            ("SERTLİK", line.get("temper")),
            ("KALIP", line.get("die_code")),
            ("TESLİM TARİHİ", self.format_value("delivery_date", record.get("delivery_date"))),
            ("İŞ EMRİ", f"{record.get('completed_work_orders')} / {record.get('work_order_count')}"),
            ("DURUM", record.get("status")),
        ]

        tables: list[dict[str, Any]] = [
            {
                "title": "İş Emirleri",
                "headers": [
                    "FİŞ NO", "SIRA", "OPERASYON", "İSTASYON", "ÜRETİM BOY",
                    "PLAN ADET", "PLAN KG", "ÜRETİLEN ADET", "ÜRETİLEN KG",
                    "HURDA KG", "BAŞLANGIÇ", "BİTİŞ", "ÖNCELİK", "DURUM",
                ],
                "rows": [
                    [
                        row.get("work_order_no"),
                        row.get("sequence_no"),
                        row.get("operation"),
                        row.get("station"),
                        self.voucher_number(row.get("production_length_mm"), 0),
                        self.voucher_number(row.get("planned_quantity"), 0),
                        self.voucher_number(row.get("planned_kg"), 2),
                        self.voucher_number(row.get("produced_quantity"), 0),
                        self.voucher_number(row.get("produced_kg"), 2),
                        self.voucher_number(row.get("scrap_kg"), 2),
                        self.format_value("actual_start", row.get("actual_start")),
                        self.format_value("actual_end", row.get("actual_end")),
                        row.get("priority"),
                        row.get("status"),
                    ]
                    for row in work_orders
                ],
            },
            {
                "title": "Reçete",
                # Referans fişte reçete alt sekme değil, ızgaraların altında sabittir.
                "pinned": True,
                "headers": [
                    "İŞLEM TİPİ", "AMBAR", "STOK KOD", "OPERASYON", "İSTASYON",
                    "SIRA", "BİRİM", "ORAN", "MİKTAR", "KG", "METRE",
                ],
                "rows": [
                    [
                        row.get("process_type") or "ÇIKTI",
                        row.get("warehouse_code"),
                        row.get("stock_code") or "profil stok kartı",
                        row.get("operation_name"),
                        row.get("station_name"),
                        row.get("route_sequence_no"),
                        row.get("unit_code"),
                        f"{row.get('numerator')}/{row.get('denominator')}",
                        self.voucher_number(row.get("quantity"), 3),
                        self.voucher_number(row.get("external_kg"), 3),
                        self.voucher_number(row.get("external_metre"), 2),
                    ]
                    for row in recipe_lines
                ],
            },
            {
                "title": "Sipariş Bilgileri",
                "headers": [
                    "SİPARİŞ NO", "SATIR", "MÜŞTERİ", "PROFİL", "BOY", "YÜZEY",
                    "ALAŞIM", "SERTLİK", "SİP. ADET", "SİP. KG", "PLAN ADET",
                    "PLAN KG", "KALAN ADET", "TESLİM",
                ],
                "rows": [
                    [
                        line.get("order_no"),
                        line.get("line_no"),
                        line.get("customer_name"),
                        line.get("profile_code"),
                        self.voucher_number(line.get("production_length_mm"), 0),
                        line.get("surface"),
                        line.get("alloy"),
                        line.get("temper"),
                        self.voucher_number(line.get("ordered_quantity"), 0),
                        self.voucher_number(line.get("ordered_kg"), 2),
                        self.voucher_number(line.get("planned_quantity"), 0),
                        self.voucher_number(line.get("planned_kg"), 2),
                        self.voucher_number(line.get("remaining_quantity"), 0),
                        self.format_value("delivery_date", line.get("delivery_date")),
                    ]
                ] if line else [],
            },
            {
                "title": "Tüm Siparişler",
                "headers": [
                    "SİPARİŞ NO", "SATIR", "TARİH", "TESLİM", "MÜŞTERİ", "PROFİL",
                    "BOY", "SİP. ADET", "SİP. KG", "PLAN ADET", "KALAN ADET", "DURUM",
                ],
                "rows": [
                    [
                        row.get("order_no"),
                        row.get("line_no"),
                        self.format_value("order_date", row.get("order_date")),
                        self.format_value("delivery_date", row.get("delivery_date")),
                        row.get("customer_name"),
                        row.get("profile_code"),
                        self.voucher_number(row.get("production_length_mm"), 0),
                        self.voucher_number(row.get("ordered_quantity"), 0),
                        self.voucher_number(row.get("ordered_kg"), 2),
                        self.voucher_number(row.get("planned_quantity"), 0),
                        self.voucher_number(row.get("remaining_quantity"), 0),
                        row.get("status"),
                    ]
                    for row in self.service.list_order_lines_for_planning()
                    if str(row.get("profile_code") or "") == profile_code
                ],
            },
            {
                "title": "Kalıplar",
                "headers": [
                    "KALIP KOD", "YEDEK", "FİGÜR", "TENEFER NO", "KALAN m",
                    "BASILAN KG", "KONUM", "DURUM",
                ],
                "rows": [
                    [
                        row.get("die_code"),
                        row.get("spare_no"),
                        row.get("figure_count"),
                        row.get("tenefer_no"),
                        self.voucher_number(row.get("tenefer_remaining_m"), 1),
                        self.voucher_number(row.get("used_kg"), 2),
                        row.get("external_label") or row.get("location"),
                        row.get("status"),
                    ]
                    for row in dies
                ],
            },
            {
                "title": "Stoklar",
                "headers": [
                    "AMBAR", "AMBAR TİPİ", "STOK KOD", "STOK AD", "LOT / ŞARJ",
                    "BAKİYE", "BİRİM", "SON HAREKET",
                ],
                "rows": [
                    [
                        row.get("warehouse_name"),
                        row.get("warehouse_type"),
                        row.get("stock_code"),
                        row.get("stock_name"),
                        row.get("lot_no") or "—",
                        self.voucher_number(row.get("balance"), 3),
                        row.get("unit"),
                        self.format_value("last_movement_at", row.get("last_movement_at")),
                    ]
                    for row in balances
                ],
            },
        ]

        planned_quantity = float(record.get("planned_quantity") or 0)
        produced_quantity = float(record.get("produced_quantity") or 0)
        planned_kg = float(record.get("planned_kg") or 0)
        produced_kg = float(record.get("produced_kg") or 0)
        stock_balance = sum(float(row.get("balance") or 0) for row in balances)
        press_stock = sum(
            float(row.get("balance") or 0)
            for row in balances
            if "PRES" in str(row.get("warehouse_type") or "").upper()
            or "PRES" in str(row.get("warehouse_name") or "").upper()
            or "PRES" in str(row.get("warehouse_code") or "").upper()
        )
        # Referans MİKTARLAR paneli: uygun / stok / plan / iş emri / üretim / hurda.
        first_station = next(
            (
                str(row.get("station") or "").strip()
                for row in work_orders
                if str(row.get("station") or "").strip()
            ),
            "PRES",
        )
        stats: list[list[Any]] = [
            [
                f"{first_station} UYGUN",
                self.voucher_number(max(0.0, planned_quantity - produced_quantity), 0),
                self.voucher_number(max(0.0, planned_kg - produced_kg), 2),
            ],
            ["STOK", "", self.voucher_number(stock_balance, 2)],
            ["PRES STOK", "", self.voucher_number(press_stock, 2)],
            [
                "SİPARİŞ",
                self.voucher_number(line.get("ordered_quantity"), 0),
                self.voucher_number(line.get("ordered_kg"), 2),
            ],
            ["PLAN", self.voucher_number(planned_quantity, 0), self.voucher_number(planned_kg, 2)],
            [
                "İŞ EMRİ",
                self.voucher_number(
                    sum(float(row.get("planned_quantity") or 0) for row in work_orders), 0
                ),
                self.voucher_number(
                    sum(float(row.get("planned_kg") or 0) for row in work_orders), 2
                ),
            ],
            [
                "ÜRETİM",
                self.voucher_number(produced_quantity, 0),
                self.voucher_number(produced_kg, 2),
            ],
            [
                "HURDA",
                "",
                self.voucher_number(
                    sum(float(row.get("scrap_kg") or 0) for row in work_orders), 2
                ),
            ],
            [
                "KALAN",
                self.voucher_number(max(0.0, planned_quantity - produced_quantity), 0),
                self.voucher_number(max(0.0, planned_kg - produced_kg), 2),
            ],
        ]
        return fields, tables, stats

    def show_record_details(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return

        columns_key = self.active_columns_key()
        column_defs = self.COLUMNS.get(columns_key) or self.COLUMNS.get(self.view) or ()
        fields: list[tuple[str, Any]] = [
            (label, self.format_value(key, record.get(key)))
            for key, label in column_defs
        ]
        tables: list[dict[str, Any]] = []
        stats: list[list[Any]] | None = None

        if self.view == "customers":
            full_record = self.service.customer(int(record["id"]))
            fields = [
                ("Müşteri Kodu", full_record["code"]),
                ("Firma", full_record["name"]),
                ("Kısa Ad", full_record["short_name"]),
                ("Sektör", full_record["sector"]),
                ("Vergi Dairesi", full_record["tax_office"]),
                ("Vergi / T.C. No", full_record["tax_number"]),
                ("Telefon", full_record["phone"]),
                ("Telefon 2", full_record["phone2"]),
                ("Faks", full_record["fax"]),
                ("E-posta", full_record["email"]),
                ("E-posta 2", full_record["email2"]),
                ("Adres", full_record["address"]),
                ("Şehir", full_record["city"]),
                ("İlçe", full_record["district"]),
                ("Ülke", full_record["country"]),
                ("Satış Temsilcisi", full_record["sales_representative"]),
                ("Döviz", full_record["currency"]),
                ("Sipariş Notu", full_record["order_note"]),
                ("Üretim Notu", full_record["production_note"]),
                ("Genel Uyarı", full_record["general_warning"]),
                ("Durum", "AKTİF" if full_record["active"] else "PASİF"),
                ("Oluşturma", full_record["created_at"]),
                ("Son Güncelleme", full_record["updated_at"]),
            ]
            contacts = self.service.list_customer_contacts(int(record["id"]))
            tables.append(
                {
                    "title": "İlgili Kişiler",
                    "headers": ["Ad", "Görev", "Telefon", "E-posta"],
                    "rows": [
                        [
                            contact.get("name"),
                            contact.get("role"),
                            contact.get("phone1"),
                            contact.get("email"),
                        ]
                        for contact in contacts
                    ],
                }
            )
            addresses = self.service.list_customer_addresses(int(record["id"]))
            tables.append(
                {
                    "title": "Teslim / Sevk Adresleri",
                    "headers": ["Ad", "Şehir", "İlçe", "Adres", "Vergi"],
                    "rows": [
                        [
                            address.get("name"),
                            address.get("city"),
                            address.get("district"),
                            address.get("address"),
                            f"{address.get('tax_office') or ''} {address.get('tax_number') or ''}".strip(),
                        ]
                        for address in addresses
                    ],
                }
            )
        elif self.view == "orders":
            progress = self.service.order_progress(int(record["id"]))
            order_lines = progress["lines"]
            tables.append(
                {
                    "title": "Sipariş Satırları",
                    "headers": [
                        "SATIR", "PROFİL KOD", "PROFİL AD", "BOY", "YÜZEY",
                        "ALAŞIM", "SERTLİK", "SİP. ADET", "SİP. KG",
                        "ÜRETİM KG", "SEVK KG", "KALAN KG", "BİRİM FİYAT",
                        "TUTAR", "DURUM",
                    ],
                    "rows": [
                        [
                            row.get("line_no"),
                            row.get("profile_code"),
                            row.get("profile_name"),
                            self.voucher_number(row.get("production_length_mm"), 0),
                            row.get("surface"),
                            row.get("alloy"),
                            row.get("temper"),
                            self.voucher_number(row.get("ordered_quantity"), 0),
                            self.voucher_number(row.get("ordered_kg"), 2),
                            self.voucher_number(row.get("produced_kg"), 2),
                            self.voucher_number(row.get("shipped_kg"), 2),
                            self.voucher_number(row.get("shipping_remaining_kg"), 2),
                            self.voucher_number(row.get("unit_price"), 4),
                            self.voucher_number(
                                float(row.get("ordered_kg") or 0)
                                * float(row.get("unit_price") or 0),
                                2,
                            ),
                            row.get("status"),
                        ]
                        for row in order_lines
                    ],
                }
            )
            production_rows: list[list[Any]] = []
            package_rows: list[list[Any]] = []
            for row in order_lines:
                line_id = int(row["id"])
                for order in self.service.production_orders_for_line(line_id):
                    production_rows.append([
                        order.get("production_order_no"),
                        row.get("line_no"),
                        row.get("profile_code"),
                        order.get("route_code"),
                        self.voucher_number(order.get("planned_quantity"), 0),
                        self.voucher_number(order.get("planned_kg"), 2),
                        order.get("completed_work_orders"),
                        order.get("work_order_count"),
                        order.get("status"),
                    ])
            for row in self.service.list_packages():
                if str(record.get("order_no") or "") in str(row.get("order_nos") or ""):
                    package_rows.append([
                        row.get("package_no"),
                        row.get("profile_codes"),
                        self.voucher_number(row.get("net_kg"), 2),
                        self.voucher_number(row.get("gross_kg"), 2),
                        row.get("warehouse_name"),
                        row.get("status"),
                    ])
            tables.append(
                {
                    "title": "Üretim Emirleri",
                    "headers": [
                        "ÜRETİM EMRİ", "SATIR", "PROFİL", "ROTA", "PLAN ADET",
                        "PLAN KG", "BİTEN İŞ", "TOPLAM İŞ", "DURUM",
                    ],
                    "rows": production_rows,
                }
            )
            tables.append(
                {
                    "title": "Paketler",
                    "headers": [
                        "PAKET NO", "PROFİL", "NET KG", "BRÜT KG", "AMBAR", "DURUM",
                    ],
                    "rows": package_rows,
                }
            )
            stats = [
                [
                    "SİPARİŞ",
                    self.voucher_number(
                        sum(float(row.get("ordered_quantity") or 0) for row in order_lines), 0
                    ),
                    self.voucher_number(
                        sum(float(row.get("ordered_kg") or 0) for row in order_lines), 2
                    ),
                ],
                [
                    "ÜRETİM",
                    self.voucher_number(
                        sum(float(row.get("produced_quantity") or 0) for row in order_lines), 0
                    ),
                    self.voucher_number(
                        sum(float(row.get("produced_kg") or 0) for row in order_lines), 2
                    ),
                ],
                [
                    "SEVK",
                    self.voucher_number(
                        sum(float(row.get("shipped_quantity") or 0) for row in order_lines), 0
                    ),
                    self.voucher_number(
                        sum(float(row.get("shipped_kg") or 0) for row in order_lines), 2
                    ),
                ],
                [
                    "KALAN",
                    "",
                    self.voucher_number(
                        sum(
                            float(row.get("shipping_remaining_kg") or 0)
                            for row in order_lines
                        ),
                        2,
                    ),
                ],
                ["SATIR", str(len(order_lines)), ""],
                ["PAKET", str(len(package_rows)), ""],
            ]
        elif self.view == "purchase_requests":
            tables.append(
                {
                    "title": "Talep Satırları",
                    "headers": [
                        "Stok",
                        "Ambar",
                        "Talep",
                        "Birim",
                        "Onay",
                        "Sipariş",
                        "Durum",
                    ],
                    "rows": [
                        [
                            f"{row.get('stock_code')} — {row.get('stock_name')}",
                            row.get("warehouse_name"),
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("unit"),
                            f"{float(row.get('approved_quantity') or 0):.3f}",
                            f"{float(row.get('ordered_quantity') or 0):.3f}",
                            row.get("status"),
                        ]
                        for row in self.service.list_purchase_request_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "purchase_orders":
            tables.append(
                {
                    "title": "Sipariş Satırları",
                    "headers": [
                        "Stok",
                        "Ambar",
                        "Miktar",
                        "Birim",
                        "Teslim",
                        "Birim Fiyat",
                        "Durum",
                    ],
                    "rows": [
                        [
                            f"{row.get('stock_code')} — {row.get('stock_name')}",
                            row.get("warehouse_name"),
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("unit"),
                            f"{float(row.get('received_quantity') or 0):.3f}",
                            f"{float(row.get('unit_price') or 0):.4f}",
                            row.get("status"),
                        ]
                        for row in self.service.list_purchase_order_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "stock_documents":
            tables.append(
                {
                    "title": "Fiş Satırları",
                    "headers": ["No", "Stok", "Miktar", "Birim", "Lot", "Not"],
                    "rows": [
                        [
                            row.get("line_no"),
                            f"{row.get('stock_code')} — {row.get('stock_name')}",
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("unit"),
                            row.get("lot_no") or "—",
                            row.get("note") or "—",
                        ]
                        for row in self.service.list_stock_document_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "unit_sets":
            tables.append(
                {
                    "title": "Birim Satırları",
                    "headers": ["Birim", "Çarpan", "Açıklama"],
                    "rows": [
                        [
                            row.get("unit_code"),
                            f"{float(row.get('factor') or 0):.6f}",
                            row.get("description") or "—",
                        ]
                        for row in self.service.list_unit_set_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "recipes":
            fields.append(("Hammadde Stok", record.get("raw_material_code") or "TANIMSIZ"))
            tables.append(
                {
                    "title": "Reçete Operasyonları",
                    "headers": [
                        "Sıra",
                        "Operasyon",
                        "İstasyon",
                        "Stok",
                        "Oran",
                        "Katsayı",
                        "Ambar",
                    ],
                    "rows": [
                        [
                            row.get("route_sequence_no"),
                            row.get("operation_name"),
                            row.get("station_name"),
                            row.get("stock_code") or "profil stok kartı",
                            f"{row.get('numerator')}/{row.get('denominator')}",
                            (
                                f"{(float(row.get('numerator') or 1) / float(row.get('denominator') or 1)):.4f}"
                                if float(row.get("denominator") or 1)
                                else "1.0000"
                            ),
                            row.get("warehouse_code"),
                        ]
                        for row in self.service.list_recipe_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "sales_quotes":
            fields.extend(
                [
                    ("Döviz", record.get("currency")),
                    ("Kur", record.get("exchange_rate")),
                ]
            )
            tables.append(
                {
                    "title": "Teklif Satırları",
                    "headers": [
                        "No",
                        "Profil",
                        "Boy",
                        "Adet",
                        "Kg",
                        "Birim Fiyat",
                        "Tutar",
                    ],
                    "rows": [
                        [
                            row.get("line_no"),
                            row.get("profile_code"),
                            f"{float(row.get('length_mm') or 0):.0f}",
                            f"{float(row.get('quantity') or 0):.0f}",
                            f"{float(row.get('kg') or 0):.3f}",
                            f"{float(row.get('unit_price') or 0):.4f}",
                            f"{float(row.get('line_amount') or 0):.2f}",
                        ]
                        for row in self.service.list_sales_quote_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "work_orders":
            entries = self.service.list_production_entries(int(record["id"]))
            movements = self.service.list_stock_movements(work_order_id=int(record["id"]))
            siblings = self.service.work_orders_for_production(
                int(record.get("production_order_id") or 0)
            )
            tables.append(
                {
                    "title": "Üretim Fişleri",
                    "headers": [
                        "TARİH", "TİP", "OPERATÖR", "VARDİYA", "LOT / ŞARJ",
                        "ADET", "BRÜT KG", "NET KG", "FİRE KG", "METRE",
                    ],
                    "rows": [
                        [
                            self.format_value("created_at", row.get("created_at")),
                            row.get("entry_type"),
                            row.get("operator_username"),
                            row.get("shift"),
                            row.get("lot_no") or "—",
                            self.voucher_number(row.get("quantity"), 0),
                            self.voucher_number(row.get("gross_kg"), 2),
                            self.voucher_number(row.get("net_kg"), 2),
                            self.voucher_number(row.get("scrap_kg"), 2),
                            self.voucher_number(row.get("metre"), 2),
                        ]
                        for row in entries
                    ],
                }
            )
            tables.append(
                {
                    "title": "Ambar Hareketleri",
                    "headers": [
                        "TARİH", "AMBAR", "STOK KOD", "HAREKET", "YÖN",
                        "MİKTAR", "LOT / ŞARJ", "BELGE",
                    ],
                    "rows": [
                        [
                            self.format_value("movement_at", row.get("movement_at")),
                            row.get("warehouse_name"),
                            row.get("stock_code"),
                            row.get("movement_type"),
                            "GİRİŞ" if int(row.get("direction") or 0) > 0 else "ÇIKIŞ",
                            self.voucher_number(row.get("quantity"), 3),
                            row.get("lot_no") or "—",
                            row.get("document_no") or "—",
                        ]
                        for row in movements
                    ],
                }
            )
            tables.append(
                {
                    "title": "Rota Adımları",
                    "headers": [
                        "İŞ EMRİ", "SIRA", "OPERASYON", "İSTASYON", "PLAN ADET",
                        "PLAN KG", "ÜRETİLEN KG", "HURDA KG", "DURUM",
                    ],
                    "rows": [
                        [
                            row.get("work_order_no"),
                            row.get("sequence_no"),
                            row.get("operation"),
                            row.get("station"),
                            self.voucher_number(row.get("planned_quantity"), 0),
                            self.voucher_number(row.get("planned_kg"), 2),
                            self.voucher_number(row.get("produced_kg"), 2),
                            self.voucher_number(row.get("scrap_kg"), 2),
                            row.get("status"),
                        ]
                        for row in siblings
                    ],
                }
            )
        elif self.view == "dies":
            fields.extend(
                [
                    ("Figür", record.get("figure_count")),
                    ("Tenefer No", record.get("tenefer_no")),
                    ("Tenefer Tip", record.get("tenefer_type")),
                    (
                        "Kullanım (m)",
                        f"{float(record.get('tenefer_used_m') or 0):.1f} / "
                        f"{float(record.get('tenefer_limit_m') or 0):.1f}",
                    ),
                    ("Basılan kg", f"{float(record.get('used_kg') or 0):.3f}"),
                    (
                        "Konum",
                        record.get("external_label") or record.get("location"),
                    ),
                ]
            )
            tables.append(
                {
                    "title": "Kalıp Hareketleri",
                    "headers": [
                        "Tarih",
                        "Tür",
                        "Firma",
                        "Nereden",
                        "Nereye",
                        "Metre",
                        "Kg",
                        "Not",
                    ],
                    "rows": [
                        [
                            row.get("movement_at"),
                            row.get("movement_type"),
                            row.get("company") or "—",
                            row.get("location_from"),
                            row.get("location_to"),
                            f"{float(row.get('metre') or 0):.1f}"
                            if float(row.get("metre") or 0) > 0
                            else "—",
                            f"{float(row.get('net_kg') or 0):.3f}"
                            if float(row.get("net_kg") or 0) > 0
                            else "—",
                            row.get("note") or "—",
                        ]
                        for row in self.service.list_die_movements(int(record["id"]))
                    ],
                }
            )
            tenefer_docs = self.service.list_tenefer_documents(int(record["id"]))
            tables.append(
                {
                    "title": "Tenefer Belgeleri",
                    "headers": ["Tarih", "Yön", "Firma", "Belge No", "Tenefer"],
                    "rows": [
                        [
                            row.get("record_date"),
                            row.get("direction"),
                            row.get("company_name"),
                            row.get("document_no"),
                            row.get("tenefer_no") or "—",
                        ]
                        for row in tenefer_docs
                    ],
                }
            )
        elif self.view == "weighing_lists":
            tables.append(
                {
                    "title": "Bağlı Paketler",
                    "headers": ["Paket No", "Profiller", "Net kg", "Durum"],
                    "rows": [
                        [
                            row.get("package_no"),
                            row.get("profile_codes"),
                            f"{float(row.get('net_kg') or 0):.3f}",
                            row.get("status"),
                        ]
                        for row in self.service.packages_for_weighing_list(int(record["id"]))
                    ],
                }
            )
        elif self.view == "profiles":
            profile_id = int(record["id"])
            tables.append(
                {
                    "title": "Bağlı Kalıplar",
                    "headers": [
                        "Kalıp Kod", "Yedek", "Figür", "Tenefer",
                        "Kalan m", "Basılan kg", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("die_code"),
                            row.get("spare_no"),
                            row.get("figure_count"),
                            row.get("tenefer_no"),
                            f"{float(row.get('tenefer_remaining_m') or 0):.1f}",
                            f"{float(row.get('used_kg') or 0):.3f}",
                            row.get("status"),
                        ]
                        for row in self.service.list_dies(profile_id)
                    ],
                }
            )
            route_rows: list[list[Any]] = []
            for route in self.service.list_routes(profile_id):
                for step in self.service.list_route_steps(int(route["id"])):
                    route_rows.append(
                        [
                            route.get("code"),
                            step.get("sequence_no"),
                            step.get("operation"),
                            step.get("default_station"),
                            step.get("input_warehouse_code"),
                            step.get("output_warehouse_code"),
                        ]
                    )
            tables.append(
                {
                    "title": "Rota Adımları",
                    "headers": [
                        "Rota", "Sıra", "Operasyon", "İstasyon",
                        "Giriş Ambar", "Çıkış Ambar",
                    ],
                    "rows": route_rows,
                }
            )
            tables.append(
                {
                    "title": "Bağlı Reçeteler",
                    "headers": ["Kod", "Ad", "Rota", "Operasyon", "Durum"],
                    "rows": [
                        [
                            row.get("recipe_code"),
                            row.get("recipe_name"),
                            row.get("route_code"),
                            row.get("line_count"),
                            "AKTİF" if row.get("active") else "PASİF",
                        ]
                        for row in self.service.list_recipes(profile_id)
                    ],
                }
            )
        elif self.view == "shipments":
            tables.append(
                {
                    "title": "Sevk Edilen Paketler",
                    "headers": [
                        "Paket No", "Sipariş", "Profil",
                        "Net kg", "Brüt kg", "Ambar", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("package_no"),
                            row.get("order_nos"),
                            row.get("profile_codes"),
                            f"{float(row.get('net_kg') or 0):.3f}",
                            f"{float(row.get('gross_kg') or 0):.3f}",
                            row.get("warehouse_name"),
                            row.get("status"),
                        ]
                        for row in self.service.packages_for_shipment(int(record["id"]))
                    ],
                }
            )
        elif self.view == "packages":
            tables.append(
                {
                    "title": "Paket İçeriği",
                    "headers": [
                        "Sipariş", "Satır", "Profil", "Boy (mm)",
                        "Lot", "Adet", "Net kg", "Brüt kg",
                    ],
                    "rows": [
                        [
                            row.get("order_no"),
                            row.get("line_no"),
                            row.get("profile_code"),
                            row.get("production_length_mm"),
                            row.get("lot_no") or "—",
                            f"{float(row.get('quantity') or 0):.0f}",
                            f"{float(row.get('net_kg') or 0):.3f}",
                            f"{float(row.get('gross_kg') or 0):.3f}",
                        ]
                        for row in self.service.list_package_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "goods_receipts":
            tables.append(
                {
                    "title": "Mal Kabul Satırları",
                    "headers": [
                        "Satır", "Stok", "Ambar", "Sipariş Miktarı",
                        "Kabul Miktarı", "Birim", "Lot", "Birim Fiyat",
                    ],
                    "rows": [
                        [
                            row.get("line_no"),
                            f"{row.get('stock_code')} — {row.get('stock_name')}",
                            row.get("warehouse_name"),
                            f"{float(row.get('ordered_quantity') or 0):.3f}",
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("unit"),
                            row.get("lot_no") or "—",
                            f"{float(row.get('unit_price') or 0):.4f}",
                        ]
                        for row in self.service.list_goods_receipt_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "production":
            fields, production_tables, stats = self.production_order_voucher(record)
            tables.extend(production_tables)
        elif self.view == "planning":
            tables.append(
                {
                    "title": "Üretim Emirleri (Partiler)",
                    "headers": [
                        "Üretim Emri", "Rota", "Plan Adet", "Plan kg",
                        "Biten İş", "Toplam İş", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("production_order_no"),
                            row.get("route_code"),
                            f"{float(row.get('planned_quantity') or 0):.0f}",
                            f"{float(row.get('planned_kg') or 0):.3f}",
                            row.get("completed_work_orders"),
                            row.get("work_order_count"),
                            row.get("status"),
                        ]
                        for row in self.service.production_orders_for_line(int(record["id"]))
                    ],
                }
            )
        elif self.view == "price_lists":
            tables.append(
                {
                    "title": "Fiyat Satırları",
                    "headers": [
                        "Profil", "Yüzey", "Alaşım", "Sertlik",
                        "Birim Fiyat", "Döviz",
                    ],
                    "rows": [
                        [
                            row.get("profile_code"),
                            row.get("surface") or "—",
                            row.get("alloy") or "—",
                            row.get("temper") or "—",
                            f"{float(row.get('unit_price') or 0):.4f}",
                            row.get("currency"),
                        ]
                        for row in self.service.list_sales_price_list_lines(int(record["id"]))
                    ],
                }
            )
        elif self.view == "property_sets":
            set_id = int(record["id"])
            tables.append(
                {
                    "title": "Özellik Değerleri",
                    "headers": ["Değer Kod", "Değer", "Durum"],
                    "rows": [
                        [
                            row.get("code"),
                            row.get("name"),
                            "AKTİF" if row.get("active") else "PASİF",
                        ]
                        for row in self.service.list_property_values()
                        if int(row.get("property_set_id") or 0) == set_id
                    ],
                }
            )
        elif self.view == "stock_items":
            stock_id = int(record["id"])
            stock_code = str(record.get("code") or "")
            tables.append(
                {
                    "title": "Ambar Bakiyeleri",
                    "headers": ["Ambar", "Lot / Şarj", "Bakiye", "Birim", "Son Hareket"],
                    "rows": [
                        [
                            row.get("warehouse_name"),
                            row.get("lot_no") or "—",
                            f"{float(row.get('balance') or 0):.3f}",
                            row.get("unit"),
                            row.get("last_movement_at"),
                        ]
                        for row in self.service.list_warehouse_balances()
                        if str(row.get("stock_code") or "") == stock_code
                    ],
                }
            )
            tables.append(
                {
                    "title": "Son Stok Hareketleri",
                    "headers": ["Tarih", "Ambar", "Hareket", "Yön", "Miktar", "Lot", "Belge"],
                    "rows": [
                        [
                            row.get("movement_at"),
                            row.get("warehouse_name"),
                            row.get("movement_type"),
                            "+" if int(row.get("direction") or 0) > 0 else "-",
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("lot_no") or "—",
                            row.get("document_no") or "—",
                        ]
                        for row in self.service.list_stock_movements(stock_item_id=stock_id)[:50]
                    ],
                }
            )
        elif self.view == "invoices":
            shipment_id = int(record.get("shipment_id") or 0)
            if shipment_id:
                tables.append(
                    {
                        "title": "Faturaya Konu Paketler",
                        "headers": [
                            "Paket No", "Sipariş", "Profil", "Net kg", "Brüt kg",
                        ],
                        "rows": [
                            [
                                row.get("package_no"),
                                row.get("order_nos"),
                                row.get("profile_codes"),
                                f"{float(row.get('net_kg') or 0):.3f}",
                                f"{float(row.get('gross_kg') or 0):.3f}",
                            ]
                            for row in self.service.packages_for_shipment(shipment_id)
                        ],
                    }
                )
        elif self.view == "order_lines":
            line_id = int(record["id"])
            tables.append(
                {
                    "title": "Satır Ambar Hareketleri",
                    "headers": [
                        "Tarih", "Ambar", "Hareket", "Yön",
                        "Miktar", "Lot", "İş Emri",
                    ],
                    "rows": [
                        [
                            row.get("movement_at"),
                            row.get("warehouse_name"),
                            row.get("movement_type"),
                            "+" if int(row.get("direction") or 0) > 0 else "-",
                            f"{float(row.get('quantity') or 0):.3f}",
                            row.get("lot_no") or "—",
                            row.get("work_order_no") or "—",
                        ]
                        for row in self.service.list_stock_movements(
                            sales_order_line_id=line_id
                        )
                    ],
                }
            )
            tables.append(
                {
                    "title": "Üretim Emirleri",
                    "headers": [
                        "Üretim Emri", "Rota", "Plan Adet", "Plan kg",
                        "Biten İş", "Toplam İş", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("production_order_no"),
                            row.get("route_code"),
                            f"{float(row.get('planned_quantity') or 0):.0f}",
                            f"{float(row.get('planned_kg') or 0):.3f}",
                            row.get("completed_work_orders"),
                            row.get("work_order_count"),
                            row.get("status"),
                        ]
                        for row in self.service.production_orders_for_line(line_id)
                    ],
                }
            )
        elif self.view == "maintenance_instructions":
            instruction_name = str(record.get("name") or "")
            tables.append(
                {
                    "title": "Bu Talimattan Açılan Bakım Emirleri",
                    "headers": [
                        "Fiş No", "Tip", "Planlanan Baş.", "Planlanan Bit.",
                        "Operasyon", "İstasyon", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("order_no"),
                            row.get("order_type"),
                            row.get("planned_start"),
                            row.get("planned_end"),
                            row.get("operation"),
                            row.get("station"),
                            row.get("status"),
                        ]
                        for row in self.service.list_maintenance_orders()
                        if str(row.get("name") or "") == instruction_name
                    ],
                }
            )
        elif self.view == "suppliers":
            supplier_name = str(record.get("name") or "")
            tables.append(
                {
                    "title": "Satın Alma Siparişleri",
                    "headers": [
                        "Sipariş No", "Tarih", "Teslim", "Satır",
                        "Miktar", "Teslim Alınan", "Toplam", "Durum",
                    ],
                    "rows": [
                        [
                            row.get("purchase_order_no"),
                            row.get("order_date"),
                            row.get("delivery_date"),
                            row.get("line_count"),
                            f"{float(row.get('ordered_quantity') or 0):.3f}",
                            f"{float(row.get('received_quantity') or 0):.3f}",
                            f"{float(row.get('total_amount') or 0):.2f}",
                            row.get("status"),
                        ]
                        for row in self.service.list_purchase_orders()
                        if str(row.get("supplier_name") or "") == supplier_name
                    ],
                }
            )

        RecordDetailsDialog(
            self.module,
            fields=fields,
            tables=tables,
            stats=stats if stats is not None else self.record_stat_rows(record),
            stats_headers=("DURUM", "ADET", "KG"),
            header_title=self.detail_header_title(),
            subtitle=self.record_subtitle(record),
            status=str(record.get("status") or record.get("status_display") or ""),
            parent=self,
        ).exec()


    def add_selected_attachment(self) -> None:
        record = self.selected_record()
        if record is None or self.view not in {"profiles", "dies"}:
            self.warn_select()
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF veya görsel seçin",
            "",
            "Belgeler (*.pdf *.jpg *.jpeg *.png)",
        )
        if not path:
            return
        self.service.add_attachment(
            entity_type="PROFILE" if self.view == "profiles" else "DIE",
            entity_id=int(record["id"]),
            document_type="TEKNİK BELGE",
            file_path=path,
            username=self.username,
        )
        self.refresh_data()

    def add_die_movement(self) -> None:
        record = self.selected_record()
        if record is None or self.view != "dies":
            self.warn_select()
            return
        movement, ok = QInputDialog.getItem(
            self,
            "Kalıp hareketi",
            "İşlem:",
            (
                "TENEFER GİTTİ", "TENEFER GELDİ",
                "BAKIMA GÖNDER", "BAKIMDAN GELDİ",
                "REVİZYON", "İMALATA VER", "HURDA", "KONUM DEĞİŞTİR",
            ),
            0,
            False,
        )
        if not ok:
            return
        company = ""
        new_tenefer = ""
        if movement in {
            "TENEFER GİTTİ", "TENEFER GELDİ", "BAKIMA GÖNDER", "BAKIMDAN GELDİ", "REVİZYON",
        }:
            company, accepted = QInputDialog.getText(
                self, "Firma", "Tenefer / bakım / imalat firması:"
            )
            if not accepted:
                return
        if movement == "TENEFER GELDİ":
            current = str(record.get("tenefer_no") or "0")
            next_no = str(int(current) + 1) if current.isdigit() else "1"
            new_tenefer, accepted = QInputDialog.getText(
                self, "Yeni tenefer no", "Dönen tenefer numarası (1, 2, 3…):",
                text=next_no,
            )
            if not accepted or not new_tenefer.strip():
                return
        location = ""
        if movement == "KONUM DEĞİŞTİR":
            location, accepted = QInputDialog.getText(
                self, "Yeni konum / raf", "Yeni konum:"
            )
            if not accepted:
                return
        try:
            if movement == "TENEFER GİTTİ":
                self.service.send_die_to_tenefer(
                    int(record["id"]), company=company, username=self.username,
                )
            elif movement == "TENEFER GELDİ":
                self.service.receive_die_from_tenefer(
                    int(record["id"]),
                    company=company,
                    new_tenefer_no=new_tenefer,
                    username=self.username,
                )
            else:
                self.service.record_die_movement(
                    int(record["id"]),
                    movement_type=movement,
                    company=company,
                    location_to=location,
                    username=self.username,
                )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kalıp hareketi", str(error))
            return
        self.refresh_data()

    def create_invoice_from_receipt(self) -> None:
        record = self.selected_record()
        if record is None or self.view != "goods_receipts":
            self.warn_select()
            return
        try:
            invoice_id = self.service.create_purchase_invoice_from_receipt(
                int(record["id"]), username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Fatura oluşturulamadı", str(error))
            return
        self.refresh_data()
        QMessageBox.information(self, "Fatura oluşturuldu", f"Satın alma faturası kaydı #{invoice_id} açıldı.")

    def complete_eloksal_hanging(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            self.service.complete_eloksal_step(
                int(record["id"]), step="ELOKSAL", username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Eloksal tamamlanamadı", str(error))
            return
        self.refresh_data()

    def complete_eloksal_stripping(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        qty, ok = QInputDialog.getDouble(self, "Sökme adet", "Adet:", 0, 0, 1_000_000, 0)
        if not ok:
            return
        kg, ok = QInputDialog.getDouble(self, "Sökme kg", "KG:", 0, 0, 1_000_000, 3)
        if not ok:
            return
        scrap_qty, ok = QInputDialog.getDouble(self, "Hurda adet", "Adet:", 0, 0, 1_000_000, 0)
        if not ok:
            return
        scrap_kg, ok = QInputDialog.getDouble(self, "Hurda kg", "KG:", 0, 0, 1_000_000, 3)
        if not ok:
            return
        try:
            self.service.complete_eloksal_step(
                int(record["id"]),
                step="SÖKME",
                quantity=qty,
                kg=kg,
                scrap_quantity=scrap_qty,
                scrap_kg=scrap_kg,
                username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Sökme tamamlanamadı", str(error))
            return
        self.refresh_data()

    def close_selected_downtime(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            self.service.close_downtime_event(int(record["id"]), username=self.username)
        except ValueError as error:
            QMessageBox.warning(self, "Duruş kapatılamadı", str(error))
            return
        self.refresh_data()

    def select_purchase_quote_row(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            self.service.select_purchase_quote(int(record["id"]), username=self.username)
        except ValueError as error:
            QMessageBox.warning(self, "Teklif seçilemedi", str(error))
            return
        self.refresh_data()

    def open_die_from_movement(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        token = str(record.get("die_code") or "")
        self.navigate_to("Kalıphane", "Kalıp Kartları", search=token)

    def open_entry_work_order(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        token = str(record.get("work_order_no") or "")
        self.navigate_to("Üretim", "İş Emirleri", search=token)

    def edit_maintenance_instruction(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        dialog = MaintenanceInstructionDialog(self.service, self, record)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_maintenance_instruction(
                int(record["id"]), username=self.username, **dialog.values()
            )
        except ValueError as error:
            QMessageBox.warning(self, "Bakım talimatı", str(error))
            return
        self.refresh_data()

    def toggle_maintenance_instruction(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        target_active = not bool(record.get("active"))
        label = "aktifleştirmek" if target_active else "pasife almak"
        answer = QMessageBox.question(
            self,
            "Bakım talimatı",
            f"{record.get('instruction_no') or ''} — {record.get('name') or ''}\n"
            f"talimatını {label} istediğinize emin misiniz?",
        )
        if answer != QMessageBox.Yes:
            return
        self.service.set_maintenance_instruction_active(
            int(record["id"]), target_active, username=self.username
        )
        self.refresh_data()

    def open_order_from_instruction(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        try:
            self.service.create_maintenance_order_from_instruction(
                int(record["id"]), username=self.username
            )
        except ValueError as error:
            QMessageBox.warning(self, "Bakım emri", str(error))
            return
        QMessageBox.information(
            self,
            "Bakım emri açıldı",
            f"{record.get('name') or ''} talimatı için bakım emri oluşturuldu.",
        )
        self.navigate_to("Bakım", "Bakım Emirleri")

    def open_order_line_order(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        token = str(record.get("order_no") or "")
        self.navigate_to("Satış", "Satış Siparişleri", search=token)

    def open_order_line_profile(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        token = str(record.get("profile_code") or "")
        self.navigate_to("Kalıphane", "Profil Kartları", search=token)

    def change_priority(self) -> None:
        records = self.selected_records()
        if not records or self.view != "work_orders":
            self.warn_select()
            return
        current = int(records[0].get("priority") or 100)
        priority, ok = QInputDialog.getInt(
            self, "İş emri önceliği", "Öncelik (1 en yüksek):", current, 1, 999
        )
        if not ok:
            return
        self.service.update_work_order_priority(
            [int(record["id"]) for record in records],
            priority,
            username=self.username,
        )
        self.refresh_data()

    def create_shipment_from_list(self) -> None:
        record = self.selected_record()
        if record is None or self.view != "weighing_lists":
            self.warn_select()
            return
        packages = self.service.packages_for_weighing_list(int(record["id"]))
        ready = [
            row for row in packages if str(row.get("status") or "") == "SEVK HAZIR"
        ]
        if not ready:
            QMessageBox.information(
                self,
                "Sevk hazır paket yok",
                "Bu çeki listesinde sevk edilecek SEVK HAZIR paket bulunmuyor.",
            )
            return
        dialog = ShipmentDialog(packages, self)
        dialog.table.selectAll()
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_shipment(
                dialog.selected_package_ids(),
                shipment_date=dialog.shipment_date.date().toString("yyyy-MM-dd"),
                vehicle_plate=dialog.plate.text(),
                weighing_list_id=int(record["id"]),
                username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "İrsaliye oluşturulamadı", str(error))
            return
        self.refresh_data()

    def create_weighing_list_from_packages(self) -> None:
        if self.view != "packages":
            self.warn_select()
            return
        selected = self.selected_records()
        packages = selected if selected else self.service.list_packages()
        dialog = WeighingListDialog(packages, self)
        if not dialog.packages:
            QMessageBox.information(
                self,
                "Sevk Ön paketi yok",
                "Çeki listesine alınacak SEVK ÖN paketi bulunmuyor.",
            )
            return
        if selected:
            dialog.table.selectAll()
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_weighing_list(
                dialog.selected_package_ids(),
                note=dialog.note.text(),
                username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Çeki listesi oluşturulamadı", str(error))
            return
        self.refresh_data()

    def create_shipment_from_packages(self) -> None:
        if self.view != "packages":
            self.warn_select()
            return
        selected = self.selected_records()
        packages = selected if selected else self.service.list_packages()
        dialog = ShipmentDialog(packages, self)
        if not dialog.packages:
            QMessageBox.information(
                self,
                "Hazır paket yok",
                "Sevke hazır SEVK HAZIR paket bulunmuyor.",
            )
            return
        if selected:
            dialog.table.selectAll()
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_shipment(
                dialog.selected_package_ids(),
                shipment_date=dialog.shipment_date.date().toString("yyyy-MM-dd"),
                vehicle_plate=dialog.plate.text(),
                username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "İrsaliye oluşturulamadı", str(error))
            return
        self.refresh_data()

    def show_audit_history(self) -> None:
        record = self.selected_record()
        if record is None:
            self.warn_select()
            return
        entity = {
            "customers": "CUSTOMER", "stock_items": "STOCK_ITEM",
            "suppliers": "SUPPLIER", "purchase_requests": "PURCHASE_REQUEST",
            "purchase_orders": "PURCHASE_ORDER", "goods_receipts": "GOODS_RECEIPT",
            "branches": "BRANCH", "warehouses": "WAREHOUSE",
            "stock_documents": "STOCK_DOCUMENT", "unit_sets": "UNIT_SET",
            "stock_movements": "STOCK_MOVEMENT", "warehouse_balances": "STOCK_MOVEMENT",
            "profiles": "PROFILE", "dies": "DIE",
            "orders": "SALES_ORDER", "production": "PRODUCTION_ORDER",
            "planning": "SALES_ORDER_LINE", "recipes": "RECIPE",
            "work_orders": "WORK_ORDER", "packages": "PACKAGE",
            "weighing_lists": "WEIGHING_LIST", "shipments": "SHIPMENT",
            "invoices": "INVOICE",
        }[self.view]
        rows = self.service.audit_history(entity, int(record["id"]))
        table_rows = [
            [
                row.get("created_at"),
                row.get("username"),
                row.get("action"),
                row.get("after_json") or "",
            ]
            for row in rows
        ]
        RecordDetailsDialog(
            "Kayıt Bilgisi",
            fields=[
                ("Modül", self.module),
                ("Kayıt", record.get("order_no") or record.get("code") or record.get("id")),
            ],
            tables=[
                {
                    "title": "Hareket Geçmişi",
                    "headers": ["Tarih", "Kullanıcı", "İşlem", "Detay"],
                    "rows": table_rows,
                }
            ],
            parent=self,
        ).exec()


    def create_invoice(self) -> None:
        record = self.selected_record()
        if record is None or self.view != "shipments":
            self.warn_select()
            return
        dialog = InvoiceDialog(record, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_sales_invoice(
                int(record["id"]),
                invoice_date=dialog.invoice_date.date().toString("yyyy-MM-dd"),
                currency=dialog.currency.currentText(),
                exchange_rate=dialog.exchange_rate.value(),
                lme_usd_ton=dialog.lme.value(),
                premium_usd_ton=dialog.premium.value(),
                pricing_mode=dialog.mode.currentText(),
                username=self.username,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Fatura oluşturulamadı", str(error))
            return
        QMessageBox.information(self, "Fatura hazır", "Satış faturası taslak olarak oluşturuldu.")

    def table_grid_data(self) -> tuple[list[str], list[list[str]]]:
        headers = [
            self.table.horizontalHeaderItem(column).text()
            for column in range(self.table.columnCount())
            if self.table.horizontalHeaderItem(column) is not None
        ]
        rows: list[list[str]] = []
        for row in range(self.table.rowCount()):
            rows.append([
                self.table.item(row, column).text()
                if self.table.item(row, column) is not None else ""
                for column in range(self.table.columnCount())
            ])
        return headers, rows

    def export_current_table(self) -> None:
        headers, rows = self.table_grid_data()
        if not headers:
            QMessageBox.information(self, "Liste boş", "Aktarılacak kayıt bulunamadı.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Listeyi Excel'e aktar", f"{self.module}.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        from reports.grid_exporter import export_grid_excel

        export_grid_excel(
            headers=headers,
            rows=rows,
            destination=path,
            title=f"RIGEL COST PRO — {self.module}",
            subtitle=(
                f"{self.date_from.date().toString('dd.MM.yyyy')} — "
                f"{self.date_to.date().toString('dd.MM.yyyy')}  |  "
                f"Ambar: {self.warehouse_filter.currentText()}"
            ),
        )
        QMessageBox.information(self, "Excel hazır", f"Dosya kaydedildi:\n{path}")

    def export_current_table_pdf(self) -> None:
        headers, rows = self.table_grid_data()
        if not headers:
            QMessageBox.information(self, "Liste boş", "Aktarılacak kayıt bulunamadı.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Listeyi PDF'e aktar", f"{self.module}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        from reports.grid_exporter import export_grid_pdf

        export_grid_pdf(
            headers=headers,
            rows=rows,
            destination=path,
            title=f"RIGEL COST PRO — {self.module}",
            subtitle=(
                f"{self.date_from.date().toString('dd.MM.yyyy')} — "
                f"{self.date_to.date().toString('dd.MM.yyyy')}  |  "
                f"Ambar: {self.warehouse_filter.currentText()}"
            ),
            landscape_mode=len(headers) > 8,
        )
        QMessageBox.information(self, "PDF hazır", f"Dosya kaydedildi:\n{path}")

    def preview_current_table(self) -> None:
        headers, rows = self.table_grid_data()
        if not headers:
            QMessageBox.information(self, "Liste boş", "Yazdırılacak kayıt bulunamadı.")
            return
        from ui.document_preview import preview_grid_document

        preview_grid_document(
            self,
            title=f"RIGEL COST PRO — {self.module}",
            subtitle=(
                f"{self.date_from.date().toString('dd.MM.yyyy')} — "
                f"{self.date_to.date().toString('dd.MM.yyyy')}  |  "
                f"Ambar: {self.warehouse_filter.currentText()}  |  "
                f"{len(rows)} kayıt"
            ),
            headers=headers,
            rows=rows,
        )

    def apply_style(self) -> None:
        from ui.rigel_theme import rigel_workflow_styles
        self.setStyleSheet(rigel_workflow_styles())
