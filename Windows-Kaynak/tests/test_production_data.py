from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from services.production_data import DEFAULT_PRESS_NAME, ProductionDataStore


class ProductionDataTests(unittest.TestCase):
    def test_excel_import_reads_turkish_months_and_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "2026_ÜRETİM_RİGEL.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "2026_ÜRETİM_RİGEL"
            sheet.append(["Tarih", "AYLIK ÜRETİM/KİLOGRAM"])
            sheet.append(["OCAK", 79_249.20])
            sheet.append(["ŞUBAT", 175_742.57])
            sheet.append(["MART", 137_346.96])
            sheet.append(["NİSAN", 81_633.41])
            workbook.save(source)

            result = ProductionDataStore.import_excel(source)

            self.assertEqual(result["year"], 2026)
            self.assertEqual(result["press_name"], DEFAULT_PRESS_NAME)
            self.assertAlmostEqual(result["monthly_kg"][0], 79_249.20)
            self.assertAlmostEqual(result["monthly_kg"][1], 175_742.57)
            self.assertAlmostEqual(result["monthly_kg"][3], 81_633.41)
            self.assertEqual(result["monthly_kg"][11], 0)

    def test_manual_months_are_saved_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("RIGELCOST_DATA_DIR")
            os.environ["RIGELCOST_DATA_DIR"] = directory
            try:
                store = ProductionDataStore()
                saved = store.save(
                    {
                        "year": 2026,
                        "press_name": DEFAULT_PRESS_NAME,
                        "monthly_kg": [100_000, 125_000] + [0] * 10,
                    }
                )
                loaded = store.load()
            finally:
                if previous is None:
                    os.environ.pop("RIGELCOST_DATA_DIR", None)
                else:
                    os.environ["RIGELCOST_DATA_DIR"] = previous

            self.assertEqual(saved, loaded)
            self.assertEqual(loaded["monthly_kg"][:2], [100_000, 125_000])


if __name__ == "__main__":
    unittest.main()
