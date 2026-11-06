from __future__ import annotations

import sqlite3
from typing import Any

from models.factory_config import factory_config


def seed_master_data(connection: sqlite3.Connection, organization_id: int) -> None:
    cfg = factory_config()
    reasons = (
        ("STOK", "Stok Eksikliği"),
        ("ACIL", "Acil Üretim"),
        ("BAKIM", "Bakım / Arıza"),
        ("PROJE", "Yeni Proje"),
        ("NUMUNE", "Numune"),
    )
    for code, name in reasons:
        connection.execute(
            """
            INSERT OR IGNORE INTO request_reasons(organization_id, code, name)
            VALUES (?, ?, ?)
            """,
            (organization_id, code, name),
        )

    property_sets = (
        ("YUZEY", "Yüzey Özellikleri", "YÜZEY", (cfg.pres_ad, "ELOKSAL", "BOYA", "HAM")),
        ("RENK", "Renk Özellikleri", "RENK", (cfg.renk_pres_ad, "SİYAH", "BRONZ", "DOĞAL")),
        ("ALASIM", "Alaşım Özellikleri", "ALAŞIM", ("6060B", "6063B", "6082")),
        ("SERTLIK", "Sertlik Özellikleri", "SERTLİK", ("T4", "T5", "T6", "T66")),
        ("MEKANIK", "Mekanik Özellikler", "MEKANİK", (cfg.mekanik_ad,)),
    )
    for code, name, kind, values in property_sets:
        connection.execute(
            """
            INSERT OR IGNORE INTO property_sets(organization_id, code, name, property_kind)
            VALUES (?, ?, ?, ?)
            """,
            (organization_id, code, name, kind),
        )
        set_id = connection.execute(
            "SELECT id FROM property_sets WHERE organization_id = ? AND code = ?",
            (organization_id, code),
        ).fetchone()[0]
        for index, value in enumerate(values):
            connection.execute(
                """
                INSERT OR IGNORE INTO property_set_values(
                    property_set_id, code, name, sort_order
                ) VALUES (?, ?, ?, ?)
                """,
                (int(set_id), value, value, index + 1),
            )

    services = (
        ("HZ-ELOKSAL", "Eloksal Hizmeti", "KG"),
        ("HZ-BOYA", "Boya Hizmeti", "KG"),
        ("HZ-FASON", "Fason İşçilik", "KG"),
        ("HZ-NAKL", "Nakliye Hizmeti", "ADET"),
    )
    for code, name, unit in services:
        connection.execute(
            """
            INSERT OR IGNORE INTO service_items(organization_id, code, name, unit)
            VALUES (?, ?, ?, ?)
            """,
            (organization_id, code, name, unit),
        )

    _ = cfg  # fabrika id sabitleri: yuzey_id, termik_on_ambari vb.


def list_request_reasons(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, code, name, active, description
        FROM request_reasons
        WHERE organization_id = ?
        ORDER BY code
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_party_product_codes(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    party_type: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT ppc.id, ppc.party_type, ppc.external_code, ppc.external_name,
               ppc.active,
               CASE ppc.party_type
                   WHEN 'CUSTOMER' THEN c.name
                   WHEN 'SUPPLIER' THEN s.name
                   ELSE ''
               END AS party_name,
               COALESCE(si.code, p.profile_code, '') AS stock_code,
               COALESCE(si.name, p.profile_name, '') AS stock_name
        FROM party_product_codes ppc
        LEFT JOIN customers c ON ppc.party_type = 'CUSTOMER' AND c.id = ppc.party_id
        LEFT JOIN suppliers s ON ppc.party_type = 'SUPPLIER' AND s.id = ppc.party_id
        LEFT JOIN stock_items si ON si.id = ppc.stock_item_id
        LEFT JOIN profiles p ON p.id = ppc.profile_id
        WHERE ppc.organization_id = ? AND ppc.party_type = ?
        ORDER BY party_name, ppc.external_code
        """,
        (organization_id, party_type.upper()),
    ).fetchall()
    return [dict(row) for row in rows]


def list_service_items(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, code, name, unit, active, description
        FROM service_items
        WHERE organization_id = ?
        ORDER BY code
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_property_sets(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT ps.id, ps.code, ps.name, ps.property_kind, ps.active,
               COUNT(v.id) AS value_count
        FROM property_sets ps
        LEFT JOIN property_set_values v ON v.property_set_id = ps.id
        WHERE ps.organization_id = ?
        GROUP BY ps.id
        ORDER BY ps.code
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_property_values(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT v.id, ps.code AS set_code, ps.name AS set_name,
               ps.property_kind, v.code, v.name, v.active, v.sort_order
        FROM property_set_values v
        JOIN property_sets ps ON ps.id = v.property_set_id
        WHERE ps.organization_id = ?
        ORDER BY ps.code, v.sort_order, v.code
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_sales_price_lists(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT pl.id, pl.list_code, pl.list_name, pl.currency,
               pl.valid_from, pl.valid_until, pl.active,
               c.name AS customer_name,
               COUNT(l.id) AS line_count
        FROM sales_price_lists pl
        LEFT JOIN customers c ON c.id = pl.customer_id
        LEFT JOIN sales_price_list_lines l ON l.price_list_id = pl.id
        WHERE pl.organization_id = ?
        GROUP BY pl.id
        ORDER BY pl.list_code
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_customer_complaints(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT cc.id, cc.complaint_no, cc.complaint_date AS record_date,
               cc.subject, cc.description, cc.status, cc.profile_code,
               c.name AS customer_name, o.order_no
        FROM customer_complaints cc
        JOIN customers c ON c.id = cc.customer_id
        LEFT JOIN sales_orders o ON o.id = cc.sales_order_id
        WHERE cc.organization_id = ?
        ORDER BY cc.complaint_date DESC, cc.id DESC
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_die_tooling_requests(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT r.id, r.request_no, r.request_date AS record_date,
               r.figure_no, r.status, r.note,
               p.profile_code, p.profile_name,
               s.name AS supplier_name
        FROM die_tooling_requests r
        JOIN profiles p ON p.id = r.profile_id
        LEFT JOIN suppliers s ON s.id = r.supplier_id
        WHERE r.organization_id = ?
        ORDER BY r.request_date DESC, r.id DESC
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_die_tooling_work_orders(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    pending_only: bool = False,
) -> list[dict[str, Any]]:
    where = "WHERE w.organization_id = ?"
    params: list[Any] = [organization_id]
    if pending_only:
        where += " AND w.status IN ('BEKLİYOR', 'İŞLEMDE')"
    rows = connection.execute(
        f"""
        SELECT w.id, w.work_order_no, w.order_type, w.order_date AS record_date,
               w.planned_end, w.status, w.note,
               d.die_code, p.profile_code, p.profile_name,
               s.name AS supplier_name
        FROM die_tooling_work_orders w
        JOIN profiles p ON p.id = w.profile_id
        LEFT JOIN dies d ON d.id = w.die_id
        LEFT JOIN suppliers s ON s.id = w.supplier_id
        {where}
        ORDER BY w.order_date DESC, w.id DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def list_die_tooling_slips(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT s.id, s.slip_no, s.slip_date AS record_date, s.slip_type,
               s.used_kg, s.location_from, s.location_to, s.note,
               d.die_code, p.profile_code
        FROM die_tooling_slips s
        JOIN dies d ON d.id = s.die_id
        JOIN profiles p ON p.id = s.profile_id
        WHERE s.organization_id = ?
        ORDER BY s.slip_date DESC, s.id DESC
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_die_tooling_problems(connection: sqlite3.Connection, organization_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT pr.id, pr.problem_no, pr.record_date, pr.problem_type,
               pr.description, pr.status,
               d.die_code, p.profile_code
        FROM die_tooling_problems pr
        JOIN dies d ON d.id = pr.die_id
        JOIN profiles p ON p.id = pr.profile_id
        WHERE pr.organization_id = ?
        ORDER BY pr.record_date DESC, pr.id DESC
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def create_request_reason(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    code: str,
    name: str,
    description: str = "",
) -> int:
    if not code or not name:
        raise ValueError("Talep sebebi kodu ve adı zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO request_reasons(organization_id, code, name, description)
        VALUES (?, ?, ?, ?)
        """,
        (organization_id, code.strip().upper(), name.strip(), description.strip()),
    )
    return int(cursor.lastrowid)


def create_customer_complaint(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    complaint_no: str,
    customer_id: int,
    complaint_date: str,
    subject: str,
    profile_code: str = "",
    description: str = "",
    username: str = "",
) -> int:
    if not complaint_no or not subject.strip():
        raise ValueError("Şikayet numarası ve konu zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO customer_complaints(
            organization_id, complaint_no, customer_id,
            complaint_date, subject, profile_code, description, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, complaint_no.strip(), int(customer_id),
            complaint_date, subject.strip(), profile_code.strip().upper(),
            description.strip(), username.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_sales_price_list(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    list_code: str,
    list_name: str,
    currency: str = "USD",
    customer_id: int | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> int:
    if not list_code or not list_name:
        raise ValueError("Fiyat listesi kodu ve adı zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO sales_price_lists(
            organization_id, list_code, list_name, customer_id,
            currency, valid_from, valid_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, list_code.strip().upper(), list_name.strip(),
            int(customer_id) if customer_id else None,
            currency.strip().upper() or "USD",
            valid_from, valid_until,
        ),
    )
    return int(cursor.lastrowid)


def create_die_tooling_request(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    request_no: str,
    profile_id: int,
    request_date: str,
    supplier_id: int | None = None,
    figure_no: str = "",
    note: str = "",
    username: str = "",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO die_tooling_requests(
            organization_id, request_no, profile_id, supplier_id,
            request_date, figure_no, note, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, request_no.strip(), int(profile_id),
            int(supplier_id) if supplier_id else None,
            request_date, figure_no.strip(), note.strip(), username.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_die_tooling_work_order(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    work_order_no: str,
    profile_id: int,
    order_date: str,
    order_type: str = "BAKIM",
    die_id: int | None = None,
    supplier_id: int | None = None,
    planned_end: str | None = None,
    note: str = "",
    username: str = "",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO die_tooling_work_orders(
            organization_id, work_order_no, die_id, profile_id, supplier_id,
            order_type, order_date, planned_end, note, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, work_order_no.strip(),
            int(die_id) if die_id else None, int(profile_id),
            int(supplier_id) if supplier_id else None,
            order_type.strip().upper(), order_date, planned_end,
            note.strip(), username.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_die_tooling_slip(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    slip_no: str,
    die_id: int,
    profile_id: int,
    slip_date: str,
    slip_type: str = "BAKIM",
    used_kg: float = 0,
    location_from: str = "",
    location_to: str = "",
    note: str = "",
    username: str = "",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO die_tooling_slips(
            organization_id, slip_no, die_id, profile_id, slip_date,
            slip_type, used_kg, location_from, location_to, note, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, slip_no.strip(), int(die_id), int(profile_id),
            slip_date, slip_type.strip().upper(), float(used_kg or 0),
            location_from.strip().upper(), location_to.strip().upper(),
            note.strip(), username.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_die_tooling_problem(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    problem_no: str,
    die_id: int,
    profile_id: int,
    record_date: str,
    problem_type: str = "",
    description: str = "",
    username: str = "",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO die_tooling_problems(
            organization_id, problem_no, die_id, profile_id, record_date,
            problem_type, description, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, problem_no.strip(), int(die_id), int(profile_id),
            record_date, problem_type.strip().upper(), description.strip(),
            username.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_service_item(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    code: str,
    name: str,
    unit: str = "KG",
    description: str = "",
) -> int:
    if not code.strip() or not name.strip():
        raise ValueError("Hizmet kartı kodu ve adı zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO service_items(organization_id, code, name, unit, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            organization_id, code.strip().upper(), name.strip(),
            unit.strip().upper() or "KG", description.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_party_product_code(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    party_type: str,
    party_id: int,
    external_code: str,
    external_name: str = "",
    stock_item_id: int | None = None,
    profile_id: int | None = None,
) -> int:
    code = external_code.strip().upper()
    if not code:
        raise ValueError("Dış ürün kodu zorunludur.")
    if stock_item_id is None and profile_id is None:
        raise ValueError("Stok kartı veya profil seçilmelidir.")
    if stock_item_id is None and profile_id is not None:
        stock_row = connection.execute(
            """
            SELECT id FROM stock_items
            WHERE profile_id = ? AND organization_id = ? AND active = 1
            LIMIT 1
            """,
            (int(profile_id), organization_id),
        ).fetchone()
        if stock_row is not None:
            stock_item_id = int(stock_row["id"])
    cursor = connection.execute(
        """
        INSERT INTO party_product_codes(
            organization_id, party_type, party_id, stock_item_id, profile_id,
            external_code, external_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id, party_type.strip().upper(), int(party_id),
            int(stock_item_id) if stock_item_id else None,
            int(profile_id) if profile_id else None,
            code, external_name.strip(),
        ),
    )
    return int(cursor.lastrowid)


def create_property_set(
    connection: sqlite3.Connection,
    organization_id: int,
    *,
    code: str,
    name: str,
    property_kind: str = "YÜZEY",
) -> int:
    if not code.strip() or not name.strip():
        raise ValueError("Özellik seti kodu ve adı zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO property_sets(organization_id, code, name, property_kind)
        VALUES (?, ?, ?, ?)
        """,
        (organization_id, code.strip().upper(), name.strip(), property_kind.strip().upper()),
    )
    return int(cursor.lastrowid)


def create_property_set_value(
    connection: sqlite3.Connection,
    *,
    property_set_id: int,
    code: str,
    name: str,
    sort_order: int = 0,
) -> int:
    if not code.strip() or not name.strip():
        raise ValueError("Özellik değeri kodu ve adı zorunludur.")
    cursor = connection.execute(
        """
        INSERT INTO property_set_values(property_set_id, code, name, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        (int(property_set_id), code.strip().upper(), name.strip(), int(sort_order)),
    )
    return int(cursor.lastrowid)


def create_sales_price_list_line(
    connection: sqlite3.Connection,
    *,
    price_list_id: int,
    profile_id: int,
    unit_price: float,
    surface: str = "",
    alloy: str = "",
    temper: str = "",
    currency: str = "USD",
) -> int:
    if unit_price <= 0:
        raise ValueError("Birim fiyat sıfırdan büyük olmalıdır.")
    cursor = connection.execute(
        """
        INSERT INTO sales_price_list_lines(
            price_list_id, profile_id, surface, alloy, temper, unit_price, currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(price_list_id), int(profile_id),
            surface.strip().upper(), alloy.strip().upper(), temper.strip().upper(),
            float(unit_price), currency.strip().upper() or "USD",
        ),
    )
    return int(cursor.lastrowid)


def list_sales_price_list_lines(
    connection: sqlite3.Connection,
    price_list_id: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT l.id, l.profile_id, l.surface, l.alloy, l.temper,
               l.unit_price, l.currency,
               p.profile_code, p.profile_name
        FROM sales_price_list_lines l
        JOIN profiles p ON p.id = l.profile_id
        WHERE l.price_list_id = ?
        ORDER BY p.profile_code, l.surface
        """,
        (int(price_list_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def list_profiles_without_die_on_open_orders(
    connection: sqlite3.Connection,
    organization_id: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT DISTINCT p.id, p.profile_code, p.profile_name,
               c.name AS customer_name, o.order_no,
               l.line_no, l.ordered_kg, l.status
        FROM sales_order_lines l
        JOIN sales_orders o ON o.id = l.sales_order_id
        JOIN customers c ON c.id = o.customer_id
        JOIN profiles p ON p.id = l.profile_id
        LEFT JOIN dies d ON d.profile_id = p.id AND d.status <> 'HURDA' AND COALESCE(d.active, 1) = 1
        WHERE o.organization_id = ?
          AND o.status NOT IN ('KAPALI', 'İPTAL', 'SEVK EDİLDİ')
          AND l.die_id IS NULL
          AND d.id IS NULL
        ORDER BY o.order_date DESC, o.order_no, l.line_no
        """,
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]
