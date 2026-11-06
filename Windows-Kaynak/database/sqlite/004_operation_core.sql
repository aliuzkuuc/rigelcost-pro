PRAGMA foreign_keys = ON;

-- RIGEL'daki kart, rota, reçete ve sevkiyat ilişkilerini kayıpsız saklayan
-- operasyon çekirdeği. Eski basit tablolar geçiş sürecinde korunur.

CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code),
    UNIQUE (organization_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    operation_id INTEGER,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (operation_id) REFERENCES operations(id),
    UNIQUE (organization_id, code),
    UNIQUE (organization_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS die_station_compatibility (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    die_id INTEGER NOT NULL,
    station_id INTEGER,
    station_external_id TEXT NOT NULL DEFAULT '',
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (die_id) REFERENCES dies(id),
    FOREIGN KEY (station_id) REFERENCES stations(id),
    UNIQUE (die_id, station_external_id),
    UNIQUE (external_source, external_id)
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    route_id INTEGER,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    recipe_code TEXT NOT NULL,
    recipe_name TEXT NOT NULL,
    main_stock_external_id TEXT NOT NULL DEFAULT '',
    raw_material_stock_external_id TEXT NOT NULL DEFAULT '',
    production_length_mm REAL NOT NULL DEFAULT 0,
    saw_allowance_mm REAL NOT NULL DEFAULT 0,
    hanger_allowance_mm REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (route_id) REFERENCES routes(id),
    UNIQUE (organization_id, recipe_code),
    UNIQUE (organization_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS recipe_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    parent_recipe_external_id TEXT NOT NULL DEFAULT '',
    operation_external_id TEXT NOT NULL DEFAULT '',
    station_external_id TEXT NOT NULL DEFAULT '',
    process_type TEXT NOT NULL DEFAULT '',
    sequence_no INTEGER NOT NULL DEFAULT 0,
    route_sequence_no INTEGER NOT NULL DEFAULT 0,
    stock_external_id TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 0,
    unit_external_id TEXT NOT NULL DEFAULT '',
    main_unit_external_id TEXT NOT NULL DEFAULT '',
    main_quantity REAL NOT NULL DEFAULT 0,
    numerator REAL NOT NULL DEFAULT 0,
    denominator REAL NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    warehouse_external_id TEXT NOT NULL DEFAULT '',
    external_unit_weight REAL NOT NULL DEFAULT 0,
    external_kg REAL NOT NULL DEFAULT 0,
    external_quantity REAL NOT NULL DEFAULT 0,
    external_metre REAL NOT NULL DEFAULT 0,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    UNIQUE (recipe_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS route_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS route_condition_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_condition_id INTEGER NOT NULL,
    external_source TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL DEFAULT '',
    property_external_id TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '=',
    value_text TEXT NOT NULL DEFAULT '',
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (route_condition_id) REFERENCES route_conditions(id) ON DELETE CASCADE,
    UNIQUE (route_condition_id, external_source, external_id)
);

CREATE TABLE IF NOT EXISTS route_condition_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_condition_id INTEGER NOT NULL,
    route_id INTEGER,
    route_external_id TEXT NOT NULL DEFAULT '',
    sequence_no INTEGER NOT NULL DEFAULT 0,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (route_condition_id) REFERENCES route_conditions(id) ON DELETE CASCADE,
    FOREIGN KEY (route_id) REFERENCES routes(id),
    UNIQUE (route_condition_id, route_external_id)
);

CREATE TABLE IF NOT EXISTS weighing_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    weighing_list_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'SEVK HAZIR',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS weighing_list_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weighing_list_id INTEGER NOT NULL,
    package_id INTEGER NOT NULL UNIQUE,
    net_kg REAL NOT NULL,
    gross_kg REAL NOT NULL,
    FOREIGN KEY (weighing_list_id) REFERENCES weighing_lists(id),
    FOREIGN KEY (package_id) REFERENCES packages(id)
);

CREATE INDEX IF NOT EXISTS ix_recipe_lines_recipe_sequence
ON recipe_lines(recipe_id, route_sequence_no, sequence_no);

CREATE INDEX IF NOT EXISTS ix_weighing_lists_customer_status
ON weighing_lists(customer_id, status, created_at);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (4, '004_operation_core.sql');
