"""Finds backordered line items whose SKU has NO open replenishment PO at
all — these are stockouts we haven't even ordered more inventory for.

Product FAMILIES (not exact SKUs) affecting 5+ distinct orders are excluded
on purpose: at that volume it's presumably already a known, actively-managed
issue. This report exists to surface the smaller, easy-to-miss ones.

Why "family" and not exact SKU: a single product sold in multiple sizes or
colors (e.g. a sweater in SM/M/L/XL) gets a different SKU per variant. Each
variant can individually stay under the order-count threshold while the
PRODUCT as a whole is clearly backordered at volume — e.g. 4 sizes each with
2 affected orders is 8 total orders on one sweater, which should trip the
threshold, but didn't when counted per exact SKU. So the threshold is
evaluated per product family instead.
"""
import re

_TRAILING_VARIANT_CODE = re.compile(r"^(.*)[-_][^-_]+$")


def _sku_prefix(sku: str) -> str:
    """Strips a trailing '-XXXX' or '_XXXX' segment, treating it as a
    size/color variant code (e.g. 'FOX-76-SWTR-2' -> 'FOX-76-SWTR'). Returns
    the SKU unchanged if there's no such delimiter to strip.
    """
    match = _TRAILING_VARIANT_CODE.match(sku)
    return match.group(1) if match else sku


def _name_base(product_name: str) -> str:
    """Strips a trailing ' - <variant>' segment from a product name (e.g.
    'Sweater - White - SM' -> 'Sweater - White'). Returns the name unchanged
    if there's no ' - ' to split on.
    """
    if " - " in product_name:
        return product_name.rsplit(" - ", 1)[0]
    return product_name


def _family_key(sku: str, product_name: str) -> tuple:
    """Two SKUs are the same family only if BOTH the SKU-prefix heuristic
    AND the product-name heuristic agree — requiring both reduces the
    chance of accidentally merging two unrelated products that happen to
    share a short prefix by coincidence.
    """
    return (_sku_prefix(sku), _name_base(product_name or ""))


def find_no_po_matches(
    backordered_orders: list[dict],
    open_po_skus: dict[str, list[dict]],
    preorder_tag: str,
    max_orders_per_sku: int = 5,
) -> tuple[list[dict], dict]:
    """Returns (rows, breakdown).

    rows = one row per backordered line item whose SKU has no inbound PO,
    for product families affecting fewer than `max_orders_per_sku` distinct
    orders, on orders not already tagged `preorder_tag`. Each row carries
    `orders_affected_for_sku` (the family-wide count, not just its own exact
    SKU) and `sku_group` (the derived family key, for auditing — so you can
    see exactly what got grouped and catch any false merge by eye).

    breakdown = counts at each filtering stage, so the email summary can
    show exactly where line items got excluded instead of just a start and
    end number with a big invisible gap in between.
    """
    total_line_items = 0
    skipped_already_tagged = 0
    skipped_has_open_po = 0
    candidates_by_family: dict[tuple, list[dict]] = {}

    for order in backordered_orders:
        already_tagged = preorder_tag in (order.get("tags") or [])
        for line_item in order["backordered_line_items"]:
            total_line_items += 1
            if already_tagged:
                skipped_already_tagged += 1
                continue
            sku = line_item["sku"]
            if sku in open_po_skus:
                skipped_has_open_po += 1
                continue  # has replenishment inbound — not what we want here
            family_key = _family_key(sku, line_item.get("product_name"))
            candidates_by_family.setdefault(family_key, []).append(
                {
                    "order_id": order["id"],
                    "order_number": order["order_number"],
                    "order_date": order.get("order_date"),
                    "customer_email": order.get("email"),
                    "sku": sku,
                    "product_name": line_item.get("product_name"),
                    "qty_backordered": line_item.get("backorder_quantity"),
                    "sku_group": family_key[0],
                }
            )

    rows: list[dict] = []
    families_excluded_over_threshold = 0
    line_items_excluded_over_threshold = 0
    for family_key, items in candidates_by_family.items():
        distinct_orders = {item["order_id"] for item in items}
        if len(distinct_orders) >= max_orders_per_sku:
            families_excluded_over_threshold += 1
            line_items_excluded_over_threshold += len(items)
            continue  # too many affected orders — treat as already known/handled
        for item in items:
            item["orders_affected_for_sku"] = len(distinct_orders)
            rows.append(item)

    breakdown = {
        "total_line_items": total_line_items,
        "skipped_already_tagged": skipped_already_tagged,
        "skipped_has_open_po": skipped_has_open_po,
        "skus_excluded_over_threshold": families_excluded_over_threshold,
        "line_items_excluded_over_threshold": line_items_excluded_over_threshold,
        "line_items_in_report": len(rows),
    }
    return rows, breakdown
