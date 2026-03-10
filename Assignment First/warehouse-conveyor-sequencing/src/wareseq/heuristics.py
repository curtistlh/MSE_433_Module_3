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


# --- Placeholders for future sequencing (totes & item order) ---

ToteSeqMethod = Literal["fifo"]


def sequence_totes(
    orders: List[OrderRecord], method: ToteSeqMethod = "fifo"
) -> List[int]:
    """Return a tote release sequence (list of tote IDs).

    For now we provide a simple FIFO placeholder that returns totes in sorted order.
    Extend this with SRPT, lookahead, etc.
    """
    tote_ids = sorted({t for o in orders for t in o.item_tote.values()})
    return tote_ids
