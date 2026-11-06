PRAGMA foreign_keys = ON;

-- Pres üretim fişini basılı çıktıyla aynı ayrıntıda saklar: fiş başlığındaki
-- kalite/kalıp alanları, şarj bazlı billet boyları, sepet dökümü ve hurda
-- kırılımı. Fiş yeniden basıldığında aynı belge birebir üretilebilir.
ALTER TABLE production_entries ADD COLUMN slip_no TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN qc_username TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN test_result TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN die_problem TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN die_problem_note TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN spare_no INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN figure_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN tenefer_no TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN raw_material_stock TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN remaining_quantity REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN fire_pct REAL NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS ux_production_entries_slip_no
ON production_entries(slip_no) WHERE slip_no <> '';

-- Bir fişte birden çok billet boyu presleneceği için şarj satırları ayrı durur.
CREATE TABLE IF NOT EXISTS production_entry_billets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_entry_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL DEFAULT 1,
    billet_length_mm REAL NOT NULL DEFAULT 0,
    billet_count REAL NOT NULL DEFAULT 0,
    length_count REAL NOT NULL DEFAULT 0,
    total_length_count REAL NOT NULL DEFAULT 0,
    gross_kg REAL NOT NULL DEFAULT 0,
    raw_material_stock TEXT NOT NULL DEFAULT '',
    lot_no TEXT NOT NULL DEFAULT '',
    dummy_length_mm REAL NOT NULL DEFAULT 0,
    press_speed_m_s REAL NOT NULL DEFAULT 0,
    container_temp_c REAL NOT NULL DEFAULT 0,
    die_temp_c REAL NOT NULL DEFAULT 0,
    billet_temp_c REAL NOT NULL DEFAULT 0,
    exit_temp_c REAL NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (production_entry_id) REFERENCES production_entries(id) ON DELETE CASCADE
);

-- Presten çıkan mamul sepet sepet sayıldığı için net adet dökümü satırlanır.
CREATE TABLE IF NOT EXISTS production_entry_baskets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_entry_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL DEFAULT 1,
    basket_no TEXT NOT NULL DEFAULT '',
    length_mm REAL NOT NULL DEFAULT 0,
    quantity REAL NOT NULL DEFAULT 0,
    net_kg REAL NOT NULL DEFAULT 0,
    work_order_no TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (production_entry_id) REFERENCES production_entries(id) ON DELETE CASCADE
);

-- Fire; ara iş ve hurda gibi sebeplere ayrıldığı için kırılım saklanır.
CREATE TABLE IF NOT EXISTS production_entry_scraps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_entry_id INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL DEFAULT 1,
    scrap_reason TEXT NOT NULL DEFAULT 'HURDA',
    quantity REAL NOT NULL DEFAULT 0,
    kg REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (production_entry_id) REFERENCES production_entries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_production_entry_billets_entry
ON production_entry_billets(production_entry_id, sequence_no);

CREATE INDEX IF NOT EXISTS ix_production_entry_baskets_entry
ON production_entry_baskets(production_entry_id, sequence_no);

CREATE INDEX IF NOT EXISTS ix_production_entry_scraps_entry
ON production_entry_scraps(production_entry_id, sequence_no);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (20, '020_press_production_slip.sql');
