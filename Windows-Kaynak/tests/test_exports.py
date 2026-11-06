from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from models.calculator import CostCalculator
from reports.exporters import (
    INPUT_FIELDS,
    REPORT_AUTHOR,
    _summary_rows,
    export_excel,
    export_pdf,
)
from reports.grid_exporter import export_grid_excel, export_grid_pdf


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        inputs = {
            "uretim": 200_000,
            "lme": 3_192,
            "prim": 625,
            "usd": 42,
            "elektrik_fiyat": 2.97,
            "gaz_fiyat": 18.90,
            "iscilik": 1_000_000,
            "sgk": 250_000,
            "yemek": 120_000,
            "ambalaj": 80_000,
            "genel_gider": 150_000,
            "su_m3_ton": 0.5,
            "su_birim_fiyat": 106.31,
            "mazot": 50_000,
            "kira": 100_000,
            "nakliye": 90_000,
            "kalip": 40_000,
            "bakim": 60_000,
            "amortisman": 200_000,
            "sarf": 75_000,
            "tenefer": 25_000,
            "diger": 10_000,
        }
        self.report_data = {
            "inputs": inputs,
            "results": CostCalculator().hesapla(**inputs),
        }

    def test_excel_report_can_be_opened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_excel(
                self.report_data, Path(directory) / "rigel-test.xlsx"
            )
            workbook = load_workbook(path, data_only=True)
            self.assertEqual(
                workbook["Maliyet Özeti"]["A1"].value,
                "RIGEL COST PRO — FABRİKA MALİYET RAPORU",
            )
            self.assertIn("Girdiler", workbook.sheetnames)
            labels = [
                workbook["Maliyet Özeti"].cell(row=row, column=1).value
                for row in range(1, 40)
            ]
            self.assertIn(
                "FABRİKA MALİYETİ TOPLAMI",
                labels,
            )
            self.assertNotIn("TOPLAM PROFİL MALİYETİ", labels)
            self.assertFalse(
                any(
                    "15 KALEM" in str(label).upper()
                    for label in labels
                    if label
                )
            )
            self.assertIn(
                REPORT_AUTHOR,
                workbook["Maliyet Özeti"]["A2"].value,
            )
            self.assertIn(
                REPORT_AUTHOR,
                workbook["Girdiler"]["A2"].value,
            )
            self.assertEqual(len(workbook["Maliyet Özeti"]._images), 1)
            self.assertEqual(len(workbook["Girdiler"]._images), 1)

    def test_report_labels_do_not_show_internal_section_wording(self) -> None:
        input_labels = [label for _, label, _ in INPUT_FIELDS]
        summary_labels = [
            label for label, _ in _summary_rows(self.report_data)
        ]

        for label in input_labels + summary_labels:
            normalized = label.casefold()
            self.assertNotIn("alt sekme", normalized)
            self.assertNotIn("15 kalem", normalized)

    def test_pdf_report_has_valid_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_pdf(
                self.report_data, Path(directory) / "rigel-test.pdf"
            )
            self.assertGreater(path.stat().st_size, 5_000)
            self.assertEqual(path.read_bytes()[:4], b"%PDF")
            self.assertIn(b"/Subtype /Image", path.read_bytes())

    def test_grid_list_exports_create_valid_files(self) -> None:
        headers = ["FİŞ NO", "FİRMA", "TARİH"]
        rows = [["S-001", "RIGEL AŞ", "05.08.2026"]]
        with tempfile.TemporaryDirectory() as directory:
            xlsx = export_grid_excel(
                headers=headers,
                rows=rows,
                destination=Path(directory) / "liste.xlsx",
                title="Satış Siparişleri",
            )
            pdf = export_grid_pdf(
                headers=headers,
                rows=rows,
                destination=Path(directory) / "liste.pdf",
                title="Satış Siparişleri",
            )
            workbook = load_workbook(xlsx, data_only=True)
            self.assertIn("SATI", str(workbook.active["A1"].value).upper())
            self.assertGreater(pdf.stat().st_size, 1_000)
            self.assertEqual(pdf.read_bytes()[:4], b"%PDF")

    def test_shipment_document_html_contains_header(self) -> None:
        from reports.shipment_documents import (
            package_label_html,
            shipment_dispatch_html,
            weighing_list_html,
            work_order_slip_html,
        )

        header = {"weighing_list_no": "CL260001", "customer_name": "RIGEL", "created_at": "2026-08-05", "created_by": "op", "status": "SEVK HAZIR"}
        html_doc = weighing_list_html(header, [{"package_no": "PK-1", "order_no": "R-1", "profile_code": "P100", "quantity": 10, "net_kg": 100, "gross_kg": 102, "lot_no": "L1"}])
        self.assertIn("ÇEKİ LİSTESİ", html_doc)
        self.assertIn("CL260001", html_doc)

        ship_html = shipment_dispatch_html(
            {"shipment_no": "SV-1", "customer_name": "RIGEL", "shipment_date": "2026-08-05", "vehicle_plate": "35 ABC 123"},
            [{"package_no": "PK-1", "order_no": "R-1", "profile_code": "P100", "quantity": 10, "net_kg": 100, "gross_kg": 102}],
        )
        self.assertIn("SEVK İRSALİYESİ", ship_html)

        label_html = package_label_html({"package_no": "PK-1", "customer_name": "RIGEL", "net_kg": 100, "gross_kg": 102, "warehouse_name": "SEVK ÖN", "packed_at": "2026-08-05"}, [])
        self.assertIn("PK-1", label_html)

        wo_html = work_order_slip_html({"work_order_no": "IE-1", "operation": "PRES ÜRETİM", "station": "PRES 1", "order_no": "R-1"})
        self.assertIn("İŞ EMRİ", wo_html)


if __name__ == "__main__":
    unittest.main()
