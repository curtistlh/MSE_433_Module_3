# Conveyor Belt Picking: Heuristics, MILP, and Validation

## Overview
This repository compares four approaches for the same conveyor-belt picking problem:

- `FIFO/`: fixed first-in-first-out baseline
- `Assignment First/`: assignment-first heuristic and related package code
- `Greedy Heuristic/`: greedy constructive heuristic
- `Order Driven/`: order-priority heuristic
- `MILP/`: mixed-integer optimization model
- `validation/`: shared simulator, adapters, plotting, and experiment runners

The core decision problem is to determine:

1. order-to-conveyor assignment
2. order sequence on each conveyor
3. tote release sequence
4. unit release sequence within each tote

## Repository Layout
```text
.
|-- Assignment First/
|-- FIFO/
|-- Greedy Heuristic/
|-- MILP/
|-- Order Driven/
|-- validation/
|-- results/
|   |-- plots/
|   |-- sensitivity/
|   `-- validation/
|-- MSE433_M3_data_generator.ipynb
|-- order_itemtypes.csv
|-- order_quantities.csv
`-- orders_totes.csv
```

### What belongs where
- Method-specific notebooks, source files, and exported heuristic outputs stay inside their own method folders.
- Shared simulation and experiment code lives in `validation/`.
- Generated analysis artifacts now live under `results/` instead of the repository root.
- Root-level CSV files are the common input tables used across methods.

## Problem Setup
Items are released one unit at a time onto:

- input conveyor `0` for transport only
- then the picking loop `1 -> 2 -> 3 -> 4 -> 1 -> ...`

An item can be picked at the midpoint of conveyors `1..4` if its item type is required by the active order assigned to that conveyor.

## Common Modeling Assumptions
- Conveyor start-to-end travel time: `2` seconds
- Induction spacing: `1` second per released unit
- One active order per conveyor
- One order is assigned to exactly one conveyor
- Up to four orders can be active at once
- Unpicked items recirculate until picked or the run terminates early

## Inputs
The common instance format is:

- `order_itemtypes.csv`
- `order_quantities.csv`
- `orders_totes.csv`

These files encode order contents and tote composition. Quantity values are expanded into physical unit records inside the simulation and optimization workflows.

## Method Folders

### FIFO
- Main notebook: `FIFO/FIFO_Baseline.ipynb`
- Exported output: `FIFO/grp_2_FIFO_Baseline_output.csv`
- Purpose: deterministic baseline with fixed release behavior

### Assignment First
- Main package/code: `Assignment First/warehouse-conveyor-sequencing/`
- Exported output: `Assignment First/grp_2_Assignment_First_heuristic_output.csv`
- Purpose: assign orders to conveyors first, then sequence within that structure

### Greedy Heuristic
- Main notebook: `Greedy Heuristic/greedy_heuristic.ipynb`
- Exported output: `Greedy Heuristic/grp_2_greedy_heuristic_output.csv`
- Purpose: greedy load-balancing and urgency-based release decisions

### Order Driven
- Main notebook: `Order Driven/order_driven_heurisitc.ipynb`
- Exported output: `Order Driven/grp_2_Order_Driven_heuristic_output.csv`
- Purpose: prioritize active order completion

### MILP
- Main notebook: `MILP/MILP.ipynb`
- Purpose: optimize assignment, sequencing, and release decisions jointly

## How to Run

### Common setup
1. Install Python 3.10+ and Jupyter.
2. Install the common packages used across the notebooks and MILP model:

```powershell
python -m pip install jupyter pandas numpy scipy matplotlib
```

3. Each method reads the three raw input CSV files by relative filename, so place the correct instance files inside the method folder you want to run:

- `order_itemtypes.csv`
- `order_quantities.csv`
- `orders_totes.csv`

If you want all methods to use the same instance, copy the same three CSV files into each method folder before running.

### FIFO
From the `FIFO/` folder, launch the notebook and run all cells:

```powershell
cd FIFO
jupyter notebook FIFO_Baseline.ipynb
```

Current behavior:
- reads `order_itemtypes.csv`, `order_quantities.csv`, and `orders_totes.csv` from `FIFO/`
- exports `fifo_baseline_output.csv`
- uses only the first `NUM_ORDERS` rows of the input tables by default

### Assignment First
From the `Assignment First/` folder, install the local package and run the generator:

```powershell
cd "Assignment First"
python -m pip install -e .
New-Item -ItemType Directory -Force outputs | Out-Null
$env:PYTHONPATH = "src"
python -m wareseq.generate_input --order-itemtypes data/order_itemtypes.csv --order-quantities data/order_quantities.csv --order-totes data/orders_totes.csv --example-input data/example_input.csv --assign-method balance_units --out outputs/simulator_input.csv --pick-plan-out outputs/pick_plan.csv
```

Current behavior:
- reads input files from `Assignment First/data/`
- writes the simulator input file to `Assignment First/outputs/simulator_input.csv`
- writes the pick plan to `Assignment First/outputs/pick_plan.csv`
- supports `round_robin` and `balance_units` for `--assign-method`

### Greedy Heuristic
From the `Greedy Heuristic/` folder, launch the notebook and run all cells:

```powershell
cd "Greedy Heuristic"
jupyter notebook greedy_heuristic.ipynb
```

Current behavior:
- reads `order_itemtypes.csv`, `order_quantities.csv`, and `orders_totes.csv` from `Greedy Heuristic/`
- exports `greedy_heuristic_output.csv`
- uses only the first `NUM_ORDERS` rows of the input tables by default

### Order Driven
From the `Order Driven/` folder, launch the notebook and run all cells:

```powershell
cd "Order Driven"
jupyter notebook order_driven_heurisitc.ipynb
```

Current behavior:
- reads `order_itemtypes.csv`, `order_quantities.csv`, and `orders_totes.csv` from `Order Driven/`
- exports `order_driven_heuristic_output.csv`
- currently reads only the first 6 rows of the input tables (`nrows=6`)

### MILP
From the `MILP/` folder, launch the notebook and run all cells:

```powershell
cd MILP
jupyter notebook MILP.ipynb
```

Current behavior:
- reads `order_itemtypes.csv`, `order_quantities.csv`, and `orders_totes.csv` from `MILP/`
- optimizes the makespan objective
- uses a `3600` second time limit and `0.02` MIP relative gap in the current notebook
- exports `MSE433_M3_all_results.csv`
- also generates `MSE433_M3_generated_input.csv` and `MSE433_M3_generated_input_first_6_orders.csv`

### Running a different instance
If you generate a new data instance, replace the three input CSV files in the method folder you plan to run. For the seed-based MILP experiments, each `MILP/seed_xxx/` folder already contains its own set of raw CSV files; move or copy those files into `MILP/` before running the notebook, or update the notebook paths to point to that seed folder directly.

## Validation and Analysis
Shared validation code lives in `validation/`.

Key scripts:

- `python -m validation.run_validation`
  - runs the main 50-seed validation study
  - writes outputs to `results/validation/`
- `python -m validation.plot_makespan_vs_completed`
  - builds the successful-run scatter plot
  - writes to `results/plots/makespan_vs_completed_success_only.png`
- `python -m validation.run_loop_capacity_sensitivity`
  - runs the loop-capacity sensitivity analysis
  - writes outputs to `results/sensitivity/`

## Generated Outputs

### Main validation outputs
Written to `results/validation/`:

- `simulation_validation_results.csv`
- `simulation_validation_summary.csv`
- `simulation_failure_investigation.csv`
- `physical_vs_simulation_comparison.csv`
- `physical_vs_simulation_detailed.csv`
- `simulation_validation_report.txt`

### Sensitivity outputs
Written to `results/sensitivity/`:

- `loop_capacity_sensitivity_results.csv`
- `loop_capacity_sensitivity_summary.csv`

### Plot outputs
Written to `results/plots/`:

- `makespan_vs_completed_success_only.png`

## Notes
- `order_driven_heurisitc.ipynb` keeps its original filename, including the typo, because that is the file currently tracked in the project.
- Python cache files are ignored via `.gitignore`.
- The repository now treats `results/` as the home for generated artifacts so the project root stays focused on inputs, code, and method folders.
