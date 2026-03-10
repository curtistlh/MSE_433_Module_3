from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .constants import ITEM_NAME_TO_ID
from .io_utils import load_orders_from_three_csvs
from .template import load_template_from_example
from .heuristics import assign_orders_to_conveyors


def _normalize_col_name(name: str) -> str:
    """Normalize column names from the simulator template.

    The provided example template uses 'cirle' (typo) rather than 'circle'.
    We normalize whitespace and fix known typos.
    """
    n = name.strip().lower()
    if n == "cirle":
        return "circle"
    return n


def build_input_dataframe(
    order_itemtypes_csv: str | Path,
    order_quantities_csv: str | Path,
    orders_totes_csv: str | Path,
    example_input_csv: str | Path,
    conveyor_assignment: Dict[int, int],
) -> pd.DataFrame:
    template = load_template_from_example(example_input_csv)
    orders = load_orders_from_three_csvs(order_itemtypes_csv, order_quantities_csv, orders_totes_csv)

    # Map template item columns to item ids
    item_cols = template.columns[1:]
    col_to_item_id: Dict[str, int] = {}
    for col in item_cols:
        key = _normalize_col_name(col)
        if key not in ITEM_NAME_TO_ID:
            raise ValueError(
                f"Template column '{col}' (normalized '{key}') not in ITEM_NAME_TO_ID mapping. "
                "Update mapping or fix template."
            )
        col_to_item_id[col] = ITEM_NAME_TO_ID[key]

    rows: List[Dict[str, int]] = []
    for o in orders:
        row: Dict[str, int] = {}
        row[template.conveyor_col] = int(conveyor_assignment[o.order_id])
        for col, item_id in col_to_item_id.items():
            row[col] = int(o.item_qty.get(item_id, 0))
        rows.append(row)

    df = pd.DataFrame(rows, columns=template.columns)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the IDEAS Clinic conveyor simulator input CSV from the three order CSVs."
    )
    parser.add_argument("--order-itemtypes", default="data/order_itemtypes.csv")
    parser.add_argument("--order-quantities", default="data/order_quantities.csv")
    parser.add_argument("--order-totes", default="data/orders_totes.csv")
    parser.add_argument("--example-input", default="data/example_input.csv")
    parser.add_argument(
        "--assign-method",
        choices=["round_robin", "balance_units"],
        default="round_robin",
        help="Heuristic for assigning orders to conveyors.",
    )
    parser.add_argument(
        "--out",
        default="outputs/simulator_input.csv",
        help="Where to write the generated simulator input CSV.",
    )

    args = parser.parse_args()

    orders = load_orders_from_three_csvs(args.order_itemtypes, args.order_quantities, args.order_totes)
    assignment = assign_orders_to_conveyors(orders, method=args.assign_method)

    df = build_input_dataframe(
        args.order_itemtypes,
        args.order_quantities,
        args.order_totes,
        args.example_input,
        assignment,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} orders to {out_path}")


if __name__ == "__main__":
    main()
