CREATE TABLE IF NOT EXISTS purchase_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    request_no TEXT NOT NULL UNIQUE,
    request_date TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    approval_status TEXT NOT NULL DEFAULT 'ONAY BEKLİYOR',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    status TEXT NOT NULL DEFAULT 'AÇIK',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS purchase_request_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_request_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    stock_item_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    required_date TEXT,
    quantity REAL NOT NULL,
    approved_quantity REAL NOT NULL DEFAULT 0,
    ordered_quantity REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'AÇIK',
    FOREIGN KEY (purchase_request_id) REFERENCES purchase_requests(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    UNIQUE (purchase_request_id, line_no)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    purchase_request_id INTEGER,
    purchase_order_no TEXT NOT NULL UNIQUE,
    supplier_document_no TEXT NOT NULL DEFAULT '',
    order_date TEXT NOT NULL,
    delivery_date TEXT,
    currency TEXT NOT NULL DEFAULT 'TRY',
    exchange_rate REAL NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'AÇIK',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (purchase_request_id) REFERENCES purchase_requests(id)
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL,
    purchase_request_line_id INTEGER,
    line_no INTEGER NOT NULL,
    stock_item_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    received_quantity REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'AÇIK',
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id),
    FOREIGN KEY (purchase_request_line_id) REFERENCES purchase_request_lines(id),
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    UNIQUE (purchase_order_id, line_no)
);

CREATE TABLE IF NOT EXISTS goods_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    purchase_order_id INTEGER NOT NULL,
    receipt_no TEXT NOT NULL UNIQUE,
    dispatch_note_no TEXT NOT NULL DEFAULT '',
    receipt_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id)
);

CREATE TABLE IF NOT EXISTS goods_receipt_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goods_receipt_id INTEGER NOT NULL,
    purchase_order_line_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    lot_no TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (goods_receipt_id) REFERENCES goods_receipts(id),
    FOREIGN KEY (purchase_order_line_id) REFERENCES purchase_order_lines(id)
);

CREATE INDEX IF NOT EXISTS ix_purchase_request_status
ON purchase_requests(organization_id, approval_status, status, request_date);

CREATE INDEX IF NOT EXISTS ix_purchase_order_status
ON purchase_orders(organization_id, supplier_id, status, order_date);

INSERT OR IGNORE INTO local_schema_versions(version_no, migration_name)
VALUES (9, 'purchase_workflow');
