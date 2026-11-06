-- Satış teklifi satırları
CREATE TABLE IF NOT EXISTS sales_quote_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_quote_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    die_id INTEGER,
    length_mm REAL NOT NULL DEFAULT 0,
    quantity REAL NOT NULL DEFAULT 0,
    kg REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    line_amount REAL NOT NULL DEFAULT 0,
    surface TEXT NOT NULL DEFAULT '',
    alloy TEXT NOT NULL DEFAULT '',
    temper TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (sales_quote_id) REFERENCES sales_quotes(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (die_id) REFERENCES dies(id),
    UNIQUE (sales_quote_id, line_no)
);

CREATE INDEX IF NOT EXISTS ix_sales_quote_lines_quote
ON sales_quote_lines(sales_quote_id);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (17, '017_sales_quote_lines.sql');
