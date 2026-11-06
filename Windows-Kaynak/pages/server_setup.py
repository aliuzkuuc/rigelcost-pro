from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from services.central_database import (
    DatabaseConfigStore,
    DatabaseSettings,
    SqlServerConnectionFactory,
    SqlServerMigrator,
    WindowsDpapi,
)
from ui.corporate_theme import stylesheet


class ServerSetupDialog(QDialog):
    """Fabrika sunucusundaki merkezi Rigel SQL veritabanını hazırlar."""

    def __init__(self, parent=None, store: DatabaseConfigStore | None = None) -> None:
        super().__init__(parent)
        self.store = store or DatabaseConfigStore()
        self.setWindowTitle("Rigel Cost Pro — Merkezi Sunucu Bağlantısı")
        self.resize(720, 610)
        self.setMinimumSize(630, 540)
        self.build_ui()
        self.load_settings()
        self.apply_style()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 21, 24, 21)
        root.setSpacing(12)

        title = QLabel("MERKEZİ SQL SERVER KURULUMU")
        title.setObjectName("serverTitle")
        detail = QLabel(
            "Fabrikadaki bütün Rigel istemcileri bu tek veritabanına bağlanır. "
            "Bu ekran kaynak ERP veritabanını değiştirmez; RIGEL_COST_PRO adında "
            "ayrı bir veritabanı kullanır."
        )
        detail.setObjectName("serverHelp")
        detail.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(detail)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        form = QFormLayout(form_card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)

        self.server = QLineEdit()
        self.server.setPlaceholderText(r"Örnek: 192.168.1.20\RIGEL veya SUNUCU")
        self.database = QLineEdit("RIGEL_COST_PRO")
        self.attachment_share = QLineEdit()
        self.attachment_share.setPlaceholderText(
            r"Örnek: \\SUNUCU\RigelData\Attachments"
        )
        self.auth_type = QComboBox()
        self.auth_type.addItem("Windows hesabıyla bağlan", "windows")
        self.auth_type.addItem("SQL kullanıcı adı ve şifresi", "sql")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.remember_password = QCheckBox(
            "Parolayı bu Windows kullanıcısı için şifreli hatırla"
        )
        self.remember_password.setEnabled(WindowsDpapi.available())
        self.remember_password.setToolTip(
            "Parola Windows DPAPI ile korunur; düz metin olarak kaydedilmez."
        )

        form.addRow("SQL Server *", self.server)
        form.addRow("Rigel veritabanı *", self.database)
        form.addRow("Ortak belge klasörü", self.attachment_share)
        form.addRow("Kimlik doğrulama", self.auth_type)
        form.addRow("SQL kullanıcı adı", self.username)
        form.addRow("SQL şifresi", self.password)
        form.addRow("Parola güvenliği", self.remember_password)
        root.addWidget(form_card)

        warning = QLabel(
            "İlk kurulumda veritabanını oluşturacak hesabın SQL Server üzerinde "
            "dbcreator yetkisi olmalıdır. Günlük kullanım için daha sınırlı bir "
            "Rigel uygulama hesabı kullanılacaktır."
        )
        warning.setObjectName("serverWarning")
        warning.setWordWrap(True)
        root.addWidget(warning)

        self.status = QLabel("Bağlantı henüz sınanmadı.")
        self.status.setObjectName("serverStatus")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.test_button = QPushButton("BAĞLANTIYI SINAYIN")
        self.test_button.setObjectName("secondaryButton")
        self.install_button = QPushButton("VERİTABANINI HAZIRLA")
        self.install_button.setObjectName("primaryButton")
        self.save_button = QPushButton("AYARLARI KAYDET")
        self.save_button.setObjectName("primaryButton")
        actions.addWidget(self.test_button)
        actions.addWidget(self.install_button)
        actions.addWidget(self.save_button)
        root.addLayout(actions)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("KAPAT")
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        root.addLayout(close_row)

        self.auth_type.currentIndexChanged.connect(self.update_auth_fields)
        self.test_button.clicked.connect(self.test_connection)
        self.install_button.clicked.connect(self.prepare_database)
        self.save_button.clicked.connect(self.save_settings)
        self.update_auth_fields()

    def settings(self) -> DatabaseSettings:
        return DatabaseSettings(
            server=self.server.text(),
            database=self.database.text(),
            trusted_connection=self.auth_type.currentData() == "windows",
            username=self.username.text(),
            password=self.password.text(),
            attachment_share=self.attachment_share.text(),
        ).validated()

    def load_settings(self) -> None:
        try:
            settings = self.store.load()
        except (ValueError, OSError) as error:
            self.status.setText(f"Kayıtlı ayar okunamadı: {error}")
            return
        if settings is None:
            return
        self.server.setText(settings.server)
        self.database.setText(settings.database)
        self.attachment_share.setText(settings.attachment_share)
        self.auth_type.setCurrentIndex(0 if settings.trusted_connection else 1)
        self.username.setText(settings.username)
        self.password.setText(settings.password)
        self.remember_password.setChecked(bool(settings.password))
        self.status.setText("Kayıtlı sunucu ayarları yüklendi.")

    def update_auth_fields(self, *_args: object) -> None:
        sql_login = self.auth_type.currentData() == "sql"
        self.username.setEnabled(sql_login)
        self.password.setEnabled(sql_login)
        self.remember_password.setEnabled(sql_login and WindowsDpapi.available())

    def test_connection(self) -> None:
        try:
            info = SqlServerConnectionFactory(self.settings()).test_connection()
        except Exception as error:
            self.status.setText(f"Bağlantı başarısız: {error}")
            QMessageBox.warning(self, "SQL bağlantısı başarısız", str(error))
            return
        self.status.setText(
            f"Bağlantı başarılı — Sunucu: {info['server']} | "
            f"Veritabanı: {info['database']} | SQL: {info['version']}"
        )

    def prepare_database(self) -> None:
        answer = QMessageBox.question(
            self,
            "Rigel veritabanını hazırla",
            "Seçilen SQL Server üzerinde ayrı RIGEL_COST_PRO veritabanı "
            "oluşturulacak veya mevcut şeması güncellenecek. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            settings = self.settings()
            factory = SqlServerConnectionFactory(settings)
            created = factory.ensure_database()
            migration_root = (
                Path(__file__).resolve().parents[1] / "database" / "sqlserver"
            )
            applied = SqlServerMigrator(factory, migration_root).migrate()
            self.store.save(
                settings,
                remember_password=self.remember_password.isChecked(),
            )
        except Exception as error:
            self.status.setText(f"Kurulum tamamlanamadı: {error}")
            QMessageBox.warning(self, "SQL kurulumu başarısız", str(error))
            return
        parts = [
            "Veritabanı oluşturuldu." if created else "Mevcut veritabanı bulundu.",
            (
                f"{len(applied)} şema güncellemesi uygulandı."
                if applied
                else "Şema zaten güncel."
            ),
        ]
        self.status.setText(" ".join(parts))
        QMessageBox.information(self, "Rigel SQL Server", " ".join(parts))

    def save_settings(self) -> None:
        try:
            settings = self.settings()
            self.store.save(
                settings,
                remember_password=self.remember_password.isChecked(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Ayar kaydedilemedi", str(error))
            return
        self.status.setText("Sunucu ayarları güvenli biçimde kaydedildi.")

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            QDialog { background:#EEF2F6; color:#1D2939; }
            QLabel, QCheckBox { color:#1D2939; background:transparent; }
            #serverTitle { color:#0B437C; font-size:18pt; font-weight:800; }
            #serverHelp { color:#475467; }
            #formCard { background:white; border:1px solid #CBD5E1; border-radius:8px; }
            #serverWarning { color:#7A4E00; background:#FFF7E6; border:1px solid #F2C66D;
                border-radius:6px; padding:10px; }
            #serverStatus { color:#1E3A5F; background:#EAF3FC; border:1px solid #B7D1EC;
                border-radius:6px; padding:10px; font-weight:700; }
            QLineEdit, QComboBox { color:#101828; background:white; border:1px solid #BFCDE0;
                border-radius:5px; min-height:32px; padding:3px 7px; }
            QComboBox QAbstractItemView { color:#101828; background:white; }
            QPushButton { min-height:36px; padding:3px 12px; font-weight:800;
                color:#163A70; background:white; border:1px solid #AFC3DC; border-radius:5px; }
            #primaryButton { color:white; background:#0B5A9C; border-color:#0B5A9C; }
            #secondaryButton { color:#0B437C; background:#EAF3FC; }
            """
        ))
