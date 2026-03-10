from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple

from .constants import CONVEYORS
from .io_utils import OrderRecord


AssignMethod = Literal["round_robin", "balance_units"]


def assign_orders_to_conveyors(
    orders: List[OrderRecord], method: AssignMethod = "round_robin"
) -> Dict[int, int]:
    """Return mapping order_id -> conveyor.

    Methods:
      - round_robin: assigns 1,2,3,4,1,...
      - balance_units: greedy load balancing by total units per order (desc), assign each order to currently lightest conveyor

    Note: this is *only* the conveyor assignment. Tote sequencing and within-tote item ordering are separate decisions.
    """
    if method == "round_robin":
        return {o.order_id: CONVEYORS[(i % len(CONVEYORS))] for i, o in enumerate(orders)}

    if method == "balance_units":
        loads = {c: 0 for c in CONVEYORS}
        out: Dict[int, int] = {}
        orders_sorted = sorted(orders, key=lambda o: sum(o.item_qty.values()), reverse=True)
        for o in orders_sorted:
            c = min(loads, key=lambda cc: loads[cc])
            out[o.order_id] = c
            loads[c] += sum(o.item_qty.values())
        return out

    raise ValueError(f"Unknown method: {method}")


"""Heuristics (rule-based policies).

This module is intentionally split into:
  1) Order -> conveyor assignment (strategic)
  2) Tote sequencing (macro sequencing)
  3) Item ordering within a tote block (micro sequencing)

Your simulator input file (one row per order) needs (1), but your physical/demo
process also needs (2) and (3) to decide what to load next.
"""


# --- Tote sequencing & within-tote item ordering ---

ToteSeqMethod = Literal["fifo", "complete_active_first"]


def sequence_totes(
    orders: List[OrderRecord],
    active_order_id: int,
    method: ToteSeqMethod = "fifo",
) -> List[int]:
    """Return a tote release sequence (list of tote IDs).

    Methods
    -------
    fifo:
        Placeholder baseline: totes in increasing tote_id order.

    complete_active_first:
        Prioritize totes that contribute to completing the *active* order.
        Concretely: put all totes required by the active order first (in any
        deterministic order), then all remaining totes.

        This is the simplest implementation of:
            "prioritize totes that complete the active order".

    Notes
    -----
    - Because each tote is released as a contiguous block in your process,
      this function outputs tote IDs (not individual items).
    - If you later want a multi-order schedule, call this repeatedly as
      the active order changes.
    """

    all_totes = sorted({t for o in orders for t in o.item_tote.values()})

    if method == "fifo":
        return all_totes

    if method == "complete_active_first":
        active = next((o for o in orders if o.order_id == active_order_id), None)
        if active is None:
            raise ValueError(f"active_order_id={active_order_id} not found")

        active_totes = sorted(set(active.item_tote.values()))
        remaining = [t for t in all_totes if t not in set(active_totes)]
        return active_totes + remaining

    raise ValueError(f"Unknown tote sequencing method: {method}")


def order_items_within_tote(
    tote_id: int,
    orders: List[OrderRecord],
    active_order_id: int,
) -> List[Tuple[int, int]]:
    """Return the item-release order for a single tote.

    Output is a list of (order_id, item_type_id) *units* in the order they
    should be placed on the belt, representing the within-tote sequence.

    Rule implemented:
      - items for active order first
      - then items for other orders

    Within each group, we use a deterministic order (item_type_id ascending)
    and expand by quantity.
    """

    # Collect all units in this tote across all orders.
    active_units: List[Tuple[int, int]] = []
    other_units: List[Tuple[int, int]] = []

    for o in orders:
        for item_type, t in o.item_tote.items():
            if t != tote_id:
                continue
            qty = o.item_qty.get(item_type, 0)
            if qty <= 0:
                continue
            units = [(o.order_id, item_type)] * qty
            if o.order_id == active_order_id:
                active_units.extend(units)
            else:
                other_units.extend(units)

    # Deterministic ordering within each group
    active_units.sort(key=lambda x: x[1])
    other_units.sort(key=lambda x: (x[0], x[1]))

    return active_units + other_units
