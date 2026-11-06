from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.auth import (
    PERMISSION_LABELS,
    ROLE_PERMISSIONS,
    AuthService,
    UserSession,
)
from ui.corporate_theme import font_family_css, stylesheet, title_style


class UserEditorDialog(QDialog):
    def __init__(
        self,
        service: AuthService,
        session: UserSession,
        user: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.session = session
        self.user = user
        self.permission_checks: dict[str, QCheckBox] = {}
        self.setWindowTitle("Kullanıcı Düzenle" if user else "Yeni Kullanıcı")
        self.resize(760, 720)
        self.setMinimumSize(650, 590)
        self.build_ui()
        self.load_values()
        self.apply_style()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("KULLANICI VE YETKİLER")
        title.setObjectName("userEditorTitle")
        help_text = QLabel(
            "Rol başlangıç yetkilerini getirir. İsterseniz kullanıcıya özel olarak "
            "tek tek açıp kapatabilirsiniz."
        )
        help_text.setObjectName("userEditorHelp")
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        self.display_name = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password_repeat = QLineEdit()
        self.password_repeat.setEchoMode(QLineEdit.Password)
        self.role = QComboBox()
        self.role.addItems(ROLE_PERMISSIONS.keys())
        self.active = QCheckBox("Kullanıcı giriş yapabilsin")
        self.active.setChecked(True)
        form.addRow(self.form_label("Ad soyad"), self.display_name)
        form.addRow(self.form_label("Kullanıcı adı"), self.username)
        form.addRow(self.form_label("Rol"), self.role)
        form.addRow(self.form_label("Şifre"), self.password)
        form.addRow(self.form_label("Şifre tekrar"), self.password_repeat)
        form.addRow(self.form_label("Durum"), self.active)
        root.addLayout(form)

        permission_header = QHBoxLayout()
        permission_title = QLabel("MODÜL VE İŞLEM YETKİLERİ")
        permission_title.setObjectName("permissionTitle")
        defaults_button = QPushButton("ROLÜN VARSAYILAN YETKİLERİNİ UYGULA")
        defaults_button.clicked.connect(self.apply_role_defaults)
        permission_header.addWidget(permission_title)
        permission_header.addStretch(1)
        permission_header.addWidget(defaults_button)
        root.addLayout(permission_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        permissions_widget = QWidget()
        permissions_widget.setObjectName("permissionsWidget")
        grid = QGridLayout(permissions_widget)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        for index, (permission, label) in enumerate(PERMISSION_LABELS.items()):
            checkbox = QCheckBox(label)
            checkbox.setProperty("permission", permission)
            self.permission_checks[permission] = checkbox
            row, column = divmod(index, 2)
            grid.addWidget(checkbox, row, column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        scroll.setWidget(permissions_widget)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        cancel = QPushButton("VAZGEÇ")
        cancel.clicked.connect(self.reject)
        save = QPushButton("KAYDET")
        save.setObjectName("saveButton")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.role.currentTextChanged.connect(self.apply_role_defaults)

    @staticmethod
    def form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:#1D2939;background:transparent;font-weight:700;{font_family_css()}"
        )
        return label

    def load_values(self) -> None:
        if self.user is None:
            self.role.setCurrentText("GÖRÜNTÜLEME")
            self.apply_role_defaults()
            return
        self.display_name.setText(str(self.user.get("display_name") or ""))
        self.username.setText(str(self.user.get("username") or ""))
        self.username.setEnabled(False)
        self.role.blockSignals(True)
        self.role.setCurrentText(str(self.user.get("role") or "GÖRÜNTÜLEME"))
        self.role.blockSignals(False)
        self.active.setChecked(bool(self.user.get("active")))
        self.password.setPlaceholderText("Değiştirmek istemiyorsanız boş bırakın")
        self.password_repeat.setPlaceholderText("Yeni şifreyi tekrar edin")
        selected = set(self.user.get("permissions") or ())
        for permission, checkbox in self.permission_checks.items():
            checkbox.setChecked(permission in selected)
            checkbox.setEnabled(self.role.currentText() != "PATRON")

    def apply_role_defaults(self, *_args: object) -> None:
        selected = ROLE_PERMISSIONS.get(self.role.currentText(), frozenset())
        for permission, checkbox in self.permission_checks.items():
            checkbox.setChecked(permission in selected)
            checkbox.setEnabled(self.role.currentText() != "PATRON")

    def selected_permissions(self) -> set[str]:
        return {
            permission
            for permission, checkbox in self.permission_checks.items()
            if checkbox.isChecked()
        }

    def save(self) -> None:
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, "Şifre uyuşmuyor", "Şifre ve tekrarı aynı olmalıdır.")
            return
        try:
            if self.user is None:
                self.service.create_user(
                    self.username.text(),
                    self.display_name.text(),
                    self.password.text(),
                    self.role.currentText(),
                    permissions=self.selected_permissions(),
                    active=self.active.isChecked(),
                    actor=self.session.username,
                )
            else:
                user_id = int(self.user["id"])
                self.service.update_user(
                    user_id,
                    display_name=self.display_name.text(),
                    role=self.role.currentText(),
                    permissions=self.selected_permissions(),
                    active=self.active.isChecked(),
                    actor=self.session.username,
                )
                if self.password.text():
                    self.service.change_password(
                        user_id,
                        self.password.text(),
                        actor=self.session.username,
                    )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kullanıcı kaydedilemedi", str(error))
            return
        self.accept()

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            QDialog { background: #F2F5F9; color: #1D2939; }
            #userEditorTitle { color: #0B437C; font-size: 18pt; font-weight: 700; }
            #userEditorHelp { color: #667085; }
            #permissionTitle { color: #344054; font-weight: 700; }
            QLabel, QCheckBox { color:#1D2939; background:transparent; }
            QLineEdit, QComboBox, QScrollArea {
                color:#101828; background: white; border: 1px solid #C4D1E0; border-radius: 5px;
                min-height: 31px; padding: 3px 7px;
            }
            QComboBox QAbstractItemView {
                color:#101828; background:#FFFFFF; selection-background-color:#DCEBFA;
                selection-color:#101828;
            }
            #permissionsWidget, #permissionsWidget QWidget {
                color:#1D2939; background:#FFFFFF;
            }
            QPushButton { min-height: 33px; padding: 3px 12px; font-weight: 700; }
            #saveButton { background: #0B437C; color: white; border: 0; border-radius: 5px; }
            """
        ))


class UsersDialog(QDialog):
    """Patronun kullanıcıları ve bölüm yetkilerini yönettiği ekran."""

    def __init__(
        self,
        service: AuthService,
        session: UserSession,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.session = session
        self.users: list[dict[str, object]] = []
        self.setWindowTitle("Rigel Cost Pro — Kullanıcı Yönetimi")
        self.resize(920, 620)
        self.setMinimumSize(760, 520)
        self.build_ui()
        self.refresh()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        title = QLabel("KULLANICI YÖNETİMİ")
        title.setStyleSheet(title_style(px=20, weight=900))
        help_text = QLabel(
            "Her kullanıcı yalnızca izin verilen ana bölümleri görür. Patron hesabı "
            "bütün bölümlere ve kullanıcı yönetimine erişir."
        )
        help_text.setStyleSheet("color:#667085;")
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)

        actions = QHBoxLayout()
        add_button = QPushButton("＋ YENİ KULLANICI")
        add_button.setObjectName("primaryButton")
        edit_button = QPushButton("DÜZENLE / ŞİFRE DEĞİŞTİR")
        close_button = QPushButton("KAPAT")
        add_button.clicked.connect(self.add_user)
        edit_button.clicked.connect(self.edit_user)
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        root.addLayout(actions)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Kullanıcı", "Ad Soyad", "Rol", "Durum", "Bölüm Yetkileri", "Kayıt Tarihi"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 300)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_user())
        root.addWidget(self.table, 1)

        self.setStyleSheet(stylesheet(
            """
            QDialog { background: #EEF2F6; color: #1D2939; }
            QPushButton { min-height: 34px; padding: 3px 12px; font-weight: 700; }
            #primaryButton { background:#0B437C;color:white;border:0;border-radius:5px; }
            QTableWidget { color:#1D2939;background:white;alternate-background-color:#F5F8FC;
                border:1px solid #CBD5E1;gridline-color:#E4E7EC; }
            QTableWidget::item { color:#1D2939;background:#FFFFFF; }
            QTableWidget::item:alternate { background:#F5F8FC; }
            QTableWidget::item:selected { color:#101828;background:#DCEBFA; }
            QHeaderView::section { background:#0B437C;color:white;padding:7px;font-weight:800; }
            """
        ))

    @staticmethod
    def permission_summary(permissions: Iterable[str]) -> str:
        return ", ".join(
            PERMISSION_LABELS[value]
            for value in PERMISSION_LABELS
            if value in permissions and value.startswith("view:")
        )

    def refresh(self) -> None:
        self.users = self.service.list_users()
        self.table.setRowCount(len(self.users))
        for row, user in enumerate(self.users):
            values = (
                str(user["username"]),
                str(user["display_name"]),
                str(user["role"]),
                "AKTİF" if bool(user["active"]) else "PASİF",
                self.permission_summary(user.get("permissions") or ()),
                str(user["created_at"])[:10],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, int(user["id"]))
                self.table.setItem(row, column, item)
        if self.users:
            self.table.selectRow(0)

    def selected_user(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.users):
            return None
        return self.users[row]

    def add_user(self) -> None:
        dialog = UserEditorDialog(self.service, self.session, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()

    def edit_user(self) -> None:
        user = self.selected_user()
        if user is None:
            QMessageBox.information(self, "Kullanıcı seçin", "Önce bir kullanıcı seçin.")
            return
        dialog = UserEditorDialog(self.service, self.session, user=user, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
