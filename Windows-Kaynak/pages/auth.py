from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.auth import AuthService, UserSession
from ui.corporate_theme import font_family_css, stylesheet


AUTH_STYLE = """
QDialog { background: #EEF3F8; color: #1D2939; }
QLabel { color: #1D2939; background: transparent; }
QCheckBox { color: #344054; background: transparent; spacing: 7px; }
#authCard { background: white; border: 1px solid #C8D5E5; border-radius: 12px; }
#authBrand { color: #0B437C; font-size: 25px; font-weight: 700; }
#authTitle { color: #101828; font-size: 19px; font-weight: 700; }
#authHelp { color: #667085; font-size: 11px; }
QLineEdit {
    color: #101828; background: white; border: 1px solid #B9C9DC; border-radius: 6px;
    min-height: 34px; padding: 3px 9px;
    selection-background-color: #0B74BE; selection-color: white;
    placeholder-text-color: #98A2B3;
}
QLineEdit:focus { border: 2px solid #0B74BE; }
#primaryButton {
    background: #0B437C; color: white; border: 0; border-radius: 6px;
    min-height: 39px; padding: 5px 18px; font-weight: 700;
}
#secondaryButton {
    background: white; color: #344054; border: 1px solid #B9C9DC;
    border-radius: 6px; min-height: 37px; padding: 5px 18px; font-weight: 700;
}
"""


class FirstOwnerDialog(QDialog):
    """İlk çalıştırmada tüm yetkilere sahip patron hesabını oluşturur."""

    def __init__(self, service: AuthService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.created_user_id: int | None = None
        self.setWindowTitle("Rigel Cost Pro — İlk Yönetici Hesabı")
        self.setModal(True)
        self.resize(610, 520)
        self.setMinimumSize(540, 470)
        self.build_ui()
        self.setStyleSheet(stylesheet(AUTH_STYLE))

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 28)
        card = QFrame()
        card.setObjectName("authCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(13)

        brand = QLabel("RIGEL COST PRO")
        brand.setObjectName("authBrand")
        title = QLabel("İlk Patron Hesabı")
        title.setObjectName("authTitle")
        help_text = QLabel(
            "Bu hesap kullanıcıları ve yetkileri yönetir; maliyet dahil bütün "
            "modülleri görür. Şifre düz metin olarak saklanmaz."
        )
        help_text.setObjectName("authHelp")
        help_text.setWordWrap(True)
        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addWidget(help_text)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)
        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Ad Soyad")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Örnek: aliuzkuc")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("En az 8 karakter, harf ve rakam")
        self.password_repeat = QLineEdit()
        self.password_repeat.setEchoMode(QLineEdit.Password)
        self.show_password = QCheckBox("Şifreyi göster")
        self.show_password.toggled.connect(self.toggle_passwords)
        form.addRow(self.form_label("Ad soyad"), self.display_name)
        form.addRow(self.form_label("Kullanıcı adı"), self.username)
        form.addRow(self.form_label("Şifre"), self.password)
        form.addRow(self.form_label("Şifre tekrar"), self.password_repeat)
        form.addRow(self.form_label(""), self.show_password)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        create_button = QPushButton("PATRON HESABINI OLUŞTUR")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self.create_owner)
        buttons.addWidget(create_button)
        layout.addLayout(buttons)
        root.addWidget(card)

    @staticmethod
    def form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:#1D2939;background:transparent;font-weight:700;{font_family_css()}"
        )
        return label

    def toggle_passwords(self, visible: bool) -> None:
        mode = QLineEdit.Normal if visible else QLineEdit.Password
        self.password.setEchoMode(mode)
        self.password_repeat.setEchoMode(mode)

    def create_owner(self) -> None:
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, "Şifre uyuşmuyor", "Şifre ve tekrarı aynı olmalıdır.")
            return
        try:
            self.created_user_id = self.service.create_first_owner(
                self.username.text(),
                self.display_name.text(),
                self.password.text(),
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Hesap oluşturulamadı", str(error))
            return
        self.accept()


class LoginDialog(QDialog):
    """Yerel kullanıcı doğrulaması yapar ve yetki oturumunu döndürür."""

    def __init__(self, service: AuthService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.session: UserSession | None = None
        self.setWindowTitle("Rigel Cost Pro — Giriş")
        self.setModal(True)
        self.resize(520, 390)
        self.setMinimumSize(470, 350)
        self.build_ui()
        self.setStyleSheet(stylesheet(AUTH_STYLE))

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 28)
        card = QFrame()
        card.setObjectName("authCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(13)

        brand = QLabel("RIGEL COST PRO")
        brand.setObjectName("authBrand")
        title = QLabel("Kullanıcı Girişi")
        title.setObjectName("authTitle")
        help_text = QLabel("Size verilen kullanıcı adı ve şifreyle giriş yapın.")
        help_text.setObjectName("authHelp")
        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addWidget(help_text)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(11)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Kullanıcı adı")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Şifre")
        self.show_password = QCheckBox("Şifreyi göster")
        self.show_password.toggled.connect(
            lambda visible: self.password.setEchoMode(
                QLineEdit.Normal if visible else QLineEdit.Password
            )
        )
        form.addRow(self.form_label("Kullanıcı adı"), self.username)
        form.addRow(self.form_label("Şifre"), self.password)
        form.addRow(self.form_label(""), self.show_password)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        cancel = QPushButton("KAPAT")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        login = QPushButton("GİRİŞ YAP")
        login.setObjectName("primaryButton")
        login.clicked.connect(self.try_login)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(login)
        layout.addLayout(buttons)
        root.addWidget(card)

        self.password.returnPressed.connect(self.try_login)
        self.username.setFocus(Qt.OtherFocusReason)

    @staticmethod
    def form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:#1D2939;background:transparent;font-weight:700;{font_family_css()}"
        )
        return label

    def try_login(self) -> None:
        self.session = self.service.authenticate(
            self.username.text(),
            self.password.text(),
        )
        if self.session is None:
            self.password.clear()
            QMessageBox.warning(
                self,
                "Giriş başarısız",
                "Kullanıcı adı veya şifre hatalı ya da hesap pasif.",
            )
            return
        self.accept()
