"""Program kapatma onay penceresi."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.corporate_theme import stylesheet


class ExitConfirmDialog(QDialog):
    """Rigel Cost Pro çıkış onayı — kurumsal kapatma sekmesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Programdan Çıkış")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(560)
        self.build_ui()
        self.setStyleSheet(stylesheet("""
            QDialog { background: #EEF2F6; }
            #exitCard {
                background: #FFFFFF;
                border: 1px solid #C8D5E5;
                border-radius: 12px;
            }
            #exitIconWrap {
                background: #FEE4E2;
                border: 1px solid #FECDCA;
                border-radius: 28px;
                min-width: 56px;
                max-width: 56px;
                min-height: 56px;
                max-height: 56px;
            }
            #exitIcon {
                color: #B42318;
                font-size: 26px;
                font-weight: 700;
                background: transparent;
            }
            #exitBrand {
                color: #0B437C;
                font-size: 11pt;
                font-weight: 800;
                letter-spacing: 0.4px;
            }
            #exitTitle {
                color: #101828;
                font-size: 14pt;
                font-weight: 800;
            }
            #exitHelp {
                color: #667085;
                font-size: 10pt;
            }
            #exitCancelButton {
                color: #344054;
                background: #FFFFFF;
                border: 1px solid #B9C9DC;
                border-radius: 6px;
                min-width: 120px;
                min-height: 40px;
                padding: 4px 16px;
                font-weight: 700;
            }
            #exitCancelButton:hover { background: #F2F4F7; }
            #exitConfirmButton {
                color: #FFFFFF;
                background: #B42318;
                border: 0;
                border-radius: 6px;
                min-width: 120px;
                min-height: 40px;
                padding: 4px 16px;
                font-weight: 800;
            }
            #exitConfirmButton:hover { background: #912018; }
        """))

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setObjectName("exitCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 24)
        card_layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(16)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("exitIconWrap")
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel("⏻")
        icon.setObjectName("exitIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon)

        text_column = QVBoxLayout()
        text_column.setSpacing(6)
        brand = QLabel("RIGEL COST PRO")
        brand.setObjectName("exitBrand")
        title = QLabel("PROGRAMI KAPATMAK İSTEDİĞİNİZE EMİN MİSİNİZ?")
        title.setObjectName("exitTitle")
        title.setWordWrap(True)
        help_text = QLabel("Kaydedilmiş verileriniz korunacaktır.")
        help_text.setObjectName("exitHelp")
        help_text.setWordWrap(True)
        text_column.addWidget(brand)
        text_column.addWidget(title)
        text_column.addWidget(help_text)

        header.addWidget(icon_wrap, 0, Qt.AlignTop)
        header.addLayout(text_column, 1)
        card_layout.addLayout(header)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("HAYIR")
        cancel.setObjectName("exitCancelButton")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("EVET, KAPAT")
        confirm.setObjectName("exitConfirmButton")
        confirm.setDefault(True)
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        card_layout.addLayout(buttons)

        root.addWidget(card)

    @classmethod
    def confirm(cls, parent: QWidget | None = None) -> bool:
        return cls(parent).exec() == QDialog.DialogCode.Accepted
