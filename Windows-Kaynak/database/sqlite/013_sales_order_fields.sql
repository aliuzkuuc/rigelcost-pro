PRAGMA foreign_keys = ON;

-- RIGEL satış siparişi başlık alanları: ödeme, kur/LME, şube/ambar.
ALTER TABLE sales_orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT '';
ALTER TABLE sales_orders ADD COLUMN maturity_days INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN contact_name TEXT NOT NULL DEFAULT '';
ALTER TABLE sales_orders ADD COLUMN usd_rate REAL NOT NULL DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN eur_rate REAL NOT NULL DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN lme_usd_ton REAL NOT NULL DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN premium_usd_ton REAL NOT NULL DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN branch_id INTEGER REFERENCES branches(id);
ALTER TABLE sales_orders ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (13, '013_sales_order_fields.sql');
