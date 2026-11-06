from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pages.department import DepartmentPage
from pages.data_import import DataImportDialog
from pages.auth import FirstOwnerDialog, LoginDialog
from pages.dashboard import DashboardPage
from pages.expense_details import ExpenseDetailsPage
from pages.home import HomePage
from pages.inventory import InventoryPage
from pages.server_setup import ServerSetupDialog
from pages.users import UsersDialog
from pages.workflow import WorkflowPage
from reports.exporters import export_excel, export_pdf
from models.erp_definitions import DEPARTMENT_MODULES, get_module_spec
from services.market_data import MarketDataService
from services.data_import import DataImportService
from services.central_database import central_database_enabled
from services.auth import (
    ERP_CREATE,
    ERP_DELETE,
    ERP_EDIT,
    EXPORT_REPORTS,
    MANAGE_USERS,
    UPDATE_MARKET,
    VIEW_COST,
    VIEW_DASHBOARD,
    VIEW_DIE,
    VIEW_MAINTENANCE,
    VIEW_MATERIAL,
    VIEW_PRODUCTION,
    VIEW_PURCHASE,
    VIEW_REPORTS,
    VIEW_SALES,
    VIEW_SETTINGS,
    VIEW_SHIPPING,
    AuthService,
    UserSession,
)


DASHBOARD_PAGE = 0
COST_PAGE = 1
EXPENSE_DETAILS_PAGE = 2
INVENTORY_PAGE = 3
DEPARTMENT_PAGE = 4
WORKFLOW_PAGE = 5


from ui.rigel_theme import rigel_main_window_styles
from ui.corporate_theme import (
    apply_corporate_typography,
    apply_rigel_typography,
    build_global_form_stylesheet,
    resolve_corporate_font_family,
    stylesheet,
)
from ui.exit_dialog import ExitConfirmDialog


def apply_rigel_light_palette(app: QApplication) -> None:
    """İşletim sistemi koyu temada olsa da form metinlerini görünür tutar."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#EEF2F6"))
    palette.setColor(QPalette.WindowText, QColor("#1D2939"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F5F8FC"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#1D2939"))
    palette.setColor(QPalette.Text, QColor("#101828"))
    palette.setColor(QPalette.Button, QColor("#F8FAFC"))
    palette.setColor(QPalette.ButtonText, QColor("#1D2939"))
    palette.setColor(QPalette.BrightText, QColor("#B42318"))
    palette.setColor(QPalette.Highlight, QColor("#0B74BE"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor("#667085"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#667085"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#667085"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#667085"))
    app.setPalette(palette)


def apply_rigel_flat_theme(app: QApplication) -> None:
    """Tüm platformlarda aynı, düz ve yüksek okunaklı form temasını uygular."""
    family = str(app.property("rigelCorporateFont") or resolve_corporate_font_family())
    app.setStyleSheet(build_global_form_stylesheet(family))


class WheelValueGuard(QObject):
    """Fare tekerleğinin giriş değerlerini fark edilmeden değiştirmesini önler."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Wheel or not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)

        editor: QWidget | None = watched
        while editor is not None and not isinstance(
            editor,
            (QAbstractSpinBox, QComboBox),
        ):
            editor = editor.parentWidget()
        if editor is None:
            return super().eventFilter(watched, event)

        scroll_parent: QWidget | None = watched.parentWidget()
        while scroll_parent is not None:
            if isinstance(scroll_parent, QAbstractScrollArea):
                bar = scroll_parent.verticalScrollBar()
                delta = event.angleDelta().y()
                if delta == 0:
                    delta = event.pixelDelta().y()
                if delta:
                    step = max(bar.singleStep() * 3, 36)
                    bar.setValue(
                        bar.value() - round((delta / 120) * step)
                    )
                break
            scroll_parent = scroll_parent.parentWidget()

        event.accept()
        return True


class MainWindow(QMainWindow):
    """Rigel'in maliyet ve işletme süreçlerini yöneten ana ekranı."""

    def __init__(
        self,
        *,
        username: str = "",
        session: UserSession | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        super().__init__()

        self.session = session or UserSession.owner(username)
        self.auth_service = auth_service or AuthService()
        self.username = self.session.display_name
        self.install_wheel_value_guard()
        self.setWindowTitle("RIGEL COST PRO")
        self.resize(1360, 900)
        self.setMinimumSize(1020, 720)

        icon_path = Path(__file__).resolve().parent / "assets" / "rigel.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.dashboard_page = DashboardPage(self.username)
        self.home_page = HomePage()
        self.expense_details_page = ExpenseDetailsPage()
        self.inventory_page = InventoryPage()
        self.inventory_page.set_access(can_create=self.can(ERP_CREATE))
        self.department_page = DepartmentPage()
        self.department_page.set_access(
            can_create=self.can(ERP_CREATE),
            can_edit=self.can(ERP_EDIT),
            can_delete=self.can(ERP_DELETE),
        )
        self.workflow_page = WorkflowPage(username=self.session.username)
        self.workflow_page.set_access(
            can_create=self.can(ERP_CREATE),
            can_approve=self.can(VIEW_PRODUCTION) and self.can(ERP_CREATE),
            can_edit=self.can(ERP_EDIT),
            can_delete=self.can(ERP_DELETE),
        )
        self.market_service = MarketDataService(self)

        self.build_toolbar()
        self.build_rigel_quick_toolbar()
        self.build_central_ui()
        self.connect_signals()
        self.apply_style()

        user_status = QLabel(
            f"Kullanıcı : {self.session.display_name.upper()}"
        )
        self.statusBar().addWidget(user_status)
        self.status_footer_usd = QLabel("USD/TRY : —")
        self.status_footer_eur = QLabel("EUR/TRY : —")
        self.status_footer_eurusd = QLabel("EUR/USD : —")
        self.status_footer_lme = QLabel("LME (USD) : —")
        self.status_footer_week = QLabel(
            f"Hafta : {datetime.now().isocalendar()[1]}"
        )
        self.status_footer_version = QLabel("Versiyon : 4.0.0")
        for label in (
            self.status_footer_usd,
            self.status_footer_eur,
            self.status_footer_eurusd,
            self.status_footer_lme,
            self.status_footer_week,
            self.status_footer_version,
        ):
            self.statusBar().addPermanentWidget(label)
        self.statusBar().showMessage("RIGEL COST PRO hazır", 3000)
        self.load_cached_market_data()
        self._initial_import_pending = self.should_show_initial_import()
        if self._initial_import_pending:
            QTimer.singleShot(700, self.open_initial_import_once)

    def can(self, permission: str) -> bool:
        return self.session.can(permission)

    def is_developer_user(self) -> bool:
        """Aktarım aracını yalnız Rigel geliştirici hesabına açık tutar."""
        identity = f"{self.session.username} {self.session.display_name}".casefold()
        for source, target in (
            ("ı", "i"), ("ş", "s"), ("ğ", "g"),
            ("ü", "u"), ("ö", "o"), ("ç", "c"),
        ):
            identity = identity.replace(source, target)
        compact = "".join(character for character in identity if character.isalnum())
        return "aliuzkuc" in compact

    @property
    def initial_import_marker(self) -> Path:
        return Path(self.auth_service.database_path).parent / ".initial_import_shown"

    def should_show_initial_import(self) -> bool:
        return (
            self.session.user_id > 0
            and self.session.role == "PATRON"
            and not self.initial_import_marker.exists()
        )

    @staticmethod
    def department_permission(department: str) -> str:
        return {
            "Satış": VIEW_SALES,
            "Satın Alma": VIEW_PURCHASE,
            "Malzeme Yönetimi": VIEW_MATERIAL,
            "Kalıphane": VIEW_DIE,
            "Üretim": VIEW_PRODUCTION,
            "Sevkiyat": VIEW_SHIPPING,
            "Bakım": VIEW_MAINTENANCE,
        }.get(department, VIEW_DASHBOARD)

    def install_wheel_value_guard(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        guard = getattr(app, "_rigel_wheel_value_guard", None)
        if guard is None:
            guard = WheelValueGuard(app)
            app.installEventFilter(guard)
            setattr(app, "_rigel_wheel_value_guard", guard)
        self.wheel_value_guard = guard

    def build_toolbar(self) -> None:
        toolbar = QToolBar("Hızlı İşlemler")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        actions: list[tuple[str, Callable[[], None]]] = []
        if self.can(VIEW_DASHBOARD):
            actions.append(("ANA SAYFA", lambda: self.show_page(DASHBOARD_PAGE)))
        if self.can(VIEW_COST):
            actions.extend(
                (
                    ("YENİ HESAP", self.new_cost_calculation),
                    ("MALİYETİ HESAPLA", self.calculate_cost),
                    ("GİDER DETAYLARI", lambda: self.show_expense_tab("")),
                )
            )
        if self.can(VIEW_MATERIAL):
            actions.append(
                ("STOK TAKİBİ", lambda: self.show_department("Malzeme Yönetimi", "Stok Kartları"))
            )
        if self.can(VIEW_COST) and self.can(EXPORT_REPORTS):
            actions.extend(
                (
                    ("EXCEL RAPORU", self.home_page.request_excel_export),
                    ("PDF RAPORU", self.home_page.request_pdf_export),
                )
            )
        for text, callback in actions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)

        if self.can(UPDATE_MARKET):
            toolbar.addSeparator()
            market_action = QAction("KURLARI / LME'Yİ GÜNCELLE", self)
            market_action.triggered.connect(self.refresh_market_data)
            toolbar.addAction(market_action)

    def build_rigel_quick_toolbar(self) -> None:
        """Üst hızlı erişim şeridi."""
        toolbar = QToolBar("Hızlı İşlemler")
        toolbar.setObjectName("rigelQuickToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        quick_actions: list[tuple[str, Callable[[], None]]] = []
        if self.can(VIEW_SALES):
            quick_actions.extend(
                (
                    ("Yeni Satış Siparişi", lambda: self.show_department("Satış", "Satış Siparişleri")),
                    ("Satış Siparişleri", lambda: self.show_department("Satış", "Satış Siparişleri")),
                    ("Bekleyen Siparişler", lambda: self.show_department("Satış", "Bekleyen Siparişler")),
                    ("Sipariş Detay", lambda: self.show_department("Satış", "Sipariş Detay (Satış)")),
                )
            )
        if self.can(VIEW_SHIPPING):
            quick_actions.append(
                ("Ambar Yükleri", lambda: self.show_department("Sevkiyat", "Ambar Yükleri"))
            )
        if self.can(VIEW_PURCHASE):
            quick_actions.append(
                ("Yeni Talep Fişi", lambda: self.show_department("Satın Alma", "Talep Fişleri"))
            )
        if self.can(VIEW_MATERIAL):
            quick_actions.append(
                ("Malzeme Bul", lambda: self.show_department("Malzeme Yönetimi", "Stok Kartları"))
            )
        quick_actions.append(("Çıkış", self.confirm_exit))

        for text, callback in quick_actions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)

    def build_central_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.market_bar = QFrame()
        self.market_bar.setObjectName("marketBar")
        market_layout = QHBoxLayout(self.market_bar)
        market_layout.setContentsMargins(8, 2, 8, 2)
        market_layout.setSpacing(6)

        brand = QVBoxLayout()
        brand_title = QLabel("RIGEL COST PRO")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("Rigel Alüminyum — Ekstrüzyon ERP")
        brand_subtitle.setObjectName("brandSubtitle")
        brand.addWidget(brand_title)
        brand.addWidget(brand_subtitle)
        market_layout.addLayout(brand, 1)

        self.usd_market_value = self.create_market_card(
            market_layout, "USD/TL", "47,4243"
        )
        self.eur_market_value = self.create_market_card(
            market_layout, "EUR/TL", "—"
        )
        self.lme_market_value = self.create_market_card(
            market_layout, "LME ALÜMİNYUM", "3.192,00 USD/ton"
        )

        self.market_date_label = QLabel("Elle girilen değerler")
        self.market_date_label.setObjectName("marketDate")
        self.market_date_label.setAlignment(Qt.AlignCenter)
        self.market_date_label.setMinimumWidth(155)
        market_layout.addWidget(self.market_date_label)

        self.market_refresh_button = QPushButton("YENİLE")
        self.market_refresh_button.setObjectName("marketRefreshButton")
        self.market_refresh_button.clicked.connect(self.refresh_market_data)
        self.market_refresh_button.setVisible(self.can(UPDATE_MARKET))
        market_layout.addWidget(self.market_refresh_button)

        self.exit_button = QPushButton("⏻  ÇIKIŞ")
        self.exit_button.setObjectName("exitButton")
        self.exit_button.setToolTip("Programı güvenli şekilde kapat")
        self.exit_button.clicked.connect(self.confirm_exit)
        market_layout.addWidget(self.exit_button)

        central_layout.addWidget(self.market_bar)

        body = QFrame()
        body.setObjectName("bodyFrame")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        navigation = QFrame()
        navigation.setObjectName("sideNavigation")
        navigation.setFixedWidth(225)
        nav_layout = QVBoxLayout(navigation)
        nav_layout.setContentsMargins(0, 0, 0, 10)
        nav_layout.setSpacing(5)

        self.nav_buttons: list[QPushButton] = []
        self.page_primary_buttons: dict[int, QPushButton] = {}

        menu_scroll = QScrollArea()
        menu_scroll.setObjectName("navScroll")
        menu_scroll.setWidgetResizable(True)
        menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        menu_scroll.setFrameShape(QFrame.NoFrame)
        menu_widget = QWidget()
        menu_widget.setObjectName("navMenuWidget")
        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setContentsMargins(9, 10, 9, 10)
        menu_layout.setSpacing(5)

        if self.can(VIEW_DASHBOARD):
            self.add_department(
                menu_layout,
                "ANA SAYFA",
                [("Yönetim Paneli", DASHBOARD_PAGE, "dashboard_nav_button")],
                expanded=True,
            )
        if self.can(VIEW_COST):
            self.add_department(
                menu_layout,
                "MALİYET",
                [
                    ("Maliyet Ana", COST_PAGE, "cost_nav_button"),
                    (
                        "Gider Alt Sekmeleri",
                        EXPENSE_DETAILS_PAGE,
                        "expense_details_nav_button",
                    ),
                    (
                        "Palet Hesabı",
                        self.show_pallet_calculation,
                        "pallet_nav_button",
                    ),
                ],
                expanded=True,
            )
        if self.can(VIEW_SALES):
            self.add_department(
                menu_layout,
                "SATIŞ",
                [(name, ("Satış", name), None) for name in DEPARTMENT_MODULES["Satış"]],
            )
        if self.can(VIEW_PURCHASE):
            self.add_department(
                menu_layout,
                "SATIN ALMA",
                [
                    (name, ("Satın Alma", name), None)
                    for name in DEPARTMENT_MODULES["Satın Alma"]
                ],
            )
        if self.can(VIEW_MATERIAL):
            self.add_department(
                menu_layout,
                "MALZEME YÖNETİMİ",
                [
                    ("Stok Takibi", ("Malzeme Yönetimi", "Stok Kartları"), "inventory_nav_button"),
                    *[
                        (name, ("Malzeme Yönetimi", name), None)
                        for name in DEPARTMENT_MODULES["Malzeme Yönetimi"]
                    ],
                ],
                expanded=True,
            )
        if self.can(VIEW_DIE):
            self.add_department(
                menu_layout,
                "KALIPHANE",
                [
                    (
                        name,
                        ("Kalıphane", name),
                        "die_nav_button" if name == "Kalıp Kartları" else None,
                    )
                    for name in DEPARTMENT_MODULES["Kalıphane"]
                ],
                expanded=True,
            )
        if self.can(VIEW_PRODUCTION):
            self.add_department(
                menu_layout,
                "ÜRETİM",
                [(name, ("Üretim", name), None) for name in DEPARTMENT_MODULES["Üretim"]],
            )
        if self.can(VIEW_SHIPPING):
            self.add_department(
                menu_layout,
                "SEVKİYAT",
                [(name, ("Sevkiyat", name), None) for name in DEPARTMENT_MODULES["Sevkiyat"]],
            )
        if self.can(VIEW_MAINTENANCE):
            self.add_department(
                menu_layout,
                "BAKIM",
                [(name, ("Bakım", name), None) for name in DEPARTMENT_MODULES["Bakım"]],
            )

        report_entries: list[tuple[str, object, str | None]] = []
        if self.can(VIEW_REPORTS) and self.can(VIEW_COST):
            report_entries.append(("Maliyet Raporları", COST_PAGE, None))
        if self.can(VIEW_REPORTS) and self.can(VIEW_MATERIAL):
            report_entries.append(
                ("Stok Raporları", ("Malzeme Yönetimi", "Stok Hareketleri"), None)
            )
        if self.can(VIEW_REPORTS) and self.can(VIEW_PRODUCTION):
            report_entries.append(
                ("Üretim Raporları", ("Üretim", "Pres Üretim Miktarları"), None)
            )
        if report_entries:
            self.add_department(menu_layout, "RAPORLAR", report_entries)

        settings_entries: list[tuple[str, Callable[[], None], str | None]] = []
        if self.can(MANAGE_USERS):
            settings_entries.append(("Kullanıcı ve Yetkiler", self.open_users, None))
            if central_database_enabled():
                settings_entries.append(("Merkezi Sunucu", self.open_server_setup, None))
        if self.is_developer_user():
            settings_entries.append(("İlk Veri Aktarımı", self.open_initial_import, None))
        if self.can(UPDATE_MARKET):
            settings_entries.append(("Piyasa Verileri", self.refresh_market_data, None))
        if settings_entries and (
            self.can(VIEW_SETTINGS) or self.can(MANAGE_USERS) or self.is_developer_user()
        ):
            self.add_department(menu_layout, "AYARLAR", settings_entries)
        menu_layout.addStretch(1)
        menu_scroll.setWidget(menu_widget)
        nav_layout.addWidget(menu_scroll, 1)

        nav_bottom = QFrame()
        nav_bottom.setObjectName("navBottom")
        nav_bottom_layout = QVBoxLayout(nav_bottom)
        nav_bottom_layout.setContentsMargins(9, 2, 9, 0)
        nav_bottom_layout.setSpacing(5)
        author_card = QFrame()
        author_card.setObjectName("authorCard")
        author_layout = QVBoxLayout(author_card)
        author_layout.setContentsMargins(9, 7, 9, 7)
        author_title = QLabel("GELİŞTİREN")
        author_title.setObjectName("authorTitle")
        author_name = QLabel("ALİ UZKUC")
        author_name.setObjectName("authorName")
        author_layout.addWidget(author_title)
        author_layout.addWidget(author_name)
        nav_bottom_layout.addWidget(author_card)
        nav_layout.addWidget(nav_bottom)

        body_layout.addWidget(navigation)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.expense_details_page)
        self.stack.addWidget(self.inventory_page)
        self.stack.addWidget(self.department_page)
        self.stack.addWidget(self.workflow_page)
        body_layout.addWidget(self.stack, 1)

        self.dashboard_page.configure_access(
            cost=self.can(VIEW_COST),
            material=self.can(VIEW_MATERIAL),
            die=self.can(VIEW_DIE),
            production=self.can(VIEW_PRODUCTION),
            sales=self.can(VIEW_SALES),
            shipping=self.can(VIEW_SHIPPING),
        )

        central_layout.addWidget(body, 1)
        self.setCentralWidget(central)
        self.show_page(DASHBOARD_PAGE)

    @staticmethod
    def create_market_card(
        layout: QHBoxLayout,
        title: str,
        initial_value: str,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("marketCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 3, 8, 3)
        card_layout.setSpacing(1)

        title_label = QLabel(title)
        title_label.setObjectName("marketCardTitle")
        value_label = QLabel(initial_value)
        value_label.setObjectName("marketCardValue")
        value_label.setAlignment(Qt.AlignCenter)
        title_label.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card)
        return value_label

    def add_department(
        self,
        layout: QVBoxLayout,
        title: str,
        entries: list[
            tuple[
                str,
                int | tuple[str, str] | Callable[[], None],
                str | None,
            ]
        ],
        *,
        expanded: bool = False,
    ) -> None:
        header = QToolButton()
        header.setObjectName("departmentButton")
        header.setText(title)
        header.setCheckable(True)
        header.setChecked(expanded)
        header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        layout.addWidget(header)

        submenu = QFrame()
        submenu.setObjectName("departmentMenu")
        submenu_layout = QVBoxLayout(submenu)
        submenu_layout.setContentsMargins(8, 0, 0, 3)
        submenu_layout.setSpacing(2)

        for text, target, attribute_name in entries:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setCheckable(True)
            self.nav_buttons.append(button)

            if isinstance(target, int):
                self.page_primary_buttons.setdefault(target, button)
                button.clicked.connect(
                    lambda checked=False, index=target: self.show_page(index)
                )
            elif isinstance(target, tuple):
                department, module = target
                button.clicked.connect(
                    lambda checked=False,
                    button=button,
                    department=department,
                    module=module: self.run_nav_action(
                        button,
                        lambda: self.show_department(department, module),
                    )
                )
            else:
                button.clicked.connect(
                    lambda checked=False,
                    button=button,
                    callback=target: self.run_nav_action(button, callback)
                )

            if attribute_name:
                setattr(self, attribute_name, button)
            submenu_layout.addWidget(button)

        submenu.setVisible(expanded)
        header.toggled.connect(submenu.setVisible)
        header.toggled.connect(
            lambda checked, header=header: header.setArrowType(
                Qt.DownArrow if checked else Qt.RightArrow
            )
        )
        layout.addWidget(submenu)

    def activate_nav_button(self, active: QPushButton | None) -> None:
        for button in self.nav_buttons:
            button.setChecked(button is active)

    def run_nav_action(
        self,
        button: QPushButton,
        callback: Callable[[], None],
    ) -> None:
        self.activate_nav_button(button)
        callback()

    def connect_signals(self) -> None:
        self.dashboard_page.open_cost_requested.connect(
            lambda: self.show_page(COST_PAGE)
        )
        self.dashboard_page.open_expenses_requested.connect(
            lambda: self.show_expense_tab("")
        )
        self.dashboard_page.open_pallet_requested.connect(
            self.show_pallet_calculation
        )
        self.dashboard_page.open_inventory_requested.connect(
            lambda: self.show_department("Malzeme Yönetimi", "Stok Kartları")
        )
        self.dashboard_page.open_stock_movement_requested.connect(
            lambda: self.show_department("Malzeme Yönetimi", "Stok Hareketleri")
        )
        self.dashboard_page.open_die_requested.connect(
            lambda: self.show_department("Kalıphane", "Kalıp Kartları")
        )
        self.dashboard_page.open_department_requested.connect(
            self.show_department
        )
        self.home_page.uretim.valueChanged.connect(
            self.expense_details_page.set_production
        )
        self.home_page.usd.valueChanged.connect(
            self.expense_details_page.set_usd_rate
        )
        self.home_page.lme.valueChanged.connect(
            self.expense_details_page.set_lme
        )
        self.home_page.prim.valueChanged.connect(
            self.expense_details_page.set_prim
        )
        self.home_page.open_expenses_requested.connect(
            self.show_expense_tab
        )
        self.expense_details_page.totals_changed.connect(
            self.home_page.set_detail_costs
        )
        self.expense_details_page.fire_parameters_changed.connect(
            self.home_page.set_fire_parameters
        )
        self.home_page.excel_export_requested.connect(
            self.export_excel_report
        )
        self.home_page.pdf_export_requested.connect(self.export_pdf_report)

        self.market_service.update_started.connect(self.market_update_started)
        self.market_service.data_updated.connect(self.on_market_data)
        self.market_service.update_failed.connect(self.market_update_failed)

        self.home_page.set_detail_costs(
            self.expense_details_page.current_totals()
        )
        self.home_page.set_fire_parameters(
            self.expense_details_page.fire_parameters()
        )
        self.expense_details_page.set_production(
            self.home_page.uretim.value()
        )

    def page_permission(self, index: int) -> str:
        return {
            DASHBOARD_PAGE: VIEW_DASHBOARD,
            COST_PAGE: VIEW_COST,
            EXPENSE_DETAILS_PAGE: VIEW_COST,
            INVENTORY_PAGE: VIEW_MATERIAL,
        }.get(index, VIEW_DASHBOARD)

    def show_page(self, index: int) -> bool:
        if not self.can(self.page_permission(index)):
            self.statusBar().showMessage("Bu bölüm için kullanıcı yetkiniz yok.", 6000)
            return False
        self.stack.setCurrentIndex(index)
        self.activate_nav_button(self.page_primary_buttons.get(index))
        if index == INVENTORY_PAGE:
            self.inventory_page.refresh_data()
        return True

    def new_cost_calculation(self) -> None:
        if not self.show_page(COST_PAGE):
            return
        self.home_page.clear_form()

    def calculate_cost(self) -> None:
        if not self.show_page(COST_PAGE):
            return
        self.home_page.hesapla()

    def show_expense_tab(self, title: str = "") -> None:
        if not self.show_page(EXPENSE_DETAILS_PAGE):
            return
        if title:
            self.expense_details_page.show_tab(title)

    def show_pallet_calculation(self) -> None:
        self.show_expense_tab("Palet Hesabı")
        button = getattr(self, "pallet_nav_button", None)
        if button is not None:
            self.activate_nav_button(button)

    def show_stock_movements(self) -> None:
        if not self.can(VIEW_MATERIAL):
            return
        self.show_department("Malzeme Yönetimi", "Stok Hareketleri")

    def open_stock_movement(self) -> None:
        self.show_department("Malzeme Yönetimi", "Stok Fişleri")

    def confirm_exit(self) -> None:
        if ExitConfirmDialog.confirm(self):
            self.close()

    def show_department(self, department: str, module: str) -> None:
        if not self.can(self.department_permission(department)):
            self.statusBar().showMessage(
                f"{department} bölümü için kullanıcı yetkiniz yok.", 6000
            )
            return
        if self.workflow_page.handles_context(department, module):
            self.workflow_page.set_context(department, module)
            self.stack.setCurrentIndex(WORKFLOW_PAGE)
        else:
            self.department_page.set_context(department, module)
            self.stack.setCurrentIndex(DEPARTMENT_PAGE)

    def load_cached_market_data(self) -> None:
        if self.market_service.values:
            self.on_market_data(
                self.market_service.values,
                cached=True,
            )

    def refresh_market_data(self) -> None:
        if not self.can(UPDATE_MARKET):
            self.statusBar().showMessage("Piyasa verisi güncelleme yetkiniz yok.", 6000)
            return
        self.market_service.refresh()

    def open_users(self) -> None:
        if not self.can(MANAGE_USERS):
            return
        UsersDialog(self.auth_service, self.session, self).exec()

    def open_server_setup(self) -> None:
        if not self.can(MANAGE_USERS):
            return
        ServerSetupDialog(self).exec()

    def open_initial_import_once(self) -> None:
        if not getattr(self, "_initial_import_pending", False):
            return
        self._initial_import_pending = False
        if self.initial_import_marker.exists():
            return
        try:
            self.initial_import_marker.parent.mkdir(parents=True, exist_ok=True)
            self.initial_import_marker.touch(exist_ok=True)
        except OSError:
            pass
        self.open_initial_import(force=True)

    def open_initial_import(self, *, force: bool = False) -> None:
        if not force and not self.is_developer_user():
            return
        service = DataImportService(self.department_page.service)
        dialog = DataImportDialog(service, self)
        dialog.import_completed.connect(self.department_page.refresh_data)
        dialog.exec()

    def market_update_started(self) -> None:
        self.market_refresh_button.setEnabled(False)
        self.market_refresh_button.setText("GÜNCELLENİYOR…")
        self.dashboard_page.set_market_loading()
        self.statusBar().showMessage(
            "TCMB kurları ve LME alüminyum verisi güncelleniyor…"
        )

    def on_market_data(
        self,
        values: dict[str, Any],
        *,
        cached: bool = False,
    ) -> None:
        # Bozuk/elle değiştirilmiş önbellek uygulama açılışını durdurmasın.
        usd = self.home_page.safe_number(values.get("usd"))
        eur = self.home_page.safe_number(values.get("eur"))
        lme = self.home_page.safe_number(values.get("lme"))

        if usd > 0:
            self.usd_market_value.setText(
                self.home_page.format_number(usd, 4)
            )
            if hasattr(self, "status_footer_usd"):
                self.status_footer_usd.setText(
                    f"USD/TRY : {self.home_page.format_number(usd, 4)}"
                )
            self.home_page.usd.setValue(usd)
        if eur > 0:
            self.eur_market_value.setText(
                self.home_page.format_number(eur, 4)
            )
            if hasattr(self, "status_footer_eur"):
                self.status_footer_eur.setText(
                    f"EUR/TRY : {self.home_page.format_number(eur, 4)}"
                )
            if usd > 0 and hasattr(self, "status_footer_eurusd"):
                self.status_footer_eurusd.setText(
                    f"EUR/USD : {self.home_page.format_number(eur / usd, 4)}"
                )
        if lme > 0:
            self.lme_market_value.setText(
                f"{self.home_page.format_number(lme, 2)} USD/ton"
            )
            if hasattr(self, "status_footer_lme"):
                self.status_footer_lme.setText(
                    f"LME (USD) : {self.home_page.format_number(lme, 2)}$"
                )
            self.home_page.lme.setValue(lme)
        self.expense_details_page.set_market_values(
            usd=usd if usd > 0 else None,
            eur=eur if eur > 0 else None,
            lme=lme if lme > 0 else None,
        )

        updated_at = str(values.get("updated_at") or "")
        if updated_at:
            try:
                readable_date = datetime.fromisoformat(updated_at).strftime(
                    "%d.%m.%Y %H:%M"
                )
            except ValueError:
                readable_date = updated_at
        else:
            readable_date = "Tarih bilinmiyor"

        prefix = "Önbellek" if cached else "Güncellendi"
        tcmb_date = str(values.get("tcmb_date") or "—")
        lme_date = str(values.get("lme_date") or "—")
        self.market_date_label.setText(
            f"{prefix} {readable_date}\n"
            f"TCMB {tcmb_date} · LME {lme_date}"
        )
        self.dashboard_page.set_market_data(
            usd=usd,
            eur=eur,
            lme=lme,
            updated_text=self.market_date_label.text(),
        )
        self.usd_market_value.setToolTip(
            str(values.get("tcmb_source") or "TCMB")
        )
        self.eur_market_value.setToolTip(
            str(values.get("tcmb_source") or "TCMB")
        )
        self.lme_market_value.setToolTip(
            str(values.get("lme_source") or "LME")
        )
        self.market_refresh_button.setEnabled(True)
        self.market_refresh_button.setText("YENİLE")
        self.statusBar().showMessage(
            "Piyasa değerleri maliyet ekranına aktarıldı.", 5000
        )

    def market_update_failed(self, message: str) -> None:
        self.market_refresh_button.setEnabled(True)
        self.market_refresh_button.setText("YENİLE")
        self.dashboard_page.set_market_error()
        self.statusBar().showMessage(
            "Bazı piyasa verileri alınamadı; mevcut/elle girilen değerler "
            f"korundu. {message}",
            12_000,
        )

    def export_excel_report(self, report_data: dict[str, Any]) -> None:
        self._request_export(
            report_data=report_data,
            title="Excel raporunu kaydet",
            extension=".xlsx",
            file_filter="Excel çalışma kitabı (*.xlsx)",
            exporter=export_excel,
        )

    def export_pdf_report(self, report_data: dict[str, Any]) -> None:
        self._request_export(
            report_data=report_data,
            title="PDF raporunu kaydet",
            extension=".pdf",
            file_filter="PDF belgesi (*.pdf)",
            exporter=export_pdf,
        )

    def _request_export(
        self,
        *,
        report_data: dict[str, Any],
        title: str,
        extension: str,
        file_filter: str,
        exporter: Callable[[dict[str, Any], str | Path], Path],
    ) -> None:
        if not self.can(EXPORT_REPORTS):
            self.statusBar().showMessage("Rapor alma yetkiniz yok.", 6000)
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        default_name = str(
            Path.home() / "Documents" / f"RigelCost_{timestamp}{extension}"
        )
        destination, _ = QFileDialog.getSaveFileName(
            self,
            title,
            default_name,
            file_filter,
        )
        if not destination:
            return

        if not destination.lower().endswith(extension):
            destination += extension

        try:
            output_path = exporter(report_data, destination)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rapor oluşturulamadı",
                f"Dosya kaydedilemedi.\n\nHata ayrıntısı: {exc}",
            )
            return

        self.statusBar().showMessage(
            f"Rapor kaydedildi: {output_path.name}", 8000
        )
        QMessageBox.information(
            self,
            "Rapor hazır",
            f"Rapor başarıyla kaydedildi:\n{output_path}",
        )

    def apply_style(self) -> None:
        base = rigel_main_window_styles()
        extra = stylesheet(
            """
            #mainToolbar {
                background: #FFFFFF;
                border: 0;
                border-bottom: 1px solid #CBD5E1;
                spacing: 3px;
                padding: 4px 8px;
            }
            #mainToolbar QToolButton {
                color: #1E3A5F;
                background: transparent;
                border: 0;
                border-radius: 4px;
                padding: 9px 13px;
                font-size: 13px;
                font-weight: 700;
            }
            #mainToolbar QToolButton:hover {
                background: #E8EEF5;
                color: #0B437C;
            }
            #mainToolbar::separator {
                background: #D0D5DD;
                width: 1px;
                margin: 5px 8px;
            }
            #marketRefreshButton {
                color: #FFFFFF;
                background: #0B5A9C;
                border: 0;
                border-radius: 6px;
                padding: 9px 13px;
                font-weight: 700;
            }
            #marketRefreshButton:disabled {
                color: #98A2B3;
                background: #D0D5DD;
            }
            #exitButton {
                color: #FFFFFF;
                background: #B42318;
                border: 0;
                border-radius: 6px;
                padding: 9px 13px;
                font-weight: 700;
            }
            #exitButton:hover { background: #912018; }
            """,
        )
        self.setStyleSheet(f"{base}\n{extra}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Rigel Cost Pro")
    app.setApplicationVersion("4.0.0")
    app.setOrganizationName("Rigel Alüminyum")
    app.setStyle("Fusion")
    apply_corporate_typography(app)
    apply_rigel_light_palette(app)
    apply_rigel_flat_theme(app)

    if "--build-smoke-test" in sys.argv:
        window = MainWindow(
            session=UserSession.owner("Windows Derleme Testi")
        )
        if window.stack.currentWidget() is not window.dashboard_page:
            return 10
        window.die_nav_button.click()
        if window.stack.currentWidget() is not window.workflow_page:
            return 11
        if window.workflow_page.module_label.text() != "Kalıp Kartları":
            return 12
        result = window.home_page.calc.hesapla(
            200_000,
            3_192,
            625,
            47.4243,
            2.97,
            18.90,
            0,
        )
        if result.get("billet_usd") != 3_817:
            return 13
        window.pallet_nav_button.click()
        if window.stack.currentWidget() is not window.expense_details_page:
            return 14
        if (
            window.expense_details_page.tabs.tabText(
                window.expense_details_page.tabs.currentIndex()
            )
            != "Palet Hesabı"
        ):
            return 15
        pallet_result = (
            window.expense_details_page.pallet_panel.last_result
        )
        if pallet_result.get("palet_adedi") != 308:
            return 16
        if abs(
            window.home_page.ambalaj.value()
            - float(pallet_result.get("toplam") or 0)
        ) > 0.01:
            return 17
        window.show_department("Üretim", "Pres Üretim Fişleri")
        press_result = window.department_page.service.calculate_data(
            get_module_spec("Üretim", "Pres Üretim Fişleri"),
            {
                "order_ref": "TEST-SIPARIS",
                "work_order_ref": "TEST-IS-EMRI",
                "profile_code": "TEST-PROFIL",
                "gross_kg": 2_352.94,
                "net_kg": 2_000,
            },
        )
        if abs(float(press_result.get("fire_pct") or 0) - 15.0) > 0.01:
            return 18
        window.close()
        return 0

    auth_service = AuthService()
    if not auth_service.has_users():
        first_owner = FirstOwnerDialog(auth_service)
        if first_owner.exec() != QDialog.Accepted:
            return 0

    login = LoginDialog(auth_service)
    if login.exec() != QDialog.Accepted or login.session is None:
        return 0

    window = MainWindow(
        session=login.session,
        auth_service=auth_service,
    )
    window.showMaximized()
    if window.can(UPDATE_MARKET):
        QTimer.singleShot(500, window.refresh_market_data)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
