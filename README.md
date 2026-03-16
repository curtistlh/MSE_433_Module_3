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
- Objective: minimize makespan of completing all orders.

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


#### Detailed MILP Formulation

##### MILP Decisions
The MILP jointly decides:
- Per-conveyor order sequence (orders on the same conveyor are non-overlapping; different conveyors may run in parallel)
- Tote release sequence (when each tote block appears)
- Item pick sequence (which physical unit is picked at each release slot)
- Order-to-conveyor assignment (each order assigned to exactly one conveyor)

##### Data Representation
Input data (from CSV files) are transformed into physical item units. Each unit has:
- Order id
- Item type
- Tote id

If a quantity is q for an item/order entry, the model creates q separate unit records.

##### Index Sets
- U: set of physical units, size N
- S: set of release slots, size N
- T: set of totes
- O: set of orders
- C: set of picking conveyors {1,2,3,4} (input conveyor 0 is non-picking)

##### Main Parameters
- slot_time_sec: release-slot spacing in seconds (default 1 second)
- belt_time_sec: conveyor traversal time from start to end (2 seconds)
- L_t: number of units belonging to tote t
- Big-M constants for sequencing and conditional timing

##### Decision Variables
- x_{u,s} in {0,1}: unit u is assigned to release slot s
- y_{t,k} in {0,1}: tote t starts at slot k
- w_{t,s} in {0,1}: slot s belongs to tote t block
- p_u >= 0: release slot index of unit u
- k_u in Z_+: recirculation loop count for unit u
- a_{o,c} in {0,1}: order o assigned to conveyor c
- S_o >= 0: start time of order o
- C_o >= 0: completion time of order o
- r_{i,j} in {0,1} for i<j: binary order precedence selector (i before j vs j before i)

##### Objective
Minimize makespan

##### Core Constraints

1) Assignment and slot feasibility:
- Each unit is released exactly once
- Each release slot contains exactly one unit

2) Tote contiguity and release structure:
- Each tote selects exactly one start slot
- Slots covered by a tote are contiguous with length equal to that tote's unit count
- Every slot belongs to exactly one tote block
- A unit can only be released in slots belonging to its tote block

3) Order-to-conveyor assignment:
- Each order is assigned to exactly one conveyor:
  sum_{c in C} a_{o,c} = 1

4) Recirculation-aware pick timing:
For a unit u of order o assigned to picking conveyor c in {1,2,3,4}:
- Release time = slot_time_sec * p_u
- Item is picked at conveyor midpoint, so midpoint offset = belt_time_sec/2 = 1 second once it reaches a conveyor start
- Input conveyor delay = belt_time_sec (2 seconds) from load point to conveyor 1 start
- Base travel offset to conveyor c midpoint = belt_time_sec + (c-1)*belt_time_sec + belt_time_sec/2
- Loop period = 4*belt_time_sec (full loop among 1->2->3->4->1)
- Pick time = slot_time_sec*p_u + (belt_time_sec + (c-1)*belt_time_sec + belt_time_sec/2) + (4*belt_time_sec)*k_u

The model links this pick-time expression to order start/completion bounds using big-M conditioning with a_{o,c}.

5) Order start/completion definition:
- S_o is bounded above by all pick times of units in order o
- C_o is bounded below by all pick times of units in order o
- S_o <= C_o

6) Per-conveyor one-order-at-a-time logic:
For each order pair (i,j) and each conveyor c, disjunctive constraints are activated only when both orders are assigned to conveyor c.

This enforces:
- orders on the same conveyor cannot overlap,
- orders on different conveyors may overlap.

Therefore, at most 4 orders can be processed simultaneously (one active order per conveyor).

##### Mathematical MILP Formulation

###### Sets and Indices
- `U`: set of physical item units, with `|U| = N`
- `S = {0, ..., N-1}`: release slots
- `T`: set of totes
- `O`: set of orders
- `C = {1,2,3,4}`: picking conveyors (input conveyor 0 is non-picking)
- `P_o subseteq U`: units belonging to order `o`
- `Q_t subseteq U`: units belonging to tote `t`

###### Parameters
- `tau`: slot release spacing in seconds (`slot_time_sec`, default 1)
- `B`: conveyor start-to-end travel time in seconds (`belt_time_sec`, default 2)
- `L_t = |Q_t|`: number of units in tote `t`
- `N = |U|`: total number of physical units
- `M`: sufficiently large big-M constant
- Loop period among picking conveyors: `Gamma = 4B`
- Base offset to pick point on conveyor `c in {1,2,3,4}`:

```math
b_c = B + (c-1)B + \frac{B}{2}
```

###### Decision Variables
- `x_{u,s} in {0,1}`: unit `u` is released at slot `s`
- `y_{t,k} in {0,1}`: tote `t` starts at slot `k`
- `w_{t,s} in {0,1}`: slot `s` belongs to tote `t`'s contiguous block
- `a_{o,c} in {0,1}`: order `o` assigned to conveyor `c`
- `p_u in [0,N-1]`: release slot index of unit `u`
- `k_u in Z_{>=0}`: recirculation loops for unit `u`, with implementation bound `k_u <= N`
- `S_o, C_o >= 0`: start and completion time of order `o`
- `r_{i,j} in {0,1}` for `i<j`: sequencing selector for order pair `(i,j)`

###### Objective

```math
\min C_{\max} \quad \text{with } C_o \le C_{\max},\ \forall o \in O
```

###### Constraints

**1) Unit/slot assignment**

```math
\sum_{s \in S} x_{u,s} = 1 \quad \forall u \in U
```

```math
\sum_{u \in U} x_{u,s} = 1 \quad \forall s \in S
```

**2) Tote contiguity and slot coverage**

```math
\sum_{k=0}^{N-L_t} y_{t,k} = 1 \quad \forall t \in T
```

```math
w_{t,s} = \sum_{k=\max(0,s-L_t+1)}^{\min(s,N-L_t)} y_{t,k}
\quad \forall t \in T,\ \forall s \in S
```

```math
\sum_{t \in T} w_{t,s} = 1 \quad \forall s \in S
```

```math
x_{u,s} \le w_{t(u),s} \quad \forall u \in U,\ \forall s \in S
```

**3) Release slot index**

```math
p_u = \sum_{s \in S} s\,x_{u,s} \quad \forall u \in U
```

**4) Recirculation-loop bound (implementation)**

```math
0 \le k_u \le N,\quad k_u \in \mathbb{Z}_{\ge 0} \quad \forall u \in U
```

Purpose: this is a computational bound to keep the MILP finite and numerically tractable (tighter time bounds and big-M scaling). It is not a physical rule; if the solution hits this bound, increase the cap and re-solve.

**5) One-conveyor-per-order**

```math
\sum_{c \in C} a_{o,c} = 1 \quad \forall o \in O
```

**6) Recirculation-aware timing (for `u in P_o`, `c in C`)**

```math
C_o \ge \tau p_u + b_c + \Gamma k_u - M(1-a_{o,c})
```

```math
S_o \le \tau p_u + b_c + \Gamma k_u + M(1-a_{o,c})
```

```math
S_o \le C_o \quad \forall o \in O
```

**7) Per-conveyor non-overlap (orders `i<j`, conveyor `c`)**

```math
C_i - S_j \le M\,(3-a_{i,c}-a_{j,c}-r_{i,j})
```

```math
C_j - S_i \le M\,(2-a_{i,c}-a_{j,c}+r_{i,j})
```

These are active only when both orders are assigned to the same conveyor; therefore, one conveyor cannot process two overlapping orders, while different conveyors may run in parallel.

###### Interpretation of Each Constraint
- Objective: minimizes total makespan of completing all orders.
- 1) Ensures one unit per slot and one slot per unit.
- 2) Forces each tote into one contiguous release block and keeps unit releases inside its tote block.
- 3) Converts slot assignment binaries into numeric release slot index `p_u`.
- 4) Caps recirculation loops for tractability (computational, not physical).
- 5) Assigns each order to exactly one conveyor.
- 6) Links order start/completion bounds to recirculation-aware pick timing.
- 7) Enforces one active order at a time per conveyor while allowing parallelism across conveyors.

###### How to Read MILP Solver Outputs
- `order_to_conveyor`: optimized order-to-conveyor assignment.
- `belt_sequence`: per-unit event timeline with release/pick time, conveyor, and recirculation loops.
- `order_start_seconds`, `order_completion_seconds`: decoded order timing values.
- `order_sequence`: reporting order based on first pick start time (not a separate decision variable).
- `tote_sequence`, `tote_blocks`, `tote_item_sequence`: tote block order and implied unit-level release ordering.

##### MILP Solver Strategy
- Solve MILP with a time limit and relative MIP gap target.
- Current notebook configuration uses a strict single run (no fallback retries).
- Accept either proven-optimal or time-limited feasible solutions.
- Current notebook configuration sets the primary solver time limit to 60 minutes (3600 seconds).

##### MILP Output Semantics
- belt sequence: release slot order of all units plus recirculation-aware pick times
- tote sequence: tote block order along release slots
- order sequence: reporting sequence obtained by sorting order first-pick start times
- order completion times: recirculation-aware completion seconds per order
- order-to-conveyor map: optimized assignment from MILP
- generated input files:
  - full-order input file for all orders
  - separate input file containing only the first 6 orders in the MILP sequence (while MILP is still solved on the full problem)

##### MILP Modeling Assumptions
- Discrete release slots with one release per slot
- Constant slot spacing (`slot_time_sec`) and conveyor travel time (`belt_time_sec`)
- Input conveyor 0 only transports items into the system and does not pick
- Recirculation loop approximated as fixed `1->2->3->4->1` cycle time
- Recirculation loop count per unit is modeled as a nonnegative integer and bounded above by N for tractability
- Conveyor assignment is order-level (not item-level)
- Non-overlap is enforced per conveyor (not globally)

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
- MILP quality depends on solver time limit settings.

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






