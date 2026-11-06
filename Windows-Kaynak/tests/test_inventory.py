from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.inventory import InventoryService


class InventoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "inventory.db"
        self.service = InventoryService(self.database)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_stock_card_and_movements_persist(self) -> None:
        item_id = self.service.add_item(
            "BLT-6063-7",
            "6063 Billet 7 inç",
            "Billet",
            "kg",
            min_quantity=150,
            opening_quantity=100,
            opening_unit_cost=10,
        )
        entry = self.service.record_movement(
            item_id,
            "GİRİŞ",
            100,
            unit_cost=20,
            document_no="IRS-001",
        )
        self.assertAlmostEqual(entry["balance_after"], 200)
        self.assertAlmostEqual(entry["average_cost"], 15)

        output = self.service.record_movement(item_id, "ÇIKIŞ", 50)
        self.assertAlmostEqual(output["balance_after"], 150)
        count = self.service.record_movement(item_id, "SAYIM", 120)
        self.assertAlmostEqual(count["quantity_delta"], -30)

        reloaded = InventoryService(self.database)
        item = reloaded.list_items()[0]
        self.assertAlmostEqual(item["current_quantity"], 120)
        self.assertAlmostEqual(item["average_cost"], 15)
        self.assertAlmostEqual(item["stock_value"], 1_800)
        self.assertEqual(item["is_low"], 1)
        self.assertEqual(len(reloaded.list_movements(item_id=item_id)), 4)

    def test_output_cannot_exceed_available_stock(self) -> None:
        item_id = self.service.add_item(
            "PRF-001",
            "Deneme profil",
            "Profil / Mamul",
            "kg",
            opening_quantity=25,
        )
        with self.assertRaisesRegex(ValueError, "mevcut stoktan fazla"):
            self.service.record_movement(item_id, "ÇIKIŞ", 30)
        self.assertAlmostEqual(
            self.service.list_items()[0]["current_quantity"],
            25,
        )

    def test_duplicate_code_and_search(self) -> None:
        self.service.add_item(
            "AMB-001",
            "Streç Film",
            "Ambalaj",
            "adet",
        )
        with self.assertRaisesRegex(ValueError, "zaten"):
            self.service.add_item(
                "amb-001",
                "Tekrar",
                "Ambalaj",
                "adet",
            )
        self.assertEqual(
            len(self.service.list_items(search="streç")),
            1,
        )
        self.assertEqual(
            len(self.service.list_items(category="Billet")),
            0,
        )

    def test_summary_reports_low_stock_and_kg_total(self) -> None:
        self.service.add_item(
            "BLT-1",
            "Billet",
            "Billet",
            "kg",
            min_quantity=500,
            opening_quantity=400,
            opening_unit_cost=100,
        )
        self.service.add_item(
            "AMB-1",
            "Köşebent",
            "Ambalaj",
            "adet",
            opening_quantity=1_000,
            opening_unit_cost=5,
        )
        summary = self.service.summary()
        self.assertEqual(summary["item_count"], 2)
        self.assertEqual(summary["low_count"], 1)
        self.assertEqual(summary["kg_stock"], 400)
        self.assertEqual(summary["stock_value"], 45_000)


if __name__ == "__main__":
    unittest.main()
