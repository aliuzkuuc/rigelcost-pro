PRAGMA foreign_keys = OFF;

-- RIGEL'da bir sipariş satırı birden fazla üretim emrine bölünebilir.
-- İlk yerel şemadaki UNIQUE kısıtı bunu engelliyordu; mevcut kayıtlar
-- korunarak üretim emri tablosu çoklu parti planlamasına açılır.
CREATE TABLE production_orders_v8 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    sales_order_line_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    recipe_id INTEGER,
    batch_no INTEGER NOT NULL DEFAULT 1,
    production_order_no TEXT NOT NULL UNIQUE,
    planned_quantity REAL NOT NULL,
    planned_kg REAL NOT NULL,
    produced_quantity REAL NOT NULL DEFAULT 0,
    produced_kg REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PLANLANDI',
    planned_start TEXT,
    planned_end TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id),
    FOREIGN KEY (route_id) REFERENCES routes(id),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id)
);

INSERT INTO production_orders_v8(
    id, organization_id, sales_order_line_id, route_id, production_order_no,
    planned_quantity, planned_kg, produced_quantity, produced_kg, status,
    planned_start, planned_end, created_by, created_at, row_version
)
SELECT id, organization_id, sales_order_line_id, route_id, production_order_no,
       planned_quantity, planned_kg, produced_quantity, produced_kg, status,
       planned_start, planned_end, created_by, created_at, row_version
FROM production_orders;

DROP TABLE production_orders;
ALTER TABLE production_orders_v8 RENAME TO production_orders;

CREATE INDEX ix_production_orders_line_status
ON production_orders(sales_order_line_id, status, batch_no);

ALTER TABLE work_orders ADD COLUMN recipe_line_id INTEGER REFERENCES recipe_lines(id);
ALTER TABLE work_orders ADD COLUMN planned_metre REAL NOT NULL DEFAULT 0;
ALTER TABLE work_orders ADD COLUMN quantity_factor REAL NOT NULL DEFAULT 1;

-- Yerel oluşturulan reçete satırlarında da RIGEL'daki operasyon/istasyon,
-- birim ve stok kimliği okunabilir biçimde saklanır. Dış kimlikler korunur.
ALTER TABLE recipe_lines ADD COLUMN operation_name TEXT NOT NULL DEFAULT '';
ALTER TABLE recipe_lines ADD COLUMN station_name TEXT NOT NULL DEFAULT '';
ALTER TABLE recipe_lines ADD COLUMN stock_code TEXT NOT NULL DEFAULT '';
ALTER TABLE recipe_lines ADD COLUMN unit_code TEXT NOT NULL DEFAULT '';
ALTER TABLE recipe_lines ADD COLUMN warehouse_code TEXT NOT NULL DEFAULT '';

-- Sipariş başlığında seçilen sevk adresi ayrı kart olarak bağlı kalır.
ALTER TABLE sales_orders ADD COLUMN delivery_address_id INTEGER REFERENCES customer_addresses(id);

PRAGMA foreign_keys = ON;

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (8, '008_production_planning.sql');
