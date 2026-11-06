CREATE TABLE IF NOT EXISTS stock_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    document_no TEXT NOT NULL UNIQUE,
    document_type TEXT NOT NULL,
    document_date TEXT NOT NULL,
    source_warehouse_id INTEGER,
    target_warehouse_id INTEGER,
    reference_no TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (source_warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (target_warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS stock_document_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_document_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    stock_item_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    lot_no TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (stock_document_id) REFERENCES stock_documents(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id),
    UNIQUE (stock_document_id, line_no)
);

CREATE INDEX IF NOT EXISTS ix_stock_documents_date
ON stock_documents(organization_id, document_date, document_type);

INSERT OR IGNORE INTO local_schema_versions(version_no, migration_name)
VALUES (11, 'stock_documents');
