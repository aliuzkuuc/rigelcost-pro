PRAGMA foreign_keys = ON;

-- Pres fişinde profil teorik gramajından billet boyuna kadar hesaplanan
-- değerleri ayrı saklar. Böylece giren billet, çıkan profil ve fire hesabı
-- sonradan denetlenebilir.
ALTER TABLE production_entries ADD COLUMN billet_diameter_mm REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN billet_density_kg_m3 REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN billet_weight_kg_m REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN theoretical_net_kg REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN theoretical_billet_kg REAL NOT NULL DEFAULT 0;
ALTER TABLE production_entries ADD COLUMN press_fire_pct REAL NOT NULL DEFAULT 0;

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (7, '007_press_theoretical_control.sql');
