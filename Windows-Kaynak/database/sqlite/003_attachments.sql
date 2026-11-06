CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'DOSYA',
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    source_system TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    UNIQUE (entity_type, entity_id, file_path)
);

CREATE INDEX IF NOT EXISTS ix_attachments_entity
ON attachments(organization_id, entity_type, entity_id, active);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (3, '003_attachments.sql');
