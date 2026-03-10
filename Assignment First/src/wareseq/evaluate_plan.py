from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd


def _normalize_col_name(name: str) -> str:
    n = name.strip().lower()
    if n == "cirle":
        return "circle"
    return n


def _load_order_totals(sim_input_csv: str | Path) -> Tuple[pd.DataFrame, Dict[int, int]]:
    df = pd.read_csv(sim_input_csv)
    if df.empty:
        raise ValueError("Simulator input CSV is empty")

    conv_col = df.columns[0]
    item_cols = list(df.columns[1:])
    out = df.copy()

    for c in item_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)

    out["order_id"] = range(1, len(out) + 1)
    out["required_items"] = out[item_cols].sum(axis=1)
    order_to_conv = dict(zip(out["order_id"], pd.to_numeric(out[conv_col], errors="coerce").fillna(0).astype(int)))
    return out[["order_id", "required_items"]], order_to_conv


def evaluate(
    sim_input_csv: str | Path,
    pick_plan_csv: str | Path,
    pick_interval_sec: float,
    belt_start_to_box_sec: float,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    order_totals, order_to_conv = _load_order_totals(sim_input_csv)
    picks = pd.read_csv(pick_plan_csv)

    required_cols = {"sequence", "order_id"}
    missing = required_cols - set(picks.columns)
    if missing:
        raise ValueError(f"Pick plan is missing required columns: {sorted(missing)}")

    picks = picks.copy()
    picks["sequence"] = pd.to_numeric(picks["sequence"], errors="raise").astype(int)
    picks["order_id"] = pd.to_numeric(picks["order_id"], errors="raise").astype(int)
    picks = picks.sort_values("sequence")

    picks["release_time_sec"] = (picks["sequence"] - 1) * pick_interval_sec
    picks["arrival_time_sec"] = picks["release_time_sec"] + belt_start_to_box_sec

    plan_counts = picks.groupby("order_id", as_index=False).size().rename(columns={"size": "planned_items"})
    first_last = picks.groupby("order_id", as_index=False).agg(
        first_arrival_sec=("arrival_time_sec", "min"),
        completion_time_sec=("arrival_time_sec", "max"),
    )

    order_metrics = order_totals.merge(plan_counts, on="order_id", how="left").merge(first_last, on="order_id", how="left")
    order_metrics["planned_items"] = order_metrics["planned_items"].fillna(0).astype(int)
    order_metrics["first_arrival_sec"] = order_metrics["first_arrival_sec"].fillna(0.0)
    order_metrics["completion_time_sec"] = order_metrics["completion_time_sec"].fillna(0.0)
    order_metrics["item_delta"] = order_metrics["planned_items"] - order_metrics["required_items"]
    order_metrics["conveyor_id"] = order_metrics["order_id"].map(order_to_conv).fillna(0).astype(int)

    completion = order_metrics["completion_time_sec"]
    makespan = float(completion.max()) if len(order_metrics) else 0.0
    total_items = int(order_metrics["planned_items"].sum())
    throughput = (total_items / makespan) if makespan > 0 else 0.0
    mismatch_orders = int((order_metrics["item_delta"] != 0).sum())

    summary = pd.DataFrame(
        {
            "metric": [
                "orders",
                "total_items_planned",
                "total_items_required",
                "mismatch_orders",
                "makespan_sec",
                "avg_completion_sec",
                "p95_completion_sec",
                "throughput_items_per_sec",
            ],
            "value": [
                int(len(order_metrics)),
                total_items,
                int(order_metrics["required_items"].sum()),
                mismatch_orders,
                round(makespan, 3),
                round(float(completion.mean()) if len(order_metrics) else 0.0, 3),
                round(float(completion.quantile(0.95)) if len(order_metrics) else 0.0, 3),
                round(throughput, 3),
            ],
        }
    )

    order_metrics = order_metrics[
        [
            "order_id",
            "conveyor_id",
            "required_items",
            "planned_items",
            "item_delta",
            "first_arrival_sec",
            "completion_time_sec",
        ]
    ].sort_values("order_id")

    return order_metrics, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pick plan timing and order completion metrics.")
    parser.add_argument("--sim-input", default="outputs/simulator_input.csv")
    parser.add_argument("--pick-plan", default="outputs/pick_plan.csv")
    parser.add_argument("--pick-interval-sec", type=float, default=1.0)
    parser.add_argument(
        "--belt-seconds-start-to-end",
        type=float,
        default=2.0,
        help="Conveyor travel time from start to end.",
    )
    parser.add_argument(
        "--belt-seconds-start-to-box",
        type=float,
        default=None,
        help="Travel time from start to order box. If omitted, uses half of start-to-end.",
    )
    parser.add_argument("--order-metrics-out", default="outputs/order_metrics.csv")
    parser.add_argument("--summary-out", default="outputs/metrics_summary.csv")
    args = parser.parse_args()

    if args.pick_interval_sec <= 0:
        raise ValueError("--pick-interval-sec must be > 0")
    if args.belt_seconds_start_to_end <= 0:
        raise ValueError("--belt-seconds-start-to-end must be > 0")

    belt_start_to_box_sec = (
        args.belt_seconds_start_to_end / 2.0
        if args.belt_seconds_start_to_box is None
        else args.belt_seconds_start_to_box
    )
    if belt_start_to_box_sec < 0:
        raise ValueError("--belt-seconds-start-to-box must be >= 0")

    order_metrics, summary = evaluate(
        sim_input_csv=args.sim_input,
        pick_plan_csv=args.pick_plan,
        pick_interval_sec=args.pick_interval_sec,
        belt_start_to_box_sec=belt_start_to_box_sec,
    )

    order_out = Path(args.order_metrics_out)
    summary_out = Path(args.summary_out)
    order_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    order_metrics.to_csv(order_out, index=False)
    summary.to_csv(summary_out, index=False)

    print(f"Wrote order metrics to {order_out}")
    print(f"Wrote summary metrics to {summary_out}")


if __name__ == "__main__":
    main()
