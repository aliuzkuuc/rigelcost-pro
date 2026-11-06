CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    row_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (organization_id, code)
);

CREATE INDEX IF NOT EXISTS ix_warehouses_branch
ON warehouses(organization_id, branch_id, active);

DROP TRIGGER IF EXISTS trg_stock_movements_negative_policy;
CREATE TRIGGER trg_stock_movements_negative_policy
BEFORE INSERT ON stock_movements
WHEN NEW.direction = -1
 AND COALESCE((
     SELECT negative_stock_policy FROM warehouses WHERE id = NEW.warehouse_id
 ), 'İZİN') = 'ENGELLE'
 AND COALESCE((
     SELECT SUM(direction * quantity)
     FROM stock_movements
     WHERE organization_id = NEW.organization_id
       AND stock_item_id = NEW.stock_item_id
       AND warehouse_id = NEW.warehouse_id
       AND lot_no = NEW.lot_no
 ), 0) < NEW.quantity
BEGIN
    SELECT RAISE(ABORT, 'NEGATIVE_STOCK_BLOCKED');
END;

INSERT OR IGNORE INTO local_schema_versions(version_no, migration_name)
VALUES (10, 'branch_warehouse_policy');
