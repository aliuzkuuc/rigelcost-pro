from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QStandardPaths, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.energy import elektrik_birim_fiyat_hesapla
from models.metal import MetalCalculator
from pages.pallet import PalletCalculationPanel
from ui.corporate_theme import stylesheet


AYLAR = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)


def calculate_electricity_row(row: list[str]) -> dict[int, float]:
    breakdown = elektrik_birim_fiyat_hesapla(
        parse_number(row[1]),
        parse_number(row[2]),
        parse_number(row[3]),
        parse_number(row[5]) if str(row[5]).strip() else 1.0,
    )
    tuketim = parse_number(row[6])
    birim = breakdown["elektrik_birim_fiyat"]
    return {
        4: breakdown["elektrik_alt_toplam"],
        7: birim,
        8: birim * tuketim,
    }


def parse_number(value: str) -> float:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    elif "." in text:
        whole, decimals = text.split(".", 1)
        if whole and len(decimals) == 3:
            text = whole + decimals
    try:
        return max(0.0, float(text))
    except ValueError:
        return 0.0


def format_number(value: float, decimals: int = 2) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


class DetailTable(QWidget):
    """Satır eklenebilen ve satır toplamını otomatik hesaplayan tablo."""

    total_changed = Signal(float)

    def __init__(
        self,
        *,
        description: str,
        headers: list[str],
        calculated_columns: set[int],
        total_column: int,
        row_calculator: Callable[[list[str]], dict[int, float]],
        combo_columns: dict[int, list[str]] | None = None,
        currency_column: int | None = None,
        rate_column: int | None = None,
        usd_rate: float = 0.0,
        eur_rate: float = 0.0,
        initial_rows: list[list[str]] | None = None,
        allow_row_changes: bool = True,
    ) -> None:
        super().__init__()
        self.headers = headers
        self.calculated_columns = calculated_columns
        self.total_column = total_column
        self.row_calculator = row_calculator
        self.combo_columns = combo_columns or {}
        self.currency_column = currency_column
        self.rate_column = rate_column
        self.usd_rate = max(0.0, float(usd_rate))
        self.eur_rate = max(0.0, float(eur_rate))
        if self.currency_column is not None:
            self.combo_columns[self.currency_column] = ["TL", "USD", "EUR"]
        self.last_total = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        note = QLabel(description)
        note.setObjectName("detailDescription")
        note.setWordWrap(True)
        layout.addWidget(note)

        button_row = QHBoxLayout()
        if allow_row_changes:
            add_button = QPushButton("SATIR EKLE")
            add_button.setObjectName("addRowButton")
            add_button.clicked.connect(
                lambda checked=False: self.add_row()
            )
            delete_button = QPushButton("SEÇİLİ SATIRI SİL")
            delete_button.setObjectName("deleteRowButton")
            delete_button.clicked.connect(self.delete_selected_row)
            button_row.addWidget(add_button)
            button_row.addWidget(delete_button)
        button_row.addStretch(1)
        self.total_label = QLabel("TOPLAM: 0,00 TL")
        self.total_label.setObjectName("detailTotal")
        button_row.addWidget(self.total_label)
        layout.addLayout(button_row)

        self.table = QTableWidget(0, len(headers))
        self.table.setObjectName("detailEntryTable")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(390)
        self.table.cellChanged.connect(self.recalculate)
        layout.addWidget(self.table, 1)

        rows = initial_rows or [[""] * len(headers)]
        for row in rows:
            self.add_row(row, recalculate=False)
        self.recalculate()

    def add_row(
        self,
        values: list[str] | None = None,
        *,
        recalculate: bool = True,
    ) -> None:
        values = list(values or [])
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column in range(len(self.headers)):
            value = values[column] if column < len(values) else ""
            if column in self.combo_columns:
                combo = QComboBox()
                combo.addItems(self.combo_columns[column])
                if value and combo.findText(value) < 0:
                    combo.addItem(value)
                if value:
                    combo.setCurrentText(value)
                elif column == self.currency_column:
                    combo.setCurrentText("TL")
                combo.currentTextChanged.connect(self.recalculate)
                self.table.setCellWidget(row, column, combo)
                continue

            item = QTableWidgetItem(value)
            if column in self.calculated_columns:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setBackground(QColor("#EDF3FA"))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        if recalculate:
            self.recalculate()

    def delete_selected_row(self, *_args: object) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self.add_row(recalculate=False)
        self.recalculate()

    def row_values(self, row: int) -> list[str]:
        values: list[str] = []
        for column in range(len(self.headers)):
            widget = self.table.cellWidget(row, column)
            if isinstance(widget, QComboBox):
                values.append(widget.currentText())
                continue
            item = self.table.item(row, column)
            values.append(item.text() if item is not None else "")
        return values

    def recalculate(self, *_args: object) -> None:
        total = 0.0
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            values = self.row_values(row)
            calculated = self.row_calculator(values)
            if self.currency_column is not None and self.rate_column is not None:
                currency = values[self.currency_column].strip().upper()
                rate = self.currency_rate(currency)
                calculated[self.rate_column] = rate
                if self.total_column in calculated:
                    calculated[self.total_column] *= rate
            for column, value in calculated.items():
                item = self.table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, column, item)
                decimals = 4 if column == self.rate_column else 2
                item.setText(format_number(value, decimals))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total += calculated.get(self.total_column, 0.0)
        self.table.blockSignals(False)
        self.last_total = total
        self.total_label.setText(f"TOPLAM: {format_number(total)} TL")
        self.total_changed.emit(total)

    def currency_rate(self, currency: str) -> float:
        if currency == "USD":
            return self.usd_rate
        if currency == "EUR":
            return self.eur_rate
        return 1.0

    def set_currency_rates(self, usd: float, eur: float) -> None:
        self.usd_rate = max(0.0, float(usd))
        self.eur_rate = max(0.0, float(eur))
        self.recalculate()

    def serializable_rows(self) -> list[list[str]]:
        return [
            self.row_values(row)
            for row in range(self.table.rowCount())
        ]

    def load_rows(self, rows: list[list[str]]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        for row in rows or [[""] * len(self.headers)]:
            self.add_row(row, recalculate=False)
        self.recalculate()


class ExpenseDetailsPage(QWidget):
    """Maliyet Ana'yı besleyen ayrıntılı gider alt sekmeleri."""

    totals_changed = Signal(dict)
    fire_parameters_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._loading = True
        self.market_usd_rate = 47.4243
        self.market_eur_rate = 54.3250
        self.build_ui()
        self.apply_style()
        self.load_data()
        self._loading = False
        self.pallet_panel.recalculate()
        self.recalculate_fire()
        self.emit_totals()

    def build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("expensePageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("expenseDetailsContainer")
        container.setMinimumHeight(850)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(22, 18, 22, 22)
        main_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("detailsHeader")
        header_layout = QVBoxLayout(header)
        title = QLabel("GİDER ALT SEKMELERİ")
        title.setObjectName("detailsTitle")
        subtitle = QLabel(
            "Buraya girilen satırların toplamı Maliyet Ana ekranına "
            "otomatik aktarılır. TL, USD veya EUR seçebilirsiniz; dövizli "
            "satırlar güncel kurla otomatik TL'ye çevrilir."
        )
        subtitle.setObjectName("detailsSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("expenseTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(650)
        main_layout.addWidget(self.tabs, 1)

        self.create_rent_tab()
        self.create_electricity_tab()
        self.create_meal_tab()
        self.create_fuel_tab()
        self.create_general_tab()
        self.create_freight_tab()
        self.create_tenefer_tab()
        self.create_die_tab()
        self.create_workflow_tab()
        self.create_depreciation_tab()
        self.create_fire_tab()
        self.create_pallet_tab()
        self.create_packaging_tab()

        self.detail_tables = {
            "yemek": self.meal_table,
            "mazot": self.fuel_table,
            "genel_gider": self.general_table,
            "nakliye": self.freight_table,
            "tenefer": self.tenefer_table,
            "kalip": self.die_table,
            "sarf": self.workflow_table,
            "amortisman": self.depreciation_table,
            "ambalaj": self.packaging_table,
        }
        for table in self.detail_tables.values():
            table.total_changed.connect(self.emit_totals)
        self.packaging_table.total_changed.connect(
            self.update_packaging_combined_total
        )
        self.pallet_panel.result_changed.connect(
            self.on_pallet_result_changed
        )
        for table in self.detail_tables.values():
            table.set_currency_rates(
                self.market_usd_rate,
                self.market_eur_rate,
            )
        self.page_scroll.setWidget(container)
        outer_layout.addWidget(self.page_scroll)

    def create_rent_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        group = QGroupBox("Bina Kirası")
        grid = QGridLayout(group)
        self.rent = self.make_spinbox(
            maximum=10_000_000_000,
        )
        self.rent_currency = QComboBox()
        self.rent_currency.addItems(["TL", "USD", "EUR"])
        self.rent_rate = self.make_spinbox(
            value=1,
            maximum=100_000,
            decimals=4,
            suffix=" TL",
            read_only=True,
        )
        self.rent_total_tl = self.make_spinbox(
            maximum=100_000_000_000,
            suffix=" TL/ay",
            read_only=True,
        )
        self.rent_note = QLineEdit()
        self.rent_note.setPlaceholderText("Bina kirası için not...")
        grid.addWidget(QLabel("Aylık kira tutarı"), 0, 0)
        grid.addWidget(self.rent, 0, 1)
        grid.addWidget(QLabel("Döviz"), 1, 0)
        grid.addWidget(self.rent_currency, 1, 1)
        grid.addWidget(QLabel("Kur"), 2, 0)
        grid.addWidget(self.rent_rate, 2, 1)
        grid.addWidget(QLabel("Toplam TL"), 3, 0)
        grid.addWidget(self.rent_total_tl, 3, 1)
        grid.addWidget(QLabel("Not"), 4, 0)
        grid.addWidget(self.rent_note, 4, 1)
        note = QLabel(
            "Bu değer sabittir; üretim miktarı değiştiğinde tutar değişmez."
        )
        note.setObjectName("detailDescription")
        note.setWordWrap(True)
        grid.addWidget(note, 5, 0, 1, 2)
        layout.addWidget(group)
        layout.addStretch(1)
        self.rent_note.textChanged.connect(self.save_data)
        self.rent.valueChanged.connect(self.update_rent_total)
        self.rent_currency.currentTextChanged.connect(self.update_rent_total)
        self.update_rent_total()
        self.tabs.addTab(tab, "Bina Kirası")

    def create_electricity_tab(self) -> None:
        self.electricity_table = DetailTable(
            description=(
                "Her ay için aktif enerji, OSB dağıtım ve iletim birim "
                "fiyatlarını (TL/kWh) girin. Alt toplam üç kalemin "
                "toplamıdır; yüzde alanına girdiğiniz oran bu toplama "
                "eklenir (örnek: %1 → birim fiyat = alt toplam × 1,01). "
                "Aylık tüketim girilirse genel toplam TL otomatik "
                "hesaplanır. Seçili ayın birim fiyatı Maliyet Ana "
                "ekranına aktarılır."
            ),
            headers=[
                "Ay",
                "Aktif Elektrik Bedeli",
                "OSB Dağıtım Bedeli",
                "İletim Bedeli",
                "Alt Toplam",
                "Yüzde (%)",
                "Aylık Tüketim",
                "Birim Fiyat",
                "Genel Toplam TL",
            ],
            calculated_columns={4, 7, 8},
            total_column=8,
            row_calculator=calculate_electricity_row,
            initial_rows=[
                [
                    month,
                    "2,40" if month == "Ocak" else "",
                    "0,30" if month == "Ocak" else "",
                    "0,24" if month == "Ocak" else "",
                    "",
                    "1",
                    "",
                    "",
                    "",
                ]
                for month in AYLAR
            ],
            allow_row_changes=False,
        )
        self.electricity_table.total_changed.connect(self.emit_totals)
        self.tabs.addTab(self.electricity_table, "Elektrik Birim Fiyatı")
        for row in range(self.electricity_table.table.rowCount()):
            item = self.electricity_table.table.item(row, 0)
            if item is not None:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setBackground(QColor("#F2F4F7"))

    def create_meal_tab(self) -> None:
        self.meal_table = DetailTable(
            description=(
                "Gündüz ve gece için günlük yemek sayısını, gün sayısını "
                "ve farklı birim fiyatları girin. Toplam = yemek sayısı × "
                "gün sayısı × birim fiyat."
            ),
            headers=[
                "Vardiya",
                "Yemek Sayısı",
                "Gün Sayısı",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {
                6: (
                    parse_number(row[1])
                    * parse_number(row[2])
                    * parse_number(row[3])
                )
            },
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
            initial_rows=[
                ["Gündüz", "", "", "", "TL", "", "", ""],
                ["Gece", "", "", "", "TL", "", "", ""],
            ],
            allow_row_changes=False,
        )
        self.tabs.addTab(self.meal_table, "Yemek")

    def create_fuel_tab(self) -> None:
        def calculate(row: list[str]) -> dict[int, float]:
            total_km = parse_number(row[1]) * parse_number(row[2])
            total = (
                total_km
                * parse_number(row[5])
                / 100
                * parse_number(row[6])
            )
            return {3: total_km, 9: total}

        self.fuel_table = DetailTable(
            description=(
                "Her araç/güzergâh için km/gün, çalışılan gün, yakıt "
                "tüketimi ve yakıt birim fiyatını girin."
            ),
            headers=[
                "Güzergâh",
                "Km/Gün",
                "Gün",
                "Toplam Km",
                "Yakıt Tipi",
                "L/100 Km",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={3, 8, 9},
            total_column=9,
            row_calculator=calculate,
            combo_columns={4: ["Motorin", "Benzin", "LPG", "Elektrik"]},
            currency_column=7,
            rate_column=8,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.fuel_table, "Araç Yakıt")

    def create_general_tab(self) -> None:
        self.general_table = DetailTable(
            description=(
                "Sabit fatura tutarını veya adet/kişi ile birim fiyatı "
                "girin. Tutar doluysa doğrudan alınır; boşsa adet/kişi × "
                "birim fiyat hesaplanır."
            ),
            headers=[
                "Tedarikçi Firma",
                "Tutar",
                "Adet/Kişi",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {
                6: (
                    parse_number(row[1])
                    if parse_number(row[1]) > 0
                    else parse_number(row[2]) * parse_number(row[3])
                )
            },
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.general_table, "Genel Gider")

    def create_freight_tab(self) -> None:
        self.freight_table = DetailTable(
            description=(
                "Tır bilgilerini girin. Toplam kg bilgi amaçlıdır; "
                "maliyet = adet × birim fiyat."
            ),
            headers=[
                "Tedarik Yeri",
                "Toplam Kg",
                "Adet",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {
                6: parse_number(row[2]) * parse_number(row[3])
            },
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.freight_table, "Nakliye")

    def create_tenefer_tab(self) -> None:
        self.tenefer_table = DetailTable(
            description="Her firma için maliyet = kg × birim fiyat.",
            headers=[
                "Firma",
                "Kg",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={4, 5},
            total_column=5,
            row_calculator=lambda row: {
                5: parse_number(row[1]) * parse_number(row[2])
            },
            currency_column=3,
            rate_column=4,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.tenefer_table, "Tenefer")

    def create_die_tab(self) -> None:
        self.die_table = DetailTable(
            description=(
                "Her kalıp için adet ve birim fiyatı girin. "
                "Toplam = adet × birim fiyat."
            ),
            headers=[
                "Firma",
                "Kalıp Bilgisi",
                "Adet",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {
                6: parse_number(row[2]) * parse_number(row[3])
            },
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.die_table, "Kalıp Maliyeti")

    def create_workflow_tab(self) -> None:
        self.workflow_table = DetailTable(
            description=(
                "Her ürün için kg/adet ve birim fiyatı girin. "
                "Toplam = kg/adet × birim fiyat × kur."
            ),
            headers=[
                "Ürün",
                "Firma",
                "Kg/Adet",
                "Birim Fiyat",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {
                6: parse_number(row[2]) * parse_number(row[3])
            },
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.workflow_table, "Fabrika İş Akışı")

    def create_depreciation_tab(self) -> None:
        self.depreciation_table = DetailTable(
            description=(
                "Yıl bilgisi kayıt amaçlıdır. Girdiğiniz makine/yatırım "
                "tutarları toplanarak Amortisman kalemine aktarılır."
            ),
            headers=["Ürün", "Yıl", "Tutar", "Döviz", "Kur", "Toplam TL", "Not"],
            calculated_columns={4, 5},
            total_column=5,
            row_calculator=lambda row: {5: parse_number(row[2])},
            currency_column=3,
            rate_column=4,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.tabs.addTab(self.depreciation_table, "Amortisman")

    def create_fire_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        inputs = QGroupBox("Fire ve Fason Parametreleri")
        grid = QGridLayout(inputs)

        self.fire_production = self.make_spinbox(
            value=200_000,
            maximum=100_000_000,
            decimals=0,
            suffix=" kg",
            read_only=True,
        )
        self.fire_lme = self.make_spinbox(
            value=3_192,
            maximum=100_000,
            suffix=" USD/ton",
        )
        self.fire_prim = self.make_spinbox(
            value=625,
            maximum=100_000,
            suffix=" USD/ton",
        )
        self.fire_usd = self.make_spinbox(
            value=47.4243,
            maximum=10_000,
            decimals=4,
            suffix=" TL",
        )
        self.fire_factory_rate = self.make_spinbox(
            value=15,
            maximum=99.99,
            suffix=" %",
        )
        self.fire_recycling_loss = self.make_spinbox(
            value=3,
            maximum=100,
            suffix=" %",
        )
        self.fire_fason = self.make_spinbox(
            value=0.25,
            maximum=100_000,
            decimals=4,
            suffix=" USD/kg",
        )

        fields = [
            ("Net üretim", self.fire_production),
            ("LME", self.fire_lme),
            ("Prim", self.fire_prim),
            ("USD/TL", self.fire_usd),
            ("Fabrika fire oranı", self.fire_factory_rate),
            ("Geri dönüşüm fire oranı", self.fire_recycling_loss),
            ("Fason kg fiyatı", self.fire_fason),
        ]
        for index, (label, field) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            grid.addWidget(QLabel(label), row, column)
            grid.addWidget(field, row, column + 1)
        layout.addWidget(inputs)

        self.fire_table = QTableWidget(1, 8)
        self.fire_table.setObjectName("fireResultTable")
        self.fire_table.setHorizontalHeaderLabels(
            [
                "Brüt Kg",
                "Net Kg",
                "Fire",
                "Geri Dönüşüm Sonrası Kg",
                "Nihai Toplam Kayıp",
                "Fason Kg Fiyat",
                "Toplam Tutar TL",
                "Not",
            ]
        )
        self.fire_table.verticalHeader().setVisible(False)
        self.fire_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.fire_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.fire_table.setMinimumHeight(120)
        for column in range(8):
            item = QTableWidgetItem("0,00" if column < 7 else "")
            if column < 7:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            self.fire_table.setItem(0, column, item)
        layout.addWidget(self.fire_table)

        self.fire_total_label = QLabel("TOPLAM FIRE-FASON: 0,00 TL")
        self.fire_total_label.setObjectName("detailTotal")
        self.fire_total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.fire_total_label)
        layout.addStretch(1)

        for field in (
            self.fire_lme,
            self.fire_prim,
            self.fire_usd,
            self.fire_factory_rate,
            self.fire_recycling_loss,
            self.fire_fason,
        ):
            field.valueChanged.connect(self.recalculate_fire)
        self.fire_table.cellChanged.connect(
            lambda row, column: self.save_data() if column == 7 else None
        )
        self.tabs.addTab(tab, "Fire-Fason")

    def create_packaging_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        automatic_group = QGroupBox(
            "Palet Hesabı'ndan Otomatik Gelen Paketleme Giderleri"
        )
        automatic_layout = QVBoxLayout(automatic_group)
        automatic_note = QLabel(
            "Bu beş satıra doğrudan veri girilmez. Değerler Palet Hesabı "
            "sekmesindeki net üretim ve birim fiyatlardan otomatik gelir."
        )
        automatic_note.setObjectName("detailDescription")
        automatic_note.setWordWrap(True)
        automatic_layout.addWidget(automatic_note)

        self.packaging_auto_table = QTableWidget(5, 5)
        self.packaging_auto_table.setObjectName("packagingAutoTable")
        self.packaging_auto_table.setHorizontalHeaderLabels(
            ["Ürün", "Miktar", "Birimi", "Birim Fiyat", "Toplam TL"]
        )
        self.packaging_auto_table.verticalHeader().setVisible(False)
        self.packaging_auto_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.packaging_auto_table.setSelectionMode(
            QAbstractItemView.NoSelection
        )
        self.packaging_auto_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        for column in range(1, 5):
            self.packaging_auto_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeToContents
            )
        self.packaging_auto_table.setMaximumHeight(205)
        for row, (product, unit) in enumerate(
            (
                ("Kereste", "M3"),
                ("Karton Köşebent", "ADET"),
                ("Şerit Çember", "METRE"),
                ("Sarma Naylon", "KG"),
                ("Streç Film", "ADET"),
            )
        ):
            values = (product, "0", unit, "0,00", "0,00")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.packaging_auto_table.setItem(row, column, item)
        automatic_layout.addWidget(self.packaging_auto_table)

        self.packaging_automatic_total = QLabel(
            "PALET HESABI TOPLAMI: 0,00 TL"
        )
        self.packaging_automatic_total.setObjectName("detailTotal")
        self.packaging_automatic_total.setAlignment(Qt.AlignRight)
        automatic_layout.addWidget(self.packaging_automatic_total)
        layout.addWidget(automatic_group)

        self.packaging_table = DetailTable(
            description=(
                "Palet Hesabı dışındaki ilave paketleme giderlerini buraya "
                "girin. Bu satırlar otomatik beş kalemin üzerine eklenir."
            ),
            headers=[
                "Ürün",
                "Firma",
                "Birimi",
                "Tutar",
                "Döviz",
                "Kur",
                "Toplam TL",
                "Not",
            ],
            calculated_columns={5, 6},
            total_column=6,
            row_calculator=lambda row: {6: parse_number(row[3])},
            combo_columns={2: ["KG", "M3", "ADET", "METRE"]},
            currency_column=4,
            rate_column=5,
            usd_rate=self.market_usd_rate,
            eur_rate=self.market_eur_rate,
        )
        self.packaging_table.table.setMinimumHeight(205)
        layout.addWidget(self.packaging_table, 1)

        self.packaging_combined_total = QLabel(
            "GENEL PAKETLEME TOPLAMI: 0,00 TL"
        )
        self.packaging_combined_total.setObjectName("detailTotal")
        self.packaging_combined_total.setAlignment(Qt.AlignRight)
        layout.addWidget(self.packaging_combined_total)
        self.tabs.addTab(tab, "Paketleme")

    def create_pallet_tab(self) -> None:
        self.pallet_panel = PalletCalculationPanel()
        self.tabs.addTab(self.pallet_panel, "Palet Hesabı")

    @staticmethod
    def make_spinbox(
        *,
        value: float = 0,
        maximum: float = 1_000_000_000,
        decimals: int = 2,
        suffix: str = "",
        read_only: bool = False,
    ) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0, maximum)
        spinbox.setDecimals(decimals)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        spinbox.setGroupSeparatorShown(True)
        spinbox.setAlignment(Qt.AlignRight)
        spinbox.setMinimumHeight(36)
        spinbox.setReadOnly(read_only)
        return spinbox

    def current_totals(self) -> dict[str, float]:
        totals = {
            "kira": self.rent_total_tl.value(),
            **{
                key: table.last_total
                for key, table in self.detail_tables.items()
            },
        }
        totals["ambalaj"] = (
            self.packaging_table.last_total
            + float(self.pallet_panel.last_result.get("toplam", 0))
        )
        totals["elektrik_birim_fiyat"] = self.electricity_unit_price()
        return totals

    def electricity_unit_price(self) -> float:
        if not hasattr(self, "electricity_table"):
            return 0.0
        month_index = date.today().month - 1
        table = self.electricity_table.table
        if month_index < 0 or month_index >= table.rowCount():
            month_index = 0
        values = self.electricity_table.row_values(month_index)
        calculated = calculate_electricity_row(values)
        if calculated.get(7, 0) > 0:
            return calculated[7]

        weighted_total = 0.0
        weighted_consumption = 0.0
        fallback_prices: list[float] = []
        for row in range(table.rowCount()):
            row_values = self.electricity_table.row_values(row)
            row_calc = calculate_electricity_row(row_values)
            birim = row_calc.get(7, 0.0)
            if birim <= 0:
                continue
            fallback_prices.append(birim)
            tuketim = parse_number(row_values[6])
            if tuketim > 0:
                weighted_total += birim * tuketim
                weighted_consumption += tuketim
        if weighted_consumption > 0:
            return weighted_total / weighted_consumption
        if fallback_prices:
            return sum(fallback_prices) / len(fallback_prices)
        return 0.0

    def currency_rate(self, currency: str) -> float:
        code = str(currency or "TL").strip().upper()
        if code == "USD":
            return self.market_usd_rate
        if code == "EUR":
            return self.market_eur_rate
        return 1.0

    def update_rent_total(self, *_args: object) -> None:
        rate = self.currency_rate(self.rent_currency.currentText())
        self.rent_rate.setValue(rate)
        self.rent_total_tl.setValue(self.rent.value() * rate)
        if hasattr(self, "detail_tables"):
            self.emit_totals()

    def update_detail_currency_rates(self) -> None:
        if not hasattr(self, "detail_tables"):
            return
        for table in self.detail_tables.values():
            table.set_currency_rates(
                self.market_usd_rate,
                self.market_eur_rate,
            )
        self.update_rent_total()

    def on_pallet_result_changed(self, result: dict) -> None:
        if hasattr(self, "packaging_auto_table"):
            self.update_packaging_summary(result)
        self.update_packaging_combined_total()
        self.emit_totals()

    def update_packaging_summary(self, result: dict[str, float]) -> None:
        rows = (
            (
                result.get("kereste_m3", 0),
                result.get("kereste_m3_fiyat", 0),
                result.get("kereste", 0),
            ),
            (
                result.get("kosebent_adedi", 0),
                result.get("kosebent_birim_fiyat", 0),
                result.get("kosebent", 0),
            ),
            (
                result.get("cember_mt", 0),
                result.get("cember_tl_mt", 0),
                result.get("cember", 0),
            ),
            (
                result.get("naylon_kg", 0),
                result.get("naylon_tl_kg", 0),
                result.get("naylon", 0),
            ),
            (
                result.get("strec_adedi", 0),
                result.get("strec_birim_fiyat", 0),
                result.get("strec", 0),
            ),
        )
        for row, (quantity, unit_price, total) in enumerate(rows):
            quantity_decimals = 5 if row == 0 else (0 if row in (1, 4) else 2)
            self.packaging_auto_table.item(row, 1).setText(
                format_number(float(quantity), quantity_decimals)
            )
            self.packaging_auto_table.item(row, 3).setText(
                format_number(float(unit_price), 4)
            )
            self.packaging_auto_table.item(row, 4).setText(
                format_number(float(total), 2)
            )
        automatic_total = float(result.get("toplam", 0))
        self.packaging_automatic_total.setText(
            f"PALET HESABI TOPLAMI: "
            f"{format_number(automatic_total)} TL"
        )

    def update_packaging_combined_total(self, *_args: object) -> None:
        if not hasattr(self, "packaging_combined_total"):
            return
        automatic_total = float(
            self.pallet_panel.last_result.get("toplam", 0)
        )
        combined = automatic_total + self.packaging_table.last_total
        self.packaging_combined_total.setText(
            f"GENEL PAKETLEME TOPLAMI: {format_number(combined)} TL"
        )

    def emit_totals(self, *_args: object) -> None:
        if not hasattr(self, "detail_tables"):
            return
        self.totals_changed.emit(self.current_totals())
        self.save_data()

    def fire_parameters(self) -> dict[str, float]:
        return {
            "lme": self.fire_lme.value(),
            "prim": self.fire_prim.value(),
            "usd": self.fire_usd.value(),
            "fire_orani": self.fire_factory_rate.value() / 100,
            "ergitme_kaybi_orani": self.fire_recycling_loss.value() / 100,
            "fason_usd_kg": self.fire_fason.value(),
        }

    def recalculate_fire(self, *_args: object) -> None:
        try:
            result = MetalCalculator().hesapla(
                self.fire_production.value(),
                self.fire_lme.value(),
                self.fire_prim.value(),
                self.fire_usd.value(),
                self.fire_factory_rate.value() / 100,
                self.fire_recycling_loss.value() / 100,
                self.fire_fason.value(),
            )
        except ValueError:
            return

        values = [
            result["billet_ihtiyaci"],
            self.fire_production.value(),
            result["fire"],
            result["geri_donusum"],
            result["ergitme"],
            result["fason_usd_kg"],
            result["fire_toplam"],
        ]
        self.fire_table.blockSignals(True)
        for column, value in enumerate(values):
            decimals = 4 if column == 5 else 2
            self.fire_table.item(0, column).setText(
                format_number(value, decimals)
            )
        self.fire_table.blockSignals(False)
        self.fire_total_label.setText(
            f"TOPLAM FIRE-FASON: "
            f"{format_number(result['fire_toplam'])} TL"
        )
        self.fire_parameters_changed.emit(self.fire_parameters())
        self.save_data()

    def set_production(self, value: float) -> None:
        self.fire_production.setValue(max(1.0, float(value)))
        self.pallet_panel.set_production(value)
        self.recalculate_fire()

    def set_market_values(
        self,
        *,
        usd: float | None = None,
        eur: float | None = None,
        lme: float | None = None,
    ) -> None:
        if usd is not None and usd > 0:
            self.market_usd_rate = float(usd)
            self.fire_usd.setValue(usd)
            self.pallet_panel.set_usd_rate(usd)
        if eur is not None and eur > 0:
            self.market_eur_rate = float(eur)
        if lme is not None and lme > 0:
            self.fire_lme.setValue(lme)
        self.update_detail_currency_rates()
        self.recalculate_fire()

    def set_usd_rate(self, value: float) -> None:
        if value > 0:
            self.market_usd_rate = float(value)
            self.fire_usd.setValue(value)
            self.pallet_panel.set_usd_rate(value)
            self.update_detail_currency_rates()

    def set_eur_rate(self, value: float) -> None:
        if value > 0:
            self.market_eur_rate = float(value)
            self.update_detail_currency_rates()

    def set_lme(self, value: float) -> None:
        if value >= 0:
            self.fire_lme.setValue(value)

    def set_prim(self, value: float) -> None:
        if value >= 0:
            self.fire_prim.setValue(value)

    def show_tab(self, title: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

    def data_path(self) -> Path:
        override = os.environ.get("RIGELCOST_DATA_DIR")
        if override:
            root = Path(override)
        else:
            root = Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.AppDataLocation
                )
            )
        return root / "expense_details.json"

    def save_data(self) -> None:
        if self._loading or not hasattr(self, "detail_tables"):
            return
        data = {
            "schema_version": 6,
            "rent": self.rent.value(),
            "rent_currency": self.rent_currency.currentText(),
            "rent_note": self.rent_note.text(),
            "tables": {
                key: table.serializable_rows()
                for key, table in self.detail_tables.items()
            },
            "elektrik": self.electricity_table.serializable_rows(),
            "fire": self.fire_parameters(),
            "fire_note": self.fire_table.item(0, 7).text(),
            "pallet": self.pallet_panel.settings(),
        }
        temp_path: Path | None = None
        try:
            path = self.data_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, path)
        except OSError:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def load_data(self) -> None:
        try:
            data = json.loads(self.data_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return

        try:
            schema_version = int(data.get("schema_version") or 1)
        except (TypeError, ValueError):
            schema_version = 1
        self.rent.setValue(parse_number(data.get("rent")))
        rent_currency = str(data.get("rent_currency") or "TL").upper()
        if self.rent_currency.findText(rent_currency) >= 0:
            self.rent_currency.setCurrentText(rent_currency)
        self.rent_note.setText(str(data.get("rent_note") or ""))
        self.pallet_panel.load_settings(data.get("pallet"))
        tables = data.get("tables") or {}
        if isinstance(tables, dict):
            for key, rows in tables.items():
                table = self.detail_tables.get(key)
                if table is not None and isinstance(rows, list):
                    rows = [row for row in rows if isinstance(row, list)]
                    if key == "yemek":
                        rows = [
                            (
                                [row[0], row[1], "1", row[2], "", ""]
                                if isinstance(row, list) and len(row) == 4
                                else row
                            )
                            for row in rows
                        ]
                    if key == "ambalaj" and schema_version < 4:
                        rows = [
                            row
                            for row in rows
                            if not self.is_legacy_automatic_packaging_row(row)
                        ]
                    if key == "kalip" and schema_version < 3:
                        migrated_rows = []
                        for row in rows:
                            if not isinstance(row, list) or len(row) < 4:
                                migrated_rows.append(row)
                                continue
                            quantity = parse_number(row[2])
                            old_total = parse_number(row[3])
                            quantity_text = row[2]
                            if quantity <= 0 and old_total > 0:
                                quantity = 1
                                quantity_text = "1"
                            unit_price = (
                                old_total / quantity
                                if quantity > 0
                                else old_total
                            )
                            migrated_rows.append(
                                [
                                    row[0],
                                    row[1],
                                    quantity_text,
                                    format_number(unit_price),
                                    "",
                                    "",
                                ]
                            )
                        rows = migrated_rows
                    if schema_version < 5 and table.currency_column is not None:
                        migrated_currency_rows = []
                        for row in rows:
                            values = list(row)
                            insert_at = table.currency_column
                            if len(values) <= insert_at:
                                values.extend(
                                    [""] * (insert_at + 1 - len(values))
                                )
                            values[insert_at:insert_at] = ["TL", ""]
                            migrated_currency_rows.append(values)
                        rows = migrated_currency_rows
                    table.load_rows(rows)

        electricity_rows = data.get("elektrik")
        if isinstance(electricity_rows, list) and hasattr(self, "electricity_table"):
            self.electricity_table.load_rows(
                [row for row in electricity_rows if isinstance(row, list)]
            )

        fire = data.get("fire") or {}
        if isinstance(fire, dict):
            self.fire_lme.setValue(
                parse_number(fire.get("lme") or 3_192)
            )
            self.fire_prim.setValue(
                parse_number(fire.get("prim") or 625)
            )
            self.fire_usd.setValue(
                parse_number(fire.get("usd") or 47.4243)
            )
            self.fire_factory_rate.setValue(
                parse_number(fire.get("fire_orani") or 0.15) * 100
            )
            self.fire_recycling_loss.setValue(
                parse_number(
                    fire.get("ergitme_kaybi_orani") or 0.03
                ) * 100
            )
            self.fire_fason.setValue(
                parse_number(fire.get("fason_usd_kg") or 0.25)
            )
        self.fire_table.item(0, 7).setText(
            str(data.get("fire_note") or "")
        )
        self.update_rent_total()

    @staticmethod
    def is_legacy_automatic_packaging_row(row: list[object]) -> bool:
        if not row:
            return False
        name = str(row[0] or "").casefold().translate(
            str.maketrans(
                {
                    "ç": "c",
                    "ğ": "g",
                    "ı": "i",
                    "ö": "o",
                    "ş": "s",
                    "ü": "u",
                }
            )
        )
        return any(
            token in name
            for token in ("kereste", "kosebent", "cember", "naylon", "strec")
        )

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            QWidget {
                background: #F4F7FB;
                color: #1F2937;
            }
            #expensePageScroll,
            #expenseDetailsContainer,
            #expensePageScroll > QWidget > QWidget {
                background: #F4F7FB;
                border: 0;
            }
            #detailsHeader {
                background: #FFFFFF;
                border: 1px solid #D8E0EA;
                border-radius: 10px;
                padding: 10px;
            }
            #detailsHeader QLabel {
                background: transparent;
            }
            #detailsTitle {
                color: #163A70;
                font-size: 22px;
                font-weight: 700;
            }
            #detailsSubtitle,
            #detailDescription {
                color: #667085;
                font-size: 11px;
            }
            #expenseTabs::pane {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
            }
            #expenseTabs QTabBar::tab {
                background: #E8EEF6;
                color: #344054;
                border: 1px solid #CBD5E1;
                padding: 9px 13px;
                font-weight: 700;
            }
            #expenseTabs QTabBar::tab:selected {
                background: #1F67B1;
                color: #FFFFFF;
            }
            #addRowButton,
            #deleteRowButton {
                border-radius: 6px;
                padding: 8px 13px;
                font-weight: 700;
            }
            #addRowButton {
                color: #FFFFFF;
                background: #1F67B1;
                border: 1px solid #1F67B1;
            }
            #deleteRowButton {
                color: #9B1C31;
                background: #FFFFFF;
                border: 1px solid #D7A3AD;
            }
            #detailTotal {
                color: #163A70;
                background: #E8F1FB;
                border: 1px solid #B8CCE2;
                border-radius: 6px;
                padding: 9px 14px;
                font-size: 13px;
                font-weight: 700;
            }
            #detailEntryTable,
            #fireResultTable,
            #packagingAutoTable,
            #palletInputTable {
                background: #FFFFFF;
                alternate-background-color: #F7F9FC;
                border: 1px solid #D8E0EA;
                gridline-color: #D8E0EA;
            }
            #detailEntryTable QHeaderView::section,
            #fireResultTable QHeaderView::section,
            #packagingAutoTable QHeaderView::section,
            #palletInputTable QHeaderView::section {
                color: #FFFFFF;
                background: #163A70;
                border: 0;
                border-right: 1px solid #365A89;
                padding: 8px 5px;
                font-weight: 700;
            }
            QGroupBox {
                background: #FFFFFF;
                border: 1px solid #D8E0EA;
                border-radius: 8px;
                margin-top: 12px;
                padding: 14px;
                color: #163A70;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background: #FFFFFF;
            }
            QDoubleSpinBox,
            QComboBox,
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 8px;
            }
            #palletItemTabs::pane {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
            }
            #palletItemTabs QTabBar::tab {
                background: #EDF2F7;
                color: #344054;
                border: 1px solid #CBD5E1;
                padding: 7px 10px;
                font-weight: 700;
            }
            #palletItemTabs QTabBar::tab:selected {
                color: #FFFFFF;
                background: #2B74B8;
            }
            #palletFieldLabel {
                color: #344054;
                font-weight: 600;
            }
            #palletResult,
            #palletItemTotal {
                background: #EDF3FA;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 8px;
            }
            #palletItemTotal {
                color: #163A70;
                font-weight: 700;
            }
            """
        ))
