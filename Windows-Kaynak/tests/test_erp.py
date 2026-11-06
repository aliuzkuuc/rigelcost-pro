from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models.erp_definitions import MODULE_SPECS, get_module_spec
from services.erp import ErpService


class ErpServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "erp.db"
        self.service = ErpService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_all_module_table_columns_are_defined(self) -> None:
        self.assertGreaterEqual(len(MODULE_SPECS), 80)
        for spec in MODULE_SPECS:
            with self.subTest(department=spec.department, module=spec.name):
                self.assertFalse(
                    set(spec.table_keys).difference(spec.field_map),
                    "Tabloda tanımsız alan var",
                )

    def test_press_calculations_match_extrusion_formulas(self) -> None:
        spec = get_module_spec("Üretim", "Pres Üretim Fişleri")
        result = self.service.calculate_data(
            spec,
            {
                "order_ref": "SIP-1",
                "work_order_ref": "ISE-1",
                "profile_code": "P-1",
                "gross_kg": 2_352.94,
                "net_kg": 2_000,
                "metre": 1_000,
                "duration_min": 120,
                "theoretical_weight": 2.0,
                "real_weight": 2.05,
                "figure": 2,
            },
        )

        self.assertAlmostEqual(result["fire_kg"], 352.94, places=2)
        self.assertAlmostEqual(result["fire_pct"], 15.0, places=2)
        self.assertAlmostEqual(result["kg_hour"], 1_000.0, places=2)
        self.assertAlmostEqual(result["theoretical_net_kg"], 2_000.0)
        self.assertAlmostEqual(result["weight_diff_pct"], 2.5)
        self.assertAlmostEqual(result["tenefer_m"], 2_000.0)

    def test_die_life_and_maintenance_status_are_automatic(self) -> None:
        spec = get_module_spec("Kalıphane", "Kalıp Kartları")
        result = self.service.calculate_data(
            spec,
            {
                "die_code": "KLP-01",
                "profile_code": "PRF-01",
                "life_limit_kg": 100_000,
                "used_kg": 100_500,
                "status": "AKTİF",
            },
        )

        self.assertEqual(result["remaining_kg"], 0)
        self.assertAlmostEqual(result["usage_pct"], 100.5)
        self.assertEqual(result["status"], "BAKIMDA")

    def test_press_kg_hour_excludes_die_setup_minutes(self) -> None:
        spec = get_module_spec("Üretim", "Pres Üretim Fişleri")
        result = self.service.calculate_data(
            spec,
            {
                "order_ref": "SIP-2",
                "work_order_ref": "ISE-2",
                "profile_code": "P-2",
                "net_kg": 2_000,
                "duration_min": 120,
                "die_setup_min": 20,
            },
        )
        self.assertAlmostEqual(result["kg_hour"], 1_200.0, places=2)

    def test_sales_order_creates_linked_production_approval(self) -> None:
        source_id = self.service.create_record(
            "Satış",
            "Satış Siparişleri",
            {
                "company": "RİGEL ALÜMİNYUM A.Ş.",
                "stock_name": "Ekstrüzyon Profil",
                "profile_code": "PRF-1001",
                "kg": 12_500,
                "quantity": 2_000,
                "unit_price": 4.1,
                "status": "ONAYLANDI",
                "production_approval": "KABUL",
            },
        )
        target_id = self.service.create_linked_record(source_id)
        target = self.service.get_record(target_id)

        self.assertIsNotNone(target)
        self.assertEqual(target["department"], "Üretim")
        self.assertEqual(target["module"], "Üretim Onayı Bekleyen Siparişler")
        self.assertEqual(target["parent_id"], source_id)
        self.assertEqual(target["data"]["company"], "RİGEL ALÜMİNYUM A.Ş.")
        self.assertEqual(target["data"]["kg"], 12_500)

    def test_records_are_searchable_and_persist_in_separate_database(self) -> None:
        record_id = self.service.create_record(
            "Satış",
            "Müşteriler",
            {
                "code": "MUS-01",
                "name": "Akseki Yapı",
                "contact": "Satın Alma",
                "active": True,
            },
        )
        reopened = ErpService(self.database_path)
        records = reopened.list_records("Satış", "Müşteriler", search="akseki")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], record_id)
        self.assertEqual(records[0]["data"]["name"], "Akseki Yapı")
        self.assertEqual(self.database_path.name, "erp.db")

    def test_maintenance_duration_and_compliance_are_calculated(self) -> None:
        spec = get_module_spec("Bakım", "Bakım Emirleri")
        result = self.service.calculate_data(
            spec,
            {
                "name": "Pres haftalık bakım",
                "planned_start": "2026-08-03T08:00:00",
                "planned_end": "2026-08-03T10:00:00",
                "actual_start": "2026-08-03T08:00:00",
                "actual_end": "2026-08-03T10:30:00",
                "status": "İŞLEME ALINDI",
            },
        )

        self.assertEqual(result["downtime_min"], 150)
        self.assertAlmostEqual(result["compliance_pct"], 75)
        self.assertEqual(result["status"], "TAMAMLANDI")


if __name__ == "__main__":
    unittest.main()
