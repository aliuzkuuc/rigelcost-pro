from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.production_data import MONTHS, ProductionDataStore
from ui.corporate_theme import stylesheet


def format_tr(value: float, decimals: int = 2) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


class MonthlyProductionChart(QWidget):
    """12 aylık reel ekstrüzyon üretimini kurumsal çubuk grafikle gösterir."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.NoAnimation)
        self.chart.setBackgroundVisible(False)
        self.chart.legend().hide()
        self.chart.setMargins(QMargins(0, 4, 0, 0))

        self.chart_view = QChartView(self.chart)
        self.chart_view.setObjectName("productionChartView")
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(275)
        layout.addWidget(self.chart_view)
        self.update_values([0.0] * 12)

    def update_values(self, monthly_kg: list[float]) -> None:
        values = [
            max(0.0, float(monthly_kg[index] if index < len(monthly_kg) else 0))
            / 1000
            for index in range(12)
        ]
        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)

        bar_set = QBarSet("Reel Üretim")
        bar_set.append(values)
        bar_set.setColor(QColor("#1F67B1"))
        bar_set.setBorderColor(QColor("#163A70"))
        bar_set.hovered.connect(
            lambda status, index: self.chart_view.setToolTip(
                (
                    f"{MONTHS[index]}: {format_tr(values[index], 2)} ton"
                    if status and 0 <= index < len(values)
                    else ""
                )
            )
        )

        series = QBarSeries()
        series.append(bar_set)
        series.setBarWidth(0.72)
        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(list(MONTHS))
        axis_x.setLabelsAngle(-35)
        axis_x.setLabelsColor(QColor("#475467"))

        maximum = max(values) if values else 0.0
        axis_maximum = max(10.0, maximum * 1.18)
        axis_y = QValueAxis()
        axis_y.setRange(0, axis_maximum)
        axis_y.setTickCount(6)
        axis_y.setLabelFormat("%.0f")
        axis_y.setTitleText("TON")
        axis_y.setLabelsColor(QColor("#475467"))
        axis_y.setTitleBrush(QColor("#344054"))
        axis_y.setGridLineColor(QColor("#DDE5EE"))

        self.chart.addAxis(axis_x, Qt.AlignBottom)
        self.chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)


class ProductionDataDialog(QDialog):
    """Aylık üretimin manuel veya Excel üzerinden girildiği pencere."""

    def __init__(
        self,
        record: dict[str, Any],
        store: ProductionDataStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.saved_record: dict[str, Any] | None = None
        self.setWindowTitle("Aylık Reel Üretim Verileri")
        self.setObjectName("productionDataDialog")
        self.resize(760, 720)
        self.setMinimumSize(680, 620)
        self.build_ui()
        self.load_record(record)
        self.apply_style()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("AYLIK REEL ÜRETİM GİRİŞİ")
        title.setObjectName("productionDialogTitle")
        subtitle = QLabel(
            "6 inç 1650 UST ekstrüzyon presinin aylık net üretimini "
            "elle girin veya Excel dosyasından aktarın."
        )
        subtitle.setObjectName("productionDialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form_frame = QFrame()
        form_frame.setObjectName("productionFormFrame")
        form = QFormLayout(form_frame)
        form.setContentsMargins(14, 12, 14, 12)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        self.press_name = QLineEdit()
        self.press_name.setObjectName("productionPressName")
        self.year = QSpinBox()
        self.year.setObjectName("productionYear")
        self.year.setRange(2000, 2100)
        self.year.setAlignment(Qt.AlignRight)
        form.addRow("Pres", self.press_name)
        form.addRow("Yıl", self.year)
        layout.addWidget(form_frame)

        self.table = QTableWidget(12, 3)
        self.table.setObjectName("productionEntryTable")
        self.table.setHorizontalHeaderLabels(
            ["Ay", "Aylık Üretim (kg)", "Aylık Üretim (ton)"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for row, month in enumerate(MONTHS):
            month_item = QTableWidgetItem(month)
            month_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            month_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, month_item)

            value = QDoubleSpinBox()
            value.setObjectName(f"productionMonth{row + 1}")
            value.setRange(0, 100_000_000)
            value.setDecimals(2)
            value.setGroupSeparatorShown(True)
            value.setSuffix(" kg")
            value.setAlignment(Qt.AlignRight)
            value.setKeyboardTracking(False)
            value.valueChanged.connect(
                lambda amount, row=row: self.update_ton_value(row, amount)
            )
            self.table.setCellWidget(row, 1, value)

            ton_item = QTableWidgetItem("0,00")
            ton_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            ton_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, ton_item)
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.import_button = QPushButton("EXCEL'DEN AKTAR")
        self.import_button.setObjectName("productionImportButton")
        self.import_button.clicked.connect(self.choose_excel)
        cancel_button = QPushButton("VAZGEÇ")
        cancel_button.setObjectName("productionCancelButton")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("KAYDET VE GRAFİĞİ GÜNCELLE")
        save_button.setObjectName("productionSaveButton")
        save_button.clicked.connect(self.save_and_accept)
        button_row.addWidget(self.import_button)
        button_row.addStretch(1)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def load_record(self, record: dict[str, Any]) -> None:
        validated = self.store.validate_record(record)
        self.press_name.setText(str(validated["press_name"]))
        self.year.setValue(int(validated["year"]))
        for row, value in enumerate(validated["monthly_kg"]):
            editor = self.table.cellWidget(row, 1)
            if isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(value))

    def update_ton_value(self, row: int, amount_kg: float) -> None:
        item = self.table.item(row, 2)
        if item is not None:
            item.setText(format_tr(amount_kg / 1000, 2))

    def choose_excel(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Aylık üretim Excel dosyasını seçin",
            str(Path.home() / "Desktop"),
            "Excel Dosyaları (*.xlsx *.xlsm)",
        )
        if source:
            self.import_from_path(source, show_message=True)

    def import_from_path(
        self,
        source: str | Path,
        *,
        show_message: bool = False,
    ) -> bool:
        try:
            imported = self.store.import_excel(source)
        except ValueError as exc:
            if show_message:
                QMessageBox.warning(self, "Aktarım tamamlanamadı", str(exc))
            return False
        imported["press_name"] = self.press_name.text().strip() or imported["press_name"]
        self.load_record(imported)
        if show_message:
            filled = sum(1 for value in imported["monthly_kg"] if value > 0)
            QMessageBox.information(
                self,
                "Excel aktarımı tamamlandı",
                f"{filled} aya ait üretim değeri bulundu. Kaydettiğinizde grafik güncellenecek.",
            )
        return True

    def collect_record(self) -> dict[str, Any]:
        monthly_kg: list[float] = []
        for row in range(12):
            editor = self.table.cellWidget(row, 1)
            monthly_kg.append(
                editor.value() if isinstance(editor, QDoubleSpinBox) else 0.0
            )
        return {
            "schema_version": 1,
            "year": self.year.value(),
            "press_name": self.press_name.text().strip(),
            "monthly_kg": monthly_kg,
        }

    def save_and_accept(self) -> None:
        if not self.press_name.text().strip():
            QMessageBox.warning(self, "Eksik bilgi", "Pres adını girin.")
            return
        try:
            self.saved_record = self.store.save(self.collect_record())
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Kayıt tamamlanamadı",
                f"Üretim verileri kaydedilemedi: {exc}",
            )
            return
        self.accept()

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            #productionDataDialog { background: #EEF2F6; }
            #productionDialogTitle {
                color: #163A70;
                font-size: 18pt;
                font-weight: 700;
            }
            #productionDialogSubtitle { color: #667085; font-size: 9pt; }
            #productionFormFrame {
                background: #FFFFFF;
                border: 1px solid #D7E0EA;
                border-radius: 7px;
            }
            #productionEntryTable {
                color: #1D2939;
                background: #FFFFFF;
                alternate-background-color: #F5F8FC;
                border: 1px solid #C9D7E6;
                gridline-color: #D7E0EA;
            }
            #productionEntryTable QHeaderView::section {
                color: #FFFFFF;
                background: #163A70;
                border: 0;
                padding: 7px;
                font-weight: 700;
            }
            #productionImportButton, #productionSaveButton {
                color: #FFFFFF;
                background: #1F67B1;
                border: 1px solid #1F67B1;
                border-radius: 5px;
                min-height: 36px;
                padding: 0 16px;
                font-weight: 700;
            }
            #productionCancelButton {
                color: #344054;
                background: #FFFFFF;
                border: 1px solid #AFC3DC;
                border-radius: 5px;
                min-height: 36px;
                padding: 0 16px;
                font-weight: 700;
            }
            """
        ))
