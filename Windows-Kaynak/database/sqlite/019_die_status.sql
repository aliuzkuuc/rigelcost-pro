-- Kalıp durum default = ARŞİVDE (RIGEL KALIP_DURUM)
UPDATE dies SET status = 'ARŞİVDE'
WHERE UPPER(REPLACE(status, 'İ', 'I')) IN ('AKTIF', 'ACTIVE')
   OR status = 'AKTİF'
   OR status = 'TENEFER YAKIN';

-- Standart ömür tablosunu Rigel dağılımına güncelle (1→2000, 2→3000, …)
INSERT INTO tenefer_life_standards(tenefer_no, operator_no, limit_m) VALUES
    (1, 1, 2000),
    (2, 1, 3000),
    (3, 1, 4500),
    (4, 1, 6000),
    (5, 1, 8000),
    (6, 1, 2000),
    (7, 1, 3000),
    (8, 1, 4500),
    (9, 1, 6000),
    (10, 1, 8000)
ON CONFLICT(tenefer_no, operator_no) DO UPDATE SET
    limit_m = excluded.limit_m;

INSERT INTO local_schema_versions(version_no, migration_name)
VALUES (19, '019_die_status.sql');
