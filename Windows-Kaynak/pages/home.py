from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.calculator import CostCalculator, MALIYET_ANA_LABELS
from ui.corporate_theme import stylesheet


class HomePage(QWidget):
    """Rigel Cost Pro ana maliyet ekranı.

    Bu sınıf yalnızca kullanıcı arayüzünü yönetir, kullanıcı girdilerini
    ``CostCalculator`` sınıfına iletir ve dönen sonuçları ekranda gösterir.
    Hesaplama formülleri ``models`` klasöründe tutulur.
    """

    calculation_completed = Signal(dict)
    excel_export_requested = Signal(dict)
    pdf_export_requested = Signal(dict)
    open_expenses_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.calc = CostCalculator()
        self.last_result: dict[str, Any] | None = None
        self.last_report_data: dict[str, Any] | None = None
        self._live_recalculation = False
        self._compact_form_layout: bool | None = None

        self.setWindowTitle("Rigel Cost Pro")
        self.setMinimumSize(640, 600)

        self.build_ui()
        self.apply_style()
        self.connect_live_recalculation()

    # ------------------------------------------------------------------
    # ANA EKRAN
    # ------------------------------------------------------------------

    def build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.content = QVBoxLayout(container)
        self.content.setSpacing(16)
        self.content.setContentsMargins(24, 20, 24, 28)

        self.create_header()

        self.form_grid = QGridLayout()
        self.form_grid.setHorizontalSpacing(16)
        self.form_grid.setVerticalSpacing(16)

        self.production_group = self.create_production_group()
        self.energy_group = self.create_energy_group()
        self.personnel_group = self.create_personnel_group()
        self.factory_group = self.create_factory_group()

        self.content.addLayout(self.form_grid)
        self.apply_responsive_form_layout(force=True)
        self.create_buttons()
        self.create_result_box()
        self.content.addStretch(1)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.apply_responsive_form_layout()

    def apply_responsive_form_layout(
        self,
        *,
        force: bool = False,
        available_width: int | None = None,
    ) -> None:
        """Dar pencerede formu tek sütuna alarak sağ taşmayı engeller."""
        if not hasattr(self, "form_grid"):
            return
        layout_width = (
            self.width() if available_width is None else available_width
        )
        compact = layout_width < 1_000
        if compact == self._compact_form_layout and not force:
            return
        self._compact_form_layout = compact

        groups = (
            self.production_group,
            self.energy_group,
            self.personnel_group,
            self.factory_group,
        )
        if compact:
            for row, group in enumerate(groups):
                self.form_grid.addWidget(group, row, 0, 1, 2)
            self.form_grid.setColumnStretch(0, 1)
            self.form_grid.setColumnStretch(1, 0)
        else:
            self.form_grid.addWidget(self.production_group, 0, 0)
            self.form_grid.addWidget(self.energy_group, 0, 1)
            self.form_grid.addWidget(self.personnel_group, 1, 0)
            self.form_grid.addWidget(self.factory_group, 1, 1)
            self.form_grid.setColumnStretch(0, 1)
            self.form_grid.setColumnStretch(1, 1)

    # ------------------------------------------------------------------
    # ÜST BİLGİ
    # ------------------------------------------------------------------

    def create_header(self) -> None:
        header = QFrame()
        header.setObjectName("headerCard")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(5)

        logo = QLabel()
        logo.setObjectName("headerLogo")
        logo.setAlignment(Qt.AlignCenter)

        project_root = Path(__file__).resolve().parents[1]
        logo_path = project_root / "assets" / "logo.jpg"
        pixmap = QPixmap(str(logo_path))

        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    180,
                    80,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            layout.addWidget(logo)

        title = QLabel("RIGEL COST PRO — MALİYET ANA")
        title.setObjectName("mainTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "15 ana gider kalemi · toplam USD · USD/kg · USD/ton"
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        self.content.addWidget(header)

    # ------------------------------------------------------------------
    # HESAPLAMA MODÜLLERİ
    # ------------------------------------------------------------------

    def create_production_group(self) -> QGroupBox:
        group = QGroupBox("1. Net Üretim ve Kur")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        self.uretim = self.make_spinbox(
            value=200_000,
            maximum=100_000_000,
            decimals=0,
            suffix=" kg",
        )
        self.lme = self.make_spinbox(
            value=3_192,
            maximum=100_000,
            decimals=2,
            suffix=" USD/ton",
        )
        self.prim = self.make_spinbox(
            value=625,
            maximum=100_000,
            decimals=2,
            suffix=" USD/ton",
        )
        self.usd = self.make_spinbox(
            value=47.4243,
            maximum=10_000,
            decimals=4,
            suffix=" TL",
        )
        self.fire_orani = self.make_spinbox(
            value=15,
            maximum=99.99,
            decimals=2,
            suffix=" %",
        )
        self.ergitme_kaybi_orani = self.make_spinbox(
            value=3,
            maximum=100,
            decimals=2,
            suffix=" %",
        )
        self.fason_usd_kg = self.make_spinbox(
            value=0.25,
            maximum=100_000,
            decimals=4,
            suffix=" USD/kg",
        )

        self.add_field(layout, 0, "Aylık net üretim", self.uretim)
        self.add_field(layout, 1, "USD/TL kuru", self.usd)

        fire_button = QPushButton("FİRE–FASON DETAYINI AÇ")
        fire_button.setObjectName("detailOpenButton")
        fire_button.clicked.connect(
            lambda checked=False: self.open_expenses_requested.emit(
                "Fire-Fason"
            )
        )
        layout.addWidget(fire_button, 2, 0, 1, 2)

        note = QLabel(
            "LME, prim, fire oranı ve fason fiyatı Gider Alt Sekmeleri "
            "içindeki Fire-Fason bölümünden girilir. Referans üretim yoktur."
        )
        note.setObjectName("groupNote")
        note.setWordWrap(True)
        layout.addWidget(note, 3, 0, 1, 2)

        return group

    def create_energy_group(self) -> QGroupBox:
        group = QGroupBox("2. Enerji")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        self.elektrik = self.make_spinbox(
            value=2.97,
            maximum=100_000,
            decimals=4,
            suffix=" TL/kWh",
            read_only=True,
        )
        self.elektrik_kwh_ton = self.make_spinbox(
            value=567,
            maximum=100_000,
            decimals=2,
            suffix=" kWh/ton",
        )
        self.gaz = self.make_spinbox(
            value=18.90,
            maximum=100_000,
            decimals=4,
            suffix=" TL/Sm³",
        )
        self.gaz_kullanim = self.make_spinbox(
            value=0,
            maximum=100_000,
            decimals=4,
            suffix=" TL/Sm³",
        )
        self.gaz_otv = self.make_spinbox(
            value=0,
            maximum=100_000,
            decimals=4,
            suffix=" TL/Sm³",
        )
        self.gaz_sm3_ton = self.make_spinbox(
            value=48,
            maximum=100_000,
            decimals=2,
            suffix=" Sm³/ton",
        )
        self.su_m3_ton = self.make_spinbox(
            value=0.5,
            maximum=100_000,
            decimals=3,
            suffix=" m³/ton",
        )
        self.su_birim_fiyat = self.make_spinbox(
            value=106.31,
            maximum=1_000_000,
            decimals=2,
            suffix=" TL/m³",
        )

        self.add_field(layout, 0, "Elektrik tüketimi", self.elektrik_kwh_ton)
        self.add_field(
            layout, 1, "Elektrik birim fiyatı (detaydan)", self.elektrik
        )
        self.add_field(layout, 2, "Doğalgaz tüketimi", self.gaz_sm3_ton)
        self.add_field(layout, 3, "Doğalgaz toplam birim fiyatı", self.gaz)
        self.add_field(layout, 4, "Su tüketimi", self.su_m3_ton)
        self.add_field(layout, 5, "Su birim fiyatı", self.su_birim_fiyat)

        electricity_button = QPushButton("ELEKTRİK BİRİM FİYATI DETAYINI AÇ")
        electricity_button.setObjectName("detailOpenButton")
        electricity_button.clicked.connect(
            lambda checked=False: self.open_expenses_requested.emit(
                "Elektrik Birim Fiyatı"
            )
        )
        layout.addWidget(electricity_button, 6, 0, 1, 2)

        note = QLabel(
            "Elektrik birim fiyatı alt sekmede aktif + OSB dağıtım + iletim "
            "kalemlerinden ve girdiğiniz yüzde payından hesaplanır. Net "
            "üretime göre tüketim 567 kWh/ton, doğalgaz 48 Sm³/ton ve su "
            "0,5 m³/ton."
        )
        note.setObjectName("groupNote")
        note.setWordWrap(True)
        layout.addWidget(note, 7, 0, 1, 2)

        return group

    def create_personnel_group(self) -> QGroupBox:
        group = QGroupBox("3. Personel")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        self.iscilik = self.make_money_spinbox()
        self.sgk = self.make_money_spinbox()
        self.yemek = self.make_money_spinbox()
        self.yemek.setReadOnly(True)

        self.add_field(
            layout,
            0,
            "Toplam maaş hakedişi (mesai + SGK dahil)",
            self.iscilik,
        )
        self.add_field(layout, 1, "Yemek toplamı (detaydan)", self.yemek)

        note = QLabel(
            "Maaş alanına aylık toplam hakedişi tek tutar olarak girin. "
            "Yemek toplamı alt sekmedeki gündüz/gece hesabından gelir."
        )
        note.setObjectName("groupNote")
        note.setWordWrap(True)
        layout.addWidget(note, 2, 0, 1, 2)

        return group

    def create_factory_group(self) -> QGroupBox:
        group = QGroupBox("4. Fabrika, Lojistik ve Paketleme")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(9)
        layout.setColumnStretch(1, 1)

        self.kira = self.make_money_spinbox()
        self.amortisman = self.make_money_spinbox()
        self.bakim = self.make_money_spinbox()
        self.kalip = self.make_money_spinbox()
        self.sarf = self.make_money_spinbox()
        self.ekipman = self.make_money_spinbox()
        self.genel_gider = self.make_money_spinbox()
        self.mazot = self.make_money_spinbox()
        self.nakliye = self.make_money_spinbox()
        self.tenefer_nakliye = self.make_money_spinbox()
        self.tenefer = self.make_money_spinbox()
        self.diger = self.make_money_spinbox()
        self.ambalaj = self.make_money_spinbox()
        for spinbox in (
            self.kira,
            self.amortisman,
            self.bakim,
            self.kalip,
            self.sarf,
            self.ekipman,
            self.genel_gider,
            self.mazot,
            self.nakliye,
            self.tenefer_nakliye,
            self.tenefer,
            self.diger,
            self.ambalaj,
        ):
            spinbox.setReadOnly(True)

        fields = [
            ("Bina kirası (alt sekmeden)", self.kira),
            ("Amortisman (alt sekmeden)", self.amortisman),
            ("Genel gider (alt sekmeden)", self.genel_gider),
            ("Kalıp maliyeti (alt sekmeden)", self.kalip),
            ("Fabrika iş akışı (alt sekmeden)", self.sarf),
            ("Araç yakıt (alt sekmeden)", self.mazot),
            ("Nakliye (alt sekmeden)", self.nakliye),
            ("Tenefer (alt sekmeden)", self.tenefer),
            ("Paketleme (alt sekmeden)", self.ambalaj),
        ]

        for index, (label_text, spinbox) in enumerate(fields):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            layout.addWidget(label, index, 0)
            layout.addWidget(spinbox, index, 1)

        note = QLabel(
            "Bu bölümde veri girişi yapılmaz. Bütün tutarlar Gider Alt "
            "Sekmeleri içindeki satırlardan otomatik gelir."
        )
        note.setObjectName("groupNote")
        note.setWordWrap(True)
        note_row = len(fields)
        layout.addWidget(note, note_row, 0, 1, 2)

        detail_button = QPushButton("GİDER ALT SEKMELERİNİ AÇ")
        detail_button.setObjectName("detailOpenButton")
        detail_button.clicked.connect(
            lambda checked=False: self.open_expenses_requested.emit("")
        )
        layout.addWidget(detail_button, note_row + 1, 0, 1, 2)

        return group

    # ------------------------------------------------------------------
    # BUTONLAR
    # ------------------------------------------------------------------

    def create_buttons(self) -> None:
        button_bar = QFrame()
        button_bar.setObjectName("buttonBar")
        layout = QHBoxLayout(button_bar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.calculate_button = QPushButton("HESAPLA")
        self.calculate_button.setObjectName("primaryButton")
        self.calculate_button.setMinimumHeight(44)
        self.calculate_button.clicked.connect(self.hesapla)

        self.clear_button = QPushButton("TEMİZLE")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.setMinimumHeight(44)
        self.clear_button.clicked.connect(self.clear_form)

        self.excel_button = QPushButton("EXCEL'E AKTAR")
        self.excel_button.setObjectName("exportButton")
        self.excel_button.setMinimumHeight(44)
        self.excel_button.setEnabled(False)
        self.excel_button.clicked.connect(self.request_excel_export)

        self.pdf_button = QPushButton("PDF OLUŞTUR")
        self.pdf_button.setObjectName("exportButton")
        self.pdf_button.setMinimumHeight(44)
        self.pdf_button.setEnabled(False)
        self.pdf_button.clicked.connect(self.request_pdf_export)

        layout.addWidget(self.calculate_button, 2)
        layout.addWidget(self.clear_button, 1)
        layout.addStretch(1)
        layout.addWidget(self.excel_button, 1)
        layout.addWidget(self.pdf_button, 1)

        self.content.addWidget(button_bar)

    # ------------------------------------------------------------------
    # SONUÇLAR
    # ------------------------------------------------------------------

    def create_result_box(self) -> None:
        result_group = QGroupBox("Maliyet Ana — 15 Kalem USD Özeti")
        result_layout = QVBoxLayout(result_group)
        result_layout.setSpacing(12)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(12)
        cards_layout.setVerticalSpacing(12)

        self.items_total_tl_value = self.create_result_card(
            cards_layout, 0, 0, "15 KALEM TOPLAM", "0,00 TL"
        )
        self.items_total_value = self.create_result_card(
            cards_layout, 0, 1, "15 KALEM TOPLAM", "0,00 USD"
        )
        self.production_value = self.create_result_card(
            cards_layout, 0, 2, "NET ÜRETİM", "0 kg"
        )
        self.unit_tl_kg_value = self.create_result_card(
            cards_layout, 1, 0, "FABRİKA MALİYETİ", "0,0000 TL/kg"
        )
        self.unit_kg_value = self.create_result_card(
            cards_layout, 1, 1, "FABRİKA MALİYETİ", "0,0000 USD/kg"
        )
        self.unit_ton_value = self.create_result_card(
            cards_layout,
            1,
            2,
            "FABRİKA MALİYETİ",
            "0,00 USD/ton",
            total=True,
        )

        for column in range(3):
            cards_layout.setColumnStretch(column, 1)

        result_layout.addLayout(cards_layout)

        self.cost_table = QTableWidget(len(MALIYET_ANA_LABELS), 6)
        self.cost_table.setObjectName("costSummaryTable")
        self.cost_table.setHorizontalHeaderLabels(
            [
                "No",
                "Maliyet Kalemi",
                "Toplam TL",
                "Toplam USD",
                "USD/kg",
                "USD/ton",
            ]
        )
        self.cost_table.verticalHeader().setVisible(False)
        self.cost_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cost_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cost_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cost_table.setAlternatingRowColors(True)
        self.cost_table.setMinimumHeight(505)
        self.cost_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.cost_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        for column in range(2, 6):
            self.cost_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeToContents
            )

        for row, (_, label) in enumerate(MALIYET_ANA_LABELS):
            self.set_cost_table_item(row, 0, str(row + 1), Qt.AlignCenter)
            self.set_cost_table_item(
                row, 1, label, Qt.AlignVCenter | Qt.AlignLeft
            )
            for column in range(2, 6):
                self.set_cost_table_item(
                    row,
                    column,
                    "0,00" if column != 4 else "0,0000",
                    Qt.AlignVCenter | Qt.AlignRight,
                )

        result_layout.addWidget(self.cost_table)

        self.detail_label = QLabel(
            "Hesaplama için değerleri girin ve HESAPLA düğmesine basın."
        )
        self.detail_label.setObjectName("detailLabel")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_layout.addWidget(self.detail_label)

        self.content.addWidget(result_group)

    def set_cost_table_item(
        self,
        row: int,
        column: int,
        text: str,
        alignment: Qt.AlignmentFlag,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(alignment)
        self.cost_table.setItem(row, column, item)

    def create_result_card(
        self,
        parent_layout: QGridLayout,
        row: int,
        column: int,
        title: str,
        initial_value: str,
        *,
        total: bool = False,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("totalCard" if total else "resultCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("resultTitle")
        title_label.setAlignment(Qt.AlignCenter)

        value_label = QLabel(initial_value)
        value_label.setObjectName("totalValue" if total else "resultValue")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        parent_layout.addWidget(card, row, column)

        return value_label

    # ------------------------------------------------------------------
    # HESAPLAMA
    # ------------------------------------------------------------------

    def hesapla(self) -> None:
        production = self.uretim.value()
        usd_rate = self.usd.value()

        if production <= 0:
            QMessageBox.warning(
                self,
                "Eksik bilgi",
                "Üretim miktarı sıfırdan büyük olmalıdır.",
            )
            self.uretim.setFocus()
            return

        if usd_rate <= 0:
            QMessageBox.warning(
                self,
                "Eksik bilgi",
                "USD/TL kuru sıfırdan büyük olmalıdır.",
            )
            self.usd.setFocus()
            return

        inputs = self.collect_inputs()

        try:
            result = self.calc.hesapla(**inputs)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hesaplama hatası",
                "Maliyet hesabı tamamlanamadı.\n\n"
                f"Hata ayrıntısı: {exc}",
            )
            return

        self.last_result = result
        self.last_report_data = {
            "inputs": inputs.copy(),
            "results": result.copy(),
        }

        self.update_result_box(result, production, usd_rate)
        self.excel_button.setEnabled(True)
        self.pdf_button.setEnabled(True)
        self.calculation_completed.emit(self.last_report_data)

    def connect_live_recalculation(self) -> None:
        """İlk hesaplamadan sonra değişen girdileri anında sonuçlara yansıtır."""
        fields = (
            self.uretim,
            self.lme,
            self.prim,
            self.usd,
            self.fire_orani,
            self.ergitme_kaybi_orani,
            self.fason_usd_kg,
            self.elektrik_kwh_ton,
            self.gaz,
            self.gaz_sm3_ton,
            self.su_m3_ton,
            self.su_birim_fiyat,
            self.iscilik,
            self.yemek,
            self.kira,
            self.amortisman,
            self.genel_gider,
            self.kalip,
            self.sarf,
            self.mazot,
            self.nakliye,
            self.tenefer,
            self.ambalaj,
        )
        for field in fields:
            field.valueChanged.connect(self.recalculate_if_calculated)

    def recalculate_if_calculated(self, *_args: object) -> None:
        if self.last_result is None or self._live_recalculation:
            return
        self._live_recalculation = True
        try:
            self.hesapla()
        finally:
            self._live_recalculation = False

    def collect_inputs(self) -> dict[str, float]:
        return {
            "uretim": self.uretim.value(),
            "lme": self.lme.value(),
            "prim": self.prim.value(),
            "usd": self.usd.value(),
            "fire_orani": self.fire_orani.value() / 100,
            "ergitme_kaybi_orani": (
                self.ergitme_kaybi_orani.value() / 100
            ),
            "fason_usd_kg": self.fason_usd_kg.value(),
            "elektrik_fiyat": self.elektrik.value(),
            "elektrik_kwh_ton": self.elektrik_kwh_ton.value(),
            "gaz_fiyat": self.gaz.value(),
            "gaz_kullanim": self.gaz_kullanim.value(),
            "gaz_otv": self.gaz_otv.value(),
            "gaz_sm3_ton": self.gaz_sm3_ton.value(),
            "iscilik": self.iscilik.value(),
            "sgk": self.sgk.value(),
            "yemek": self.yemek.value(),
            "ambalaj": self.ambalaj.value(),
            "genel_gider": self.genel_gider.value(),
            "su_m3_ton": self.su_m3_ton.value(),
            "su_birim_fiyat": self.su_birim_fiyat.value(),
            "mazot": self.mazot.value(),
            "kira": self.kira.value(),
            "nakliye": self.nakliye.value(),
            "kalip": self.kalip.value(),
            "bakim": self.bakim.value(),
            "amortisman": self.amortisman.value(),
            "sarf": self.sarf.value(),
            "ekipman": self.ekipman.value(),
            "tenefer_nakliye": self.tenefer_nakliye.value(),
            "tenefer": self.tenefer.value(),
            "diger": self.diger.value(),
        }

    def update_result_box(
        self,
        result: dict[str, Any],
        production: float,
        usd_rate: float,
    ) -> None:
        items_total_tl = self.safe_number(
            result.get("maliyet_ana_toplam_tl")
        )
        items_total_usd = self.safe_number(
            result.get("maliyet_ana_toplam_usd")
        )
        items_usd_kg = self.safe_number(
            result.get("maliyet_ana_usd_kg_toplam")
        )
        items_usd_ton = self.safe_number(
            result.get("maliyet_ana_usd_ton_toplam")
        )
        items_tl_kg = (
            items_total_tl / production if production > 0 else 0.0
        )

        self.items_total_tl_value.setText(self.format_tl(items_total_tl))
        self.items_total_value.setText(
            f"{self.format_number(items_total_usd, 2)} USD"
        )
        self.unit_kg_value.setText(
            f"{self.format_number(items_usd_kg, 4)} USD/kg"
        )
        self.unit_ton_value.setText(self.format_usd_ton(items_usd_ton))
        self.unit_tl_kg_value.setText(
            f"{self.format_number(items_tl_kg, 4)} TL/kg"
        )
        self.production_value.setText(
            f"{self.format_number(production, 0)} kg"
        )

        labels = result.get("maliyet_ana_labels") or {}
        totals_tl = result.get("maliyet_ana_tl") or {}
        totals_usd = result.get("maliyet_ana_usd") or {}
        units_usd_kg = result.get("maliyet_ana_usd_kg") or {}
        units_usd_ton = result.get("maliyet_ana_usd_ton") or {}
        for row, (key, default_label) in enumerate(MALIYET_ANA_LABELS):
            label = str(labels.get(key, default_label))
            self.cost_table.item(row, 1).setText(label)
            values = (
                self.format_number(self.safe_number(totals_tl.get(key)), 2),
                self.format_number(self.safe_number(totals_usd.get(key)), 2),
                self.format_number(
                    self.safe_number(units_usd_kg.get(key)), 4
                ),
                self.format_number(
                    self.safe_number(units_usd_ton.get(key)), 2
                ),
            )
            for column, text in enumerate(values, start=2):
                self.cost_table.item(row, column).setText(text)

        billet_need = self.safe_number(result.get("billet_ihtiyaci"))
        electricity_consumption = self.safe_number(
            result.get("elektrik_tuketim")
        )
        gas_consumption = self.safe_number(result.get("gaz_tuketim"))
        water_consumption = self.safe_number(result.get("su_tuketim"))
        recovered_scrap = self.safe_number(result.get("geri_donusum"))
        final_loss = self.safe_number(result.get("ergitme"))
        fire_cost = self.safe_number(result.get("fire_toplam"))

        self.detail_label.setText(
            "<b>Hesaplama tamamlandı.</b><br>"
            f"Toplam aylık fabrika gideri: "
            f"{self.format_tl(items_total_tl)}<br>"
            f"Fabrika maliyeti: "
            f"{self.format_number(items_total_usd, 2)} USD toplam | "
            f"{self.format_number(items_usd_kg, 4)} USD/kg | "
            f"{self.format_number(items_usd_ton, 2)} USD/ton<br>"
            f"Billet ihtiyacı: {self.format_number(billet_need, 2)} kg<br>"
            f"Fire geri dönüşümü: {self.format_number(recovered_scrap, 2)} kg | "
            f"Nihai kayıp: {self.format_number(final_loss, 2)} kg | "
            f"Fire maliyeti: {self.format_tl(fire_cost)}<br>"
            f"Tüketimler: {self.format_number(electricity_consumption, 2)} kWh elektrik, "
            f"{self.format_number(gas_consumption, 2)} Sm³ gaz, "
            f"{self.format_number(water_consumption, 2)} m³ su"
        )

    # ------------------------------------------------------------------
    # DIŞ MODÜL BAĞLANTILARI
    # ------------------------------------------------------------------

    def set_detail_costs(self, totals: dict[str, float]) -> None:
        """Alt sekme toplamlarını ana ekrandaki salt okunur alanlara alır."""
        field_map = {
            "kira": self.kira,
            "yemek": self.yemek,
            "mazot": self.mazot,
            "genel_gider": self.genel_gider,
            "nakliye": self.nakliye,
            "tenefer": self.tenefer,
            "kalip": self.kalip,
            "sarf": self.sarf,
            "amortisman": self.amortisman,
            "ambalaj": self.ambalaj,
        }
        for key, field in field_map.items():
            field.setValue(max(0.0, float(totals.get(key, 0))))
        if totals.get("elektrik_birim_fiyat") is not None:
            self.elektrik.setValue(
                max(0.0, float(totals.get("elektrik_birim_fiyat", 0)))
            )

    def set_fire_parameters(self, values: dict[str, float]) -> None:
        """Fire-Fason alt sekmesindeki parametreleri hesap motoruna aktarır."""
        setters = (
            (self.lme, values.get("lme")),
            (self.prim, values.get("prim")),
            (self.usd, values.get("usd")),
            (
                self.fire_orani,
                (
                    float(values["fire_orani"]) * 100
                    if "fire_orani" in values
                    else None
                ),
            ),
            (
                self.ergitme_kaybi_orani,
                (
                    float(values["ergitme_kaybi_orani"]) * 100
                    if "ergitme_kaybi_orani" in values
                    else None
                ),
            ),
            (self.fason_usd_kg, values.get("fason_usd_kg")),
        )
        for field, value in setters:
            if value is not None:
                field.setValue(max(0.0, float(value)))

    def request_excel_export(self) -> None:
        if self.last_report_data is None:
            QMessageBox.information(
                self,
                "Önce hesaplama yapın",
                "Excel raporu oluşturmadan önce maliyeti hesaplayın.",
            )
            return
        self.excel_export_requested.emit(self.last_report_data)

    def request_pdf_export(self) -> None:
        if self.last_report_data is None:
            QMessageBox.information(
                self,
                "Önce hesaplama yapın",
                "PDF raporu oluşturmadan önce maliyeti hesaplayın.",
            )
            return
        self.pdf_export_requested.emit(self.last_report_data)

    # ------------------------------------------------------------------
    # TEMİZLEME VE YARDIMCI METOTLAR
    # ------------------------------------------------------------------

    def clear_form(self) -> None:
        answer = QMessageBox.question(
            self,
            "Formu temizle",
            "Girilen maliyet değerleri temizlensin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.last_result = None
        self.last_report_data = None
        self.uretim.setValue(200_000)
        self.usd.setValue(47.4243)
        self.elektrik_kwh_ton.setValue(567)
        self.elektrik.setValue(2.97)
        self.gaz_sm3_ton.setValue(48)
        self.gaz.setValue(18.90)
        self.gaz_kullanim.setValue(0)
        self.gaz_otv.setValue(0)
        self.su_m3_ton.setValue(0.5)
        self.su_birim_fiyat.setValue(106.31)

        for spinbox in (
            self.iscilik,
            self.sgk,
            self.bakim,
            self.ekipman,
            self.tenefer_nakliye,
            self.diger,
        ):
            spinbox.setValue(0)

        self.excel_button.setEnabled(False)
        self.pdf_button.setEnabled(False)
        self.reset_result_box()

    def reset_result_box(self) -> None:
        self.items_total_tl_value.setText("0,00 TL")
        self.items_total_value.setText("0,00 USD")
        self.unit_tl_kg_value.setText("0,0000 TL/kg")
        self.unit_kg_value.setText("0,0000 USD/kg")
        self.unit_ton_value.setText("0,00 USD/ton")
        self.production_value.setText("0 kg")

        for row in range(self.cost_table.rowCount()):
            for column in range(2, self.cost_table.columnCount()):
                self.cost_table.item(row, column).setText(
                    "0,0000" if column == 4 else "0,00"
                )

        self.detail_label.setText(
            "Hesaplama için değerleri girin ve HESAPLA düğmesine basın."
        )

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
        spinbox.setMinimumWidth(155)
        spinbox.setKeyboardTracking(False)
        spinbox.setReadOnly(read_only)
        return spinbox

    def make_money_spinbox(self) -> QDoubleSpinBox:
        return self.make_spinbox(
            value=0,
            maximum=10_000_000_000,
            decimals=2,
            suffix=" TL/ay",
        )

    @staticmethod
    def add_field(
        layout: QGridLayout,
        row: int,
        label_text: str,
        widget: QWidget,
    ) -> None:
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label, row, 0)
        layout.addWidget(widget, row, 1)

    @staticmethod
    def safe_number(value: Any) -> float:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return 0.0
        return number if math.isfinite(number) else 0.0

    @staticmethod
    def tl_total_to_usd_ton(
        total_tl: float,
        production_kg: float,
        usd_rate: float,
    ) -> float:
        if production_kg <= 0 or usd_rate <= 0:
            return 0.0
        return (total_tl / production_kg) * 1000 / usd_rate

    @staticmethod
    def format_number(value: float, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def format_tl(self, value: float) -> str:
        return f"{self.format_number(value, 2)} TL"

    def format_usd_ton(self, value: float) -> str:
        return f"{self.format_number(value, 2)} USD/ton"

    # ------------------------------------------------------------------
    # GÖRSEL STİL
    # ------------------------------------------------------------------

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            QWidget {
                background-color: #F4F7FB;
                color: #1F2937;
            }

            QScrollArea,
            QScrollArea > QWidget > QWidget {
                background-color: #F4F7FB;
            }

            #headerCard,
            #buttonBar {
                background-color: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 12px;
            }

            #mainTitle {
                color: #163A70;
                font-size: 27px;
                font-weight: 700;
            }

            #subtitle {
                color: #667085;
                font-size: 13px;
            }
            #headerCard QLabel {
                background-color: transparent;
            }

            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 12px;
                margin-top: 14px;
                padding: 18px 12px 12px 12px;
                font-size: 13px;
                font-weight: 700;
                color: #163A70;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 7px;
                background-color: #FFFFFF;
            }

            #fieldLabel {
                color: #344054;
                font-weight: 500;
            }

            #groupNote {
                color: #667085;
                font-size: 11px;
                font-style: italic;
                padding-top: 4px;
            }

            QDoubleSpinBox {
                min-height: 34px;
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
                padding: 0 8px;
                color: #101828;
                font-weight: 600;
            }

            QDoubleSpinBox:focus {
                border: 2px solid #2563EB;
            }

            QPushButton {
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
            }

            #primaryButton {
                background-color: #163A70;
                color: #FFFFFF;
                border: 1px solid #163A70;
            }

            #primaryButton:hover {
                background-color: #1E4E94;
            }

            #detailOpenButton {
                background-color: #E8F1FB;
                color: #163A70;
                border: 1px solid #9EB1C8;
                min-height: 35px;
            }

            #detailOpenButton:hover {
                background-color: #DCEBFA;
            }

            #secondaryButton {
                background-color: #FFFFFF;
                color: #344054;
                border: 1px solid #CBD5E1;
            }

            #secondaryButton:hover,
            #exportButton:hover {
                background-color: #F2F4F7;
            }

            #exportButton {
                background-color: #FFFFFF;
                color: #163A70;
                border: 1px solid #8FA7C7;
            }

            #exportButton:disabled {
                color: #98A2B3;
                border-color: #D0D5DD;
                background-color: #F9FAFB;
            }

            #resultCard,
            #totalCard {
                background-color: #F8FAFC;
                border: 1px solid #DCE3EC;
                border-radius: 10px;
            }

            #totalCard {
                background-color: #163A70;
                border-color: #163A70;
            }

            #resultCard QLabel,
            #totalCard QLabel {
                background-color: transparent;
            }

            #resultTitle {
                color: #667085;
                font-size: 11px;
                font-weight: 700;
            }

            #resultValue {
                color: #163A70;
                font-size: 18px;
                font-weight: 700;
            }

            #totalCard #resultTitle,
            #totalValue {
                color: #FFFFFF;
            }

            #totalValue {
                font-size: 19px;
                font-weight: 700;
            }

            #detailLabel {
                background-color: #F8FAFC;
                border: 1px solid #E4E7EC;
                border-radius: 8px;
                padding: 12px;
                color: #475467;
                line-height: 1.4;
            }

            #costSummaryTable {
                background-color: #FFFFFF;
                alternate-background-color: #F7F9FC;
                border: 1px solid #DCE3EC;
                border-radius: 8px;
                gridline-color: #E4E7EC;
                color: #1F2937;
                selection-background-color: #DCEBFA;
                selection-color: #102A4C;
            }

            #costSummaryTable::item {
                padding: 7px;
            }

            #costSummaryTable QHeaderView::section {
                background-color: #163A70;
                color: #FFFFFF;
                border: 0;
                border-right: 1px solid #365A89;
                padding: 8px 6px;
                font-weight: 700;
            }
            """
        ))
