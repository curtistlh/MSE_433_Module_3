from __future__ import annotations

from pathlib import Path

import pandas as pd

from validation.heuristic_adapters import build_plan
from validation.instance_generator import generate_instance
from validation.run_validation import HEURISTICS, SEEDS
from validation.sim_engine import ConveyorSimulator


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results" / "sensitivity"
CAPACITIES = [5, 7, 10]


def run_once(seed: int, heuristic: str, capacity: int) -> dict[str, float | int | str]:
    instance = generate_instance(seed)
    plan = build_plan(instance, heuristic)
    simulator = ConveyorSimulator(
        plan.order_rows,
        plan.release_units,
        heuristic_name=heuristic,
        max_loop_items=capacity,
    )
    result = simulator.run()
    orders_completed = result.total_picks - result.unfinished_orders
    return {
        "capacity": capacity,
        "seed": seed,
        "heuristic": heuristic,
        "n_orders": len(instance.orders),
        "orders_completed": len(simulator.completed_orders),
        "terminated_early": result.terminated_early,
        "makespan_sec": result.makespan_sec,
    }


def build_results_df() -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for capacity in CAPACITIES:
        for seed in SEEDS:
            for heuristic in HEURISTICS:
                rows.append(run_once(seed, heuristic, capacity))
    return pd.DataFrame(rows).sort_values(["capacity", "seed", "heuristic"]).reset_index(drop=True)


def build_summary_df(results_df: pd.DataFrame) -> pd.DataFrame:
    success_only = (
        results_df[results_df["terminated_early"] == 0]
        .groupby(["capacity", "heuristic"], as_index=False)
        .agg(
            success_count=("makespan_sec", "size"),
            avg_makespan_success_sec=("makespan_sec", "mean"),
        )
    )

    overall = (
        results_df.groupby(["capacity", "heuristic"], as_index=False)
        .agg(
            total_runs=("seed", "size"),
            failed_runs=("terminated_early", "sum"),
            avg_orders_completed=("orders_completed", "mean"),
        )
    )

    summary = overall.merge(success_only, on=["capacity", "heuristic"], how="left")
    summary["success_count"] = summary["success_count"].fillna(0).astype(int)
    summary["avg_makespan_success_sec"] = summary["avg_makespan_success_sec"].round(6)
    summary["success_rate"] = (summary["success_count"] / summary["total_runs"]).round(6)
    summary["avg_orders_completed"] = summary["avg_orders_completed"].round(6)
    return summary[["capacity", "heuristic", "success_count", "success_rate", "avg_makespan_success_sec", "avg_orders_completed"]]


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results_df = build_results_df()
    summary_df = build_summary_df(results_df)

    results_path = RESULTS_DIR / "loop_capacity_sensitivity_results.csv"
    summary_path = RESULTS_DIR / "loop_capacity_sensitivity_summary.csv"
    results_df.to_csv(results_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print(summary_df.to_string(index=False))
    print(f"\nSaved detailed results to {results_path}")
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
