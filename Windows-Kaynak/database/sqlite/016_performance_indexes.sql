-- Performans indeksleri — sipariş durum ve stok hareket sorguları
CREATE INDEX IF NOT EXISTS ix_sales_order_line_status_order
ON sales_order_line_status(sales_order_id);

CREATE INDEX IF NOT EXISTS ix_stock_movements_line_warehouse
ON stock_movements(sales_order_line_id, warehouse_id);

CREATE INDEX IF NOT EXISTS ix_package_lines_order_line
ON package_lines(sales_order_line_id);

CREATE INDEX IF NOT EXISTS ix_production_orders_line
ON production_orders(sales_order_line_id, status);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (16, '016_performance_indexes.sql');
