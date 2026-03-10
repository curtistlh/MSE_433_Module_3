from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class OrderRecord:
    """One order with item-type quantities and tote mapping.

    item_qty: maps item_type_id -> quantity
    item_tote: maps item_type_id -> tote_id (as int)
    """

    order_id: int
    item_qty: Dict[int, int]
    item_tote: Dict[int, int]


def _read_ragged_csv(path: Path) -> List[List[str]]:
    """Reads a CSV where rows can have trailing empty cells.

    Keeps empty strings as "".
    """
    rows: List[List[str]] = []
    with path.open(newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            rows.append([c.strip() for c in r])
    return rows


def _to_int_safe(val: str) -> Optional[int]:
    if val is None:
        return None
    v = val.strip()
    if v == "":
        return None
    # Handles values like "1.0"
    try:
        return int(float(v))
    except ValueError:
        return None


def load_orders_from_three_csvs(
    order_itemtypes_csv: str | Path,
    order_quantities_csv: str | Path,
    orders_totes_csv: str | Path,
) -> List[OrderRecord]:
    """Loads orders from the three provided CSVs.

    Assumption (matches your sample files):
      - Each row index corresponds to an order (1..N)
      - Row contains item type IDs (ragged)
      - Row contains quantities aligned position-wise with item types
      - Row contains tote IDs aligned position-wise with item types

    Returns a list of OrderRecord with order_id = 1..N.
    """
    p_types = Path(order_itemtypes_csv)
    p_qty = Path(order_quantities_csv)
    p_totes = Path(orders_totes_csv)

    rows_types = _read_ragged_csv(p_types)
    rows_qty = _read_ragged_csv(p_qty)
    rows_totes = _read_ragged_csv(p_totes)

    n = len(rows_types)
    if len(rows_qty) != n or len(rows_totes) != n:
        raise ValueError(
            f"Mismatched number of rows: itemtypes={len(rows_types)}, quantities={len(rows_qty)}, totes={len(rows_totes)}"
        )

    orders: List[OrderRecord] = []
    for i in range(n):
        types_row = [_to_int_safe(x) for x in rows_types[i]]
        qty_row = [_to_int_safe(x) for x in rows_qty[i]]
        totes_row = [_to_int_safe(x) for x in rows_totes[i]]

        # Keep aligned positions where item type exists
        item_qty: Dict[int, int] = {}
        item_tote: Dict[int, int] = {}

        max_len = max(len(types_row), len(qty_row), len(totes_row))
        # Pad
        types_row += [None] * (max_len - len(types_row))
        qty_row += [None] * (max_len - len(qty_row))
        totes_row += [None] * (max_len - len(totes_row))

        for t, q, tt in zip(types_row, qty_row, totes_row):
            if t is None:
                continue
            if q is None:
                # If quantity missing, assume 1
                q = 1
            if q <= 0:
                continue
            item_qty[t] = item_qty.get(t, 0) + q
            if tt is not None:
                # If multiple entries map same item type to different totes, keep the first but you can extend later.
                item_tote.setdefault(t, tt)

        orders.append(OrderRecord(order_id=i + 1, item_qty=item_qty, item_tote=item_tote))

    return orders
