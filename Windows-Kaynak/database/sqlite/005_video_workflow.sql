PRAGMA foreign_keys = ON;

-- 1.1-1.11 RIGEL eğitim videolarında görülen pres, termik, kalıp,
-- çeki listesi ve irsaliye ayrıntıları. Kolonlar mevcut yerel kayıtları
-- bozmadan eklenir; uygulama henüz girilmeyen alanları boş kabul eder.

ALTER TABLE production_entries ADD COLUMN production_type TEXT NOT NULL DEFAULT 'PLANLI ÜRETİM';
ALTER TABLE production_entries ADD COLUMN press_status TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN saw_status TEXT NOT NULL DEFAULT '';
ALTER TABLE production_entries ADD COLUMN real_weight_kg_m REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN theoretical_weight_kg_m REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN billet_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN billet_length_mm REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN basket_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN result_length_mm REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN preparation_min REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN duration_min REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN missing_quantity REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN missing_reason TEXT NOT NULL DEFAULT '';

ALTER TABLE shipments ADD COLUMN weighing_list_id INTEGER REFERENCES weighing_lists(id);
ALTER TABLE shipments ADD COLUMN dispatch_note_no TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS die_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    die_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'ADET',
    location_from TEXT NOT NULL DEFAULT '',
    location_to TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    movement_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (die_id) REFERENCES dies(id)
);

CREATE TABLE IF NOT EXISTS sales_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    shipment_id INTEGER NOT NULL UNIQUE,
    invoice_no TEXT NOT NULL UNIQUE,
    invoice_date TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    exchange_rate REAL NOT NULL DEFAULT 1,
    lme_usd_ton REAL NOT NULL DEFAULT 0,
    premium_usd_ton REAL NOT NULL DEFAULT 0,
    pricing_mode TEXT NOT NULL DEFAULT 'BİRİM FİYAT',
    total_amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'TASLAK',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (shipment_id) REFERENCES shipments(id)
);

CREATE INDEX IF NOT EXISTS ix_die_movements_die_date
ON die_movements(die_id, movement_at DESC);

CREATE INDEX IF NOT EXISTS ix_production_entries_work_date
ON production_entries(work_order_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ix_shipments_weighing_list
ON shipments(weighing_list_id)
WHERE weighing_list_id IS NOT NULL;

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (5, '005_video_workflow.sql');
