# MILP Formulation: Conveyor-Tote Order Picking

## Problem Statement
The model schedules tote releases and item picks in a conveyor-based warehouse system to minimize total order completion time.

The system has four conveyors (0, 1, 2, 3). Totes are released to the start of conveyor 0. If an item is not picked when it reaches the assigned conveyor for its order, it recirculates through conveyors 0 -> 1 -> 2 -> 3 -> 0.

## Decisions
The MILP jointly decides:
- Order sequence (which order is completed before another)
- Tote release sequence (when each tote block appears)
- Item pick sequence (which physical unit is picked at each release slot)
- Order-to-conveyor assignment (each order assigned to exactly one conveyor)

## Data Representation
Input data (from CSV files) are transformed into physical item units. Each unit has:
- Order id
- Item type
- Tote id

If a quantity is q for an item/order entry, the model creates q separate unit records.

## Index Sets
- U: set of physical units, size N
- S: set of release slots, size N
- T: set of totes
- O: set of orders
- C: set of conveyors {0,1,2,3}

## Main Parameters
- slot_time_sec: release-slot spacing in seconds (default 1 second)
- belt_time_sec: conveyor traversal time from start to end (2 seconds)
- L_t: number of units belonging to tote t
- Big-M constants for sequencing and conditional timing

## Decision Variables
- x_{u,s} in {0,1}: unit u is assigned to release slot s
- y_{t,k} in {0,1}: tote t starts at slot k
- w_{t,s} in {0,1}: slot s belongs to tote t block
- p_u >= 0: release slot index of unit u
- k_u in Z_+: recirculation loop count for unit u
- a_{o,c} in {0,1}: order o assigned to conveyor c
- S_o >= 0: start time of order o
- C_o >= 0: completion time of order o
- r_{i,j} in {0,1} for i<j: binary order precedence selector (i before j vs j before i)
- Optional gap binaries for same-order spacing (when min_gap > 0)

## Objective
Primary objective (default):
- Minimize sum of order completion times
  min sum_{o in O} C_o

Alternative supported objective:
- Minimize makespan

## Core Constraints

### 1) Assignment and Slot Feasibility
- Each unit is released exactly once
- Each release slot contains exactly one unit

### 2) Tote Contiguity and Release Structure
- Each tote selects exactly one start slot
- Slots covered by a tote are contiguous with length equal to that tote's unit count
- Every slot belongs to exactly one tote block
- A unit can only be released in slots belonging to its tote block

### 3) Order-to-Conveyor Assignment
- Each order is assigned to exactly one conveyor:
  sum_{c in C} a_{o,c} = 1

### 4) Recirculation-Aware Pick Timing
For a unit u of order o assigned to conveyor c:
- Release time = slot_time_sec * p_u
- Item is picked at conveyor midpoint, so midpoint offset = belt_time_sec/2 = 1 second once it reaches a conveyor start
- Base travel offset to conveyor c midpoint = c*belt_time_sec + belt_time_sec/2
- Loop period = 4*belt_time_sec (full loop 0->1->2->3->0)
- Pick time = slot_time_sec*p_u + (c*belt_time_sec + belt_time_sec/2) + (4*belt_time_sec)*k_u

The model links this pick-time expression to order start/completion bounds using big-M conditioning with a_{o,c}.

### 5) Order Start/Completion Definition
- S_o is bounded above by all pick times of units in order o
- C_o is bounded below by all pick times of units in order o
- S_o <= C_o

### 6) Per-Conveyor One-Order-at-a-Time Logic
For each order pair (i,j) and each conveyor c, disjunctive constraints are activated only when both orders are assigned to conveyor c.

This enforces:
- orders on the same conveyor cannot overlap,
- orders on different conveyors may overlap.

Therefore, at most 4 orders can be processed simultaneously (one active order per conveyor).

### 7) Optional User-Defined Precedence
Additional precedence pairs (o1,o2) can be imposed as:
- C_{o1} <= S_{o2}

### 8) Optional Intra-Order Spacing
If min_gap > 0, the model can enforce minimum slot-distance between units of the same order.

## Solver Strategy
- Solve MILP with a time limit and relative MIP gap target
- Current notebook configuration uses a strict single run (no fallback retries)
- Accept either proven-optimal or time-limited feasible solutions
- Current notebook configuration sets the primary solver time limit to 60 minutes (3600 seconds)

## Output Semantics
- belt sequence: release slot order of all units plus recirculation-aware pick times
- tote sequence: tote block order along release slots
- order sequence: order of first pick start times
- order completion times: recirculation-aware completion seconds per order
- order-to-conveyor map: optimized assignment from MILP
- generated input files:
  - full-order input file for all orders
  - separate input file containing only the first 6 orders in the MILP sequence (while MILP is still solved on the full problem)

## Modeling Assumptions
- Discrete release slots with one release per slot
- Constant transfer step duration g
- Recirculation loop approximated as fixed 0->1->2->3->0 cycle time
- Conveyor assignment is order-level (not item-level)
- Non-overlap is enforced per conveyor (not globally)


