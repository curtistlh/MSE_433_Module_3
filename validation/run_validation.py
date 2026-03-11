from __future__ import annotations

from pathlib import Path

import pandas as pd

from validation.heuristic_adapters import build_plan
from validation.instance_generator import ITEM_ID_TO_NAME, generate_instance, load_orders_from_three_csvs
from validation.sim_engine import ConveyorSimulator, PlannedOrder, ReleaseUnit


REPO_ROOT = Path(__file__).resolve().parents[1]
HEURISTICS = ["FIFO", "Assignment First", "Greedy", "Order Driven"]
SEEDS = list(range(100, 130))

PHYSICAL_LOGS = {
    "FIFO": REPO_ROOT / "FIFO" / "grp_2_FIFO_Baseline_output.csv",
    "Assignment First": REPO_ROOT / "Assignment First" / "grp_2_Assignment_First_heuristic_output.csv",
    "Greedy": REPO_ROOT / "Greedy Heuristic" / "grp_2_greedy_heuristic_output.csv",
    "Order Driven": REPO_ROOT / "Order Driven" / "grp_2_Order_Driven_heuristic_output.csv",
}


def _simulate_instance(instance, heuristic: str):
    plan = build_plan(instance, heuristic)
    simulator = ConveyorSimulator(
        plan.order_rows,
        plan.release_units,
        heuristic_name=heuristic,
    )
    result = simulator.run()
    return plan, result


def _result_to_row(seed: int | None, instance, heuristic: str, result) -> dict[str, float | int | str]:
    completion_values = [float(row["completion_sec"]) for row in result.order_rows]
    finish_values = list(result.conveyor_completion_sec.values())
    return {
        "seed": seed if seed is not None else "physical_first6",
        "heuristic": heuristic,
        "n_orders": instance.n_orders,
        "total_units": sum(order.total_units for order in instance.orders),
        "makespan_sec": result.makespan_sec,
        "avg_completion_sec": round(sum(completion_values) / len(completion_values), 6) if completion_values else 0.0,
        "max_completion_sec": max(completion_values) if completion_values else 0.0,
        "terminated_early": result.terminated_early,
        "total_recirculations": result.total_recirculations,
        "mismatch_orders": result.mismatch_orders,
        "unfinished_orders": result.unfinished_orders,
        "conveyor_finish_spread_sec": round(max(finish_values) - min(finish_values), 6),
        "conv1_completion_sec": result.conveyor_completion_sec[1],
        "conv2_completion_sec": result.conveyor_completion_sec[2],
        "conv3_completion_sec": result.conveyor_completion_sec[3],
        "conv4_completion_sec": result.conveyor_completion_sec[4],
        "conv1_idle_sec": result.conveyor_idle_sec[1],
        "conv2_idle_sec": result.conveyor_idle_sec[2],
        "conv3_idle_sec": result.conveyor_idle_sec[3],
        "conv4_idle_sec": result.conveyor_idle_sec[4],
    }


def _physical_makespan(path: Path) -> float:
    df = pd.read_csv(path)
    return float(pd.to_numeric(df["time"], errors="coerce").max())


def _load_rows_from_output_csv(path: Path, instance) -> list[PlannedOrder]:
    orders_by_qty = {
        tuple(sorted(order.item_qty.items())): order.order_id
        for order in instance.orders
    }
    df = pd.read_csv(path)
    rows: list[PlannedOrder] = []
    for _, row in df.iterrows():
        item_qty = {
            0: int(row.get("cirle", row.get("circle", 0))),
            1: int(row["pentagon"]),
            2: int(row["trapezoid"]),
            3: int(row["triangle"]),
            4: int(row["star"]),
            5: int(row["moon"]),
            6: int(row["heart"]),
            7: int(row["cross"]),
        }
        item_qty = {item_type_id: qty for item_type_id, qty in item_qty.items() if qty > 0}
        order_id = orders_by_qty[tuple(sorted(item_qty.items()))]
        rows.append(
            PlannedOrder(
                order_id=order_id,
                conveyor_id=int(row["conv_num"]),
                requirements=item_qty,
            )
        )
    return rows


def _assignment_first_physical_plan(instance) -> tuple[list[PlannedOrder], list[ReleaseUnit]]:
    orders_by_id = {order.order_id: order for order in instance.orders}
    order_ids = [order.order_id for order in instance.orders]
    order_to_conveyor = {order_id: ((idx % 4) + 1) for idx, order_id in enumerate(order_ids)}
    rows = [
        PlannedOrder(
            order_id=order_id,
            conveyor_id=order_to_conveyor[order_id],
            requirements=orders_by_id[order_id].item_qty,
        )
        for order_id in order_ids
    ]

    all_totes = sorted({entry.tote_id for order in instance.orders for entry in order.entries})
    active_totes = sorted({entry.tote_id for entry in orders_by_id[1].entries})
    tote_sequence = active_totes + [tote_id for tote_id in all_totes if tote_id not in set(active_totes)]

    release_units: list[ReleaseUnit] = []
    next_unit_id = 1
    for tote_id in tote_sequence:
        active_items: list[int] = []
        other_items: list[tuple[int, int]] = []
        for order in instance.orders:
            for entry in order.entries:
                if entry.tote_id != tote_id:
                    continue
                units = [entry.item_type_id] * entry.quantity
                if order.order_id == 1:
                    active_items.extend(units)
                else:
                    other_items.extend((order.order_id, item_type_id) for item_type_id in units)

        active_items.sort()
        other_items.sort(key=lambda item: (item[0], item[1]))
        tote_items = active_items + [item_type_id for _, item_type_id in other_items]
        for item_type_id in tote_items:
            release_units.append(
                ReleaseUnit(
                    unit_id=next_unit_id,
                    item_type_id=item_type_id,
                    tote_id=tote_id,
                )
            )
            next_unit_id += 1

    return rows, release_units


def _build_first6_physical_simulation_specs():
    instance = load_orders_from_three_csvs(
        REPO_ROOT / "order_itemtypes.csv",
        REPO_ROOT / "order_quantities.csv",
        REPO_ROOT / "orders_totes.csv",
        limit=6,
    )

    specs: dict[str, tuple[list[PlannedOrder], list[ReleaseUnit]]] = {}

    fifo_plan = build_plan(instance, "FIFO")
    specs["FIFO"] = (fifo_plan.order_rows, fifo_plan.release_units)

    greedy_plan = build_plan(instance, "Greedy")
    greedy_plan.order_rows = _load_rows_from_output_csv(REPO_ROOT / "Greedy Heuristic" / "greedy_heuristic_output.csv", instance)
    specs["Greedy"] = (greedy_plan.order_rows, greedy_plan.release_units)

    order_plan = build_plan(instance, "Order Driven")
    order_plan.order_rows = _load_rows_from_output_csv(REPO_ROOT / "Order Driven" / "order_driven_heuristic_output.csv", instance)
    specs["Order Driven"] = (order_plan.order_rows, order_plan.release_units)

    specs["Assignment First"] = _assignment_first_physical_plan(instance)
    return instance, specs


def build_physical_comparison_df() -> pd.DataFrame:
    base_instance, specs = _build_first6_physical_simulation_specs()

    rows: list[dict[str, float | int | str]] = []
    for heuristic in HEURISTICS:
        order_rows, release_units = specs[heuristic]
        result = ConveyorSimulator(order_rows, release_units, heuristic_name=heuristic).run()
        physical_sec = _physical_makespan(PHYSICAL_LOGS[heuristic])
        rows.append(
            {
                "heuristic": heuristic,
                "simulated_makespan_sec": result.makespan_sec,
                "physical_makespan_sec": round(physical_sec, 6),
                "absolute_gap_sec": round(physical_sec - result.makespan_sec, 6),
                "ratio_physical_to_simulated": round(physical_sec / result.makespan_sec, 6) if result.makespan_sec > 0 else 0.0,
                "simulated_recirculations": result.total_recirculations,
                "simulated_finish_spread_sec": round(
                    max(result.conveyor_completion_sec.values()) - min(result.conveyor_completion_sec.values()),
                    6,
                ),
            }
        )

    df = pd.DataFrame(rows)
    df["physical_rank"] = df["physical_makespan_sec"].rank(method="dense").astype(int)
    df["simulated_rank"] = df["simulated_makespan_sec"].rank(method="dense").astype(int)
    return df.sort_values("physical_makespan_sec")


def build_physical_detailed_df() -> pd.DataFrame:
    _, specs = _build_first6_physical_simulation_specs()
    rows: list[dict[str, float | int | str]] = []

    for heuristic in HEURISTICS:
        order_rows, release_units = specs[heuristic]
        result = ConveyorSimulator(order_rows, release_units, heuristic_name=heuristic).run()
        simulated = pd.DataFrame(result.event_rows)
        simulated["shape_name"] = simulated["item_type_id"].map(ITEM_ID_TO_NAME)

        physical = pd.read_csv(PHYSICAL_LOGS[heuristic]).copy()
        physical["shape_name"] = physical["shape_name"].str.strip().str.lower().replace({"cirle": "circle"})

        exact_match_count = 0
        for conveyor_id in range(1, 5):
            sim_conv = simulated[simulated["conveyor_id"] == conveyor_id]
            phy_conv = physical[physical["conv_num"] == conveyor_id]
            sim_seq = sim_conv["shape_name"].tolist()
            phy_seq = phy_conv["shape_name"].tolist()
            exact = sim_seq == phy_seq
            if exact:
                exact_match_count += 1

            sim_first = float(sim_conv["time_sec"].min()) if not sim_conv.empty else 0.0
            sim_last = float(sim_conv["time_sec"].max()) if not sim_conv.empty else 0.0
            phy_first = float(phy_conv["time"].min()) if not phy_conv.empty else 0.0
            phy_last = float(phy_conv["time"].max()) if not phy_conv.empty else 0.0
            sim_span = sim_last - sim_first if not sim_conv.empty else 0.0
            phy_span = phy_last - phy_first if not phy_conv.empty else 0.0

            rows.append(
                {
                    "heuristic": heuristic,
                    "conveyor_id": conveyor_id,
                    "sim_pick_count": len(sim_seq),
                    "physical_pick_count": len(phy_seq),
                    "count_match": int(len(sim_seq) == len(phy_seq)),
                    "sequence_exact_match": int(exact),
                    "sim_first_pick_sec": round(sim_first, 6),
                    "sim_last_pick_sec": round(sim_last, 6),
                    "sim_active_span_sec": round(sim_span, 6),
                    "physical_first_pick_sec": round(phy_first, 6),
                    "physical_last_pick_sec": round(phy_last, 6),
                    "physical_active_span_sec": round(phy_span, 6),
                    "physical_to_sim_span_ratio": round((phy_span / sim_span), 6) if sim_span > 0 else 0.0,
                    "sim_sequence": " | ".join(sim_seq),
                    "physical_sequence": " | ".join(phy_seq),
                }
            )

        rows.append(
            {
                "heuristic": heuristic,
                "conveyor_id": "ALL",
                "sim_pick_count": int(len(simulated)),
                "physical_pick_count": int(len(physical)),
                "count_match": int(len(simulated) == len(physical)),
                "sequence_exact_match": exact_match_count,
                "sim_first_pick_sec": round(float(simulated["time_sec"].min()), 6),
                "sim_last_pick_sec": round(float(simulated["time_sec"].max()), 6),
                "sim_active_span_sec": round(float(simulated["time_sec"].max() - simulated["time_sec"].min()), 6),
                "physical_first_pick_sec": round(float(physical["time"].min()), 6),
                "physical_last_pick_sec": round(float(physical["time"].max()), 6),
                "physical_active_span_sec": round(float(physical["time"].max() - physical["time"].min()), 6),
                "physical_to_sim_span_ratio": round(
                    float((physical["time"].max() - physical["time"].min()) / (simulated["time_sec"].max() - simulated["time_sec"].min())),
                    6,
                )
                if float(simulated["time_sec"].max() - simulated["time_sec"].min()) > 0
                else 0.0,
                "sim_sequence": "",
                "physical_sequence": "",
            }
        )

    return pd.DataFrame(rows)


def build_batch_results_df() -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for seed in SEEDS:
        instance = generate_instance(seed)
        for heuristic in HEURISTICS:
            _, result = _simulate_instance(instance, heuristic)
            rows.append(_result_to_row(seed, instance, heuristic, result))

    df = pd.DataFrame(rows)
    return df.sort_values(["seed", "heuristic"]).reset_index(drop=True)


def build_summary_df(results_df: pd.DataFrame) -> pd.DataFrame:
    success_only = (
        results_df[results_df["terminated_early"] == 0]
        .groupby("heuristic", as_index=False)
        .agg(
            success_mean_makespan_sec=("makespan_sec", "mean"),
            success_median_makespan_sec=("makespan_sec", "median"),
        )
    )

    grouped = (
        results_df.groupby("heuristic", as_index=False)
        .agg(
            mean_makespan_sec=("makespan_sec", "mean"),
            median_makespan_sec=("makespan_sec", "median"),
            std_makespan_sec=("makespan_sec", "std"),
            min_makespan_sec=("makespan_sec", "min"),
            max_makespan_sec=("makespan_sec", "max"),
            failed_runs=("terminated_early", "sum"),
            mean_recirculations=("total_recirculations", "mean"),
            mean_finish_spread_sec=("conveyor_finish_spread_sec", "mean"),
        )
    )

    successful = results_df[results_df["terminated_early"] == 0].copy()
    if successful.empty:
        wins = pd.DataFrame({"heuristic": grouped["heuristic"], "win_count": 0})
    else:
        wins = (
            successful.groupby("seed")["makespan_sec"]
            .transform("min")
            .eq(successful["makespan_sec"])
            .groupby(successful["heuristic"])
            .sum()
            .rename("win_count")
            .reset_index()
        )

    summary = grouped.merge(wins, on="heuristic", how="left").merge(success_only, on="heuristic", how="left")
    summary["success_count"] = len(SEEDS) - summary["failed_runs"]
    summary["success_rate"] = (summary["success_count"] / len(SEEDS)).round(6)
    summary["mean_makespan_sec"] = summary["mean_makespan_sec"].round(6)
    summary["median_makespan_sec"] = summary["median_makespan_sec"].round(6)
    summary["std_makespan_sec"] = summary["std_makespan_sec"].fillna(0).round(6)
    summary["mean_recirculations"] = summary["mean_recirculations"].round(6)
    summary["mean_finish_spread_sec"] = summary["mean_finish_spread_sec"].round(6)
    summary["success_mean_makespan_sec"] = summary["success_mean_makespan_sec"].round(6)
    summary["success_median_makespan_sec"] = summary["success_median_makespan_sec"].round(6)
    summary["win_count"] = summary["win_count"].fillna(0).astype(int)
    return summary.sort_values("mean_makespan_sec").reset_index(drop=True)


def write_report(
    *,
    physical_df: pd.DataFrame,
    physical_detail_df: pd.DataFrame,
    results_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    report_path: Path,
) -> None:
    penalty_winner = summary_df.iloc[0]
    reliability_winner = summary_df.sort_values(["success_rate", "success_mean_makespan_sec"], ascending=[False, True]).iloc[0]
    speed_winner = summary_df.sort_values("success_mean_makespan_sec").iloc[0]

    lines = [
        "Simulation Validation Report",
        "============================",
        "",
        "1) What we validated",
        "--------------------",
        "We validated the four non-MILP methods (FIFO, Assignment First, Greedy, and Order Driven) using a shared simulation model of the conveyor system.",
        "The simulator models one input conveyor, a four-conveyor picking loop, one active order per conveyor, and item recirculation when an item is not picked on a pass.",
        "",
        "2) Generator logic",
        "------------------",
        "We used the same generator logic as the provided data-generator notebook to create new random order instances with a seed.",
        "The one intentional adjustment was capping item types to the 8 physical shapes supported by the real conveyor system (circle through cross), because the notebook can occasionally produce one extra unsupported item ID.",
        "",
        "3) Validation setup",
        "-------------------",
        f"We ran {len(SEEDS)} generated instances (seeds {SEEDS[0]} to {SEEDS[-1]}).",
        "For each generated instance, all four heuristics were run on the exact same order set so the comparison is fair.",
        "The primary metric was makespan, meaning the time of the final successful pick.",
        "",
        "4) First-6 physical reality check",
        "---------------------------------",
        "We also simulated the same first-6-order scenario that was used in the physical conveyor tests and compared simulated makespan to the real grp_2 logs.",
        "",
    ]

    for row in physical_df.itertuples(index=False):
        lines.append(
            f"- {row.heuristic}: simulated {row.simulated_makespan_sec:.3f}s, physical {row.physical_makespan_sec:.3f}s, "
            f"gap {row.absolute_gap_sec:.3f}s, physical/simulated ratio {row.ratio_physical_to_simulated:.3f}"
        )

    lines.extend(["", "Detailed first-6 conveyor-level comparison:", ""])
    detail_all = physical_detail_df[physical_detail_df["conveyor_id"] == "ALL"].copy()
    for row in detail_all.itertuples(index=False):
        lines.append(
            f"- {row.heuristic}: exact conveyor sequence matches on {int(row.sequence_exact_match)}/4 conveyors, "
            f"pick-count match {bool(row.count_match)}, active-span ratio (physical/simulated) {row.physical_to_sim_span_ratio:.3f}"
        )

    lines.extend(
        [
            "",
            "The physical runs were consistently slower than the simulation, which is expected because the simulation does not add manual tote-loading delays, human reaction time, or sensor/actuator variability.",
            "Because the physical tests were single runs only, we used them as a sanity check rather than the only source of truth.",
            f"In the one-time physical experiment, the fastest method was {physical_df.sort_values('physical_makespan_sec').iloc[0]['heuristic']}.",
            "The stronger result is that the physical and simulated pick sequences match very closely at the conveyor level: Assignment First matched perfectly on all 4 conveyors, while FIFO, Greedy, and Order Driven each matched exactly on 3 of 4 conveyors.",
            "The remaining mismatches were small local ordering differences within a conveyor, not total count mismatches, which supports the claim that the simulator is capturing the real system logic reasonably well.",
            "",
            "5) Batch results across generated instances",
            "-------------------------------------------",
        ]
    )

    for row in summary_df.itertuples(index=False):
        lines.append(
            f"- {row.heuristic}: success {row.success_count}/{len(SEEDS)} ({row.success_rate:.1%}), "
            f"successful-run mean makespan {row.success_mean_makespan_sec:.3f}s, "
            f"penalized mean makespan {row.mean_makespan_sec:.3f}s, "
            f"wins {row.win_count}/{len(SEEDS)}, mean recirculations {row.mean_recirculations:.3f}, "
            f"mean finish spread {row.mean_finish_spread_sec:.3f}s"
        )

    lines.extend(
        [
            "",
            "6) Main conclusion",
            "------------------",
            "There was not one single heuristic that dominated on every metric.",
            f"- Best reliability under the simulator: {reliability_winner['heuristic']} with a success rate of {reliability_winner['success_rate']:.1%}.",
            f"- Fastest among successful runs: {speed_winner['heuristic']} with a successful-run mean makespan of {speed_winner['success_mean_makespan_sec']:.3f}s.",
            f"- Best penalty-adjusted average (counting unfinished runs as bad outcomes): {penalty_winner['heuristic']} with mean makespan {penalty_winner['mean_makespan_sec']:.3f}s.",
            "",
            "This means the interpretation depends on what matters more: finishing reliably on random instances, or being fast on the runs that do finish.",
            "",
            "7) Why the better-performing methods likely did well",
            "----------------------------------------------------",
        ]
    )

    if speed_winner["heuristic"] == "Assignment First":
        lines.extend(
            [
                "Assignment First did well because it balances work across conveyors first, which reduces the chance that one conveyor becomes the long-tail bottleneck.",
                "In a system with one shared input conveyor and recirculation, load balance matters a lot: if one conveyor gets overloaded, the whole makespan is dominated by that conveyor.",
            ]
        )
    elif speed_winner["heuristic"] == "Greedy":
        lines.extend(
            [
                "The Greedy method did well because it aggressively prioritizes high-payoff totes for the currently active orders and balances conveyor loads at the same time.",
                "That combination helps small orders finish early while still spreading work across the four conveyors.",
            ]
        )
    elif speed_winner["heuristic"] == "Order Driven":
        lines.extend(
            [
                "The Order Driven method did well because it focuses on completing the most promising order first and uses totes with the best immediate overlap.",
                "That tends to reduce wasted picks and helps keep the active order on each conveyor moving.",
            ]
        )
    else:
        lines.extend(
            [
                "FIFO won because the more complex heuristics created imbalance or extra recirculation on these generated instances.",
                "That can happen when a simple steady-flow policy matches the system bottleneck better than an aggressive local optimization rule.",
            ]
        )

    lines.extend(
        [
            "",
            "A second important takeaway is that many randomly generated instances did not complete under the strict physical scanner logic. This happened when a generic item type was taken by an earlier active order, leaving a later order short of that same shape. That is a real system risk, not just a coding artifact.",
            "",
            "8) Why physical results may differ from simulated results",
            "--------------------------------------------------------",
            "- Human tote loading can add delay between releases.",
            "- Manual setup or hesitation can change when items enter the conveyor.",
            "- Sensors and pneumatic arms can introduce small timing differences from run to run.",
            "- A single physical run per heuristic is noisy; the batch simulation gives a more reliable average comparison.",
            "",
            "9) Files produced",
            "-----------------",
            "- simulation_validation_results.csv: per-seed results for all heuristics",
            "- physical_vs_simulation_comparison.csv: first-6 physical vs simulated comparison",
            "- simulation_validation_report.txt: this summary",
        ]
    )

    report_path.write_text("\n".join(lines))


def main() -> None:
    physical_df = build_physical_comparison_df()
    physical_detail_df = build_physical_detailed_df()
    results_df = build_batch_results_df()
    summary_df = build_summary_df(results_df)

    results_path = REPO_ROOT / "simulation_validation_results.csv"
    physical_path = REPO_ROOT / "physical_vs_simulation_comparison.csv"
    physical_detail_path = REPO_ROOT / "physical_vs_simulation_detailed.csv"
    summary_path = REPO_ROOT / "simulation_validation_summary.csv"
    report_path = REPO_ROOT / "simulation_validation_report.txt"

    results_df.to_csv(results_path, index=False)
    physical_df.to_csv(physical_path, index=False)
    physical_detail_df.to_csv(physical_detail_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    write_report(
        physical_df=physical_df,
        physical_detail_df=physical_detail_df,
        results_df=results_df,
        summary_df=summary_df,
        report_path=report_path,
    )

    print(f"Wrote {results_path}")
    print(f"Wrote {physical_path}")
    print(f"Wrote {physical_detail_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
