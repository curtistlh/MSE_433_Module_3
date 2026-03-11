from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from validation.instance_generator import (
    GeneratedInstance,
    OrderSpec,
    build_tote_inventory,
    first_appearance_tote_sequence,
)
from validation.sim_engine import PlannedOrder, ReleaseUnit


ITEM_COLUMNS = ["circle", "pentagon", "trapezoid", "triangle", "star", "moon", "heart", "cross"]


@dataclass
class HeuristicPlan:
    heuristic: str
    order_rows: list[PlannedOrder]
    release_units: list[ReleaseUnit]
    order_to_conveyor: dict[int, int]
    order_sequence: list[int]
    tote_sequence: list[int]


def _orders_by_id(instance: GeneratedInstance) -> dict[int, OrderSpec]:
    return {order.order_id: order for order in instance.orders}


def _round_robin_assignment(order_ids: list[int]) -> dict[int, int]:
    return {order_id: ((idx % 4) + 1) for idx, order_id in enumerate(order_ids)}


def _least_loaded_assignment(orders: list[OrderSpec]) -> dict[int, int]:
    loads = {1: 0, 2: 0, 3: 0, 4: 0}
    assignment: dict[int, int] = {}
    for order in sorted(orders, key=lambda record: (-record.total_units, record.order_id)):
        conveyor_id = min(loads, key=loads.get)
        assignment[order.order_id] = conveyor_id
        loads[conveyor_id] += order.total_units
    return assignment


def _queues_from_order_sequence(order_sequence: list[int], order_to_conveyor: dict[int, int]) -> dict[int, list[int]]:
    queues = {1: [], 2: [], 3: [], 4: []}
    for order_id in order_sequence:
        queues[order_to_conveyor[order_id]].append(order_id)
    return queues


def _interleave_queues(queues: dict[int, list[int]]) -> list[int]:
    output: list[int] = []
    max_depth = max((len(queue) for queue in queues.values()), default=0)
    for depth in range(max_depth):
        for conveyor_id in range(1, 5):
            if depth < len(queues[conveyor_id]):
                output.append(queues[conveyor_id][depth])
    return output


def _build_order_rows(order_ids: list[int], order_to_conveyor: dict[int, int], orders_by_id: dict[int, OrderSpec]) -> list[PlannedOrder]:
    rows: list[PlannedOrder] = []
    for order_id in order_ids:
        rows.append(
            PlannedOrder(
                order_id=order_id,
                conveyor_id=order_to_conveyor[order_id],
                requirements=orders_by_id[order_id].item_qty,
            )
        )
    return rows


def _append_units_for_tote(
    units: list[ReleaseUnit],
    *,
    tote_id: int,
    item_type_ids: list[int],
    next_unit_id: int,
) -> int:
    for item_type_id in item_type_ids:
        units.append(
            ReleaseUnit(
                unit_id=next_unit_id,
                item_type_id=item_type_id,
                tote_id=tote_id,
                source_order_id=None,
            )
        )
        next_unit_id += 1
    return next_unit_id


def _units_in_original_order_for_tote(orders: list[OrderSpec], tote_id: int) -> list[int]:
    item_type_ids: list[int] = []
    for order in orders:
        for entry in order.entries:
            if entry.tote_id == tote_id:
                item_type_ids.extend([entry.item_type_id] * entry.quantity)
    return item_type_ids


def _active_orders(queues: dict[int, list[int]], finished: set[int]) -> dict[int, int]:
    active: dict[int, int] = {}
    for conveyor_id in range(1, 5):
        for order_id in queues[conveyor_id]:
            if order_id not in finished:
                active[conveyor_id] = order_id
                break
    return active


def fifo_plan(instance: GeneratedInstance) -> HeuristicPlan:
    order_sequence = [order.order_id for order in instance.orders]
    order_to_conveyor = _round_robin_assignment(order_sequence)
    order_rows = _build_order_rows(order_sequence, order_to_conveyor, _orders_by_id(instance))

    tote_sequence = first_appearance_tote_sequence(instance.orders)
    release_units: list[ReleaseUnit] = []
    next_unit_id = 1
    for tote_id in tote_sequence:
        next_unit_id = _append_units_for_tote(
            release_units,
            tote_id=tote_id,
            item_type_ids=_units_in_original_order_for_tote(list(instance.orders), tote_id),
            next_unit_id=next_unit_id,
        )

    return HeuristicPlan(
        heuristic="FIFO",
        order_rows=order_rows,
        release_units=release_units,
        order_to_conveyor=order_to_conveyor,
        order_sequence=order_sequence,
        tote_sequence=tote_sequence,
    )


def greedy_plan(instance: GeneratedInstance) -> HeuristicPlan:
    orders = list(instance.orders)
    orders_by_id = _orders_by_id(instance)
    order_sizes = {order.order_id: order.total_units for order in orders}
    spt_order = sorted([order.order_id for order in orders], key=lambda order_id: (order_sizes[order_id], order_id))

    conveyor_loads = {1: 0, 2: 0, 3: 0, 4: 0}
    order_to_conveyor: dict[int, int] = {}
    queues = {1: [], 2: [], 3: [], 4: []}
    for order_id in spt_order:
        conveyor_id = min(conveyor_loads, key=conveyor_loads.get)
        order_to_conveyor[order_id] = conveyor_id
        queues[conveyor_id].append(order_id)
        conveyor_loads[conveyor_id] += order_sizes[order_id]

    remaining = {order.order_id: deepcopy(order.item_qty) for order in orders}
    available_totes = build_tote_inventory(orders)
    queue_pos = {}
    for conveyor_id, queue in queues.items():
        for idx, order_id in enumerate(queue):
            queue_pos[order_id] = idx

    finished: set[int] = set()
    tote_sequence: list[int] = []
    while len(finished) < len(orders):
        active = _active_orders(queues, finished)
        if not active:
            break

        best_tote = None
        best_score = -1.0
        for tote_id, inventory in available_totes.items():
            score = 0.0
            for order_id in active.values():
                urgency = 1.0 / (1 + queue_pos[order_id])
                for item_type_id, qty_avail in inventory.items():
                    qty_needed = remaining[order_id].get(item_type_id, 0)
                    if qty_avail > 0 and qty_needed > 0:
                        score += min(qty_avail, qty_needed) * urgency
            if score > best_score:
                best_score = score
                best_tote = tote_id

        if best_tote is None or best_score <= 0:
            best_tote = min(available_totes)

        tote_sequence.append(best_tote)
        inventory = available_totes[best_tote]
        for order_id in [order.order_id for order in orders]:
            if order_id in finished:
                continue
            for item_type_id in list(inventory.keys()):
                if inventory[item_type_id] <= 0:
                    continue
                qty_needed = remaining[order_id].get(item_type_id, 0)
                if qty_needed <= 0:
                    continue
                used = min(inventory[item_type_id], qty_needed)
                remaining[order_id][item_type_id] -= used
                inventory[item_type_id] -= used

        if all(qty <= 0 for qty in inventory.values()):
            del available_totes[best_tote]

        for order_id in [order.order_id for order in orders]:
            if order_id not in finished and all(qty <= 0 for qty in remaining[order_id].values()):
                finished.add(order_id)

    release_units: list[ReleaseUnit] = []
    next_unit_id = 1
    for tote_id in tote_sequence:
        next_unit_id = _append_units_for_tote(
            release_units,
            tote_id=tote_id,
            item_type_ids=_units_in_original_order_for_tote(orders, tote_id),
            next_unit_id=next_unit_id,
        )

    row_order = _interleave_queues(queues)
    order_rows = _build_order_rows(row_order, order_to_conveyor, orders_by_id)

    return HeuristicPlan(
        heuristic="Greedy",
        order_rows=order_rows,
        release_units=release_units,
        order_to_conveyor=order_to_conveyor,
        order_sequence=spt_order,
        tote_sequence=tote_sequence,
    )


def order_driven_plan(instance: GeneratedInstance) -> HeuristicPlan:
    orders = list(instance.orders)
    orders_by_id = _orders_by_id(instance)
    order_work = {order.order_id: deepcopy(order.item_qty) for order in orders}
    tote_inventory = build_tote_inventory(orders)

    order_sequence = sorted([order.order_id for order in orders], key=lambda order_id: sum(order_work[order_id].values()))
    remaining_orders = deepcopy(order_work)
    available_totes = deepcopy(tote_inventory)

    tote_sequence_pairs: list[tuple[int, int]] = []
    tote_pick_sequence: dict[int, list[int]] = {}

    for order_id in order_sequence:
        while sum(remaining_orders[order_id].values()) > 0:
            best_tote = None
            best_score = 0
            for tote_id, tote_items in available_totes.items():
                score = 0
                for item_type_id, qty_needed in remaining_orders[order_id].items():
                    score += min(qty_needed, tote_items.get(item_type_id, 0))
                if score > best_score:
                    best_score = score
                    best_tote = tote_id

            if best_tote is None or best_score == 0:
                break

            tote_sequence_pairs.append((order_id, best_tote))
            tote_pick_sequence.setdefault(best_tote, [])

            for item_type_id in list(remaining_orders[order_id].keys()):
                used = min(
                    remaining_orders[order_id][item_type_id],
                    available_totes[best_tote].get(item_type_id, 0),
                )
                if used > 0:
                    tote_pick_sequence[best_tote].extend([item_type_id] * used)
                    remaining_orders[order_id][item_type_id] -= used
                    available_totes[best_tote][item_type_id] -= used

            if all(qty == 0 for qty in available_totes[best_tote].values()):
                del available_totes[best_tote]

    order_to_conveyor = {
        order_id: ((idx % 4) + 1)
        for idx, order_id in enumerate(order_sequence)
    }
    order_rows = _build_order_rows(order_sequence, order_to_conveyor, orders_by_id)

    seen_totes: set[int] = set()
    tote_sequence: list[int] = []
    for _, tote_id in tote_sequence_pairs:
        if tote_id not in seen_totes:
            seen_totes.add(tote_id)
            tote_sequence.append(tote_id)

    release_units: list[ReleaseUnit] = []
    next_unit_id = 1
    for tote_id in tote_sequence:
        next_unit_id = _append_units_for_tote(
            release_units,
            tote_id=tote_id,
            item_type_ids=tote_pick_sequence.get(tote_id, []),
            next_unit_id=next_unit_id,
        )

    return HeuristicPlan(
        heuristic="Order Driven",
        order_rows=order_rows,
        release_units=release_units,
        order_to_conveyor=order_to_conveyor,
        order_sequence=order_sequence,
        tote_sequence=tote_sequence,
    )


def assignment_first_plan(instance: GeneratedInstance) -> HeuristicPlan:
    orders = list(instance.orders)
    orders_by_id = _orders_by_id(instance)
    arrival_order = [order.order_id for order in orders]
    order_to_conveyor = _least_loaded_assignment(orders)
    queues = _queues_from_order_sequence(arrival_order, order_to_conveyor)

    remaining_by_order = {order.order_id: deepcopy(order.item_qty) for order in orders}
    remaining_totes = build_tote_inventory(orders)
    finished: set[int] = set()
    tote_sequence: list[int] = []
    release_units: list[ReleaseUnit] = []
    next_unit_id = 1

    while len(finished) < len(orders):
        active = _active_orders(queues, finished)
        if not active:
            break

        best_tote = None
        best_score = -1
        for tote_id, inventory in remaining_totes.items():
            score = 0
            for order_id in active.values():
                for item_type_id, qty_avail in inventory.items():
                    score += min(qty_avail, remaining_by_order[order_id].get(item_type_id, 0))
            if score > best_score or (score == best_score and best_tote is not None and tote_id < best_tote):
                best_tote = tote_id
                best_score = score

        if best_tote is None or best_score <= 0:
            best_tote = min(remaining_totes)

        tote_sequence.append(best_tote)
        inventory = remaining_totes.pop(best_tote)

        tote_item_order: list[int] = []
        active_order_ids = [active[conveyor_id] for conveyor_id in sorted(active)]
        other_order_ids = [order_id for order_id in arrival_order if order_id not in active_order_ids and order_id not in finished]
        priority_order_ids = active_order_ids + other_order_ids

        working_inventory = deepcopy(inventory)
        for order_id in priority_order_ids:
            for item_type_id in sorted(list(working_inventory.keys())):
                if working_inventory[item_type_id] <= 0:
                    continue
                qty_needed = remaining_by_order[order_id].get(item_type_id, 0)
                if qty_needed <= 0:
                    continue
                used = min(working_inventory[item_type_id], qty_needed)
                if used > 0:
                    tote_item_order.extend([item_type_id] * used)
                    remaining_by_order[order_id][item_type_id] -= used
                    working_inventory[item_type_id] -= used

        # Release any leftover units from the tote in deterministic item order.
        for item_type_id in sorted(working_inventory.keys()):
            if working_inventory[item_type_id] > 0:
                tote_item_order.extend([item_type_id] * working_inventory[item_type_id])

        next_unit_id = _append_units_for_tote(
            release_units,
            tote_id=best_tote,
            item_type_ids=tote_item_order,
            next_unit_id=next_unit_id,
        )

        for order_id in arrival_order:
            if order_id not in finished and all(qty <= 0 for qty in remaining_by_order[order_id].values()):
                finished.add(order_id)

    row_order = _interleave_queues(queues)
    order_rows = _build_order_rows(row_order, order_to_conveyor, orders_by_id)

    return HeuristicPlan(
        heuristic="Assignment First",
        order_rows=order_rows,
        release_units=release_units,
        order_to_conveyor=order_to_conveyor,
        order_sequence=row_order,
        tote_sequence=tote_sequence,
    )


def build_plan(instance: GeneratedInstance, heuristic: str) -> HeuristicPlan:
    normalized = heuristic.strip().lower()
    if normalized == "fifo":
        return fifo_plan(instance)
    if normalized == "greedy":
        return greedy_plan(instance)
    if normalized in {"order driven", "order_driven"}:
        return order_driven_plan(instance)
    if normalized in {"assignment first", "assignment_first"}:
        return assignment_first_plan(instance)
    raise ValueError(f"Unknown heuristic: {heuristic}")
