from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class WorkflowSidePanel(QFrame):
    """Sağ panel — seçili kayıt özeti (Sipariş Bilgileri / Profil Kartı)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workflowSidePanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel("KAYIT BİLGİSİ")
        self.title.setObjectName("workflowSideTitle")
        self.body = QLabel("Listeden bir satır seçin.")
        self.body.setWordWrap(True)
        self.body.setObjectName("workflowSideBody")
        layout.addWidget(self.title)
        layout.addWidget(self.body, 1)

    def show_record(self, *, title: str, record: dict[str, Any] | None) -> None:
        self.title.setText(title.upper())
        if record is None:
            self.body.setText("Listeden bir satır seçin.")
            return
        lines = [
            f"<b>{title}</b>",
            "",
        ]
        for key, label in (
            ("order_no", "Fiş No"),
            ("customer_name", "Firma"),
            ("profile_code", "Profil"),
            ("production_length_mm", "Boy (mm)"),
            ("surface", "Yüzey"),
            ("alloy", "Alaşım"),
            ("temper", "Sertlik"),
            ("fulfillment_status", "Karşılanma"),
            ("ordered_quantity", "Sipariş Adet"),
            ("ordered_kg", "Sipariş kg"),
            ("production_kg", "Üretim kg"),
            ("shipped_kg", "Sevk kg"),
            ("pending_production_kg", "Üretim Bekleyen kg"),
            ("field_kg", "Sahadaki kg"),
            ("ready_shipment_kg", "Sevk Bekleyen kg"),
            ("warehouses", "Ambarlar"),
            ("plans", "Planlar"),
            ("die_code", "Kalıp"),
            ("work_order_no", "İş Emri"),
            ("operation", "Operasyon"),
            ("station", "İstasyon"),
            ("status", "Durum"),
        ):
            if key in record and str(record.get(key) or "").strip():
                value = record[key]
                if isinstance(value, float):
                    if key.endswith("_kg"):
                        text = f"{value:,.3f}"
                    else:
                        text = f"{value:,.0f}"
                else:
                    text = str(value)
                lines.append(f"<span style='color:#667085'>{label}:</span> {text}")
        self.body.setText("<br>".join(lines))
