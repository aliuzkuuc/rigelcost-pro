PRAGMA foreign_keys = ON;

-- RIGEL birim setleri: stok kartı ve reçete satırı farklı birimlerle
-- çalıştığında tek hareket defterine doğru miktar yazılır.
CREATE TABLE IF NOT EXISTS unit_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    base_unit TEXT NOT NULL DEFAULT 'KG',
    active INTEGER NOT NULL DEFAULT 1,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS unit_set_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_set_id INTEGER NOT NULL,
    unit_code TEXT NOT NULL,
    factor REAL NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (unit_set_id) REFERENCES unit_sets(id) ON DELETE CASCADE,
    UNIQUE (unit_set_id, unit_code)
);

ALTER TABLE stock_items ADD COLUMN unit_set_id INTEGER REFERENCES unit_sets(id);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (12, '012_unit_sets.sql');
