from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.central_database import (
    DatabaseConfigStore,
    DatabaseSettings,
    SqlServerMigrator,
    select_sql_server_driver,
    sql_server_connection_string,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CentralDatabaseTests(unittest.TestCase):
    def test_driver_selection_prefers_modern_odbc(self) -> None:
        driver = select_sql_server_driver(
            ["SQL Server", "ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]
        )
        self.assertEqual(driver, "ODBC Driver 18 for SQL Server")

    def test_sql_login_connection_string_contains_expected_security_values(self) -> None:
        settings = DatabaseSettings(
            server=r"FABRIKA\RIGEL",
            database="RIGEL_COST_PRO",
            trusted_connection=False,
            username="rigel_app",
            password="Secret-123",
        )
        value = sql_server_connection_string(
            settings,
            ["ODBC Driver 18 for SQL Server"],
        )
        self.assertIn("SERVER=FABRIKA\\RIGEL", value)
        self.assertIn("DATABASE=RIGEL_COST_PRO", value)
        self.assertIn("UID=rigel_app", value)
        self.assertIn("PWD=Secret-123", value)
        self.assertIn("Encrypt=yes", value)
        self.assertNotIn("Trusted_Connection=yes", value)

    def test_config_never_writes_plain_password(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "database.json"
            store = DatabaseConfigStore(path)
            store.save(
                DatabaseSettings(
                    server="192.168.1.10",
                    trusted_connection=False,
                    username="rigel_app",
                    password="VerySecret",
                ),
                remember_password=False,
            )
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            self.assertNotIn("VerySecret", raw)
            self.assertNotIn("password", payload)
            self.assertEqual(payload["password_protected"], "")
            loaded = store.load()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.username, "rigel_app")
            self.assertEqual(loaded.password, "")

    def test_initial_schema_contains_connected_factory_workflow(self) -> None:
        schema = (
            PROJECT_ROOT / "database" / "sqlserver" / "001_core.sql"
        ).read_text(encoding="utf-8")
        for table in (
            "customers",
            "profiles",
            "dies",
            "stock_items",
            "sales_orders",
            "sales_order_lines",
            "routes",
            "route_steps",
            "production_orders",
            "work_orders",
            "production_entries",
            "stock_movements",
            "packages",
            "shipments",
            "attachments",
            "audit_log",
        ):
            self.assertIn(f"CREATE TABLE dbo.{table}", schema)
        self.assertIn("row_version rowversion", schema)

    def test_migration_batch_splitter_understands_go(self) -> None:
        batches = SqlServerMigrator.split_batches(
            "CREATE TABLE dbo.a(id int);\nGO\nINSERT INTO dbo.a VALUES (1);\nGO\n"
        )
        self.assertEqual(len(batches), 2)
        self.assertTrue(batches[0].startswith("CREATE TABLE"))
        self.assertTrue(batches[1].startswith("INSERT INTO"))


if __name__ == "__main__":
    unittest.main()
