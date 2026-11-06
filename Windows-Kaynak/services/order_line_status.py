from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


FIELD_WAREHOUSE_CODES = ("PRES", "TERMIK_ON", "TERMIK", "YUZEY", "ELOKSAL_ON", "BOYA_ON")
READY_WAREHOUSE_CODES = ("SEVK_ON", "SEVK_HAZIR", "MAMUL_STOK")


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fulfillment_label(
    *,
    ordered_kg: float,
    produced_kg: float,
    ready_kg: float,
    shipped_kg: float,
    field_kg: float,
) -> str:
    if ordered_kg > 0 and shipped_kg + 0.001 >= ordered_kg:
        return "SEVK EDİLDİ"
    if shipped_kg > 0.001:
        return "KISMİ SEVK"
    if ready_kg > 0.001:
        return "SEVK BEKLİYOR"
    if field_kg > 0.001:
        return "SAHADA"
    if ordered_kg > 0 and produced_kg + 0.001 >= ordered_kg:
        return "ÜRETİLDİ"
    if produced_kg > 0.001:
        return "KISMİ ÜRETİM"
    return "ÜRETİLECEK"


def recalculate_order_line_status(
    connection: sqlite3.Connection,
    *,
    sales_order_line_id: int | None = None,
    sales_order_id: int | None = None,
) -> int:
    """Satır üretim/sevk durumunu yeniler."""
    params: list[int] = []
    where = "WHERE 1=1"
    if sales_order_line_id is not None:
        where += " AND l.id = ?"
        params.append(int(sales_order_line_id))
    if sales_order_id is not None:
        where += " AND l.sales_order_id = ?"
        params.append(int(sales_order_id))

    lines = connection.execute(
        f"""
        SELECT l.id, l.sales_order_id, l.ordered_quantity, l.ordered_kg
        FROM sales_order_lines l
        {where}
        """,
        params,
    ).fetchall()
    updated = 0
    now = datetime.now().isoformat(timespec="seconds")
    for line in lines:
        line_id = int(line["id"])
        order_id = int(line["sales_order_id"])
        ordered_qty = _num(line["ordered_quantity"])
        ordered_kg = _num(line["ordered_kg"])

        plan = connection.execute(
            """
            SELECT COALESCE(SUM(planned_quantity), 0) AS qty,
                   COALESCE(SUM(planned_kg), 0) AS kg
            FROM production_orders
            WHERE sales_order_line_id = ? AND status <> 'İPTAL'
            """,
            (line_id,),
        ).fetchone()

        produced = connection.execute(
            """
            SELECT COALESCE(SUM(po.produced_quantity), 0) AS qty,
                   COALESCE(SUM(po.produced_kg), 0) AS kg
            FROM production_orders po
            WHERE po.sales_order_line_id = ? AND po.status <> 'İPTAL'
            """,
            (line_id,),
        ).fetchone()

        shipped = connection.execute(
            """
            SELECT COALESCE(SUM(pl.quantity), 0) AS qty,
                   COALESCE(SUM(pl.net_kg), 0) AS kg,
                   MAX(s.shipment_date) AS last_shipment_date
            FROM package_lines pl
            JOIN packages pkg ON pkg.id = pl.package_id
            JOIN shipment_lines sl ON sl.package_id = pkg.id
            JOIN shipments s ON s.id = sl.shipment_id
            WHERE pl.sales_order_line_id = ?
            """,
            (line_id,),
        ).fetchone()

        field = connection.execute(
            """
            SELECT COALESCE(SUM(
                       CASE
                           WHEN UPPER(COALESCE(si.unit, 'KG')) IN ('ADET', 'PCS')
                           THEN CASE sm.direction WHEN 1 THEN sm.quantity ELSE -sm.quantity END
                           ELSE 0
                       END
                   ), 0) AS qty,
                   COALESCE(SUM(
                       CASE
                           WHEN UPPER(COALESCE(si.unit, 'KG')) IN ('ADET', 'PCS')
                           THEN 0
                           ELSE CASE sm.direction WHEN 1 THEN sm.quantity ELSE -sm.quantity END
                       END
                   ), 0) AS kg
            FROM stock_movements sm
            JOIN stock_items si ON si.id = sm.stock_item_id
            JOIN warehouses w ON w.id = sm.warehouse_id
            WHERE sm.sales_order_line_id = ?
              AND UPPER(w.code) IN ({})
            """.format(",".join("?" * len(FIELD_WAREHOUSE_CODES))),
            (line_id, *FIELD_WAREHOUSE_CODES),
        ).fetchone()

        ready = connection.execute(
            """
            SELECT COALESCE(SUM(pl.quantity), 0) AS qty,
                   COALESCE(SUM(pl.net_kg), 0) AS kg
            FROM packages pkg
            JOIN package_lines pl ON pl.package_id = pkg.id
            JOIN warehouses w ON w.id = pkg.warehouse_id
            WHERE pl.sales_order_line_id = ?
              AND pkg.status IN ('SEVK ÖN', 'SEVK HAZIR', 'HAZIR')
              AND UPPER(w.code) IN ({})
              AND pkg.id NOT IN (SELECT package_id FROM shipment_lines)
            """.format(",".join("?" * len(READY_WAREHOUSE_CODES))),
            (line_id, *READY_WAREHOUSE_CODES),
        ).fetchone()

        warehouses = connection.execute(
            """
            SELECT GROUP_CONCAT(DISTINCT w.name) AS names
            FROM stock_movements sm
            JOIN warehouses w ON w.id = sm.warehouse_id
            WHERE sm.sales_order_line_id = ?
            """,
            (line_id,),
        ).fetchone()

        plans = connection.execute(
            """
            SELECT GROUP_CONCAT(DISTINCT po.production_order_no) AS plan_nos
            FROM production_orders po
            WHERE po.sales_order_line_id = ? AND po.status <> 'İPTAL'
            """,
            (line_id,),
        ).fetchone()

        produced_qty = _num(produced["qty"])
        produced_kg = _num(produced["kg"])
        shipped_qty = _num(shipped["qty"])
        shipped_kg = _num(shipped["kg"])
        field_qty = max(0.0, _num(field["qty"]))
        field_kg = max(0.0, _num(field["kg"]))
        ready_qty = _num(ready["qty"])
        ready_kg = _num(ready["kg"])

        pending_prod_qty = max(0.0, ordered_qty - produced_qty)
        pending_prod_kg = max(0.0, ordered_kg - produced_kg)
        pending_ship_qty = max(0.0, ordered_qty - shipped_qty)
        pending_ship_kg = max(0.0, ordered_kg - shipped_kg)
        progress = (shipped_kg / ordered_kg * 100.0) if ordered_kg > 0 else 0.0

        status = fulfillment_label(
            ordered_kg=ordered_kg,
            produced_kg=produced_kg,
            ready_kg=ready_kg,
            shipped_kg=shipped_kg,
            field_kg=field_kg,
        )

        connection.execute(
            """
            INSERT INTO sales_order_line_status(
                sales_order_line_id, sales_order_id,
                planned_quantity, planned_kg,
                produced_quantity, produced_kg,
                pending_production_quantity, pending_production_kg,
                field_quantity, field_kg,
                ready_package_quantity, ready_package_kg,
                shipped_quantity, shipped_kg,
                pending_shipment_quantity, pending_shipment_kg,
                fulfillment_status, progress_pct,
                warehouse_summary, plan_summary,
                last_shipment_date, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sales_order_line_id) DO UPDATE SET
                sales_order_id = excluded.sales_order_id,
                planned_quantity = excluded.planned_quantity,
                planned_kg = excluded.planned_kg,
                produced_quantity = excluded.produced_quantity,
                produced_kg = excluded.produced_kg,
                pending_production_quantity = excluded.pending_production_quantity,
                pending_production_kg = excluded.pending_production_kg,
                field_quantity = excluded.field_quantity,
                field_kg = excluded.field_kg,
                ready_package_quantity = excluded.ready_package_quantity,
                ready_package_kg = excluded.ready_package_kg,
                shipped_quantity = excluded.shipped_quantity,
                shipped_kg = excluded.shipped_kg,
                pending_shipment_quantity = excluded.pending_shipment_quantity,
                pending_shipment_kg = excluded.pending_shipment_kg,
                fulfillment_status = excluded.fulfillment_status,
                progress_pct = excluded.progress_pct,
                warehouse_summary = excluded.warehouse_summary,
                plan_summary = excluded.plan_summary,
                last_shipment_date = excluded.last_shipment_date,
                updated_at = excluded.updated_at
            """,
            (
                line_id, order_id,
                _num(plan["qty"]), _num(plan["kg"]),
                produced_qty, produced_kg,
                pending_prod_qty, pending_prod_kg,
                field_qty, field_kg,
                ready_qty, ready_kg,
                shipped_qty, shipped_kg,
                pending_ship_qty, pending_ship_kg,
                status, progress,
                str(warehouses["names"] or ""),
                str(plans["plan_nos"] or ""),
                str(shipped["last_shipment_date"] or "")[:10] or None,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE sales_order_lines
            SET produced_quantity = ?, produced_kg = ?,
                shipped_quantity = ?, shipped_kg = ?,
                row_version = row_version + 1
            WHERE id = ?
            """,
            (produced_qty, produced_kg, shipped_qty, shipped_kg, line_id),
        )
        updated += 1

    if sales_order_id is not None or sales_order_line_id is not None:
        order_ids = {int(line["sales_order_id"]) for line in lines}
        for oid in order_ids:
            recalculate_sales_order_header(connection, sales_order_id=oid)
    return updated


def recalculate_sales_order_header(
    connection: sqlite3.Connection,
    *,
    sales_order_id: int,
) -> None:
    totals = connection.execute(
        """
        SELECT COALESCE(SUM(ordered_kg), 0) AS ordered_kg,
               COALESCE(SUM(shipped_kg), 0) AS shipped_kg
        FROM sales_order_lines
        WHERE sales_order_id = ?
        """,
        (int(sales_order_id),),
    ).fetchone()
    ordered = _num(totals["ordered_kg"])
    shipped = _num(totals["shipped_kg"])
    if ordered > 0 and shipped + 0.001 >= ordered:
        status = "SEVK EDİLDİ"
    elif shipped > 0.001:
        status = "KISMİ SEVK"
    else:
        return
    connection.execute(
        """
        UPDATE sales_orders
        SET status = CASE WHEN status <> 'İPTAL' THEN ? ELSE status END,
            updated_at = CURRENT_TIMESTAMP,
            row_version = row_version + 1
        WHERE id = ?
        """,
        (status, int(sales_order_id)),
    )
