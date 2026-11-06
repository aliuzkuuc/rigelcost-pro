PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS local_schema_versions (
    version_no INTEGER PRIMARY KEY,
    migration_name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS local_sequences (
    prefix TEXT PRIMARY KEY,
    last_value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    tax_office TEXT NOT NULL DEFAULT '',
    tax_number TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT 'TÜRKİYE',
    sales_representative TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'TRY',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    supplier_type TEXT NOT NULL DEFAULT 'TEDARİKÇİ',
    active INTEGER NOT NULL DEFAULT 1,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    customer_id INTEGER,
    profile_code TEXT NOT NULL,
    profile_name TEXT NOT NULL,
    profile_group TEXT NOT NULL DEFAULT '',
    unit_weight_kg_m REAL NOT NULL DEFAULT 0,
    perimeter_mm REAL NOT NULL DEFAULT 0,
    area_mm2 REAL NOT NULL DEFAULT 0,
    alloy TEXT NOT NULL DEFAULT '6060B',
    temper TEXT NOT NULL DEFAULT 'T5',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    UNIQUE (organization_id, profile_code)
);

CREATE TABLE IF NOT EXISTS dies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    supplier_id INTEGER,
    die_code TEXT NOT NULL,
    spare_no INTEGER NOT NULL DEFAULT 0,
    figure_count INTEGER NOT NULL DEFAULT 1,
    life_limit_kg REAL NOT NULL DEFAULT 0,
    used_kg REAL NOT NULL DEFAULT 0,
    tenefer_limit_m REAL NOT NULL DEFAULT 0,
    tenefer_used_m REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'AKTİF',
    location TEXT NOT NULL DEFAULT 'KALIPHANE',
    note TEXT NOT NULL DEFAULT '',
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    UNIQUE (organization_id, die_code, spare_no)
);

CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    warehouse_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS stock_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    profile_id INTEGER,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    stock_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    tracks_lot INTEGER NOT NULL DEFAULT 0,
    minimum_quantity REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    order_no TEXT NOT NULL,
    revision_no INTEGER NOT NULL DEFAULT 0,
    customer_document_no TEXT NOT NULL DEFAULT '',
    msp TEXT NOT NULL DEFAULT '',
    order_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    status TEXT NOT NULL DEFAULT 'ONAY BEKLİYOR',
    production_approval TEXT NOT NULL DEFAULT 'BEKLİYOR',
    representative TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    UNIQUE (organization_id, order_no, revision_no)
);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_order_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    die_id INTEGER,
    stock_length_mm INTEGER NOT NULL,
    production_length_mm INTEGER NOT NULL,
    surface TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '*',
    alloy TEXT NOT NULL,
    temper TEXT NOT NULL,
    mechanical TEXT NOT NULL DEFAULT '',
    ordered_quantity REAL NOT NULL DEFAULT 0,
    ordered_kg REAL NOT NULL DEFAULT 0,
    produced_quantity REAL NOT NULL DEFAULT 0,
    produced_kg REAL NOT NULL DEFAULT 0,
    shipped_quantity REAL NOT NULL DEFAULT 0,
    shipped_kg REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'AÇIK',
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    UNIQUE (sales_order_id, line_no)
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS route_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL,
    operation TEXT NOT NULL,
    default_station TEXT NOT NULL,
    input_warehouse_id INTEGER,
    output_warehouse_id INTEGER,
    FOREIGN KEY (route_id) REFERENCES routes(id),
    FOREIGN KEY (input_warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (output_warehouse_id) REFERENCES warehouses(id),
    UNIQUE (route_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS production_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    sales_order_line_id INTEGER NOT NULL UNIQUE,
    route_id INTEGER NOT NULL,
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
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL,
    route_step_id INTEGER NOT NULL,
    work_order_no TEXT NOT NULL UNIQUE,
    sequence_no INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    operation TEXT NOT NULL,
    station TEXT NOT NULL,
    planned_quantity REAL NOT NULL,
    planned_kg REAL NOT NULL,
    produced_quantity REAL NOT NULL DEFAULT 0,
    produced_kg REAL NOT NULL DEFAULT 0,
    scrap_kg REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'BEKLİYOR',
    actual_start TEXT,
    actual_end TEXT,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (production_order_id) REFERENCES production_orders(id),
    FOREIGN KEY (route_step_id) REFERENCES route_steps(id),
    UNIQUE (production_order_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS production_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id INTEGER NOT NULL,
    entry_type TEXT NOT NULL,
    operator_username TEXT NOT NULL,
    shift TEXT NOT NULL DEFAULT '',
    die_id INTEGER,
    lot_no TEXT NOT NULL DEFAULT '',
    gross_kg REAL NOT NULL DEFAULT 0,
    net_kg REAL NOT NULL DEFAULT 0,
    scrap_kg REAL NOT NULL DEFAULT 0,
    quantity REAL NOT NULL DEFAULT 0,
    metre REAL NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_order_id) REFERENCES work_orders(id),
    FOREIGN KEY (die_id) REFERENCES dies(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    stock_item_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    direction INTEGER NOT NULL CHECK (direction IN (-1, 1)),
    quantity REAL NOT NULL,
    lot_no TEXT NOT NULL DEFAULT '',
    sales_order_line_id INTEGER,
    work_order_id INTEGER,
    document_no TEXT NOT NULL DEFAULT '',
    movement_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id),
    FOREIGN KEY (work_order_id) REFERENCES work_orders(id)
);

CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    package_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    net_kg REAL NOT NULL DEFAULT 0,
    gross_kg REAL NOT NULL DEFAULT 0,
    package_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'HAZIR',
    packed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    packed_by TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS package_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL,
    sales_order_line_id INTEGER NOT NULL,
    stock_item_id INTEGER NOT NULL,
    lot_no TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL,
    net_kg REAL NOT NULL,
    gross_kg REAL NOT NULL,
    FOREIGN KEY (package_id) REFERENCES packages(id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id)
);

CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    shipment_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    shipment_date TEXT NOT NULL,
    vehicle_plate TEXT NOT NULL DEFAULT '',
    container_no TEXT NOT NULL DEFAULT '',
    delivery_address TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'SEVK EDİLDİ',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS shipment_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL,
    package_id INTEGER NOT NULL UNIQUE,
    net_kg REAL NOT NULL,
    gross_kg REAL NOT NULL,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id),
    FOREIGN KEY (package_id) REFERENCES packages(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    record_key TEXT NOT NULL DEFAULT '',
    before_json TEXT,
    after_json TEXT,
    machine_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE INDEX IF NOT EXISTS ix_sales_orders_status_delivery
ON sales_orders(organization_id, status, delivery_date);
CREATE INDEX IF NOT EXISTS ix_work_orders_station_status
ON work_orders(station, status, priority, sequence_no);
CREATE INDEX IF NOT EXISTS ix_stock_movements_balance
ON stock_movements(organization_id, stock_item_id, warehouse_id, movement_at);
CREATE INDEX IF NOT EXISTS ix_packages_status
ON packages(organization_id, status, packed_at);
CREATE INDEX IF NOT EXISTS ix_audit_entity
ON audit_log(organization_id, entity_type, entity_id, created_at DESC);

INSERT OR IGNORE INTO local_schema_versions(version_no, migration_name)
VALUES (1, '001_core.sql');
