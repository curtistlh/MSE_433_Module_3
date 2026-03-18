from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = REPO_ROOT / "results" / "validation" / "simulation_validation_results.csv"
OUTPUT_PNG = REPO_ROOT / "results" / "plots" / "makespan_vs_completed_success_only.png"

HEURISTIC_ORDER = ["Assignment First", "FIFO", "Greedy", "Order Driven"]
COLORS = {
    "Assignment First": "tab:orange",
    "FIFO": "tab:blue",
    "Greedy": "tab:green",
    "Order Driven": "tab:red",
}


def main() -> None:
    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    successful = df[df["terminated_early"] == 0].copy()
    successful["orders_completed"] = successful["n_orders"]

    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=200)

    for heuristic in HEURISTIC_ORDER:
        subset = successful[successful["heuristic"] == heuristic]
        if subset.empty:
            continue
        ax.scatter(
            subset["orders_completed"],
            subset["makespan_sec"],
            s=55,
            alpha=0.8,
            color=COLORS[heuristic],
            label=heuristic,
        )

    ax.set_title("Makespan vs Orders Completed (Successful Runs Only)")
    ax.set_xlabel("Orders Completed")
    ax.set_ylabel("Makespan (sec)")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved plot to {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
