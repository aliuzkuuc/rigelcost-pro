-- RIGEL FIRMA / FIRMA_ILGILI / PROFIL / KALIP yapısına uyumlu ana kart genişletmesi.
ALTER TABLE customers ADD COLUMN short_name TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN sector TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN district TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN postal_code TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN phone2 TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN fax TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN email2 TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN accounting_code TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN bank_name TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN notes TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN order_note TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN production_note TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN general_warning TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN is_supplier INTEGER NOT NULL DEFAULT 0;
ALTER TABLE customers ADD COLUMN is_subcontractor INTEGER NOT NULL DEFAULT 0;

CREATE TABLE customer_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    phone1 TEXT NOT NULL DEFAULT '',
    phone2 TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE INDEX idx_customer_contacts_customer
    ON customer_contacts(organization_id, customer_id, active);

CREATE TABLE customer_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT 'MERKEZ',
    country TEXT NOT NULL DEFAULT 'TÜRKİYE',
    city TEXT NOT NULL DEFAULT '',
    district TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    tax_office TEXT NOT NULL DEFAULT '',
    tax_number TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE INDEX idx_customer_addresses_customer
    ON customer_addresses(organization_id, customer_id, active);

ALTER TABLE dies ADD COLUMN tenefer_no TEXT NOT NULL DEFAULT '';
ALTER TABLE dies ADD COLUMN tenefer_type TEXT NOT NULL DEFAULT '';

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (6, 'master_cards');
