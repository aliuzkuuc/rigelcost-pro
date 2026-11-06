PRAGMA foreign_keys = ON;

-- Farklı çıkan boy devam iş emri zinciri
ALTER TABLE work_orders ADD COLUMN production_length_mm REAL NOT NULL DEFAULT 0;
ALTER TABLE work_orders ADD COLUMN parent_work_order_id INTEGER REFERENCES work_orders(id);
ALTER TABLE production_orders ADD COLUMN actual_length_mm REAL NOT NULL DEFAULT 0;
ALTER TABLE production_orders ADD COLUMN parent_production_order_id INTEGER REFERENCES production_orders(id);

-- Eloksal fişleri (RIGEL Eloksal Fişleri.xlsx)
CREATE TABLE IF NOT EXISTS eloksal_slips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    slip_no TEXT NOT NULL UNIQUE,
    hanger_no TEXT NOT NULL DEFAULT '',
    hanging_date TEXT,
    color_group TEXT NOT NULL DEFAULT '',
    work_order_id INTEGER,
    sales_order_line_id INTEGER,
    customer_name TEXT NOT NULL DEFAULT '',
    profile_code TEXT NOT NULL DEFAULT '',
    order_color TEXT NOT NULL DEFAULT '',
    eloksal_finished INTEGER NOT NULL DEFAULT 0,
    eloksal_finished_at TEXT,
    stripping_finished INTEGER NOT NULL DEFAULT 0,
    stripping_finished_at TEXT,
    hanging_quantity REAL NOT NULL DEFAULT 0,
    hanging_kg REAL NOT NULL DEFAULT 0,
    stripping_quantity REAL NOT NULL DEFAULT 0,
    stripping_kg REAL NOT NULL DEFAULT 0,
    scrap_quantity REAL NOT NULL DEFAULT 0,
    scrap_kg REAL NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (work_order_id) REFERENCES work_orders(id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id)
);

CREATE INDEX IF NOT EXISTS ix_eloksal_slips_hanger ON eloksal_slips(hanger_no);
CREATE INDEX IF NOT EXISTS ix_eloksal_slips_work_order ON eloksal_slips(work_order_id);

-- Duruş kayıtları (RIGEL Duruş Listesi.xlsx)
CREATE TABLE IF NOT EXISTS downtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    sub_reason TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_min REAL NOT NULL DEFAULT 0,
    operation TEXT NOT NULL DEFAULT '',
    station TEXT NOT NULL DEFAULT '',
    station_section TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'AÇIK',
    has_downtime INTEGER NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE INDEX IF NOT EXISTS ix_downtime_events_station ON downtime_events(station, started_at DESC);

-- Bakım emirleri (RIGEL Bakım Emirleri.xlsx)
CREATE TABLE IF NOT EXISTS maintenance_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    order_no TEXT NOT NULL UNIQUE,
    order_type TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'BEKLİYOR',
    operation TEXT NOT NULL DEFAULT '',
    station TEXT NOT NULL DEFAULT '',
    station_section TEXT NOT NULL DEFAULT '',
    order_date TEXT NOT NULL,
    downtime_note TEXT NOT NULL DEFAULT '',
    planned_start TEXT,
    planned_end TEXT,
    actual_start TEXT,
    actual_end TEXT,
    compliance_pct REAL NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS maintenance_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    instruction_no TEXT NOT NULL UNIQUE,
    instruction_type TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    operation TEXT NOT NULL DEFAULT '',
    station TEXT NOT NULL DEFAULT '',
    period_days INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Satın alma faturaları ve teklif karşılaştırma
CREATE TABLE IF NOT EXISTS purchase_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    invoice_no TEXT NOT NULL UNIQUE,
    goods_receipt_id INTEGER,
    purchase_order_id INTEGER,
    supplier_id INTEGER NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'TRY',
    exchange_rate REAL NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'TASLAK',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (goods_receipt_id) REFERENCES goods_receipts(id),
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    request_id INTEGER,
    supplier_id INTEGER NOT NULL,
    quote_no TEXT NOT NULL DEFAULT '',
    quote_date TEXT NOT NULL,
    delivery_date TEXT,
    unit_price REAL NOT NULL DEFAULT 0,
    quantity REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'TRY',
    selected INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (request_id) REFERENCES purchase_requests(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Satış teklifleri
CREATE TABLE IF NOT EXISTS sales_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    quote_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    quote_date TEXT NOT NULL,
    valid_until TEXT,
    currency TEXT NOT NULL DEFAULT 'EUR',
    exchange_rate REAL NOT NULL DEFAULT 1,
    total_amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'TASLAK',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (14, '014_modules.sql');
