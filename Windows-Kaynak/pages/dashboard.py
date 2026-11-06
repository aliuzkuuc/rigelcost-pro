from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pages.production_dashboard import MonthlyProductionChart, ProductionDataDialog
from services.production_data import MONTHS, ProductionDataStore
from ui.corporate_theme import stylesheet


class DashboardPage(QWidget):
    """Uygulamanın maliyet sonucu göstermeyen yönetim ana sayfası."""

    open_cost_requested = Signal()
    open_expenses_requested = Signal()
    open_pallet_requested = Signal()
    open_inventory_requested = Signal()
    open_stock_movement_requested = Signal()
    open_die_requested = Signal()
    open_department_requested = Signal(str, str)

    def __init__(self, username: str = "") -> None:
        super().__init__()
        self.username = username
        self.production_store = ProductionDataStore()
        self.production_record = self.production_store.load()
        self._compact_layout: bool | None = None
        self.quick_cards: list[QFrame] = []
        self.build_ui()
        self.apply_style()
        self.apply_responsive_layout(force=True)

    def build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("dashboardScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("dashboardContainer")
        content = QVBoxLayout(container)
        content.setContentsMargins(24, 20, 24, 26)
        content.setSpacing(14)

        self.create_hero(content)

        self.quick_title = self.create_section_title(
            "HIZLI İŞLEMLER",
            "Günlük kullanılan ekranlara tek tıkla ulaşın.",
        )
        content.addWidget(self.quick_title)

        self.quick_grid = QGridLayout()
        self.quick_grid.setHorizontalSpacing(10)
        self.quick_grid.setVerticalSpacing(10)
        self.quick_cards = [
            self.create_quick_card(
                "01",
                "MALİYET HESABI",
                "15 gider kalemini hesapla",
                "AÇ",
                self.open_cost_requested.emit,
                primary=True,
            ),
            self.create_quick_card(
                "02",
                "GİDER GİRİŞİ",
                "Aylık gider detaylarını kaydet",
                "AÇ",
                self.open_expenses_requested.emit,
            ),
            self.create_quick_card(
                "03",
                "PALET HESABI",
                "Paketleme sarflarını hesapla",
                "AÇ",
                self.open_pallet_requested.emit,
            ),
            self.create_quick_card(
                "04",
                "STOK HAREKETİ",
                "Giriş, çıkış veya sayım kaydet",
                "AÇ",
                self.open_stock_movement_requested.emit,
            ),
        ]
        content.addLayout(self.quick_grid)

        self.production_panel = self.create_production_panel()
        content.addWidget(self.production_panel)

        self.main_grid = QGridLayout()
        self.main_grid.setHorizontalSpacing(12)
        self.main_grid.setVerticalSpacing(12)
        self.module_area = self.create_module_area()
        self.side_area = self.create_side_area()
        content.addLayout(self.main_grid)

        self.workflow = QFrame()
        self.workflow.setObjectName("workflowBar")
        workflow_layout = QHBoxLayout(self.workflow)
        workflow_layout.setContentsMargins(16, 11, 16, 11)
        workflow_layout.setSpacing(12)
        workflow_title = QLabel("ÖNERİLEN GÜNLÜK AKIŞ")
        workflow_title.setObjectName("workflowTitle")
        workflow_text = QLabel(
            "1  Giderleri güncelle   →   2  Net üretimi gir   →   "
            "3  Maliyeti hesapla   →   4  Excel/PDF raporu al"
        )
        workflow_text.setObjectName("workflowText")
        workflow_text.setWordWrap(True)
        workflow_layout.addWidget(workflow_title)
        workflow_layout.addWidget(workflow_text, 1)
        content.addWidget(self.workflow)
        content.addStretch(1)

        self.scroll.setWidget(container)
        outer.addWidget(self.scroll)

    def create_hero(self, parent: QVBoxLayout) -> None:
        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 16, 22, 16)
        hero_layout.setSpacing(18)

        logo = QLabel()
        logo.setObjectName("dashboardLogo")
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.jpg"
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    125,
                    64,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        hero_layout.addWidget(logo)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        welcome_text = (
            f"HOŞ GELDİN, {self.username.upper()}"
            if self.username
            else "HOŞ GELDİNİZ"
        )
        self.welcome_label = QLabel(welcome_text)
        self.welcome_label.setObjectName("welcomeLabel")
        title = QLabel("Rigel İşletme Yönetim Paneli")
        title.setObjectName("dashboardTitle")
        subtitle = QLabel(
            "Maliyet, paketleme, stok ve işletme modüllerini tek merkezden yönetin."
        )
        subtitle.setObjectName("dashboardSubtitle")
        subtitle.setWordWrap(True)
        hero_text.addWidget(self.welcome_label)
        hero_text.addWidget(title)
        hero_text.addWidget(subtitle)
        hero_layout.addLayout(hero_text, 1)

        hero_status = QFrame()
        hero_status.setObjectName("heroStatus")
        status_layout = QVBoxLayout(hero_status)
        status_layout.setContentsMargins(14, 9, 14, 9)
        status_layout.setSpacing(2)
        date_label = QLabel(datetime.now().strftime("%d.%m.%Y"))
        date_label.setObjectName("todayValue")
        date_label.setAlignment(Qt.AlignCenter)
        ready = QLabel("●  SİSTEM HAZIR")
        ready.setObjectName("systemReady")
        ready.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(date_label)
        status_layout.addWidget(ready)
        hero_layout.addWidget(hero_status)
        parent.addWidget(hero)

    def create_production_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("productionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(2)
        title = QLabel("6 İNÇ 1650 UST PRES - AYLIK REEL ÜRETİM")
        title.setObjectName("productionPanelTitle")
        self.production_description = QLabel()
        self.production_description.setObjectName("productionPanelDescription")
        heading.addWidget(title)
        heading.addWidget(self.production_description)
        header.addLayout(heading, 1)

        self.production_edit_button = QPushButton("VERİ GİR / EXCEL AKTAR")
        self.production_edit_button.setObjectName("productionEditButton")
        self.production_edit_button.clicked.connect(self.open_production_editor)
        header.addWidget(self.production_edit_button)
        layout.addLayout(header)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(9)
        self.production_total_value = self.create_production_kpi(
            kpi_row, "YIL TOPLAMI"
        )
        self.production_average_value = self.create_production_kpi(
            kpi_row, "AYLIK ORTALAMA"
        )
        self.production_best_value = self.create_production_kpi(
            kpi_row, "EN YÜKSEK AY"
        )
        layout.addLayout(kpi_row)

        self.production_chart = MonthlyProductionChart()
        layout.addWidget(self.production_chart)
        self.refresh_production_chart()
        return panel

    @staticmethod
    def create_production_kpi(layout: QHBoxLayout, title: str) -> QLabel:
        card = QFrame()
        card.setObjectName("productionKpi")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 7, 12, 7)
        card_layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("productionKpiTitle")
        value_label = QLabel("0,00 ton")
        value_label.setObjectName("productionKpiValue")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, 1)
        return value_label

    def open_production_editor(self) -> None:
        dialog = ProductionDataDialog(
            self.production_record,
            self.production_store,
            self,
        )
        if dialog.exec() == QDialog.Accepted and dialog.saved_record is not None:
            self.production_record = dialog.saved_record
            self.refresh_production_chart()

    def refresh_production_chart(self) -> None:
        self.production_record = self.production_store.validate_record(
            self.production_record
        )
        values = [float(value) for value in self.production_record["monthly_kg"]]
        positive_values = [value for value in values if value > 0]
        total_kg = sum(values)
        average_kg = total_kg / len(positive_values) if positive_values else 0.0
        best_index = max(range(12), key=values.__getitem__) if positive_values else None

        self.production_description.setText(
            f"{self.production_record['year']} · "
            f"{self.production_record['press_name']} · Değerler aylık net kilogramdır."
        )
        self.production_total_value.setText(
            f"{self.format_number(total_kg / 1000, 2)} ton"
        )
        self.production_average_value.setText(
            f"{self.format_number(average_kg / 1000, 2)} ton"
        )
        self.production_best_value.setText(
            (
                f"{MONTHS[best_index]} · "
                f"{self.format_number(values[best_index] / 1000, 2)} ton"
                if best_index is not None
                else "Henüz veri yok"
            )
        )
        self.production_chart.update_values(values)

    @staticmethod
    def create_section_title(title: str, subtitle: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionHeading")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 2, 0, 0)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("sectionSubtitle")
        subtitle_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label, 1)
        return frame

    @staticmethod
    def create_quick_card(
        number: str,
        title: str,
        description: str,
        button_text: str,
        callback: Callable[[], None],
        *,
        primary: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("quickPrimaryCard" if primary else "quickCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QGridLayout(card)
        layout.setContentsMargins(13, 11, 13, 11)
        layout.setHorizontalSpacing(9)
        layout.setVerticalSpacing(2)

        number_label = QLabel(number)
        number_label.setObjectName(
            "quickPrimaryNumber" if primary else "quickNumber"
        )
        number_label.setAlignment(Qt.AlignCenter)
        number_label.setFixedSize(31, 31)

        title_label = QLabel(title)
        title_label.setObjectName("quickTitle")
        description_label = QLabel(description)
        description_label.setObjectName("quickDescription")
        description_label.setWordWrap(True)

        button = QPushButton(button_text)
        button.setObjectName(
            "quickPrimaryButton" if primary else "quickButton"
        )
        button.setFixedWidth(50)
        button.setMinimumHeight(31)
        button.clicked.connect(callback)

        layout.addWidget(number_label, 0, 0, 2, 1)
        layout.addWidget(title_label, 0, 1)
        layout.addWidget(description_label, 1, 1)
        layout.addWidget(button, 0, 2, 2, 1)
        layout.setColumnStretch(1, 1)
        return card

    def create_module_area(self) -> QFrame:
        area = QFrame()
        area.setObjectName("dashboardPanel")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(
            self.create_section_title(
                "İŞLETME MODÜLLERİ",
                "Aktif ve hazırlanan çalışma alanları",
            )
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(9)
        modules = (
            (
                "MALİYET YÖNETİMİ",
                "15 kalem, gider detayları ve raporlama",
                "AKTİF",
                self.open_cost_requested.emit,
            ),
            (
                "STOK YÖNETİMİ",
                "Billet, profil, hurda ve sarf hareketleri",
                "AKTİF",
                self.open_inventory_requested.emit,
            ),
            (
                "KALIPHANE",
                "Kalıp kartı, bakım, konum ve ömür altyapısı",
                "ALTYAPI HAZIR",
                self.open_die_requested.emit,
            ),
            (
                "ÜRETİM",
                "Üretim planı ve pres üretim kayıtları",
                "AKTİF",
                lambda: self.open_department_requested.emit(
                    "Üretim", "Üretim Siparişleri"
                ),
            ),
            (
                "SATIŞ",
                "Müşteri, teklif ve satış siparişleri",
                "AKTİF",
                lambda: self.open_department_requested.emit(
                    "Satış", "Satış Siparişleri"
                ),
            ),
            (
                "SEVKİYAT",
                "Sevk planı, irsaliye ve hazır kasalar",
                "AKTİF",
                lambda: self.open_department_requested.emit(
                    "Sevkiyat", "Hazır Kasalar"
                ),
            ),
        )
        self.module_cards: dict[str, QFrame] = {}
        for index, (title, description, status, callback) in enumerate(
            modules
        ):
            card = self.create_status_card(
                title,
                description,
                status,
                callback,
            )
            self.module_cards[title] = card
            grid.addWidget(card, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return area

    def configure_access(
        self,
        *,
        cost: bool,
        material: bool,
        die: bool,
        production: bool,
        sales: bool,
        shipping: bool,
    ) -> None:
        """Ana sayfada yalnızca kullanıcının erişebildiği kısayolları gösterir."""
        quick_visibility = (cost, cost, cost, material)
        for card, visible in zip(self.quick_cards, quick_visibility):
            card.setVisible(visible)
        self.quick_title.setVisible(any(quick_visibility))
        for title, visible in {
            "MALİYET YÖNETİMİ": cost,
            "STOK YÖNETİMİ": material,
            "KALIPHANE": die,
            "ÜRETİM": production,
            "SATIŞ": sales,
            "SEVKİYAT": shipping,
        }.items():
            self.module_cards[title].setVisible(visible)
        self.production_panel.setVisible(production)
        self.workflow.setVisible(cost)

    @staticmethod
    def create_status_card(
        title: str,
        description: str,
        status: str,
        callback: Callable[[], None] | None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("statusCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("statusCardTitle")
        status_label = QLabel(status)
        status_label.setObjectName(
            "activeStatus" if callback is not None else "plannedStatus"
        )
        status_label.setAlignment(Qt.AlignCenter)
        top.addWidget(title_label, 1)
        top.addWidget(status_label)

        description_label = QLabel(description)
        description_label.setObjectName("statusCardDescription")
        description_label.setWordWrap(True)

        layout.addLayout(top)
        layout.addWidget(description_label)
        if callback is not None:
            button = QPushButton("MODÜLÜ AÇ  →")
            button.setObjectName("statusCardButton")
            button.clicked.connect(callback)
            layout.addWidget(button)
        else:
            waiting = QLabel("İş akışı netleştikçe aktif edilecek.")
            waiting.setObjectName("plannedDescription")
            layout.addWidget(waiting)
        return card

    def create_side_area(self) -> QFrame:
        area = QFrame()
        area.setObjectName("dashboardSide")
        area.setMinimumWidth(285)
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        market = QFrame()
        market.setObjectName("dashboardPanel")
        market_layout = QVBoxLayout(market)
        market_layout.setContentsMargins(16, 14, 16, 14)
        market_layout.setSpacing(8)
        market_layout.addWidget(
            self.create_section_title("PİYASA ÖZETİ", "Canlı değerler")
        )
        self.dashboard_usd = self.add_market_row(
            market_layout, "USD/TL", "47,4243"
        )
        self.dashboard_eur = self.add_market_row(
            market_layout, "EUR/TL", "—"
        )
        self.dashboard_lme = self.add_market_row(
            market_layout, "LME Alüminyum", "3.192,00 USD/ton"
        )
        self.dashboard_market_date = QLabel("Elle girilen başlangıç değerleri")
        self.dashboard_market_date.setObjectName("dashboardMarketDate")
        self.dashboard_market_date.setWordWrap(True)
        market_layout.addWidget(self.dashboard_market_date)
        layout.addWidget(market)

        data_status = QFrame()
        data_status.setObjectName("dashboardPanel")
        status_layout = QVBoxLayout(data_status)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(8)
        status_layout.addWidget(
            self.create_section_title("VERİ DURUMU", "Yerel sistem")
        )
        self.add_health_row(
            status_layout,
            "●",
            "Gider kayıtları",
            "Otomatik kaydediliyor",
        )
        self.add_health_row(
            status_layout,
            "●",
            "Stok veritabanı",
            "Kullanıma hazır",
        )
        self.add_health_row(
            status_layout,
            "●",
            "Paketleme motoru",
            "Net üretime bağlı",
        )
        layout.addWidget(data_status)

        note = QFrame()
        note.setObjectName("dashboardTip")
        note_layout = QVBoxLayout(note)
        note_layout.setContentsMargins(15, 12, 15, 12)
        tip_title = QLabel("HATIRLATMA")
        tip_title.setObjectName("tipTitle")
        tip_text = QLabel(
            "Ana sayfa maliyet sonucu göstermez. Sonuçlar yalnızca "
            "Maliyet Ana ekranında hesaplandıktan sonra görüntülenir."
        )
        tip_text.setObjectName("tipText")
        tip_text.setWordWrap(True)
        note_layout.addWidget(tip_title)
        note_layout.addWidget(tip_text)
        layout.addWidget(note)
        layout.addStretch(1)
        return area

    @staticmethod
    def add_market_row(
        layout: QVBoxLayout,
        title: str,
        initial_value: str,
    ) -> QLabel:
        row = QFrame()
        row.setObjectName("dashboardMarketRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 7, 10, 7)
        title_label = QLabel(title)
        title_label.setObjectName("dashboardMarketTitle")
        value_label = QLabel(initial_value)
        value_label.setObjectName("dashboardMarketValue")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(title_label)
        row_layout.addWidget(value_label, 1)
        layout.addWidget(row)
        return value_label

    @staticmethod
    def add_health_row(
        layout: QVBoxLayout,
        symbol: str,
        title: str,
        detail: str,
    ) -> None:
        row = QHBoxLayout()
        dot = QLabel(symbol)
        dot.setObjectName("healthDot")
        title_label = QLabel(title)
        title_label.setObjectName("healthTitle")
        detail_label = QLabel(detail)
        detail_label.setObjectName("healthDetail")
        detail_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(dot)
        row.addWidget(title_label)
        row.addWidget(detail_label, 1)
        layout.addLayout(row)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.apply_responsive_layout()

    def apply_responsive_layout(
        self,
        *,
        force: bool = False,
        available_width: int | None = None,
    ) -> None:
        width = self.width() if available_width is None else available_width
        compact = width < 1_000
        if compact == self._compact_layout and not force:
            return
        self._compact_layout = compact

        if compact:
            for index, card in enumerate(self.quick_cards):
                self.quick_grid.addWidget(card, index // 2, index % 2)
            self.main_grid.addWidget(self.module_area, 0, 0)
            self.main_grid.addWidget(self.side_area, 1, 0)
            self.main_grid.setColumnStretch(0, 1)
            self.main_grid.setColumnStretch(1, 0)
        else:
            for index, card in enumerate(self.quick_cards):
                self.quick_grid.addWidget(card, 0, index)
            self.main_grid.addWidget(self.module_area, 0, 0)
            self.main_grid.addWidget(self.side_area, 0, 1)
            self.main_grid.setColumnStretch(0, 3)
            self.main_grid.setColumnStretch(1, 1)
        for column in range(4):
            self.quick_grid.setColumnStretch(
                column,
                1 if (not compact or column < 2) else 0,
            )

    def set_market_data(
        self,
        *,
        usd: float = 0,
        eur: float = 0,
        lme: float = 0,
        updated_text: str = "",
    ) -> None:
        if usd > 0:
            self.dashboard_usd.setText(self.format_number(usd, 4))
        if eur > 0:
            self.dashboard_eur.setText(self.format_number(eur, 4))
        if lme > 0:
            self.dashboard_lme.setText(
                f"{self.format_number(lme, 2)} USD/ton"
            )
        if updated_text:
            self.dashboard_market_date.setText(updated_text)

    def set_market_loading(self) -> None:
        self.dashboard_market_date.setText(
            "TCMB kurları ve LME verisi güncelleniyor…"
        )

    def set_market_error(self) -> None:
        self.dashboard_market_date.setText(
            "Bağlantı kurulamadı; son kayıtlı değerler korunuyor."
        )

    @staticmethod
    def format_number(value: float, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        return (
            formatted.replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            DashboardPage,
            #dashboardScroll,
            #dashboardContainer,
            #dashboardScroll > QWidget > QWidget {
                color: #1F2937;
                background: #EEF2F6;
                border: 0;
            }
            #dashboardHero,
            #dashboardPanel,
            #productionPanel,
            #quickCard,
            #quickPrimaryCard,
            #statusCard {
                background: #FFFFFF;
                border: 1px solid #D7E0EA;
                border-radius: 9px;
            }
            #dashboardHero QLabel,
            #dashboardPanel QLabel,
            #productionPanel QLabel,
            #quickCard QLabel,
            #quickPrimaryCard QLabel,
            #statusCard QLabel,
            #workflowBar QLabel,
            #dashboardTip QLabel {
                background: transparent;
            }
            #dashboardHero {
                border-left: 5px solid #163A70;
            }
            #productionPanel {
                background: #FFFFFF;
                border: 1px solid #D7E0EA;
                border-radius: 9px;
                border-left: 5px solid #1F67B1;
            }
            #productionPanelTitle {
                color: #163A70;
                font-size: 14px;
                font-weight: 700;
            }
            #productionPanelDescription {
                color: #667085;
                font-size: 10px;
            }
            #productionEditButton {
                color: #FFFFFF;
                background: #1F67B1;
                border: 1px solid #1F67B1;
                border-radius: 5px;
                min-height: 34px;
                padding: 0 14px;
                font-size: 10px;
                font-weight: 700;
            }
            #productionKpi {
                background: #F4F8FC;
                border: 1px solid #D7E0EA;
                border-radius: 6px;
            }
            #productionKpiTitle {
                color: #667085;
                font-size: 9px;
                font-weight: 700;
            }
            #productionKpiValue {
                color: #163A70;
                font-size: 12px;
                font-weight: 700;
            }
            #productionChartView {
                background: transparent;
                border: 0;
            }
            #welcomeLabel {
                color: #C81E3A;
                font-size: 11px;
                font-weight: 700;
            }
            #dashboardTitle {
                color: #102A4C;
                font-size: 24px;
                font-weight: 700;
            }
            #dashboardSubtitle {
                color: #667085;
                font-size: 11px;
            }
            #heroStatus {
                background: #F4F8FC;
                border: 1px solid #C9D7E6;
                border-radius: 7px;
                min-width: 130px;
            }
            #todayValue {
                color: #163A70;
                font-size: 14px;
                font-weight: 700;
            }
            #systemReady {
                color: #087443;
                font-size: 10px;
                font-weight: 700;
            }
            #sectionTitle {
                color: #344054;
                font-size: 12px;
                font-weight: 700;
            }
            #sectionSubtitle {
                color: #98A2B3;
                font-size: 10px;
            }
            #quickCard,
            #quickPrimaryCard {
                min-height: 68px;
            }
            #quickPrimaryCard {
                background: #F4F9FE;
                border: 2px solid #2B74B8;
            }
            #quickNumber,
            #quickPrimaryNumber {
                color: #163A70;
                background: #E7EEF7;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            #quickPrimaryNumber {
                color: #FFFFFF;
                background: #1F67B1;
            }
            #quickTitle {
                color: #163A70;
                font-size: 12px;
                font-weight: 700;
            }
            #quickDescription {
                color: #667085;
                font-size: 10px;
            }
            #quickButton,
            #quickPrimaryButton {
                color: #163A70;
                background: #FFFFFF;
                border: 1px solid #9EB1C8;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 700;
            }
            #quickPrimaryButton {
                color: #FFFFFF;
                background: #1F67B1;
                border-color: #1F67B1;
            }
            #statusCard {
                min-height: 96px;
                background: #FBFCFE;
            }
            #statusCardTitle {
                color: #163A70;
                font-size: 12px;
                font-weight: 700;
            }
            #statusCardDescription {
                color: #667085;
                font-size: 10px;
            }
            #activeStatus,
            #plannedStatus {
                color: #087443;
                background: #DFF7EA;
                border: 1px solid #A6E5C4;
                border-radius: 5px;
                padding: 2px 5px;
                font-size: 9px;
                font-weight: 700;
            }
            #plannedStatus {
                color: #7A4D00;
                background: #FFF4D6;
                border-color: #F1D590;
            }
            #statusCardButton {
                color: #163A70;
                background: transparent;
                border: 0;
                padding: 2px 0;
                text-align: left;
                font-size: 10px;
                font-weight: 700;
            }
            #plannedDescription {
                color: #98A2B3;
                font-size: 10px;
                font-style: italic;
            }
            #dashboardMarketRow {
                background: #F7F9FC;
                border: 1px solid #E1E7EF;
                border-radius: 6px;
            }
            #dashboardMarketTitle {
                color: #667085;
                font-size: 10px;
                font-weight: 600;
            }
            #dashboardMarketValue {
                color: #163A70;
                font-size: 12px;
                font-weight: 700;
            }
            #dashboardMarketDate {
                color: #667085;
                font-size: 9px;
                font-style: italic;
            }
            #healthDot {
                color: #12A05C;
                font-size: 10px;
            }
            #healthTitle {
                color: #344054;
                font-size: 10px;
                font-weight: 600;
            }
            #healthDetail {
                color: #667085;
                font-size: 9px;
            }
            #dashboardTip {
                background: #E9F2FC;
                border: 1px solid #BAD0E7;
                border-radius: 8px;
            }
            #tipTitle {
                color: #163A70;
                font-size: 10px;
                font-weight: 700;
            }
            #tipText {
                color: #475467;
                font-size: 10px;
            }
            #workflowBar {
                background: #163A70;
                border-radius: 8px;
            }
            #workflowTitle {
                color: #FFFFFF;
                font-size: 10px;
                font-weight: 700;
            }
            #workflowText {
                color: #E7EEF7;
                font-size: 10px;
            }
            """
        ))
