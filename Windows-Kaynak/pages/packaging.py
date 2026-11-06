from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.packaging_calculator import PackagingCalculator
from ui.corporate_theme import stylesheet


class PackagingPage(QWidget):
    """Excel referansındaki palet ve paketleme maliyet ekranı."""

    calculation_completed = Signal(float)

    def __init__(self) -> None:
        super().__init__()

        self.calculator = PackagingCalculator()
        self.last_total = 0.0
        self.build_ui()
        self.apply_style()

    def build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 24)
        main_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("packagingHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("PAKETLEME MALİYETİ")
        title.setObjectName("packagingTitle")
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Palet sayısı üretimden otomatik hesaplanır; Excel'deki kereste, "
            "köşebent, çember, naylon ve streç formülleri üretime göre uygulanır."
        )
        subtitle.setObjectName("packagingSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        main_layout.addWidget(header)

        groups_layout = QGridLayout()
        groups_layout.setHorizontalSpacing(14)
        groups_layout.setColumnStretch(0, 1)
        groups_layout.setColumnStretch(1, 2)

        reference_group = QGroupBox("Üretim ve Palet")
        reference_layout = QGridLayout(reference_group)
        reference_layout.setColumnStretch(1, 1)

        self.uretim = self.make_spinbox(
            200_000, 100_000_000, 0, " kg", read_only=True
        )
        self.usd = self.make_spinbox(
            47.4243, 10_000, 4, " TL", read_only=True
        )
        self.referans_uretim = self.make_spinbox(
            200_000, 100_000_000, 0, " kg", read_only=True
        )
        self.ortalama_palet_kg = self.make_spinbox(
            650, 100_000, 2, " kg"
        )
        self.yansiz_oran = self.make_spinbox(75, 100, 2, " %")

        self.add_field(reference_layout, 0, 0, "Aylık üretim", self.uretim)
        self.add_field(reference_layout, 1, 0, "USD/TL kuru", self.usd)
        self.add_field(
            reference_layout,
            2,
            0,
            "Gider referans üretimi",
            self.referans_uretim,
        )
        self.add_field(
            reference_layout,
            3,
            0,
            "Ortalama palet ağırlığı",
            self.ortalama_palet_kg,
        )
        self.add_field(
            reference_layout, 4, 0, "Yansız palet oranı", self.yansiz_oran
        )

        material_group = QGroupBox("Paketleme Birim Değerleri")
        material_layout = QGridLayout(material_group)
        material_layout.setHorizontalSpacing(10)
        material_layout.setVerticalSpacing(9)
        material_layout.setColumnStretch(1, 1)
        material_layout.setColumnStretch(3, 1)

        self.kereste_m3_fiyat = self.make_spinbox(
            14_000, 10_000_000, 2, " TL/m³"
        )
        self.kosebent_birim_fiyat = self.make_spinbox(
            12.25, 1_000_000, 2, " TL/adet"
        )
        self.cember_1000mt_fiyat = self.make_spinbox(
            2_000, 10_000_000, 2, " TL/1000 m"
        )
        self.naylon_kg_palet = self.make_spinbox(
            8, 10_000, 2, " kg/palet"
        )
        self.naylon_usd_ton = self.make_spinbox(
            3_100, 100_000, 2, " USD/ton"
        )
        self.strec_adet = self.make_spinbox(
            168, 10_000_000, 2, " adet"
        )
        self.strec_birim_fiyat = self.make_spinbox(
            48, 1_000_000, 2, " TL/adet"
        )
        self.etiket = self.make_spinbox(
            0, 1_000_000_000, 2, " TL/ay"
        )

        material_fields = [
            ("Kereste m³ fiyatı", self.kereste_m3_fiyat),
            ("Köşebent birim fiyatı", self.kosebent_birim_fiyat),
            ("Çember fiyatı", self.cember_1000mt_fiyat),
            ("Palet başı naylon", self.naylon_kg_palet),
            ("Naylon fiyatı", self.naylon_usd_ton),
            ("Streç adedi (referans)", self.strec_adet),
            ("Streç birim fiyatı", self.strec_birim_fiyat),
            ("Etiket gideri (referans)", self.etiket),
        ]
        for index, (label, widget) in enumerate(material_fields):
            row = index // 2
            column = (index % 2) * 2
            self.add_field(material_layout, row, column, label, widget)

        groups_layout.addWidget(reference_group, 0, 0)
        groups_layout.addWidget(material_group, 0, 1)
        main_layout.addLayout(groups_layout)

        button_bar = QFrame()
        button_bar.setObjectName("packagingButtonBar")
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(14, 10, 14, 10)
        button_layout.setSpacing(10)

        self.calculate_button = QPushButton("HESAPLA VE MALİYETE AKTAR")
        self.calculate_button.setObjectName("packagingPrimaryButton")
        self.calculate_button.setMinimumHeight(42)
        self.calculate_button.clicked.connect(self.hesapla)

        self.clear_button = QPushButton("VARSAYILANLARA DÖN")
        self.clear_button.setObjectName("packagingSecondaryButton")
        self.clear_button.setMinimumHeight(42)
        self.clear_button.clicked.connect(self.clear_form)

        button_layout.addWidget(self.calculate_button, 2)
        button_layout.addWidget(self.clear_button, 1)
        main_layout.addWidget(button_bar)

        result_card = QFrame()
        result_card.setObjectName("packagingResult")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(20, 15, 20, 15)

        result_title = QLabel("TOPLAM PAKETLEME")
        result_title.setObjectName("packagingResultTitle")
        result_title.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(result_title)

        self.sonuc = QLabel("0,00 TL/ay")
        self.sonuc.setObjectName("packagingResultValue")
        self.sonuc.setAlignment(Qt.AlignCenter)
        self.sonuc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_layout.addWidget(self.sonuc)

        self.detail = QLabel(
            "Değerleri kontrol edip hesaplama düğmesine basın."
        )
        self.detail.setObjectName("packagingTransferNote")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_layout.addWidget(self.detail)

        main_layout.addWidget(result_card)
        main_layout.addStretch(1)

    def hesapla(self) -> None:
        try:
            result = self.calculator.excel_hesapla(
                uretim=self.uretim.value(),
                usd=self.usd.value(),
                ortalama_palet_kg=self.ortalama_palet_kg.value(),
                yansiz_oran=self.yansiz_oran.value() / 100,
                kereste_m3_fiyat=self.kereste_m3_fiyat.value(),
                kosebent_birim_fiyat=self.kosebent_birim_fiyat.value(),
                cember_1000mt_fiyat=self.cember_1000mt_fiyat.value(),
                naylon_kg_palet=self.naylon_kg_palet.value(),
                naylon_usd_ton=self.naylon_usd_ton.value(),
                strec_adet=self.strec_adet.value(),
                strec_birim_fiyat=self.strec_birim_fiyat.value(),
                etiket=self.etiket.value(),
                referans_uretim=self.referans_uretim.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Geçersiz değer", str(exc))
            return

        self.last_total = result["toplam"]
        self.sonuc.setText(f"{self.format_number(self.last_total)} TL/ay")
        self.detail.setText(
            f"{self.format_number(result['palet_adedi'], 0)} palet | "
            f"Kereste {self.format_number(result['kereste'])} TL | "
            f"Köşebent {self.format_number(result['kosebent'])} TL | "
            f"Çember {self.format_number(result['cember'])} TL | "
            f"Naylon {self.format_number(result['naylon'])} TL | "
            f"Streç {self.format_number(result['strec_adedi'], 2)} adet / "
            f"{self.format_number(result['strec'])} TL<br>"
            "Toplam ana maliyet ekranına aktarıldı."
        )
        self.calculation_completed.emit(self.last_total)

    def set_production(self, value: float) -> None:
        self.uretim.setValue(max(0.0, float(value)))
        self.recalculate_if_ready()

    def set_usd_rate(self, value: float) -> None:
        self.usd.setValue(max(0.0, float(value)))
        self.recalculate_if_ready()

    def set_reference_production(self, value: float) -> None:
        self.referans_uretim.setValue(max(0.0, float(value)))
        self.recalculate_if_ready()

    def recalculate_if_ready(self) -> None:
        if (
            self.uretim.value() > 0
            and self.usd.value() > 0
            and self.referans_uretim.value() > 0
        ):
            self.hesapla()

    def clear_form(self) -> None:
        self.ortalama_palet_kg.setValue(650)
        self.yansiz_oran.setValue(75)
        self.kereste_m3_fiyat.setValue(14_000)
        self.kosebent_birim_fiyat.setValue(12.25)
        self.cember_1000mt_fiyat.setValue(2_000)
        self.naylon_kg_palet.setValue(8)
        self.naylon_usd_ton.setValue(3_100)
        self.strec_adet.setValue(168)
        self.strec_birim_fiyat.setValue(48)
        self.etiket.setValue(0)
        self.hesapla()

    @staticmethod
    def make_spinbox(
        value: float,
        maximum: float,
        decimals: int,
        suffix: str,
        *,
        read_only: bool = False,
    ) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0, maximum)
        spinbox.setDecimals(decimals)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        spinbox.setGroupSeparatorShown(True)
        spinbox.setAlignment(Qt.AlignRight)
        spinbox.setMinimumHeight(34)
        spinbox.setMinimumWidth(155)
        spinbox.setKeyboardTracking(False)
        spinbox.setReadOnly(read_only)
        return spinbox

    @staticmethod
    def add_field(
        layout: QGridLayout,
        row: int,
        column: int,
        text: str,
        widget: QWidget,
    ) -> None:
        label = QLabel(text)
        label.setObjectName("packagingFieldLabel")
        layout.addWidget(label, row, column)
        layout.addWidget(widget, row, column + 1)

    @staticmethod
    def format_number(value: float, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            PackagingPage {
                background-color: #F4F7FB;
                color: #1F2937;
            }
            #packagingHeader, #packagingButtonBar {
                background-color: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 12px;
            }
            #packagingTitle {
                color: #163A70;
                font-size: 24px;
                font-weight: 700;
            }
            #packagingSubtitle, #packagingTransferNote {
                color: #667085;
                font-size: 12px;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 12px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                color: #163A70;
                font-size: 13px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 7px;
                background-color: #FFFFFF;
            }
            #packagingFieldLabel {
                color: #344054;
                font-weight: 500;
            }
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
                padding: 0 8px;
                color: #101828;
                font-weight: 600;
            }
            QDoubleSpinBox:read-only {
                background-color: #EEF2F6;
                color: #475467;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #2563EB;
            }
            QPushButton {
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
            }
            #packagingPrimaryButton {
                background-color: #163A70;
                color: #FFFFFF;
                border: 1px solid #163A70;
            }
            #packagingPrimaryButton:hover {
                background-color: #1E4E94;
            }
            #packagingSecondaryButton {
                background-color: #FFFFFF;
                color: #344054;
                border: 1px solid #CBD5E1;
            }
            #packagingSecondaryButton:hover {
                background-color: #F2F4F7;
            }
            #packagingResult {
                background-color: #163A70;
                border: 1px solid #163A70;
                border-radius: 12px;
            }
            #packagingResultTitle {
                color: #D8E5F5;
                background-color: transparent;
                font-size: 11px;
                font-weight: 700;
            }
            #packagingResultValue {
                color: #FFFFFF;
                background-color: transparent;
                font-size: 25px;
                font-weight: 700;
            }
            #packagingResult #packagingTransferNote {
                color: #D8E5F5;
                background-color: transparent;
            }
            """
        ))
