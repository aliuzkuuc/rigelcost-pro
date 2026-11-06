PRAGMA foreign_keys = ON;

-- RIGEL SIPARIS_D_DURUM karşılığı — satır bazlı üretim/sevk durumu önbelleği
CREATE TABLE IF NOT EXISTS sales_order_line_status (
    sales_order_line_id INTEGER PRIMARY KEY,
    sales_order_id INTEGER NOT NULL,
    planned_quantity REAL NOT NULL DEFAULT 0,
    planned_kg REAL NOT NULL DEFAULT 0,
    produced_quantity REAL NOT NULL DEFAULT 0,
    produced_kg REAL NOT NULL DEFAULT 0,
    pending_production_quantity REAL NOT NULL DEFAULT 0,
    pending_production_kg REAL NOT NULL DEFAULT 0,
    field_quantity REAL NOT NULL DEFAULT 0,
    field_kg REAL NOT NULL DEFAULT 0,
    ready_package_quantity REAL NOT NULL DEFAULT 0,
    ready_package_kg REAL NOT NULL DEFAULT 0,
    shipped_quantity REAL NOT NULL DEFAULT 0,
    shipped_kg REAL NOT NULL DEFAULT 0,
    pending_shipment_quantity REAL NOT NULL DEFAULT 0,
    pending_shipment_kg REAL NOT NULL DEFAULT 0,
    fulfillment_status TEXT NOT NULL DEFAULT 'ÜRETİLECEK',
    progress_pct REAL NOT NULL DEFAULT 0,
    warehouse_summary TEXT NOT NULL DEFAULT '',
    plan_summary TEXT NOT NULL DEFAULT '',
    last_shipment_date TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id) ON DELETE CASCADE,
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_order_line_status_order
ON sales_order_line_status(sales_order_id);

-- Talep sebepleri
CREATE TABLE IF NOT EXISTS request_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (organization_id, code),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Müşteri / tedarikçi ürün kodları
CREATE TABLE IF NOT EXISTS party_product_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    party_type TEXT NOT NULL,
    party_id INTEGER NOT NULL,
    stock_item_id INTEGER,
    profile_id INTEGER,
    external_code TEXT NOT NULL,
    external_name TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

-- Hizmet kartları
CREATE TABLE IF NOT EXISTS service_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'ADET',
    active INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (organization_id, code),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Özellik setleri
CREATE TABLE IF NOT EXISTS property_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    property_kind TEXT NOT NULL DEFAULT 'YÜZEY',
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE (organization_id, code),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS property_set_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_set_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (property_set_id) REFERENCES property_sets(id) ON DELETE CASCADE
);

-- Profil fiyat listeleri
CREATE TABLE IF NOT EXISTS sales_price_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    list_code TEXT NOT NULL,
    list_name TEXT NOT NULL,
    customer_id INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    valid_from TEXT,
    valid_until TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE (organization_id, list_code),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS sales_price_list_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price_list_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    surface TEXT NOT NULL DEFAULT '',
    alloy TEXT NOT NULL DEFAULT '',
    temper TEXT NOT NULL DEFAULT '',
    unit_price REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    FOREIGN KEY (price_list_id) REFERENCES sales_price_lists(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

-- Şikayetler
CREATE TABLE IF NOT EXISTS customer_complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    complaint_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    sales_order_id INTEGER,
    sales_order_line_id INTEGER,
    profile_code TEXT NOT NULL DEFAULT '',
    complaint_date TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'AÇIK',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id)
);

-- Kalıphane stub modülleri
CREATE TABLE IF NOT EXISTS die_tooling_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    request_no TEXT NOT NULL UNIQUE,
    profile_id INTEGER NOT NULL,
    supplier_id INTEGER,
    request_date TEXT NOT NULL,
    figure_no TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'BEKLİYOR',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS die_tooling_work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    work_order_no TEXT NOT NULL UNIQUE,
    die_id INTEGER,
    profile_id INTEGER NOT NULL,
    supplier_id INTEGER,
    order_type TEXT NOT NULL DEFAULT 'BAKIM',
    status TEXT NOT NULL DEFAULT 'BEKLİYOR',
    order_date TEXT NOT NULL,
    planned_end TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS die_tooling_slips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    slip_no TEXT NOT NULL UNIQUE,
    die_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    slip_date TEXT NOT NULL,
    slip_type TEXT NOT NULL DEFAULT 'BAKIM',
    used_kg REAL NOT NULL DEFAULT 0,
    location_from TEXT NOT NULL DEFAULT '',
    location_to TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

CREATE TABLE IF NOT EXISTS die_tooling_problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    problem_no TEXT NOT NULL UNIQUE,
    die_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    record_date TEXT NOT NULL,
    problem_type TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'AÇIK',
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (15, '015_order_line_status_and_master.sql');
