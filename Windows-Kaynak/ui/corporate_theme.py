"""kurumsal tipografi ve global form teması."""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# RIGEL COST PRO ve klasik Windows ERP arayüzlerinde kullanılan yazı tipleri.
ERP_FONT_CANDIDATES = (
    "Segoe UI",
    "Tahoma",
    "Segoe UI Variable Text",
    "Segoe UI Variable Display",
    "Inter",
    "Aptos",
    "SF Pro Text",
    ".AppleSystemUIFont",
    "Helvetica Neue",
    "Noto Sans",
    "Arial",
)

# Tam ekranda (maximize) grid'in kaydırmasız sığması için yoğunluk dostu boyutlar
# Tam ekranda grid'in kaydırmasız sığması için yoğunluk dostu boyutlar (~11–12pt)
BASE_POINT_SIZE = 11.5
TABLE_POINT_SIZE = 11.0

_FONT_SELECTORS = (
    "QWidget",
    "QDialog",
    "QMessageBox",
    "QLabel",
    "QPushButton",
    "QLineEdit",
    "QPlainTextEdit",
    "QTextEdit",
    "QComboBox",
    "QSpinBox",
    "QDoubleSpinBox",
    "QDateEdit",
    "QDateTimeEdit",
    "QTableWidget",
    "QTableView",
    "QHeaderView",
    "QHeaderView::section",
    "QMenu",
    "QMenuBar",
    "QToolBar",
    "QToolButton",
    "QTabWidget",
    "QTabBar",
    "QStatusBar",
    "QCheckBox",
    "QRadioButton",
    "QGroupBox",
    "QListWidget",
    "QTreeWidget",
    "QAbstractItemView",
    "QFrame",
    "QScrollBar",
)


def resolve_corporate_font_family() -> str:
    """Sistemde Kurumsal yazı tipini seçer."""
    app = QApplication.instance()
    if app is not None:
        stored = app.property("rigelCorporateFont")
        if stored:
            return str(stored)
    try:
        available = {
            family.casefold(): family for family in QFontDatabase.families()
        }
    except RuntimeError:
        available = {}
    for candidate in ERP_FONT_CANDIDATES:
        matched = available.get(candidate.casefold())
        if matched:
            return matched
    if app is not None:
        return app.font().family()
    return ERP_FONT_CANDIDATES[0]


def active_font_family() -> str:
    app = QApplication.instance()
    if app is not None:
        stored = app.property("rigelCorporateFont")
        if stored:
            return str(stored)
    return resolve_corporate_font_family()


def font_family_css(family: str | None = None) -> str:
    return f'font-family:"{family or active_font_family()}";'


def font_selector_block(family: str | None = None) -> str:
    ff = font_family_css(family)
    joined = ", ".join(_FONT_SELECTORS)
    return f"""
    {joined} {{
        {ff}
    }}
    QTableWidget, QTableView, QAbstractItemView {{
        {ff}
        font-size: {TABLE_POINT_SIZE}pt;
    }}
    QHeaderView::section {{
        {ff}
        font-size: 11pt;
        font-weight: 700;
        padding: 4px 6px;
    }}
    QTabBar::tab {{
        {ff}
        font-size: 11pt;
        min-height: 24px;
        padding: 4px 10px;
    }}
    QMenu {{
        {ff}
        font-size: 11pt;
    }}
    QPushButton, QToolButton {{
        {ff}
        font-size: 11pt;
        min-height: 26px;
    }}
    QStatusBar, QStatusBar QLabel {{
        {ff}
        font-size: 11pt;
    }}
    """


def apply_corporate_typography(app: QApplication) -> str:
    """Tüm uygulamaya tek kurumsal yazı tipini uygular."""
    family = resolve_corporate_font_family()
    font = QFont(family)
    font.setPointSizeF(BASE_POINT_SIZE)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setProperty("rigelCorporateFont", family)
    return family


def stylesheet(*rules: str, family: str | None = None) -> str:
    """Sayfa/dialog QSS kurallarını kurumsal font ile birleştirir."""
    base = font_selector_block(family)
    extra = "\n".join(part.strip() for part in rules if part.strip())
    return f"{base}\n{extra}" if extra else base


def title_style(*, px: int = 18, weight: int = 800) -> str:
    return (
        f"color:#0B437C;font-size:{px}px;font-weight:{weight};"
        f"background:transparent;{font_family_css()}"
    )


def voucher_no_style() -> str:
    return f"font-weight:800;color:#0B437C;font-size:15px;{font_family_css()}"


def build_global_form_stylesheet(family: str) -> str:
    """QApplication düzeyinde form ve liste teması."""
    ff = font_family_css(family)
    return stylesheet(
        f"""
        QWidget {{
            color: #1D2939;
            font-size: {BASE_POINT_SIZE}pt;
            {ff}
        }}
        QDialog, QMessageBox {{ background: #F3F6FA; }}
        QLabel, QCheckBox, QRadioButton {{
            color: #1D2939;
            background: transparent;
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox,
        QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit {{
            color: #101828;
            background: #FFFFFF;
            border: 1px solid #BFCDE0;
            border-radius: 4px;
            selection-color: #FFFFFF;
            selection-background-color: #0B74BE;
        }}
        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
        QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
        QDateEdit:disabled, QDateTimeEdit:disabled {{
            color: #475467;
            background: #F2F4F7;
        }}
        QComboBox QAbstractItemView, QAbstractItemView {{
            color: #101828;
            background: #FFFFFF;
            alternate-background-color: #F7F9FC;
            selection-color: #101828;
            selection-background-color: #DCEBFA;
        }}
        QScrollArea, QScrollArea > QWidget > QWidget {{
            color: #1D2939;
            background: #F3F6FA;
        }}
        QPushButton {{
            color: #163A70;
            background: #FFFFFF;
            border: 1px solid #AFC3DC;
            border-radius: 4px;
        }}
        QPushButton:disabled {{
            color: #98A2B3;
            background: #F2F4F7;
        }}
        QToolTip {{
            color: #101828;
            background: #FFFFFF;
            border: 1px solid #98A2B3;
        }}
        """,
        family=family,
    )


# Geriye dönük uyumluluk
apply_rigel_typography = apply_corporate_typography
CORPORATE_FONT_CANDIDATES = ERP_FONT_CANDIDATES
