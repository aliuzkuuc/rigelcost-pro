from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from services.local_workflow import LocalWorkflowService
from ui.corporate_theme import stylesheet


class _BaseMasterDialog(QDialog):
    def __init__(self, parent=None, *, title: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.form = QFormLayout()
        root = QVBoxLayout(self)
        root.addLayout(self.form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("KAYDET")
        buttons.button(QDialogButtonBox.Cancel).setText("VAZGEÇ")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setStyleSheet(stylesheet("QDialog { background:#F3F6FA; }"))

    def _date_edit(self) -> QDateEdit:
        editor = QDateEdit(QDate.currentDate())
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd")
        return editor


class RequestReasonDialog(_BaseMasterDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Talep Sebebi")
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(80)
        self.form.addRow("Kod", self.code)
        self.form.addRow("Ad", self.name)
        self.form.addRow("Açıklama", self.description)

    def values(self) -> dict[str, str]:
        return {
            "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
        }


class ComplaintDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Müşteri Şikayeti")
        self.customer = QComboBox()
        for row in service.list_customers():
            self.customer.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.complaint_date = self._date_edit()
        self.profile_code = QLineEdit()
        self.subject = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(100)
        self.form.addRow("Müşteri", self.customer)
        self.form.addRow("Tarih", self.complaint_date)
        self.form.addRow("Profil Kodu", self.profile_code)
        self.form.addRow("Konu", self.subject)
        self.form.addRow("Açıklama", self.description)

    def values(self) -> dict[str, Any]:
        return {
            "customer_id": int(self.customer.currentData()),
            "complaint_date": self.complaint_date.date().toString("yyyy-MM-dd"),
            "profile_code": self.profile_code.text().strip().upper(),
            "subject": self.subject.text().strip(),
            "description": self.description.toPlainText().strip(),
        }


class SalesPriceListDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Profil Fiyat Listesi")
        self.list_code = QLineEdit()
        self.list_name = QLineEdit()
        self.currency = QComboBox()
        self.currency.addItems(("USD", "EUR", "TRY"))
        self.valid_from = self._date_edit()
        self.valid_until = self._date_edit()
        self.valid_until.setDate(QDate.currentDate().addYears(1))
        self.customer = QComboBox()
        self.customer.addItem("— Genel —", None)
        for row in service.list_customers():
            self.customer.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.form.addRow("Liste Kodu", self.list_code)
        self.form.addRow("Liste Adı", self.list_name)
        self.form.addRow("Döviz", self.currency)
        self.form.addRow("Müşteri", self.customer)
        self.form.addRow("Geçerlilik Başlangıç", self.valid_from)
        self.form.addRow("Geçerlilik Bitiş", self.valid_until)

    def values(self) -> dict[str, Any]:
        return {
            "list_code": self.list_code.text().strip().upper(),
            "list_name": self.list_name.text().strip(),
            "currency": self.currency.currentText(),
            "customer_id": self.customer.currentData(),
            "valid_from": self.valid_from.date().toString("yyyy-MM-dd"),
            "valid_until": self.valid_until.date().toString("yyyy-MM-dd"),
        }


class DieToolingRequestDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Kalıp Talebi")
        self.profile = QComboBox()
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.supplier = QComboBox()
        self.supplier.addItem("— Seçilmedi —", None)
        for row in service.list_suppliers():
            self.supplier.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.request_date = self._date_edit()
        self.figure_no = QLineEdit()
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(80)
        self.form.addRow("Profil", self.profile)
        self.form.addRow("Tedarikçi", self.supplier)
        self.form.addRow("Talep Tarihi", self.request_date)
        self.form.addRow("Figür No", self.figure_no)
        self.form.addRow("Not", self.note)

    def values(self) -> dict[str, Any]:
        return {
            "profile_id": int(self.profile.currentData()),
            "supplier_id": self.supplier.currentData(),
            "request_date": self.request_date.date().toString("yyyy-MM-dd"),
            "figure_no": self.figure_no.text().strip(),
            "note": self.note.toPlainText().strip(),
        }


class DieToolingWorkOrderDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Kalıp İş Emri")
        self.profile = QComboBox()
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.die = QComboBox()
        self.die.addItem("— Seçilmedi —", None)
        for row in service.list_dies():
            self.die.addItem(row["die_code"], row["id"])
        self.supplier = QComboBox()
        self.supplier.addItem("— Seçilmedi —", None)
        for row in service.list_suppliers():
            self.supplier.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.order_type = QComboBox()
        self.order_type.addItems(("BAKIM", "TENEFER", "YENİ KALIP", "TAMİR"))
        self.order_date = self._date_edit()
        self.planned_end = self._date_edit()
        self.planned_end.setDate(QDate.currentDate().addDays(14))
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(80)
        self.form.addRow("Profil", self.profile)
        self.form.addRow("Kalıp", self.die)
        self.form.addRow("Tedarikçi", self.supplier)
        self.form.addRow("Emir Tipi", self.order_type)
        self.form.addRow("Emir Tarihi", self.order_date)
        self.form.addRow("Plan Bitiş", self.planned_end)
        self.form.addRow("Not", self.note)

    def values(self) -> dict[str, Any]:
        return {
            "profile_id": int(self.profile.currentData()),
            "die_id": self.die.currentData(),
            "supplier_id": self.supplier.currentData(),
            "order_type": self.order_type.currentText(),
            "order_date": self.order_date.date().toString("yyyy-MM-dd"),
            "planned_end": self.planned_end.date().toString("yyyy-MM-dd"),
            "note": self.note.toPlainText().strip(),
        }


class ProfileEditDialog(_BaseMasterDialog):
    def __init__(
        self, service: LocalWorkflowService, profile_id: int, parent=None
    ) -> None:
        super().__init__(parent, title="Profil Kartı Düzenle")
        profile = service.profile(profile_id)
        self.profile_id = profile_id
        self.code = QLineEdit(str(profile["profile_code"]))
        self.code.setReadOnly(True)
        self.name = QLineEdit(str(profile["profile_name"]))
        self.unit_weight = QDoubleSpinBox()
        self.unit_weight.setDecimals(4)
        self.unit_weight.setRange(0.0001, 1_000_000)
        self.unit_weight.setValue(float(profile["unit_weight_kg_m"] or 0))
        self.alloy = QComboBox()
        self.alloy.addItems(("6060B", "6063B", "6060", "6063", "6082"))
        self.alloy.setCurrentText(str(profile.get("alloy") or "6060B"))
        self.temper = QComboBox()
        self.temper.addItems(("T5", "T6", "T4", "T66"))
        self.temper.setCurrentText(str(profile.get("temper") or "T5"))
        self.form.addRow("Profil kodu", self.code)
        self.form.addRow("Profil adı *", self.name)
        self.form.addRow("Teorik kg/m *", self.unit_weight)
        self.form.addRow("Alaşım", self.alloy)
        self.form.addRow("Sertlik", self.temper)

    def values(self) -> dict[str, Any]:
        return {
            "profile_name": self.name.text().strip(),
            "unit_weight_kg_m": self.unit_weight.value(),
            "alloy": self.alloy.currentText(),
            "temper": self.temper.currentText(),
        }


class DieEditDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, die_id: int, parent=None) -> None:
        super().__init__(parent, title="Kalıp Kartı Düzenle")
        die = service.die(die_id)
        self.die_id = die_id
        self.code = QLineEdit(str(die["die_code"]))
        self.code.setReadOnly(True)
        self.profile_label = QLineEdit(str(die.get("profile_code") or ""))
        self.profile_label.setReadOnly(True)
        self.figure_count = QSpinBox()
        self.figure_count.setRange(1, 32)
        self.figure_count.setValue(max(1, int(die.get("figure_count") or 1)))
        self.life_limit = QDoubleSpinBox()
        self.life_limit.setDecimals(0)
        self.life_limit.setRange(0, 1_000_000_000)
        self.life_limit.setValue(float(die.get("life_limit_kg") or 0))
        self.tenefer_no = QLineEdit(str(die.get("tenefer_no") or ""))
        self.tenefer_type = QLineEdit(str(die.get("tenefer_type") or ""))
        self.tenefer_limit = QDoubleSpinBox()
        self.tenefer_limit.setDecimals(0)
        self.tenefer_limit.setRange(0, 1_000_000_000)
        self.tenefer_limit.setValue(float(die.get("tenefer_limit_m") or 0))
        self.supplier_name = QLineEdit(str(die.get("supplier_name") or ""))
        self.location = QLineEdit(str(die.get("location") or "ARŞİVDE"))
        self.note = QPlainTextEdit(str(die.get("note") or ""))
        self.note.setMaximumHeight(80)
        self.form.addRow("Kalıp kodu", self.code)
        self.form.addRow("Profil", self.profile_label)
        self.form.addRow("Figür adet", self.figure_count)
        self.form.addRow("Ömür limiti (kg)", self.life_limit)
        self.form.addRow("Tenefer no", self.tenefer_no)
        self.form.addRow("Tenefer cinsi", self.tenefer_type)
        self.form.addRow("Tenefer ömrü (m)", self.tenefer_limit)
        self.form.addRow("Tedarikçi", self.supplier_name)
        self.form.addRow("Konum / raf", self.location)
        self.form.addRow("Not", self.note)

    def values(self) -> dict[str, Any]:
        return {
            "figure_count": self.figure_count.value(),
            "life_limit_kg": self.life_limit.value(),
            "tenefer_no": self.tenefer_no.text(),
            "tenefer_type": self.tenefer_type.text(),
            "tenefer_limit_m": self.tenefer_limit.value(),
            "supplier_name": self.supplier_name.text(),
            "location": self.location.text(),
            "note": self.note.toPlainText(),
        }


class PriceListPickerDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Fiyat Listesi Seç")
        self.list_combo = QComboBox()
        lists = service.list_sales_price_lists()
        if not lists:
            raise ValueError("Tanımlı fiyat listesi yok.")
        for row in lists:
            label = f"{row['list_code']} — {row['list_name']}"
            if row.get("customer_name"):
                label += f" ({row['customer_name']})"
            self.list_combo.addItem(label, row["id"])
        self.form.addRow("Fiyat listesi *", self.list_combo)

    def price_list_id(self) -> int:
        return int(self.list_combo.currentData())


class ServiceItemDialog(_BaseMasterDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Hizmet Kartı")
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.unit = QComboBox()
        self.unit.addItems(("KG", "ADET", "METRE", "SAAT"))
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(80)
        self.form.addRow("Kod *", self.code)
        self.form.addRow("Ad *", self.name)
        self.form.addRow("Birim", self.unit)
        self.form.addRow("Açıklama", self.description)

    def values(self) -> dict[str, str]:
        return {
            "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(),
            "unit": self.unit.currentText(),
            "description": self.description.toPlainText().strip(),
        }


class DieToolingSlipDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Kalıp Fişi")
        self.die = QComboBox()
        self.profile = QComboBox()
        profile_map: dict[int, str] = {}
        for row in service.list_dies():
            label = f"{row['die_code']} / {row['profile_code']}"
            self.die.addItem(label, row["id"])
            profile_map[int(row["id"])] = int(row["profile_id"])
        self._profile_map = profile_map
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.die.currentIndexChanged.connect(self._sync_profile)
        self._sync_profile()
        self.slip_date = self._date_edit()
        self.slip_type = QComboBox()
        self.slip_type.addItems(("BAKIM", "TENEFER", "SEVK", "İADE"))
        self.used_kg = QDoubleSpinBox()
        self.used_kg.setDecimals(3)
        self.used_kg.setRange(0, 1_000_000)
        self.location_from = QLineEdit("KALIPHANE")
        self.location_to = QLineEdit("PRES")
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(80)
        self.form.addRow("Kalıp *", self.die)
        self.form.addRow("Profil *", self.profile)
        self.form.addRow("Fiş tarihi", self.slip_date)
        self.form.addRow("Fiş tipi", self.slip_type)
        self.form.addRow("Kullanılan kg", self.used_kg)
        self.form.addRow("Nereden", self.location_from)
        self.form.addRow("Nereye", self.location_to)
        self.form.addRow("Not", self.note)

    def _sync_profile(self) -> None:
        die_id = self.die.currentData()
        if die_id is None:
            return
        profile_id = self._profile_map.get(int(die_id))
        if profile_id is None:
            return
        index = self.profile.findData(profile_id)
        if index >= 0:
            self.profile.setCurrentIndex(index)

    def values(self) -> dict[str, Any]:
        return {
            "die_id": int(self.die.currentData()),
            "profile_id": int(self.profile.currentData()),
            "slip_date": self.slip_date.date().toString("yyyy-MM-dd"),
            "slip_type": self.slip_type.currentText(),
            "used_kg": self.used_kg.value(),
            "location_from": self.location_from.text().strip(),
            "location_to": self.location_to.text().strip(),
            "note": self.note.toPlainText().strip(),
        }


class DieToolingProblemDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Kalıp Problemi")
        self.die = QComboBox()
        self.profile = QComboBox()
        profile_map: dict[int, int] = {}
        for row in service.list_dies():
            self.die.addItem(f"{row['die_code']} / {row['profile_code']}", row["id"])
            profile_map[int(row["id"])] = int(row["profile_id"])
        self._profile_map = profile_map
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.die.currentIndexChanged.connect(self._sync_profile)
        self._sync_profile()
        self.record_date = self._date_edit()
        self.problem_type = QComboBox()
        self.problem_type.addItems(("ÇATLAK", "AŞINMA", "BOYUT", "YÜZEY", "DİĞER"))
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.form.addRow("Kalıp *", self.die)
        self.form.addRow("Profil *", self.profile)
        self.form.addRow("Tarih", self.record_date)
        self.form.addRow("Problem tipi", self.problem_type)
        self.form.addRow("Açıklama *", self.description)

    def _sync_profile(self) -> None:
        die_id = self.die.currentData()
        if die_id is None:
            return
        profile_id = self._profile_map.get(int(die_id))
        if profile_id is None:
            return
        index = self.profile.findData(profile_id)
        if index >= 0:
            self.profile.setCurrentIndex(index)

    def values(self) -> dict[str, Any]:
        return {
            "die_id": int(self.die.currentData()),
            "profile_id": int(self.profile.currentData()),
            "record_date": self.record_date.date().toString("yyyy-MM-dd"),
            "problem_type": self.problem_type.currentText(),
            "description": self.description.toPlainText().strip(),
        }


class PartyProductCodeDialog(_BaseMasterDialog):
    def __init__(
        self,
        service: LocalWorkflowService,
        *,
        party_type: str,
        parent=None,
    ) -> None:
        super().__init__(parent, title="Ürün Kodu Eşlemesi")
        self.party_type = party_type.upper()
        self.party = QComboBox()
        if party_type.upper() == "CUSTOMER":
            for row in service.list_customers():
                self.party.addItem(f"{row['code']} — {row['name']}", row["id"])
        else:
            for row in service.list_suppliers():
                self.party.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.profile = QComboBox()
        self.profile.addItem("— Stok kartı profili —", None)
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.external_code = QLineEdit()
        self.external_name = QLineEdit()
        self.form.addRow("Taraf", QLabel("Müşteri" if party_type == "CUSTOMER" else "Tedarikçi"))
        self.form.addRow("Firma *", self.party)
        self.form.addRow("Profil", self.profile)
        self.form.addRow("Dış kod *", self.external_code)
        self.form.addRow("Dış ad", self.external_name)

    def values(self) -> dict[str, Any]:
        profile_id = self.profile.currentData()
        return {
            "party_type": self.party_type,
            "party_id": int(self.party.currentData()),
            "profile_id": int(profile_id) if profile_id is not None else None,
            "stock_item_id": None,
            "external_code": self.external_code.text().strip().upper(),
            "external_name": self.external_name.text().strip(),
        }


class PropertySetDialog(_BaseMasterDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Özellik Seti")
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.kind = QComboBox()
        self.kind.addItems(("YÜZEY", "RENK", "ALAŞIM", "SERTLİK", "MEKANİK"))
        self.form.addRow("Kod *", self.code)
        self.form.addRow("Ad *", self.name)
        self.form.addRow("Tür", self.kind)

    def values(self) -> dict[str, str]:
        return {
            "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(),
            "property_kind": self.kind.currentText(),
        }


class PropertyValueDialog(_BaseMasterDialog):
    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Özellik Değeri")
        self.property_set = QComboBox()
        for row in service.list_property_sets():
            self.property_set.addItem(f"{row['code']} — {row['name']}", row["id"])
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 9999)
        self.form.addRow("Özellik seti *", self.property_set)
        self.form.addRow("Kod *", self.code)
        self.form.addRow("Ad *", self.name)
        self.form.addRow("Sıra", self.sort_order)

    def values(self) -> dict[str, Any]:
        return {
            "property_set_id": int(self.property_set.currentData()),
            "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(),
            "sort_order": self.sort_order.value(),
        }


class PriceListLineDialog(_BaseMasterDialog):
    def __init__(
        self, service: LocalWorkflowService, price_list_id: int, parent=None
    ) -> None:
        super().__init__(parent, title="Fiyat Listesi Satırı")
        self.price_list_id = price_list_id
        self.profile = QComboBox()
        for row in service.list_profiles():
            self.profile.addItem(f"{row['profile_code']} — {row['profile_name']}", row["id"])
        self.surface = QLineEdit()
        self.alloy = QLineEdit("6060B")
        self.temper = QLineEdit("T5")
        self.unit_price = QDoubleSpinBox()
        self.unit_price.setDecimals(4)
        self.unit_price.setRange(0.0001, 1_000_000)
        self.currency = QComboBox()
        self.currency.addItems(("USD", "EUR", "TRY"))
        self.form.addRow("Profil *", self.profile)
        self.form.addRow("Yüzey", self.surface)
        self.form.addRow("Alaşım", self.alloy)
        self.form.addRow("Sertlik", self.temper)
        self.form.addRow("Birim fiyat *", self.unit_price)
        self.form.addRow("Döviz", self.currency)

    def values(self) -> dict[str, Any]:
        return {
            "price_list_id": self.price_list_id,
            "profile_id": int(self.profile.currentData()),
            "surface": self.surface.text().strip().upper(),
            "alloy": self.alloy.text().strip().upper(),
            "temper": self.temper.text().strip().upper(),
            "unit_price": self.unit_price.value(),
            "currency": self.currency.currentText(),
        }


class SubcontractorDialog(_BaseMasterDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Fasoncu Kartı")
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.city = QLineEdit()
        self.form.addRow("Kod *", self.code)
        self.form.addRow("Unvan *", self.name)
        self.form.addRow("Telefon", self.phone)
        self.form.addRow("Şehir", self.city)

    def values(self) -> dict[str, str]:
        return {
            "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(),
            "phone": self.phone.text().strip(),
            "city": self.city.text().strip().upper(),
        }



class ProfileCreateDialog(_BaseMasterDialog):
    """Yalnız profil kartı — rota/reçete/hammadde bu diyalogda yok."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Yeni Profil Kartı")
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.unit_weight = QDoubleSpinBox()
        self.unit_weight.setDecimals(4)
        self.unit_weight.setRange(0.0001, 1_000_000)
        self.unit_weight.setValue(1.0)
        self.alloy = QComboBox()
        self.alloy.addItems(("6060B", "6063B", "6060", "6063", "6082"))
        self.temper = QComboBox()
        self.temper.addItems(("T5", "T6", "T4", "T66"))
        hint = QLabel(
            "Üretim rotası ve reçete Üretim modülünden tanımlanır; "
            "bu ekran yalnızca profil ana kartıdır."
        )
        hint.setWordWrap(True)
        self.form.addRow(hint)
        self.form.addRow("Profil kodu *", self.code)
        self.form.addRow("Profil adı *", self.name)
        self.form.addRow("Teorik kg/m *", self.unit_weight)
        self.form.addRow("Alaşım", self.alloy)
        self.form.addRow("Sertlik", self.temper)

    def values(self) -> dict[str, Any]:
        return {
            "profile_code": self.code.text().strip().upper(),
            "profile_name": self.name.text().strip(),
            "unit_weight_kg_m": self.unit_weight.value(),
            "alloy": self.alloy.currentText(),
            "temper": self.temper.currentText(),
        }


class DieCreateDialog(_BaseMasterDialog):
    """Yalnız kalıp kartı — rota/reçete/hammadde seçilmez."""

    def __init__(self, service: LocalWorkflowService, parent=None) -> None:
        super().__init__(parent, title="Yeni Kalıp Kartı")
        self.setMinimumWidth(520)
        self.profile = QComboBox()
        for row in service.list_profiles():
            self.profile.addItem(
                f"{row['profile_code']} — {row['profile_name']}", row["id"]
            )
        self.die_code = QLineEdit()
        self.spare_no = QSpinBox()
        self.spare_no.setRange(0, 99)
        self.figure_count = QSpinBox()
        self.figure_count.setRange(1, 32)
        self.figure_count.setValue(1)
        self.life_limit = QDoubleSpinBox()
        self.life_limit.setDecimals(0)
        self.life_limit.setRange(0, 1_000_000_000)
        self.tenefer_no = QComboBox()
        self.tenefer_no.setEditable(True)
        self.tenefer_no.addItems(("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"))
        self.tenefer_no.setCurrentText("1")
        self.tenefer_type = QLineEdit("STANDART")
        self.tenefer_limit = QDoubleSpinBox()
        self.tenefer_limit.setDecimals(0)
        self.tenefer_limit.setRange(0, 1_000_000_000)
        self.tenefer_limit.setValue(2000)
        self.supplier_name = QLineEdit()
        self.press_station = QComboBox()
        self.press_station.addItems(("PRES 1", "PRES 2", "PRES 3"))
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(70)
        hint = QLabel(
            "Kalıp kartı profil, yedek no, tedarikçi ve tenefer bilgilerini tutar. "
            "Rota / reçete / hammadde seçimi Üretim Emri ekranındadır."
        )
        hint.setWordWrap(True)
        self.form.addRow(hint)
        self.form.addRow("Profil *", self.profile)
        self.form.addRow("Kalıp kodu *", self.die_code)
        self.form.addRow("Yedek no", self.spare_no)
        self.form.addRow("Figür adet *", self.figure_count)
        self.form.addRow("Ömür limiti (kg)", self.life_limit)
        self.form.addRow("Tenefer no *", self.tenefer_no)
        self.form.addRow("Tenefer cinsi", self.tenefer_type)
        self.form.addRow("Tenefer ömrü (m) *", self.tenefer_limit)
        self.form.addRow("Tedarikçi", self.supplier_name)
        self.form.addRow("Uyumlu pres", self.press_station)
        self.form.addRow("Not", self.note)
        self.tenefer_no.currentTextChanged.connect(self._apply_tenefer_standard)
        self._apply_tenefer_standard()

    def _apply_tenefer_standard(self, *_args: object) -> None:
        text = self.tenefer_no.currentText().strip()
        if not text.isdigit():
            return
        standards = {
            1: 2000, 2: 3000, 3: 4500, 4: 6000, 5: 8000,
            6: 2000, 7: 3000, 8: 4500, 9: 6000, 10: 8000,
        }
        suggested = standards.get(int(text))
        if suggested:
            self.tenefer_limit.setValue(suggested)

    def values(self) -> dict[str, Any]:
        if self.profile.currentData() is None:
            raise ValueError("Önce bir profil kartı seçin.")
        code = self.die_code.text().strip().upper()
        if not code:
            raise ValueError("Kalıp kodu zorunludur.")
        if not self.tenefer_no.currentText().strip():
            raise ValueError("Tenefer no zorunludur.")
        if self.tenefer_limit.value() <= 0:
            raise ValueError("Tenefer ömrü sıfırdan büyük olmalıdır.")
        return {
            "profile_id": int(self.profile.currentData()),
            "die_code": code,
            "spare_no": self.spare_no.value(),
            "figure_count": self.figure_count.value(),
            "life_limit_kg": self.life_limit.value(),
            "tenefer_no": self.tenefer_no.currentText().strip(),
            "tenefer_type": self.tenefer_type.text().strip(),
            "tenefer_limit_m": self.tenefer_limit.value(),
            "supplier_name": self.supplier_name.text().strip(),
            "compatible_stations": [self.press_station.currentText()],
            "note": self.note.toPlainText().strip(),
        }
