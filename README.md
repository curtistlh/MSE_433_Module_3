# Conveyor Belt Picking: MILP and Heuristic Methods

## Project Overview
This repository contains four approaches for the same conveyor-belt picking problem:
- `FIFO/` : fixed first-in-first-out baseline simulation
- `Greedy Heuristic/` : SPT + least-loaded conveyor assignment + urgency tote selection
- `Order Driven/` : SRPT order-first heuristic + best-match tote selection
- `MILP/` : mixed-integer linear programming optimization model

## Problem Statement
Totes contain items needed by customer orders. Items are released one-by-one and move through the conveyor system as:
- input conveyor `0` (transport only, no picking)
- then picking loop `1 -> 2 -> 3 -> 4 -> 1 -> ...`

An item can be picked at the midpoint of conveyors `1..4` if its item type is needed by the order currently assigned to that conveyor.

The planning decisions are:
1. order-to-conveyor assignment
2. order processing sequence
3. tote release sequence
4. item release sequence within each tote

## Common Assumptions
- Conveyor travel time from start to end: 2 seconds.
- Pick point is at conveyor midpoint (1 second from conveyor start).
- Input conveyor adds transport delay before item enters conveyor 1.
- One conveyor handles one active order at a time.
- One order is handled by only one conveyor (no split across conveyors).
- Up to 4 orders can be processed simultaneously (one per conveyor 1..4).

## Constraints Represented in the Models
- Each demanded unit must be picked.
- Tote units are released in sequence and cannot be removed from the flow except by a valid pick.
- Recirculation occurs when an item is not picked on a pass.
- Conveyor-level non-overlap for orders (strictly enforced in MILP, approximated in heuristics).

## Data Format
Each method uses the same base input tables:
- `order_itemtypes.csv`
- `order_quantities.csv`
- `orders_totes.csv`

Interpretation:
- each row = one order
- each column position links item type, quantity, and tote id
- quantity expands into physical unit records

## Methodologies

### 1) FIFO Baseline (`FIFO/FIFO_Baseline.ipynb`)
What it does:
- Uses hardcoded order definitions, conveyor assignments, tote contents, and tote sequence.
- Builds one FIFO induction queue from the fixed tote sequence.
- Simulates belt movement step-by-step with transfer, diversion, internal movement, and controlled induction.

Key characteristics:
- Not optimization-driven.
- Conveyor assignment is pre-fixed in code.
- Tote release sequence is pre-fixed in code.
- Useful as a deterministic baseline simulation.

Outputs:
- Console log of picks/completions.
- Total cumulative completion time from the simulation loop.

Important note:
- This notebook does not currently read the CSV files directly for planning logic; configuration is embedded in code.

### 2) Greedy Heuristic (`Greedy Heuristic/greedy_heuristic.ipynb`)
What it does:
- Reads CSV data (currently `NUM_ORDERS = 6`).
- Phase 1: orders sorted by SPT (shortest processing time by unit count).
- Phase 2: each order assigned to the least-loaded conveyor.
- Phase 3: greedy tote choice by urgency score over currently active orders.
- Builds slot release schedule and computes recirculation-aware pick times analytically.

Key characteristics:
- Fast constructive heuristic.
- Balances conveyor loads greedily.
- Tote sequencing prioritizes immediate payoff for active orders.
- No optimality guarantee.

Outputs:
- `greedy_heuristic_output.csv`
- printed schedule, order timing, and heuristic objective.

Important note:
- Output column currently uses `cirle` (typo) instead of `circle`.

### 3) Order-Driven Heuristic (`Order Driven/order_driven_heurisitc.ipynb`)
What it does:
- Reads CSV data (currently first 6 orders via `nrows=6`).
- Orders sorted by SRPT-style remaining work.
- For each current order, repeatedly picks the tote with best immediate item overlap.
- Records tote loading sequence and item pick sequence per tote.
- Uses round-robin order-to-conveyor assignment for timing and output generation.

Key characteristics:
- Strong order-priority behavior.
- Tote choice focuses on current order fulfillment.
- Conveyor assignment is not optimized jointly; it is assigned by sequence position.
- No optimality guarantee.

Outputs:
- `order_driven_heuristic_output.csv`
- printed order sequence, tote sequence, and estimated total time.

Important note:
- Notebook filename is `order_driven_heurisitc.ipynb` (typo in filename).

### 4) MILP Optimization (`MILP/MILP.ipynb`)
What it does:
- Reads full CSV data (all rows by default).
- Optimizes jointly:
  - order-to-conveyor assignment
  - per-conveyor order timing
  - tote contiguous block placement
  - unit-to-release-slot assignment
  - recirculation loop count per unit
- Objective: minimize sum of order completion times.

Model highlights:
- Binary assignment variables for unit-slot, tote-start, slot-tote, and order-conveyor.
- Continuous/integer timing variables for release slot, start/completion times, and recirculation loops.
- Recirculation-aware timing constraints linked via big-M activation.
- Per-conveyor non-overlap constraints.

Solver configuration (current notebook):
- `time_limit = 3600` seconds
- `mip_rel_gap = 0.02`
- no fallback reruns (`retry_time_limits = ()`)

Outputs:
- `MSE433_M3_all_results.csv`
- `MSE433_M3_generated_input.csv`
- `MSE433_M3_generated_input_first_6_orders.csv`

## Method Comparison (At a Glance)

| Method | Uses full orders by default | Joint conveyor assignment decision | Tote sequence decision | Item release sequence decision | Recirculation modeled | Optimality guarantee |
|---|---|---|---|---|---|---|
| FIFO Baseline | No (hardcoded config) | No (fixed in code) | No (fixed in code) | Indirect via fixed queue | Yes (discrete simulation) | No |
| Greedy Heuristic | No (`NUM_ORDERS=6`) | Yes (greedy least-load) | Yes (urgency score) | Yes (from tote sequence + unit order) | Yes (analytic timing with loops) | No |
| Order-Driven Heuristic | No (`nrows=6`) | No (round-robin) | Yes (best-match to active order) | Yes (logged picks per tote) | Yes (coarse loop-time simulation) | No |
| MILP | Yes | Yes (optimized) | Yes (optimized) | Yes (optimized) | Yes (constraint-based recirculation) | Best incumbent; proven optimal only if solver closes gap |

## How to Run
1. Open the notebook in the target method folder.
2. Make sure that folder has the three CSV input files.
3. Run all cells in order.

Recommended Python packages:
- `numpy`
- `pandas`
- `scipy` (required for MILP)
- `jupyter`

## Known Limitations
- FIFO notebook currently uses embedded order/tote configuration instead of dynamic CSV-driven planning.
- Greedy and Order-Driven notebooks currently default to first 6 orders.
- Heuristic methods do not provide optimality certificates.
- MILP quality depends on solver time limit and mip gap settings.

## Folder Structure
- `FIFO/`
  - `FIFO_Baseline.ipynb`
- `Greedy Heuristic/`
  - `greedy_heuristic.ipynb`
  - `greedy_heuristic_output.csv`
- `Order Driven/`
  - `order_driven_heurisitc.ipynb`
  - `order_driven_heuristic_output.csv`
- `MILP/`
  - `MILP.ipynb`
  - `MSE433_M3_all_results.csv`
  - `MSE433_M3_generated_input.csv`
  - `MSE433_M3_generated_input_first_6_orders.csv`
