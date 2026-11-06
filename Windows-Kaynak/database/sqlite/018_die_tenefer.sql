-- Kalıp / tenefer ERP uyumu
ALTER TABLE dies ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE dies ADD COLUMN external_company TEXT NOT NULL DEFAULT '';
ALTER TABLE dies ADD COLUMN is_external INTEGER NOT NULL DEFAULT 0;
ALTER TABLE dies ADD COLUMN supplier_name TEXT NOT NULL DEFAULT '';
ALTER TABLE dies ADD COLUMN opening_tenefer_no TEXT NOT NULL DEFAULT '';
ALTER TABLE dies ADD COLUMN opening_tenefer_used_m REAL NOT NULL DEFAULT 0;

ALTER TABLE die_movements ADD COLUMN production_entry_id INTEGER;
ALTER TABLE die_movements ADD COLUMN net_kg REAL NOT NULL DEFAULT 0;
ALTER TABLE die_movements ADD COLUMN metre REAL NOT NULL DEFAULT 0;
ALTER TABLE die_movements ADD COLUMN tenefer_no TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS tenefer_life_standards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenefer_no INTEGER NOT NULL,
    operator_no INTEGER NOT NULL DEFAULT 1,
    limit_m REAL NOT NULL,
    UNIQUE (tenefer_no, operator_no)
);

CREATE TABLE IF NOT EXISTS tenefer_life_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    profile_id INTEGER,
    die_id INTEGER,
    tenefer_no INTEGER NOT NULL,
    operator_no INTEGER NOT NULL DEFAULT 1,
    limit_m REAL NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    UNIQUE (die_id, tenefer_no, operator_no)
);

CREATE TABLE IF NOT EXISTS tenefer_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    document_no TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL,
    document_date TEXT NOT NULL,
    total_kg REAL NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS tenefer_document_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenefer_document_id INTEGER NOT NULL,
    die_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    tenefer_no TEXT NOT NULL DEFAULT '',
    tenefer_type TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL,
    FOREIGN KEY (tenefer_document_id) REFERENCES tenefer_documents(id) ON DELETE CASCADE,
    FOREIGN KEY (die_id) REFERENCES dies(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

CREATE INDEX IF NOT EXISTS ix_die_movements_production
ON die_movements(production_entry_id);

CREATE INDEX IF NOT EXISTS ix_tenefer_doc_lines_die
ON tenefer_document_lines(die_id);

-- RIGEL TENEFER_OMUR_ST — Rigel fabrika dağılımı (2000/3000 ağırlıklı)
INSERT OR IGNORE INTO tenefer_life_standards(tenefer_no, operator_no, limit_m) VALUES
    (1, 1, 2000),
    (2, 1, 3000),
    (3, 1, 4500),
    (4, 1, 6000),
    (5, 1, 8000),
    (6, 1, 2000),
    (7, 1, 3000),
    (8, 1, 4500),
    (9, 1, 6000),
    (10, 1, 8000);

-- Mevcut yanlış durum etiketlerini RIGEL ile hizala
UPDATE dies SET status = 'ARŞİVDE'
WHERE UPPER(status) IN ('AKTIF', 'AKTİF', 'ACTIVE');

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (18, '018_die_tenefer.sql');
