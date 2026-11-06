ALTER TABLE routes ADD COLUMN recipe_name TEXT NOT NULL DEFAULT '';
ALTER TABLE routes ADD COLUMN production_length_mm INTEGER NOT NULL DEFAULT 0;
ALTER TABLE routes ADD COLUMN surface TEXT NOT NULL DEFAULT '';
ALTER TABLE routes ADD COLUMN color TEXT NOT NULL DEFAULT '';
ALTER TABLE routes ADD COLUMN alloy TEXT NOT NULL DEFAULT '';
ALTER TABLE routes ADD COLUMN temper TEXT NOT NULL DEFAULT '';
ALTER TABLE routes ADD COLUMN mechanical TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_routes_recipe_match
ON routes(
    organization_id, profile_id, active, production_length_mm,
    surface, alloy, temper
);

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (2, '002_recipe_attributes.sql');
