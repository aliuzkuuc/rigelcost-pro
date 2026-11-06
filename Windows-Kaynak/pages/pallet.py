from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.packaging_calculator import PackagingCalculator


class PalletCalculationPanel(QWidget):
    """Net üretimden palet ve beş paketleme kalemini hesaplar."""

    result_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.calculator = PackagingCalculator()
        self.last_result: dict[str, float] = {}
        self._loading = True
        self._syncing_rates = False
        self.setting_fields: dict[str, QDoubleSpinBox] = {}
        self.note_fields: dict[str, QLineEdit] = {}
        self.build_ui()
        self._loading = False
        self.recalculate()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        description = QLabel(
            "Net üretime göre toplam palet ve beş paketleme kalemi "
            "otomatik hesaplanır. Buradaki toplam, Paketleme sekmesine "
            "ve Maliyet Ana ekranına doğrudan aktarılır."
        )
        description.setObjectName("detailDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        assumptions = QGroupBox("Üretim ve Palet Dağılımı")
        assumptions_grid = QGridLayout(assumptions)
        assumptions_grid.setHorizontalSpacing(12)
        assumptions_grid.setVerticalSpacing(8)

        self.production = self.make_spinbox(
            value=200_000,
            maximum=100_000_000,
            decimals=0,
            suffix=" kg",
            read_only=True,
        )
        self.usd_rate = self.make_spinbox(
            value=47.4243,
            maximum=10_000,
            decimals=4,
            suffix=" TL",
            read_only=True,
        )
        self.average_pallet_kg = self.make_setting_spinbox(
            "average_pallet_kg",
            value=650,
            minimum=0.01,
            maximum=1_000_000,
            decimals=2,
            suffix=" kg/palet",
        )
        self.yansiz_rate = self.make_setting_spinbox(
            "yansiz_rate",
            value=75,
            maximum=100,
            decimals=2,
            suffix=" %",
        )
        self.yanli_rate = self.make_setting_spinbox(
            "yanli_rate",
            value=25,
            maximum=100,
            decimals=2,
            suffix=" %",
        )
        self.pallet_count_value = self.make_result_label("0 palet")

        self.add_field(
            assumptions_grid, 0, 0, "Aylık net üretim", self.production
        )
        self.add_field(
            assumptions_grid, 0, 2, "USD/TL kuru", self.usd_rate
        )
        self.add_field(
            assumptions_grid,
            1,
            0,
            "Ortalama palet ağırlığı",
            self.average_pallet_kg,
        )
        self.add_field(
            assumptions_grid, 1, 2, "Toplam palet", self.pallet_count_value
        )
        self.add_field(
            assumptions_grid, 2, 0, "Yansız palet oranı", self.yansiz_rate
        )
        self.add_field(
            assumptions_grid, 2, 2, "Yanlı palet oranı", self.yanli_rate
        )
        assumptions_grid.setColumnStretch(1, 1)
        assumptions_grid.setColumnStretch(3, 1)
        layout.addWidget(assumptions)

        self.item_tabs = QTabWidget()
        self.item_tabs.setObjectName("palletItemTabs")
        self.item_tabs.setDocumentMode(True)
        self.create_wood_tab()
        self.create_corner_tab()
        self.create_strap_tab()
        self.create_nylon_tab()
        self.create_stretch_tab()
        layout.addWidget(self.item_tabs, 1)

        self.total_value = QLabel("PALET HESABI TOPLAMI: 0,00 TL")
        self.total_value.setObjectName("detailTotal")
        self.total_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.total_value)

        self.production.valueChanged.connect(self.recalculate)
        self.usd_rate.valueChanged.connect(self.recalculate)
        self.yansiz_rate.valueChanged.connect(self.sync_from_yansiz)
        self.yanli_rate.valueChanged.connect(self.sync_from_yanli)
        for field in self.setting_fields.values():
            if field not in (self.yansiz_rate, self.yanli_rate):
                field.valueChanged.connect(self.recalculate)
        for field in self.note_fields.values():
            field.textChanged.connect(self.notify_note_change)

    def create_wood_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        explanation = QLabel(
            "Yansız palet = takoz + üst kereste. Yanlı palet = takoz + "
            "üst kereste + yan kereste. Hacimler ölçülerden hesaplanır."
        )
        explanation.setObjectName("detailDescription")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.wood_table = QTableWidget(3, 5)
        self.wood_table.setObjectName("palletInputTable")
        self.wood_table.setHorizontalHeaderLabels(
            ["Parça", "Adet", "Boy (m)", "En (m)", "Yükseklik (m)"]
        )
        self.wood_table.verticalHeader().setVisible(False)
        self.wood_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.wood_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.wood_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.wood_table.setMinimumHeight(165)

        component_defaults = (
            ("Takoz", "takoz", 3, 0.70, 0.07, 0.08),
            ("Üst Kereste", "ust_kereste", 3, 0.70, 0.02, 0.10),
            ("Yan Kereste", "yan_kereste", 6, 0.70, 0.02, 0.10),
        )
        for row, (
            label,
            key,
            quantity,
            length,
            width,
            height,
        ) in enumerate(component_defaults):
            name_item = QTableWidgetItem(label)
            name_item.setFlags(Qt.ItemIsEnabled)
            self.wood_table.setItem(row, 0, name_item)
            fields = (
                self.make_setting_spinbox(
                    f"{key}_adet",
                    value=quantity,
                    maximum=1_000,
                    decimals=0,
                ),
                self.make_setting_spinbox(
                    f"{key}_boy_m",
                    value=length,
                    maximum=100,
                    decimals=3,
                    suffix=" m",
                ),
                self.make_setting_spinbox(
                    f"{key}_en_m",
                    value=width,
                    maximum=100,
                    decimals=3,
                    suffix=" m",
                ),
                self.make_setting_spinbox(
                    f"{key}_yukseklik_m",
                    value=height,
                    maximum=100,
                    decimals=3,
                    suffix=" m",
                ),
            )
            for column, field in enumerate(fields, start=1):
                self.wood_table.setCellWidget(row, column, field)
        layout.addWidget(self.wood_table)

        controls = QGridLayout()
        self.wood_price = self.make_setting_spinbox(
            "wood_price",
            value=14_000,
            maximum=100_000_000,
            decimals=2,
            suffix=" TL/m³",
        )
        self.yansiz_m3_value = self.make_result_label("0,00000 m³/palet")
        self.yanli_m3_value = self.make_result_label("0,00000 m³/palet")
        self.wood_total_m3_value = self.make_result_label("0,00000 m³")
        self.wood_total_value = self.make_result_label("0,00 TL", total=True)
        self.add_field(
            controls, 0, 0, "Kereste birim fiyatı", self.wood_price
        )
        self.add_field(
            controls, 0, 2, "Yansız palet hacmi", self.yansiz_m3_value
        )
        self.add_field(
            controls, 1, 0, "Yanlı palet hacmi", self.yanli_m3_value
        )
        self.add_field(
            controls, 1, 2, "Toplam kereste hacmi", self.wood_total_m3_value
        )
        self.add_field(
            controls, 2, 0, "Kereste toplamı", self.wood_total_value
        )
        self.wood_note = self.add_note_field(
            controls, 3, "wood", "Kereste için not..."
        )
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)
        layout.addLayout(controls)
        layout.addStretch(1)
        self.item_tabs.addTab(tab, "Kereste")

    def create_corner_tab(self) -> None:
        tab, grid = self.make_item_tab(
            "Toplam köşebent = toplam palet × palet başı köşebent adedi."
        )
        self.corner_per_pallet = self.make_setting_spinbox(
            "corner_per_pallet",
            value=2,
            maximum=1_000,
            decimals=0,
            suffix=" adet/palet",
        )
        self.corner_price = self.make_setting_spinbox(
            "corner_price",
            value=12.25,
            maximum=10_000_000,
            decimals=2,
            suffix=" TL/adet",
        )
        self.corner_count_value = self.make_result_label("0 adet")
        self.corner_total_value = self.make_result_label(
            "0,00 TL", total=True
        )
        self.add_field(
            grid, 0, 0, "Palet başı köşebent", self.corner_per_pallet
        )
        self.add_field(grid, 1, 0, "Birim fiyat", self.corner_price)
        self.add_field(
            grid, 2, 0, "Toplam köşebent", self.corner_count_value
        )
        self.add_field(
            grid, 3, 0, "Köşebent toplamı", self.corner_total_value
        )
        self.corner_note = self.add_note_field(
            grid, 4, "corner", "Karton köşebent için not..."
        )
        self.item_tabs.addTab(tab, "Karton Köşebent")

    def create_strap_tab(self) -> None:
        tab, grid = self.make_item_tab(
            "Toplam metre = toplam palet × palet başı metre. Birim fiyat "
            "istenen paket/metre miktarı üzerinden metre fiyatına çevrilir."
        )
        self.strap_m_per_pallet = self.make_setting_spinbox(
            "strap_m_per_pallet",
            value=14,
            maximum=1_000_000,
            decimals=2,
            suffix=" m/palet",
        )
        self.strap_price_basis_m = self.make_setting_spinbox(
            "strap_price_basis_m",
            value=1_000,
            minimum=1,
            maximum=100_000_000,
            decimals=0,
            suffix=" metre",
        )
        self.strap_price = self.make_setting_spinbox(
            "strap_price",
            value=2_000,
            maximum=100_000_000,
            decimals=2,
            suffix=" TL",
        )
        self.strap_total_m_value = self.make_result_label("0,00 metre")
        self.strap_unit_value = self.make_result_label("0,0000 TL/metre")
        self.strap_total_value = self.make_result_label(
            "0,00 TL", total=True
        )
        self.add_field(
            grid, 0, 0, "Palet başı çember", self.strap_m_per_pallet
        )
        self.add_field(
            grid, 1, 0, "Fiyatın geçerli olduğu miktar",
            self.strap_price_basis_m
        )
        self.add_field(grid, 2, 0, "Bu miktarın fiyatı", self.strap_price)
        self.add_field(
            grid, 3, 0, "Toplam çember", self.strap_total_m_value
        )
        self.add_field(
            grid, 4, 0, "Metre birim fiyatı", self.strap_unit_value
        )
        self.add_field(
            grid, 5, 0, "Şerit çember toplamı", self.strap_total_value
        )
        self.strap_note = self.add_note_field(
            grid, 6, "strap", "Şerit çember için not..."
        )
        self.item_tabs.addTab(tab, "Şerit Çember")

    def create_nylon_tab(self) -> None:
        tab, grid = self.make_item_tab(
            "Sarılan palet sayısı, toplam paletin seçilen yüzdesidir. "
            "USD/ton fiyatı güncel USD/TL kuruyla TL'ye çevrilir."
        )
        self.nylon_rate = self.make_setting_spinbox(
            "nylon_rate",
            value=75,
            maximum=100,
            decimals=2,
            suffix=" %",
        )
        self.nylon_kg_per_pallet = self.make_setting_spinbox(
            "nylon_kg_per_pallet",
            value=8,
            maximum=10_000,
            decimals=2,
            suffix=" kg/palet",
        )
        self.nylon_usd_ton = self.make_setting_spinbox(
            "nylon_usd_ton",
            value=3_100,
            maximum=1_000_000,
            decimals=2,
            suffix=" USD/ton",
        )
        self.nylon_pallet_value = self.make_result_label("0,00 palet")
        self.nylon_kg_value = self.make_result_label("0,00 kg")
        self.nylon_tl_kg_value = self.make_result_label("0,0000 TL/kg")
        self.nylon_total_value = self.make_result_label(
            "0,00 TL", total=True
        )
        self.add_field(grid, 0, 0, "Sarma yapılan palet oranı", self.nylon_rate)
        self.add_field(
            grid, 1, 0, "Bir palette kullanılan naylon",
            self.nylon_kg_per_pallet
        )
        self.add_field(
            grid, 2, 0, "Naylon birim fiyatı", self.nylon_usd_ton
        )
        self.add_field(
            grid, 3, 0, "Sarılan palet", self.nylon_pallet_value
        )
        self.add_field(grid, 4, 0, "Toplam naylon", self.nylon_kg_value)
        self.add_field(
            grid, 5, 0, "Güncel TL/kg fiyatı", self.nylon_tl_kg_value
        )
        self.add_field(
            grid, 6, 0, "Sarma naylon toplamı", self.nylon_total_value
        )
        self.nylon_note = self.add_note_field(
            grid, 7, "nylon", "Sarma naylon için not..."
        )
        self.item_tabs.addTab(tab, "Sarma Naylon")

    def create_stretch_tab(self) -> None:
        tab, grid = self.make_item_tab(
            "Streç adedi, 200.000 kg net üretimde kullanılan adet "
            "üzerinden net üretime oranlanır ve yukarı yuvarlanır."
        )
        self.stretch_reference_count = self.make_setting_spinbox(
            "stretch_reference_count",
            value=168,
            maximum=10_000_000,
            decimals=0,
            suffix=" adet",
        )
        self.stretch_price = self.make_setting_spinbox(
            "stretch_price",
            value=48,
            maximum=10_000_000,
            decimals=2,
            suffix=" TL/adet",
        )
        self.stretch_count_value = self.make_result_label("0 adet")
        self.stretch_total_value = self.make_result_label(
            "0,00 TL", total=True
        )
        self.add_field(
            grid,
            0,
            0,
            "200.000 kg üretimde kullanılan",
            self.stretch_reference_count,
        )
        self.add_field(grid, 1, 0, "Birim fiyat", self.stretch_price)
        self.add_field(
            grid, 2, 0, "Üretime göre streç adedi", self.stretch_count_value
        )
        self.add_field(
            grid, 3, 0, "Streç film toplamı", self.stretch_total_value
        )
        self.stretch_note = self.add_note_field(
            grid, 4, "stretch", "Streç film için not..."
        )
        self.item_tabs.addTab(tab, "Streç Film")

    def make_item_tab(self, description: str) -> tuple[QWidget, QGridLayout]:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        explanation = QLabel(description)
        explanation.setObjectName("detailDescription")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        group = QGroupBox("Hesap Bilgileri")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        layout.addWidget(group)
        layout.addStretch(1)
        return tab, grid

    def make_setting_spinbox(
        self,
        key: str,
        *,
        value: float,
        minimum: float = 0,
        maximum: float,
        decimals: int,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        spinbox = self.make_spinbox(
            value=value,
            minimum=minimum,
            maximum=maximum,
            decimals=decimals,
            suffix=suffix,
        )
        self.setting_fields[key] = spinbox
        return spinbox

    @staticmethod
    def make_spinbox(
        *,
        value: float,
        minimum: float = 0,
        maximum: float,
        decimals: int,
        suffix: str = "",
        read_only: bool = False,
    ) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(decimals)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        spinbox.setGroupSeparatorShown(True)
        spinbox.setAlignment(Qt.AlignRight)
        spinbox.setMinimumHeight(34)
        spinbox.setKeyboardTracking(False)
        spinbox.setReadOnly(read_only)
        return spinbox

    @staticmethod
    def make_result_label(text: str, *, total: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName("palletItemTotal" if total else "palletResult")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setMinimumHeight(34)
        return label

    @staticmethod
    def add_field(
        layout: QGridLayout,
        row: int,
        column: int,
        text: str,
        widget: QWidget,
    ) -> None:
        label = QLabel(text)
        label.setObjectName("palletFieldLabel")
        layout.addWidget(label, row, column)
        layout.addWidget(widget, row, column + 1)

    def add_note_field(
        self,
        layout: QGridLayout,
        row: int,
        key: str,
        placeholder: str,
    ) -> QLineEdit:
        note = QLineEdit()
        note.setPlaceholderText(placeholder)
        self.note_fields[key] = note
        self.add_field(layout, row, 0, "Not", note)
        return note

    def sync_from_yansiz(self, value: float) -> None:
        if self._syncing_rates:
            return
        self._syncing_rates = True
        try:
            self.yanli_rate.setValue(max(0.0, 100.0 - value))
        finally:
            self._syncing_rates = False
        self.recalculate()

    def sync_from_yanli(self, value: float) -> None:
        if self._syncing_rates:
            return
        self._syncing_rates = True
        try:
            self.yansiz_rate.setValue(max(0.0, 100.0 - value))
        finally:
            self._syncing_rates = False
        self.recalculate()

    def notify_note_change(self, *_args: object) -> None:
        if not self._loading:
            self.result_changed.emit(dict(self.last_result))

    def recalculate(self, *_args: object) -> None:
        if self._loading:
            return
        try:
            result = self.calculator.excel_hesapla(
                uretim=self.production.value(),
                usd=self.usd_rate.value(),
                ortalama_palet_kg=self.average_pallet_kg.value(),
                yansiz_oran=self.yansiz_rate.value() / 100,
                kereste_m3_fiyat=self.wood_price.value(),
                kosebent_birim_fiyat=self.corner_price.value(),
                cember_1000mt_fiyat=self.strap_price.value(),
                naylon_kg_palet=self.nylon_kg_per_pallet.value(),
                naylon_usd_ton=self.nylon_usd_ton.value(),
                strec_adet=self.stretch_reference_count.value(),
                strec_birim_fiyat=self.stretch_price.value(),
                takoz_adet=self.setting_fields["takoz_adet"].value(),
                takoz_boy_m=self.setting_fields["takoz_boy_m"].value(),
                takoz_en_m=self.setting_fields["takoz_en_m"].value(),
                takoz_yukseklik_m=(
                    self.setting_fields["takoz_yukseklik_m"].value()
                ),
                ust_kereste_adet=(
                    self.setting_fields["ust_kereste_adet"].value()
                ),
                ust_kereste_boy_m=(
                    self.setting_fields["ust_kereste_boy_m"].value()
                ),
                ust_kereste_en_m=(
                    self.setting_fields["ust_kereste_en_m"].value()
                ),
                ust_kereste_yukseklik_m=(
                    self.setting_fields["ust_kereste_yukseklik_m"].value()
                ),
                yan_kereste_adet=(
                    self.setting_fields["yan_kereste_adet"].value()
                ),
                yan_kereste_boy_m=(
                    self.setting_fields["yan_kereste_boy_m"].value()
                ),
                yan_kereste_en_m=(
                    self.setting_fields["yan_kereste_en_m"].value()
                ),
                yan_kereste_yukseklik_m=(
                    self.setting_fields["yan_kereste_yukseklik_m"].value()
                ),
                kosebent_adet_palet=self.corner_per_pallet.value(),
                cember_mt_palet=self.strap_m_per_pallet.value(),
                cember_fiyat_metresi=self.strap_price_basis_m.value(),
                naylon_sarim_orani=self.nylon_rate.value() / 100,
            )
        except ValueError:
            return

        self.last_result = result
        self.update_results(result)
        self.result_changed.emit(dict(result))

    def update_results(self, result: dict[str, float]) -> None:
        self.pallet_count_value.setText(
            f"{self.format_number(result['palet_adedi'], 0)} palet"
        )
        self.yansiz_m3_value.setText(
            f"{self.format_number(result['yansiz_palet_m3'], 5)} m³/palet"
        )
        self.yanli_m3_value.setText(
            f"{self.format_number(result['yanli_palet_m3'], 5)} m³/palet"
        )
        self.wood_total_m3_value.setText(
            f"{self.format_number(result['kereste_m3'], 5)} m³"
        )
        self.wood_total_value.setText(self.format_tl(result["kereste"]))
        self.corner_count_value.setText(
            f"{self.format_number(result['kosebent_adedi'], 0)} adet"
        )
        self.corner_total_value.setText(self.format_tl(result["kosebent"]))
        self.strap_total_m_value.setText(
            f"{self.format_number(result['cember_mt'], 2)} metre"
        )
        self.strap_unit_value.setText(
            f"{self.format_number(result['cember_tl_mt'], 4)} TL/metre"
        )
        self.strap_total_value.setText(self.format_tl(result["cember"]))
        self.nylon_pallet_value.setText(
            f"{self.format_number(result['naylon_palet_adedi'], 2)} palet"
        )
        self.nylon_kg_value.setText(
            f"{self.format_number(result['naylon_kg'], 2)} kg"
        )
        self.nylon_tl_kg_value.setText(
            f"{self.format_number(result['naylon_tl_kg'], 4)} TL/kg"
        )
        self.nylon_total_value.setText(self.format_tl(result["naylon"]))
        self.stretch_count_value.setText(
            f"{self.format_number(result['strec_adedi'], 0)} adet"
        )
        self.stretch_total_value.setText(self.format_tl(result["strec"]))

        self.total_value.setText(
            f"PALET HESABI TOPLAMI: {self.format_tl(result['toplam'])}"
        )

    def set_production(self, value: float) -> None:
        self.production.setValue(max(1.0, float(value)))

    def set_usd_rate(self, value: float) -> None:
        if value > 0:
            self.usd_rate.setValue(float(value))

    def settings(self) -> dict[str, Any]:
        return {
            "fields": {
                key: field.value()
                for key, field in self.setting_fields.items()
            },
            "notes": {
                key: field.text()
                for key, field in self.note_fields.items()
            },
        }

    def load_settings(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        fields = data.get("fields")
        notes = data.get("notes")
        self._loading = True
        self._syncing_rates = True
        try:
            if isinstance(fields, dict):
                for key, value in fields.items():
                    field = self.setting_fields.get(str(key))
                    if field is None:
                        continue
                    try:
                        field.setValue(float(value))
                    except (TypeError, ValueError):
                        continue
            if isinstance(notes, dict):
                for key, value in notes.items():
                    field = self.note_fields.get(str(key))
                    if field is not None:
                        field.setText(str(value or ""))
            self.yanli_rate.setValue(
                max(0.0, 100.0 - self.yansiz_rate.value())
            )
        finally:
            self._syncing_rates = False
            self._loading = False
        self.recalculate()

    @staticmethod
    def format_number(value: float, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        return (
            formatted.replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    @classmethod
    def format_tl(cls, value: float) -> str:
        return f"{cls.format_number(value, 2)} TL"
