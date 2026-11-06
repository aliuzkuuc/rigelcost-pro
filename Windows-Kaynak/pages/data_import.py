from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from services.data_import import (
    DataImportService,
    EncryptedConnectionStringError,
)
from ui.corporate_theme import stylesheet


class SqlConnectionDialog(QDialog):
    """Şifreli kaynak ayarında ilk aktarım için SQL bilgilerini bir kez alır."""

    def __init__(self, config_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rigel Cost Pro — İlk SQL Bağlantısı")
        self.resize(570, 390)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        title = QLabel("FABRİKA VERİTABANI BAĞLANTISI")
        title.setObjectName("sqlTitle")
        detail = QLabel(
            "Seçilen rigel.config bağlantıyı şifreli saklıyor. Bilgiler yalnız "
            "bu aktarım sırasında kullanılır; Rigel'e parola olarak kaydedilmez."
        )
        detail.setObjectName("sqlHelp")
        detail.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(detail)

        default_server = DataImportService.infer_server_from_config(config_path)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.server = QLineEdit(default_server)
        self.server.setPlaceholderText("Örnek: 192.168.1.135 veya SUNUCU\\SQLEXPRESS")
        self.database = QLineEdit("RIGEL")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.trusted = QCheckBox("Windows hesabıyla bağlan")
        self.trusted.setChecked(True)
        form.addRow("SQL sunucusu *", self.server)
        form.addRow("Veritabanı *", self.database)
        form.addRow("SQL kullanıcı adı", self.username)
        form.addRow("SQL şifresi", self.password)
        form.addRow("Bağlantı tipi", self.trusted)
        root.addLayout(form)

        hint = QLabel(
            "Bu bilgileri bilmiyorsanız fabrikanın SQL Server yöneticisinden "
            "sunucu, veritabanı ve salt-okuma yetkili kullanıcı isteyin."
        )
        hint.setObjectName("sqlHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("BAĞLAN VE AKTAR")
        buttons.button(QDialogButtonBox.Cancel).setText("VAZGEÇ")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.trusted.toggled.connect(self.update_login_state)
        self.update_login_state()

        self.setStyleSheet(stylesheet(
            """
            QDialog { background:#F3F6FA; color:#1D2939; }
            QLabel, QCheckBox { color:#1D2939; background:transparent; }
            #sqlTitle { color:#0B437C; font-size:18pt; font-weight:800; }
            #sqlHelp { color:#475467; }
            #sqlHint { color:#7A4E00; background:#FFF7E6; border:1px solid #F2C66D;
                border-radius:5px; padding:8px; }
            QLineEdit { color:#101828; background:white; border:1px solid #BFCDE0;
                border-radius:4px; min-height:31px; padding:3px 7px; }
            QPushButton { min-height:34px; padding:3px 12px; font-weight:800; }
            """
        ))

    def update_login_state(self, *_args: object) -> None:
        enabled = not self.trusted.isChecked()
        self.username.setEnabled(enabled)
        self.password.setEnabled(enabled)

    def validate_and_accept(self) -> None:
        if not self.server.text().strip() or not self.database.text().strip():
            QMessageBox.warning(
                self,
                "Eksik bağlantı",
                "SQL sunucusu ve veritabanı boş bırakılamaz.",
            )
            return
        if not self.trusted.isChecked() and not self.username.text().strip():
            QMessageBox.warning(
                self,
                "Eksik kullanıcı",
                "SQL kullanıcı adını girin veya Windows hesabıyla bağlantıyı seçin.",
            )
            return
        self.accept()

    def connection_values(self) -> dict[str, str]:
        return {
            "DATA SOURCE": self.server.text().strip(),
            "DATABASE": self.database.text().strip(),
            "USER ID": self.username.text().strip(),
            "PASSWORD": self.password.text(),
            "TRUSTED CONNECTION": "YES" if self.trusted.isChecked() else "NO",
        }


class DataImportDialog(QDialog):
    """Eski sistem verisini kaynağa yazmadan Rigel'e taşıyan ekran."""

    import_completed = Signal()

    def __init__(
        self,
        service: DataImportService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Rigel Cost Pro — İlk Kurulum Veri Aktarımı")
        self.resize(820, 610)
        self.setMinimumSize(690, 520)
        self.build_ui()
        self.apply_style()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title = QLabel("RIGEL İLK KURULUM VERİ AKTARIMI")
        title.setObjectName("importTitle")
        help_text = QLabel(
            "İlk kurulumda müşteri, profil ve kalıp Excel dosyaları ayrı "
            "kavramlardır. Kalıp Excel'i yalnız kalıp/profil kartlarını yükler; "
            "rota ve reçete Üretim modülünden veya ayrı üretim aktarımından gelir. "
            "Aynı aktarım tekrar çalıştırıldığında kopya kayıt oluşturulmaz."
        )
        help_text.setObjectName("importHelp")
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)

        warning = QFrame()
        warning.setObjectName("readOnlyCard")
        warning_layout = QVBoxLayout(warning)
        warning_layout.setContentsMargins(14, 11, 14, 11)
        warning_title = QLabel("✓  SALT OKUNUR KAYNAK BAĞLANTISI")
        warning_title.setObjectName("readOnlyTitle")
        warning_text = QLabel(
            "Bu işlem eski sistem kayıtlarını değiştirmez, silmez veya kaynak sisteme "
            "yeni kayıt yazmaz. Veriler yalnızca Rigel Cost Pro'nun ayrı "
            "veritabanına kopyalanır."
        )
        warning_text.setObjectName("readOnlyText")
        warning_text.setWordWrap(True)
        warning_layout.addWidget(warning_title)
        warning_layout.addWidget(warning_text)
        root.addWidget(warning)

        excel_card = self.create_option_card(
            "1. EXCEL — PROFİL / KALIP KARTLARI",
            "Kalıp/profil Excel listesi ve SharedFiles klasörünün bulunduğu ana "
            "klasörü seçin. Bu adım yalnız profil ve kalıp kartlarını (yedek no, "
            "tenefer, tedarikçi vb.) yükler; rota / reçete / hammadde tanımı "
            "burada yapılmaz. PDF/JPG teknik belgeler otomatik bağlanır.",
            "KALIP / PROFİL EXCEL KLASÖRÜ SEÇ",
            self.choose_excel_folder,
        )
        root.addWidget(excel_card)
        if sys.platform.startswith("win") and importlib.util.find_spec("pyodbc"):
            sql_card = self.create_option_card(
                "2. FABRİKA VERİTABANI (TAM AKTARIM)",
                "Fabrika ağına bağlı Windows bilgisayarda rigel.config dosyasını "
                "seçin. Yetkili iş tabloları salt okunur alınır; kullanıcı/parola "
                "tabloları aktarılmaz.",
                "BAĞLANTI DOSYASI SEÇ VE SALT OKUNUR AKTAR",
                self.choose_config,
            )
            root.addWidget(sql_card)
        else:
            platform_note = QLabel(
                "SQL Server aktarımı yalnız gerekli ODBC bileşenlerinin kurulu "
                "olduğu Windows bilgisayarda gösterilir. Bu bilgisayarda Excel "
                "aktarımı kullanılabilir."
            )
            platform_note.setObjectName("platformNote")
            platform_note.setWordWrap(True)
            root.addWidget(platform_note)

        self.progress_label = QLabel("Aktarım bekleniyor.")
        self.progress_label.setObjectName("progressLabel")
        root.addWidget(self.progress_label)

        self.result = QPlainTextEdit()
        self.result.setObjectName("resultBox")
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Aktarım sonucu burada görüntülenecek.")
        root.addWidget(self.result, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("ATLA VE KAPAT")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    @staticmethod
    def create_option_card(
        title: str,
        description: str,
        button_text: str,
        callback,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("optionCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)
        text_layout = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("optionTitle")
        detail = QLabel(description)
        detail.setObjectName("optionDetail")
        detail.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(detail)
        layout.addLayout(text_layout, 1)
        button = QPushButton(button_text)
        button.setObjectName("importButton")
        button.setMinimumWidth(255)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return card

    def choose_excel_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Excel veri klasörünü seçin",
            str(Path.home() / "Desktop"),
        )
        if folder:
            self.run_import("Excel", lambda: self.service.import_excel_folder(folder, self.progress))

    def choose_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Eski sistem bağlantı dosyasını seçin",
            str(Path.home()),
            "Bağlantı yapılandırması (rigel.config *.config);;Tüm dosyalar (*)",
        )
        if not path:
            return
        connection_values: dict[str, str] | None = None
        try:
            self.service.parse_config_connection(path)
        except EncryptedConnectionStringError:
            connection_dialog = SqlConnectionDialog(path, self)
            if connection_dialog.exec() != QDialog.Accepted:
                return
            connection_values = connection_dialog.connection_values()
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Bağlantı dosyası okunamadı", str(error))
            return
        answer = QMessageBox.question(
            self,
            "Salt okunur SQL aktarımı",
            "Fabrika SQL Server bağlantısı açılacak ve yalnızca okuma "
            "yapılacaktır. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.run_import(
                "SQL Server",
                lambda: self.service.import_sql_server(
                    path,
                    self.progress,
                    connection_values,
                ),
            )

    def progress(self, name: str, current: int, total: int) -> None:
        self.progress_label.setText(f"Aktarılıyor: {name}  ({current}/{total})")
        QApplication.processEvents()

    def run_import(self, source: str, callback) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.result.clear()
        self.progress_label.setText(f"{source} aktarımı başlatılıyor…")
        QApplication.processEvents()
        try:
            summary = callback()
        except Exception as error:
            self.progress_label.setText("Aktarım tamamlanamadı.")
            self.result.setPlainText(str(error))
            QMessageBox.warning(self, "Veri aktarımı başarısız", str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()

        lines = [
            f"Kaynak: {source}",
            f"Yeni kayıt: {int(summary.get('inserted', 0))}",
            f"Güncellenen kayıt: {int(summary.get('updated', 0))}",
            f"Atlanan kayıt: {int(summary.get('skipped', 0))}",
        ]
        if summary.get("files") is not None:
            lines.append(f"Okunan Excel dosyası: {int(summary['files'])}")
        attachments = summary.get("attachments") or {}
        if attachments.get("found"):
            lines.append(f"Bulunan SharedFiles belgesi: {int(attachments['found'])}")
            lines.append(f"Kopyalanan/güncellenen belge: {int(attachments['copied'])}")
            lines.append(f"Profile bağlanan belge: {int(attachments['linked_profiles'])}")
            lines.append(f"Kalıba bağlanan belge: {int(attachments.get('linked_dies', 0))}")
        tables = summary.get("tables") or {}
        if tables:
            lines.append(f"Okunan SQL tablosu: {len(tables)}")
            lines.append(f"Ham SQL satırı: {sum(int(value) for value in tables.values())}")
        errors = summary.get("errors") or []
        if errors:
            lines.extend(("", "Uyarılar:", *(str(value) for value in errors)))
        self.result.setPlainText("\n".join(lines))
        self.progress_label.setText("Aktarım tamamlandı; Rigel ekranları yenilendi.")
        self.import_completed.emit()
        QMessageBox.information(self, "Veri aktarımı", "Veri aktarımı tamamlandı.")

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            QDialog { background:#EEF2F6; color:#1D2939; }
            #importTitle { color:#0B437C; font-size:18pt; font-weight:800; }
            #importHelp, #optionDetail { color:#667085; }
            #readOnlyCard { background:#ECFDF3; border:1px solid #75E0A7; border-radius:7px; }
            #readOnlyTitle { color:#067647; font-weight:800; }
            #readOnlyText { color:#065F46; background:transparent; }
            #optionCard { background:white; border:1px solid #CBD5E1; border-radius:8px; }
            #optionTitle { color:#344054; font-weight:800; }
            #importButton { background:#0B437C; color:white; border:0; border-radius:5px;
                min-height:36px; padding:4px 12px; font-weight:800; }
            #progressLabel { color:#1E3A5F; background:#EAF3FC; border:1px solid #B7D1EC;
                border-radius:5px; padding:8px; font-weight:700; }
            #platformNote { color:#475467; background:#FFF7E6; border:1px solid #F2C66D;
                border-radius:6px; padding:9px; }
            #resultBox { color:#101828;background:white; border:1px solid #CBD5E1; border-radius:6px; }
            QPushButton { min-height:34px; padding:3px 13px; font-weight:800; }
            """
        ))
