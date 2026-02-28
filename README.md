# MILP Formulation: Conveyor-Tote Order Picking

## Problem Statement
The model schedules tote releases and item picks in a conveyor-based warehouse system to minimize total order completion time.

The system has four conveyors (0, 1, 2, 3). Totes are released to the start of conveyor 0. If an item is not picked when it reaches the assigned conveyor for its order, it recirculates through conveyors 1 -> 2 -> 3 -> 1.

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
- g: seconds per transfer step (5 seconds)
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
- Release time = g * p_u
- Base travel offset = (c+1) * g
- Loop period = 0 if c=0, else 3*g
- Pick time = g*p_u + (c+1)*g + (3*g)*k_u for c in {1,2,3}

The model links this pick-time expression to order start/completion bounds using big-M conditioning with a_{o,c}.

Additional physical rule:
- If an order is assigned to conveyor 0, recirculation loops are forced to zero for its units.

### 5) Order Start/Completion Definition
- S_o is bounded above by all pick times of units in order o
- C_o is bounded below by all pick times of units in order o
- S_o <= C_o

### 6) One-Order-at-a-Time Logic
For each order pair (i,j), a binary r_{i,j} chooses one of:
- C_i <= S_j, or
- C_j <= S_i

This enforces non-overlap between orders and lets the model choose order sequence.

### 7) Optional User-Defined Precedence
Additional precedence pairs (o1,o2) can be imposed as:
- C_{o1} <= S_{o2}

### 8) Optional Intra-Order Spacing
If min_gap > 0, the model can enforce minimum slot-distance between units of the same order.

## Solver Strategy
- Solve MILP with a time limit and relative MIP gap target
- If no feasible incumbent is found, retry with extended limits
- Accept either proven-optimal or time-limited feasible solutions

## Output Semantics
- belt sequence: release slot order of all units plus recirculation-aware pick times
- tote sequence: tote block order along release slots
- order sequence: order of first pick start times
- order completion times: recirculation-aware completion seconds per order
- order-to-conveyor map: optimized assignment from MILP

## Modeling Assumptions
- Discrete release slots with one release per slot
- Constant transfer step duration g
- Recirculation loop approximated as fixed 1->2->3->1 cycle time
- Conveyor assignment is order-level (not item-level)
- Non-overlap between orders is enforced globally
