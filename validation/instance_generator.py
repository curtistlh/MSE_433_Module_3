from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ITEM_ID_TO_NAME = {
    0: "circle",
    1: "pentagon",
    2: "trapezoid",
    3: "triangle",
    4: "star",
    5: "moon",
    6: "heart",
    7: "cross",
}


@dataclass(frozen=True)
class OrderEntry:
    item_type_id: int
    quantity: int
    tote_id: int


@dataclass(frozen=True)
class OrderSpec:
    order_id: int
    entries: tuple[OrderEntry, ...]

    @property
    def total_units(self) -> int:
        return sum(entry.quantity for entry in self.entries)

    @property
    def item_qty(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for entry in self.entries:
            out[entry.item_type_id] = out.get(entry.item_type_id, 0) + entry.quantity
        return out


@dataclass(frozen=True)
class GeneratedInstance:
    seed: int | None
    n_orders: int
    n_itemtypes_raw: int
    n_totes: int
    orders: tuple[OrderSpec, ...]


def _read_ragged_csv(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            rows.append([cell.strip() for cell in row])
    return rows


def _to_int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(float(stripped))


def load_orders_from_three_csvs(
    order_itemtypes_csv: str | Path,
    order_quantities_csv: str | Path,
    orders_totes_csv: str | Path,
    *,
    limit: int | None = None,
) -> GeneratedInstance:
    p_types = Path(order_itemtypes_csv)
    p_qty = Path(order_quantities_csv)
    p_totes = Path(orders_totes_csv)

    rows_types = _read_ragged_csv(p_types)
    rows_qty = _read_ragged_csv(p_qty)
    rows_totes = _read_ragged_csv(p_totes)

    if len(rows_types) != len(rows_qty) or len(rows_types) != len(rows_totes):
        raise ValueError("The three CSV files must have the same number of rows.")

    if limit is not None:
        rows_types = rows_types[:limit]
        rows_qty = rows_qty[:limit]
        rows_totes = rows_totes[:limit]

    orders: list[OrderSpec] = []
    max_item_type = 0
    max_tote = 0

    for row_idx, (types_row, qty_row, totes_row) in enumerate(zip(rows_types, rows_qty, rows_totes), start=1):
        max_len = max(len(types_row), len(qty_row), len(totes_row))
        types_row = types_row + [""] * (max_len - len(types_row))
        qty_row = qty_row + [""] * (max_len - len(qty_row))
        totes_row = totes_row + [""] * (max_len - len(totes_row))

        entries: list[OrderEntry] = []
        for item_type_raw, qty_raw, tote_raw in zip(types_row, qty_row, totes_row):
            item_type_id = _to_int_or_none(item_type_raw)
            quantity = _to_int_or_none(qty_raw)
            tote_id = _to_int_or_none(tote_raw)
            if item_type_id is None or quantity is None or tote_id is None or quantity <= 0:
                continue
            entries.append(OrderEntry(item_type_id=item_type_id, quantity=quantity, tote_id=tote_id))
            max_item_type = max(max_item_type, item_type_id)
            max_tote = max(max_tote, tote_id)

        orders.append(OrderSpec(order_id=row_idx, entries=tuple(entries)))

    return GeneratedInstance(
        seed=None,
        n_orders=len(orders),
        n_itemtypes_raw=max_item_type + 1,
        n_totes=max_tote + 1,
        orders=tuple(orders),
    )


def generate_instance(seed: int) -> GeneratedInstance:
    # Mirror the notebook's behavior: each helper reseeds with the same seed,
    # so the global RNG state that generates orders is whatever remains after
    # the final "n_totes" draw.
    random.seed(seed)
    n_orders = random.randint(10, 15)

    random.seed(seed)
    n_itemtypes_raw = random.randint(7, 10)

    random.seed(seed)
    n_totes = random.randint(15, 20)

    # Physical system supports 8 readable shapes only. The notebook can
    # accidentally expose item type 8 when n_itemtypes_raw == 10; we cap the
    # usable IDs to the physical set while keeping the rest of the generation
    # logic identical.
    available_item_ids = [item_id for item_id in range(0, n_itemtypes_raw - 1) if item_id <= 7]
    if len(available_item_ids) < 3:
        raise ValueError("Generator produced fewer than 3 usable physical item types.")

    orders: list[OrderSpec] = []
    for order_id in range(1, n_orders + 1):
        order_size = random.randint(1, 3)
        item_type_ids = random.sample(available_item_ids, order_size)
        quantities = [random.randint(1, 3) for _ in range(order_size)]

        tote_ids: list[int] = []
        for entry_idx in range(order_size):
            if entry_idx == 0:
                tote_ids.append(random.randint(0, n_totes - 1))
            else:
                if random.randint(0, 1) == 0:
                    tote_ids.append(tote_ids[0])
                else:
                    tote_ids.append(random.randint(0, n_totes - 1))

        entries = tuple(
            OrderEntry(item_type_id=item_type_id, quantity=quantity, tote_id=tote_id)
            for item_type_id, quantity, tote_id in zip(item_type_ids, quantities, tote_ids)
        )
        orders.append(OrderSpec(order_id=order_id, entries=entries))

    return GeneratedInstance(
        seed=seed,
        n_orders=n_orders,
        n_itemtypes_raw=n_itemtypes_raw,
        n_totes=n_totes,
        orders=tuple(orders),
    )


def slice_instance(instance: GeneratedInstance, count: int) -> GeneratedInstance:
    sliced_orders = tuple(
        OrderSpec(order_id=new_idx, entries=order.entries)
        for new_idx, order in enumerate(instance.orders[:count], start=1)
    )
    return GeneratedInstance(
        seed=instance.seed,
        n_orders=len(sliced_orders),
        n_itemtypes_raw=instance.n_itemtypes_raw,
        n_totes=instance.n_totes,
        orders=sliced_orders,
    )


def iter_units_in_order_entry_sequence(orders: Iterable[OrderSpec]) -> list[dict[str, int]]:
    units: list[dict[str, int]] = []
    unit_id = 1
    for order in orders:
        for entry in order.entries:
            for _ in range(entry.quantity):
                units.append(
                    {
                        "unit_id": unit_id,
                        "order_id": order.order_id,
                        "item_type_id": entry.item_type_id,
                        "tote_id": entry.tote_id,
                    }
                )
                unit_id += 1
    return units


def build_tote_inventory(orders: Iterable[OrderSpec]) -> dict[int, dict[int, int]]:
    inventory: dict[int, dict[int, int]] = {}
    for order in orders:
        for entry in order.entries:
            inventory.setdefault(entry.tote_id, {})
            inventory[entry.tote_id][entry.item_type_id] = (
                inventory[entry.tote_id].get(entry.item_type_id, 0) + entry.quantity
            )
    return inventory


def first_appearance_tote_sequence(orders: Iterable[OrderSpec]) -> list[int]:
    seen: set[int] = set()
    sequence: list[int] = []
    for order in orders:
        for entry in order.entries:
            if entry.tote_id not in seen:
                seen.add(entry.tote_id)
                sequence.append(entry.tote_id)
    return sequence
