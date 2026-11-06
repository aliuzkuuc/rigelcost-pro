from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QDate, QDateTime, QPoint, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.erp_definitions import (
    DEPARTMENT_MODULES,
    FieldSpec,
    ModuleSpec,
    get_module_spec,
)
from services.erp import ErpService
from ui.column_filter_bar import ColumnFilterBar
from ui.corporate_theme import font_family_css, stylesheet
from ui.record_details_dialog import RecordDetailsDialog


class AttachmentPicker(QWidget):
    """PDF ve görselleri Rigel veri klasörüne bağlayan dosya alanı."""

    def __init__(
        self,
        *,
        file_kind: str,
        department: str,
        module: str,
        value: object = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.file_kind = file_kind
        self.department = department
        self.module = module
        self.path_edit = QLineEdit(str(value or ""))
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText(
            "PDF dosyası seçilmedi" if file_kind == "file_pdf"
            else "JPG / PNG görseli seçilmedi"
        )
        self.choose_button = QPushButton(
            "PDF EKLE" if file_kind == "file_pdf" else "JPG / PNG EKLE"
        )
        self.choose_button.setObjectName("attachmentButton")
        self.open_button = QPushButton("AÇ")
        self.open_button.setObjectName("openAttachmentButton")
        self.open_button.setEnabled(bool(self.path_edit.text()))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self.path_edit, 1)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.open_button)
        self.choose_button.clicked.connect(self.choose_file)
        self.open_button.clicked.connect(self.open_file)

    @staticmethod
    def _safe_part(value: str) -> str:
        cleaned = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in value.strip()
        )
        return cleaned.strip("_") or "kayit"

    def choose_file(self) -> None:
        if self.file_kind == "file_pdf":
            caption = "PDF dosyası seçin"
            file_filter = "PDF Dosyaları (*.pdf)"
        else:
            caption = "Profil / kalıp görseli seçin"
            file_filter = "Görsel Dosyaları (*.jpg *.jpeg *.png)"
        source, _ = QFileDialog.getOpenFileName(
            self,
            caption,
            str(Path.home() / "Desktop"),
            file_filter,
        )
        if not source:
            return

        source_path = Path(source)
        data_root = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        target_dir = (
            Path(data_root or Path.home() / ".rigelcost")
            / "attachments"
            / self._safe_part(self.department)
            / self._safe_part(self.module)
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (
            f"{uuid4().hex[:12]}_{self._safe_part(source_path.stem)}"
            f"{source_path.suffix.lower()}"
        )
        try:
            shutil.copy2(source_path, target)
        except OSError as error:
            QMessageBox.warning(self, "Dosya eklenemedi", str(error))
            return
        self.path_edit.setText(str(target))
        self.open_button.setEnabled(True)

    def open_file(self) -> None:
        path = Path(self.value())
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        QMessageBox.warning(self, "Dosya bulunamadı", "Bağlı dosya artık bu konumda değil.")

    def value(self) -> str:
        return self.path_edit.text().strip()


class RecordDialog(QDialog):
    """Modül tanımından güvenli ve tekrar kullanılabilir kayıt formu üretir."""

    def __init__(
        self,
        spec: ModuleSpec,
        values: dict[str, Any] | None = None,
        parent: QWidget | None = None,
        service: ErpService | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.service = service or ErpService()
        self.initial_values = values or {}
        self.editors: dict[str, QWidget] = {}
        self.profile_records: dict[str, dict[str, Any]] = {}
        self.die_records: list[dict[str, Any]] = []
        self.setWindowTitle(f"{spec.name} — Kayıt")
        self.resize(790, 700)
        self.setMinimumSize(620, 520)
        self.build_ui()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel(self.spec.name)
        title.setObjectName("recordDialogTitle")
        help_text = QLabel(self.spec.description)
        help_text.setObjectName("recordDialogHelp")
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)

        scroll = QScrollArea()
        scroll.setObjectName("recordScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        form_widget = QWidget()
        form_widget.setObjectName("recordFormWidget")
        form = QFormLayout(form_widget)
        form.setContentsMargins(4, 4, 12, 4)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        for field in self.spec.fields:
            editor = self.create_editor(field, self.initial_values.get(field.key))
            self.editors[field.key] = editor
            label = self.form_label(field.label + (" *" if field.required else ""))
            form.addRow(label, editor)

        self.configure_card_relations()

        scroll.setWidget(form_widget)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Save).setText("KAYDET")
        buttons.button(QDialogButtonBox.Cancel).setText("VAZGEÇ")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setStyleSheet(stylesheet(
            """
            QDialog, #recordScroll, #recordScroll > QWidget > QWidget,
            #recordFormWidget { background: #F3F6FA; color: #1F2937; }
            QLabel, QCheckBox { color: #1D2939; background: transparent; }
            #recordDialogTitle { color: #0B437C; font-size: 18pt; font-weight: 700; }
            #recordDialogHelp { color: #667085; font-size: 9pt; }
            QLineEdit, QPlainTextEdit, QComboBox, QSpinBox,
            QDoubleSpinBox, QDateEdit, QDateTimeEdit {
                color: #101828;
                background: white; border: 1px solid #C9D6E5;
                border-radius: 5px; padding: 6px; min-height: 25px;
            }
            QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled,
            QSpinBox:disabled, QDoubleSpinBox:disabled,
            QDateEdit:disabled, QDateTimeEdit:disabled {
                color: #475467; background: #F2F4F7;
            }
            QComboBox QAbstractItemView {
                color: #101828; background: #FFFFFF;
                selection-background-color: #DCEBFA; selection-color: #101828;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus,
            QDateEdit:focus, QDateTimeEdit:focus { border: 2px solid #0B74BE; }
            QPushButton {
                color: #163A70; background: #FFFFFF; border: 1px solid #AFC3DC;
                border-radius: 5px; min-width: 110px; min-height: 34px;
                padding: 2px 10px; font-weight: 700;
            }
            #attachmentButton { color: white; background: #0B74BE; border-color: #0B74BE; }
            #openAttachmentButton { min-width: 48px; max-width: 55px; }
            """
        ))

    @staticmethod
    def form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:#1D2939;background:transparent;font-weight:700;{font_family_css()}"
        )
        return label

    @staticmethod
    def _date_from_value(value: object) -> QDate:
        text = str(value or "").strip()
        parsed = QDate.fromString(text[:10], "yyyy-MM-dd")
        return parsed if parsed.isValid() else QDate.currentDate()

    @staticmethod
    def _datetime_from_value(value: object) -> QDateTime:
        text = str(value or "").strip().replace(" ", "T")
        parsed = QDateTime.fromString(text, Qt.ISODate)
        return parsed if parsed.isValid() else QDateTime.currentDateTime()

    def create_editor(self, field: FieldSpec, value: object) -> QWidget:
        current = field.default if value is None else value
        lookup = self.create_lookup_editor(field, current)
        if lookup is not None:
            editor = lookup
        elif field.kind in {"file_pdf", "file_image"}:
            editor = AttachmentPicker(
                file_kind=field.kind,
                department=self.spec.department,
                module=self.spec.name,
                value=current,
            )
        elif field.kind == "textarea":
            editor = QPlainTextEdit(str(current or ""))
            editor.setMaximumHeight(78)
        elif field.kind == "number":
            editor = QDoubleSpinBox()
            editor.setRange(-999_999_999_999.0, 999_999_999_999.0)
            editor.setDecimals(field.decimals)
            editor.setGroupSeparatorShown(True)
            editor.setValue(ErpService.number(current))
        elif field.kind == "integer":
            editor = QSpinBox()
            editor.setRange(-1_000_000_000, 1_000_000_000)
            editor.setGroupSeparatorShown(True)
            editor.setValue(int(ErpService.number(current)))
        elif field.kind == "choice":
            editor = QComboBox()
            editor.addItems(field.options)
            position = editor.findText(str(current or ""))
            if position >= 0:
                editor.setCurrentIndex(position)
        elif field.kind == "bool":
            editor = QCheckBox("Evet")
            editor.setChecked(bool(current))
        elif field.kind == "date":
            editor = QDateEdit(self._date_from_value(current))
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd.MM.yyyy")
        elif field.kind == "datetime":
            editor = QDateTimeEdit(self._datetime_from_value(current))
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd.MM.yyyy HH:mm")
        else:
            editor = QLineEdit(str(current or ""))

        editor.setEnabled(not field.readonly)
        if field.readonly:
            editor.setToolTip("Bu alan girilen bilgilere göre otomatik hesaplanır.")
        return editor

    def records_for(self, department: str, module: str) -> list[dict[str, Any]]:
        try:
            return self.service.list_records(department, module)
        except (KeyError, OSError):
            return []

    @staticmethod
    def add_lookup_items(
        combo: QComboBox,
        options: list[tuple[str, str]],
        current: object,
        empty_text: str,
    ) -> None:
        combo.setProperty("cardLookup", True)
        combo.addItem(empty_text, "")
        seen: set[str] = set()
        for display, value in options:
            normalized = str(value or "").strip()
            if not normalized or normalized.casefold() in seen:
                continue
            seen.add(normalized.casefold())
            combo.addItem(display, normalized)
        current_text = str(current or "").strip()
        position = combo.findData(current_text)
        if current_text and position < 0:
            combo.addItem(f"{current_text}  (mevcut kayıt)", current_text)
            position = combo.count() - 1
        combo.setCurrentIndex(max(0, position))

    def create_lookup_editor(
        self,
        field: FieldSpec,
        current: object,
    ) -> QComboBox | None:
        key = field.key
        is_master_customer = self.spec.name in {"Müşteriler", "Tedarikçiler"}
        is_master_profile = self.spec.name == "Profil Kartları"
        is_master_die = self.spec.name == "Kalıp Kartları"
        is_master_stock = self.spec.name == "Stok Kartları"
        options: list[tuple[str, str]] | None = None
        empty_text = "Kart seçiniz…"

        if key in {"company", "customer"} and not is_master_customer:
            source = (
                ("Satın Alma", "Tedarikçiler")
                if self.spec.department == "Satın Alma"
                else ("Satış", "Müşteriler")
            )
            options = []
            for record in self.records_for(*source):
                data = record["data"]
                name = str(data.get("name") or "").strip()
                code = str(data.get("code") or "").strip()
                if name:
                    options.append((f"{code} — {name}" if code else name, name))
            empty_text = "Müşteri / firma kartı seçiniz…"
        elif key == "supplier":
            options = []
            for record in self.records_for("Satın Alma", "Tedarikçiler"):
                data = record["data"]
                name = str(data.get("name") or "").strip()
                code = str(data.get("code") or "").strip()
                if name:
                    options.append((f"{code} — {name}" if code else name, name))
            empty_text = "Tedarikçi kartı seçiniz…"
        elif key == "profile_code" and not is_master_profile:
            options = []
            self.profile_records = {}
            for record in self.records_for("Kalıphane", "Profil Kartları"):
                data = record["data"]
                code = str(data.get("profile_code") or "").strip()
                name = str(data.get("profile_name") or "").strip()
                if code:
                    self.profile_records[code] = data
                    options.append((f"{code} — {name}" if name else code, code))
            empty_text = "Profil kartı seçiniz…"
        elif key == "die_code" and not is_master_die:
            options = []
            self.die_records = []
            for record in self.records_for("Kalıphane", "Kalıp Kartları"):
                data = record["data"]
                code = str(data.get("die_code") or "").strip()
                profile = str(data.get("profile_code") or "").strip()
                spare = str(data.get("spare_no") or "0")
                if code:
                    self.die_records.append(data)
                    label = f"{code} — Profil {profile} — Yedek {spare}"
                    options.append((label, code))
            empty_text = "Kalıp kartı seçiniz…"
        elif key == "stock_name" and not is_master_stock:
            options = []
            for record in self.records_for("Malzeme Yönetimi", "Stok Kartları"):
                data = record["data"]
                name = str(data.get("stock_name") or "").strip()
                code = str(data.get("stock_code") or "").strip()
                if name:
                    options.append((f"{code} — {name}" if code else name, name))
            for record in self.records_for("Kalıphane", "Profil Kartları"):
                data = record["data"]
                name = str(data.get("profile_name") or "").strip()
                code = str(data.get("profile_code") or "").strip()
                if name:
                    options.append((f"{code} — {name}", name))
            empty_text = "Stok / profil kartı seçiniz…"

        if options is None:
            return None
        combo = QComboBox()
        self.add_lookup_items(combo, options, current, empty_text)
        combo.setToolTip(
            "Bu alan serbest yazılmaz. Önce ilgili kartı oluşturun, sonra listeden seçin."
        )
        return combo

    def configure_card_relations(self) -> None:
        profile_editor = self.editors.get("profile_code")
        if isinstance(profile_editor, QComboBox) and profile_editor.property("cardLookup"):
            profile_editor.currentIndexChanged.connect(self.apply_selected_profile)
            profile_editor.currentIndexChanged.connect(self.filter_dies_for_profile)
            self.apply_selected_profile()
            self.filter_dies_for_profile()

    def apply_selected_profile(self, *_args: object) -> None:
        editor = self.editors.get("profile_code")
        if not isinstance(editor, QComboBox):
            return
        code = str(editor.currentData() or "")
        profile = self.profile_records.get(code)
        if not profile:
            return
        stock_name = str(profile.get("profile_name") or "").strip()
        stock_editor = self.editors.get("stock_name")
        if stock_name and isinstance(stock_editor, QComboBox):
            position = stock_editor.findData(stock_name)
            if position < 0:
                stock_editor.addItem(f"{code} — {stock_name}", stock_name)
                position = stock_editor.count() - 1
            stock_editor.setCurrentIndex(position)
        elif stock_name and isinstance(stock_editor, QLineEdit):
            stock_editor.setText(stock_name)

        for key in ("unit_weight", "theoretical_weight"):
            target = self.editors.get(key)
            if isinstance(target, QDoubleSpinBox):
                target.setValue(ErpService.number(profile.get("unit_weight")))

    def filter_dies_for_profile(self, *_args: object) -> None:
        profile_editor = self.editors.get("profile_code")
        die_editor = self.editors.get("die_code")
        if not isinstance(profile_editor, QComboBox) or not isinstance(die_editor, QComboBox):
            return
        profile_code = str(profile_editor.currentData() or "").strip()
        current_die = str(die_editor.currentData() or "").strip()
        options: list[tuple[str, str]] = []
        for data in self.die_records:
            if profile_code and str(data.get("profile_code") or "").strip() != profile_code:
                continue
            code = str(data.get("die_code") or "").strip()
            spare = str(data.get("spare_no") or "0")
            options.append((f"{code} — Yedek {spare}", code))
        die_editor.blockSignals(True)
        die_editor.clear()
        self.add_lookup_items(
            die_editor,
            options,
            current_die,
            "Bu profile ait kalıp kartı seçiniz…",
        )
        die_editor.blockSignals(False)

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in self.spec.fields:
            editor = self.editors[field.key]
            if isinstance(editor, AttachmentPicker):
                value: Any = editor.value()
            elif isinstance(editor, QPlainTextEdit):
                value: Any = editor.toPlainText().strip()
            elif isinstance(editor, QLineEdit):
                value = editor.text().strip()
            elif isinstance(editor, QDoubleSpinBox):
                value = editor.value()
            elif isinstance(editor, QSpinBox):
                value = editor.value()
            elif isinstance(editor, QComboBox):
                value = (
                    str(editor.currentData() or "")
                    if editor.property("cardLookup")
                    else editor.currentText()
                )
            elif isinstance(editor, QCheckBox):
                value = editor.isChecked()
            elif isinstance(editor, QDateTimeEdit):
                value = editor.dateTime().toString(Qt.ISODate)
            elif isinstance(editor, QDateEdit):
                value = editor.date().toString("yyyy-MM-dd")
            else:
                value = ""
            result[field.key] = value
        return result


class DepartmentPage(QWidget):
    """Rigel işletme iş akışlarını ortak kayıt motoruyla yöneten ekran."""

    def __init__(self, service: ErpService | None = None) -> None:
        super().__init__()
        self.service = service or ErpService()
        self.current_department = "Kalıphane"
        self.current_module = "Kalıp Kartları"
        self.records: list[dict[str, Any]] = []
        self.can_create = True
        self.can_edit = True
        self.can_delete = True
        self.build_ui()
        self.apply_style()
        self.set_context(self.current_department, self.current_module)

    @property
    def spec(self) -> ModuleSpec:
        return get_module_spec(self.current_department, self.current_module)

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        header = QFrame()
        header.setObjectName("departmentHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(10)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        self.department_label = QLabel("KALIPHANE")
        self.department_label.setObjectName("departmentName")
        self.module_label = QLabel("Kalıp Kartları")
        self.module_label.setObjectName("moduleName")
        self.description = QLabel("")
        self.description.setObjectName("departmentDescription")
        self.description.setWordWrap(True)
        self.description.setVisible(False)
        title_layout.addWidget(self.department_label)
        title_layout.addWidget(self.module_label)
        title_layout.addWidget(self.description)
        header_layout.addLayout(title_layout, 1)

        selector_layout = QVBoxLayout()
        selector_layout.setSpacing(2)
        selector_title = QLabel("BÖLÜM EKRANI")
        selector_title.setObjectName("selectorTitle")
        self.module_combo = QComboBox()
        self.module_combo.setObjectName("moduleCombo")
        self.module_combo.setMinimumWidth(220)
        self.module_combo.currentTextChanged.connect(self.change_module)
        selector_layout.addWidget(selector_title)
        selector_layout.addWidget(self.module_combo)
        header_layout.addLayout(selector_layout)
        layout.addWidget(header)

        kpi_layout = QGridLayout()
        kpi_layout.setHorizontalSpacing(4)
        kpi_layout.setVerticalSpacing(0)
        self.kpi_values: dict[str, QLabel] = {}
        for column, (key, title) in enumerate(
            (
                ("record_count", "TOPLAM KAYIT"),
                ("open_count", "AÇIK / BEKLEYEN"),
                ("total_kg", "TOPLAM KG"),
                ("total_amount", "TOPLAM TUTAR"),
            )
        ):
            card = QFrame()
            card.setObjectName("kpiCard")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 2, 8, 2)
            card_layout.setSpacing(6)
            title_label = QLabel(title)
            title_label.setObjectName("kpiTitle")
            value_label = QLabel("0")
            value_label.setObjectName("kpiValue")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addStretch(1)
            self.kpi_values[key] = value_label
            kpi_layout.addWidget(card, 0, column)
            kpi_layout.setColumnStretch(column, 1)
        layout.addLayout(kpi_layout)

        controls = QFrame()
        controls.setObjectName("controls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(6, 3, 6, 3)
        controls_layout.setSpacing(4)
        self.add_button = QPushButton("＋ YENİ KAYIT")
        self.add_button.setObjectName("primaryButton")
        self.edit_button = QPushButton("DÜZENLE")
        self.delete_button = QPushButton("SİL")
        self.next_button = QPushButton("SONRAKİ AŞAMAYA AKTAR")
        self.next_button.setObjectName("flowButton")
        self.refresh_button = QPushButton("YENİLE")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara…")
        self.search.setClearButtonEnabled(True)
        self.clear_column_filters = QPushButton("FİLTRE TEMİZLE")
        controls_layout.addWidget(self.add_button)
        controls_layout.addWidget(self.edit_button)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.clear_column_filters)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.search, 1)
        layout.addWidget(controls)

        self.table = QTableWidget()
        self.table.setObjectName("erpTable")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.column_filter_bar = ColumnFilterBar()
        self.column_filter_bar.attach_table(self.table)
        grid_host = QWidget()
        grid_layout = QVBoxLayout(grid_host)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)
        grid_layout.addWidget(self.column_filter_bar)
        grid_layout.addWidget(self.table, 1)
        layout.addWidget(grid_host, 1)

        self.status = QLabel("")
        self.status.setObjectName("departmentStatus")
        self.status.setWordWrap(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

        self.add_button.clicked.connect(self.add_record)
        self.edit_button.clicked.connect(self.edit_record)
        self.delete_button.clicked.connect(self.delete_record)
        self.next_button.clicked.connect(self.create_next_step)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.search.textChanged.connect(self.refresh_data)
        self.clear_column_filters.clicked.connect(self.column_filter_bar.clear_filters)
        self.column_filter_bar.filtersChanged.connect(self.refresh_data)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_record())
        self.table.itemSelectionChanged.connect(self.update_selection_state)
        self.table.customContextMenuRequested.connect(self.open_context_menu)

    def set_context(self, department: str, module: str) -> None:
        if department not in DEPARTMENT_MODULES:
            raise KeyError(f"Bilinmeyen bölüm: {department}")
        modules = DEPARTMENT_MODULES[department]
        if module not in modules:
            module = modules[0]
        self.current_department = department
        self.current_module = module

        self.module_combo.blockSignals(True)
        self.module_combo.clear()
        self.module_combo.addItems(modules)
        self.module_combo.setCurrentText(module)
        self.module_combo.blockSignals(False)
        self.apply_context()

    def change_module(self, module: str) -> None:
        if not module:
            return
        self.current_module = module
        self.apply_context()

    def apply_context(self) -> None:
        spec = self.spec
        self.department_label.setText(self.current_department.upper())
        self.module_label.setText(spec.name)
        self.description.setText(spec.description)
        if spec.next_step and self.can_create:
            self.next_button.setVisible(True)
            self.next_button.setText(f"AKTAR → {spec.next_step[1].upper()}")
        else:
            self.next_button.setVisible(False)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.configure_table()
        self.refresh_data()

    def set_access(
        self,
        *,
        can_create: bool,
        can_edit: bool,
        can_delete: bool,
    ) -> None:
        self.can_create = bool(can_create)
        self.can_edit = bool(can_edit)
        self.can_delete = bool(can_delete)
        self.add_button.setVisible(self.can_create)
        self.delete_button.setVisible(self.can_delete)
        self.apply_context()

    def configure_table(self) -> None:
        spec = self.spec
        keys = ("record_no", *spec.table_keys)
        labels = ["Kayıt No"]
        labels.extend(spec.field_map[key].label for key in spec.table_keys)
        self.table.clear()
        self.table.setColumnCount(len(keys))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setProperty("field_keys", keys)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        for index in range(len(keys)):
            self.table.setColumnWidth(index, 132)
        columns = list(zip(keys, labels))
        self.column_filter_bar.configure(columns, preserve=False)
        self.column_filter_bar.setVisible(True)

    @staticmethod
    def format_number(value: object, decimals: int = 2) -> str:
        number = ErpService.number(value)
        text = f"{number:,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")

    def display_value(self, key: str, value: object) -> str:
        if key == "record_no":
            return str(value or "")
        field = self.spec.field_map[key]
        if field.kind in {"number", "integer"}:
            return self.format_number(value, field.decimals)
        if field.kind == "bool":
            return "EVET" if bool(value) else "HAYIR"
        if field.kind == "date":
            try:
                return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")
            except ValueError:
                return str(value or "")
        if field.kind == "datetime":
            try:
                return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                return str(value or "")
        return str(value or "")

    def refresh_data(self, *_args: object) -> None:
        self.records = self.service.list_records(
            self.current_department,
            self.current_module,
            search=self.search.text(),
        )
        keys: tuple[str, ...] = self.table.property("field_keys") or ()

        def _row_view(record: dict) -> dict:
            data = dict(record.get("data") or {})
            data["record_no"] = record.get("record_no")
            return {
                key: self.display_value(
                    key,
                    record.get("record_no") if key == "record_no" else data.get(key),
                )
                for key in keys
            }

        source_views = [_row_view(record) for record in self.records]
        self.column_filter_bar.update_distinct_values(source_views)

        if self.column_filter_bar.has_active_filters():
            filtered = []
            for record, row_view in zip(self.records, source_views):
                if self.column_filter_bar.row_matches(row_view):
                    filtered.append(record)
            self.records = filtered
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            data = record["data"]
            for column, key in enumerate(keys):
                raw = record.get("record_no") if key == "record_no" else data.get(key)
                item = QTableWidgetItem(self.display_value(key, raw))
                if column == 0:
                    item.setData(Qt.UserRole, record["id"])
                    item.setForeground(QColor("#0B437C"))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if key in {"status", "production_approval", "press_status"}:
                    item.setForeground(QColor("#0B6B43"))
                self.table.setItem(row, column, item)

        summary = self.service.summary(self.current_department, self.current_module)
        self.kpi_values["record_count"].setText(str(int(summary["record_count"])))
        self.kpi_values["open_count"].setText(str(int(summary["open_count"])))
        self.kpi_values["total_kg"].setText(
            self.format_number(summary["total_kg"]) + " kg"
        )
        self.kpi_values["total_amount"].setText(
            self.format_number(summary["total_amount"])
        )
        filter_note = (
            " (sütun filtreli)" if self.column_filter_bar.has_active_filters() else ""
        )
        self.status.setText(
            f"{self.current_department} / {self.current_module}: "
            f"{len(self.records)} kayıt gösteriliyor{filter_note}. "
            "Veriler maliyet motorundan ayrı saklanır."
        )
        self.column_filter_bar.sync_widths()
        self.update_selection_state()

    def selected_record_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item is not None else None

    def update_selection_state(self) -> None:
        selected = self.selected_record_id() is not None
        self.edit_button.setVisible(self.can_edit)
        self.edit_button.setEnabled(selected and self.can_edit)
        self.delete_button.setEnabled(selected and self.can_delete)
        self.next_button.setEnabled(
            selected and self.can_create and self.spec.next_step is not None
        )

    def add_record(self) -> None:
        if not self.can_create:
            return
        dialog = RecordDialog(self.spec, parent=self, service=self.service)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            record_id = self.service.create_record(
                self.current_department,
                self.current_module,
                dialog.values(),
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kayıt eklenemedi", str(error))
            return
        self.refresh_data()
        self.select_record(record_id)
        self.status.setText("Kayıt başarıyla oluşturuldu.")

    def edit_record(self) -> None:
        if not self.can_edit:
            return
        record_id = self.selected_record_id()
        if record_id is None:
            return
        record = self.service.get_record(record_id)
        if record is None:
            self.refresh_data()
            return
        dialog = RecordDialog(
            self.spec,
            record["data"],
            self,
            service=self.service,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_record(record_id, dialog.values())
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kayıt güncellenemedi", str(error))
            return
        self.refresh_data()
        self.select_record(record_id)
        self.status.setText("Kayıt güncellendi; hesaplanan alanlar yenilendi.")

    def delete_record(self) -> None:
        if not self.can_delete:
            return
        record_id = self.selected_record_id()
        if record_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Kaydı sil",
            "Seçili kayıt silinsin mi? Bu işlem geri alınamaz.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.delete_record(record_id)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Kayıt silinemedi", str(error))
            return
        self.refresh_data()
        self.status.setText("Kayıt silindi.")

    def create_next_step(self) -> None:
        if not self.can_create:
            return
        record_id = self.selected_record_id()
        if record_id is None or self.spec.next_step is None:
            return
        target = self.spec.next_step
        try:
            new_id = self.service.create_linked_record(record_id)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Aktarım yapılamadı", str(error))
            return
        self.set_context(*target)
        self.select_record(new_id)
        self.status.setText(
            f"Bağlantılı kayıt oluşturuldu: {target[0]} / {target[1]}."
        )

    def select_record(self, record_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and int(item.data(Qt.UserRole)) == int(record_id):
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break

    def context_action_texts(self) -> list[str]:
        actions: list[str] = []
        if self.can_create:
            actions.append("Ekle")
        if self.can_edit:
            actions.append("Değiştir")
        if self.can_delete:
            actions.append("Sil")
        if self.spec.next_step and self.can_create:
            actions.append("Sonraki Aşamaya Aktar")
        if any(field.kind in {"file_pdf", "file_image"} for field in self.spec.fields):
            actions.append("Dokümanları Aç")
        actions.extend(("Kayıt Bilgisi", "Yenile", "Listeyi Excel'e Aktar", "Sütunları Sıfırla"))
        return actions

    def open_context_menu(self, position: QPoint) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
        callbacks = {
            "Ekle": self.add_record,
            "Değiştir": self.edit_record,
            "Sil": self.delete_record,
            "Sonraki Aşamaya Aktar": self.create_next_step,
            "Dokümanları Aç": self.open_selected_documents,
            "Kayıt Bilgisi": self.show_record_info,
            "Yenile": self.refresh_data,
            "Listeyi Excel'e Aktar": self.export_current_table,
            "Sütunları Sıfırla": self.reset_columns,
        }
        menu = QMenu(self)
        for text in self.context_action_texts():
            if text in {"Kayıt Bilgisi", "Yenile"} and menu.actions():
                menu.addSeparator()
            action = QAction(text, menu)
            action.triggered.connect(callbacks[text])
            action.setEnabled(
                text in {"Ekle", "Yenile", "Listeyi Excel'e Aktar", "Sütunları Sıfırla"}
                or self.selected_record_id() is not None
            )
            menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def show_record_info(self) -> None:
        record_id = self.selected_record_id()
        if record_id is None:
            return
        record = self.service.get_record(record_id)
        if record is None:
            return
        data = record["data"]
        rows = [
            ("Kayıt No", record.get("record_no", "")),
            ("Bölüm", record.get("department", "")),
            ("Modül", record.get("module", "")),
            ("Oluşturma", record.get("created_at", "")),
            ("Son güncelleme", record.get("updated_at", "")),
        ]
        rows.extend((field.label, data.get(field.key, "")) for field in self.spec.fields)
        RecordDetailsDialog(
            "Kayıt Bilgisi",
            fields=rows,
            header_title="KART BİLGİSİ",
            subtitle=str(record.get("record_no", "")),
            parent=self,
        ).exec()

    def open_selected_documents(self) -> None:
        record_id = self.selected_record_id()
        if record_id is None:
            return
        record = self.service.get_record(record_id)
        if record is None:
            return
        opened = 0
        for field in self.spec.fields:
            if field.kind not in {"file_pdf", "file_image"}:
                continue
            path = Path(str(record["data"].get(field.key) or ""))
            if path.is_file() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                opened += 1
        if opened == 0:
            QMessageBox.information(self, "Doküman yok", "Seçili kayda bağlı PDF veya görsel bulunmuyor.")

    def export_current_table(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Listeyi Excel'e aktar", f"{self.current_module}.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = self.current_module[:31]
        sheet.append([self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())])
        for row in range(self.table.rowCount()):
            sheet.append([
                self.table.item(row, column).text() if self.table.item(row, column) else ""
                for column in range(self.table.columnCount())
            ])
        workbook.save(path)

    def reset_columns(self) -> None:
        self.configure_table()
        self.refresh_data()

    def apply_style(self) -> None:
        self.setStyleSheet(stylesheet(
            """
            DepartmentPage { background: #EEF2F6; color: #1F2937; }
            DepartmentPage QLabel { color: #1D2939; background: transparent; }
            #departmentHeader, #kpiCard, #controls {
                background: #FFFFFF; border: 1px solid #D5DDE7; border-radius: 8px;
            }
            #departmentName, #selectorTitle, #kpiTitle {
                color: #667085; font-size: 9pt; font-weight: 600;
            }
            #moduleName { color: #0B437C; font-size: 12pt; font-weight: 700; }
            #departmentDescription { color: #667085; font-size: 9pt; }
            #moduleCombo, #controls QLineEdit {
                color: #101828;
                background: #FFFFFF; border: 1px solid #BFCDE0;
                border-radius: 3px; min-height: 24px; padding: 1px 6px;
            }
            #moduleCombo QAbstractItemView {
                color: #101828; background: #FFFFFF;
                selection-color: #101828; selection-background-color: #DCEBFA;
            }
            #kpiValue { color: #0B437C; font-size: 11pt; font-weight: 700; }
            #controls QPushButton {
                background: #FFFFFF; color: #163A70; border: 1px solid #AFC3DC;
                border-radius: 3px; padding: 2px 8px; font-weight: 700;
                min-height: 24px;
            }
            #controls QPushButton:hover { background: #EAF3FC; }
            #controls QPushButton:disabled { color: #98A2B3; background: #F2F4F7; }
            #controls #primaryButton { background: #0B74BE; color: white; border-color: #0B74BE; }
            #controls #flowButton { background: #0B437C; color: white; border-color: #0B437C; }
            #erpTable {
                color: #1D2939;
                background: white; alternate-background-color: #F5F8FC;
                border: 1px solid #C8D3E1; gridline-color: #D7E0EB;
                selection-background-color: #DCEBFA; selection-color: #12233B;
            }
            #erpTable QHeaderView::section {
                background: #0B437C; color: white; border: none;
                border-right: 1px solid #35628E; padding: 8px; font-weight: 700;
            }
            #departmentStatus {
                color: #1E3A5F; background: #EAF3FC; border: 1px solid #B7D1EC;
                border-radius: 6px; padding: 8px;
            }
            """
        ))
