# Warehouse Conveyor Sequencing (MSE433 Module 3)

This repo turns the three order CSV files you get from the random data generator into the **input CSV** required by the IDEAS Clinic conveyor belt simulator.

## Inputs
You provide three CSVs (one row per order):

- `order_itemtypes.csv`: item type IDs present in each order (ragged rows)
- `order_quantities.csv`: quantities aligned with the item types row
- `orders_totes.csv`: tote IDs aligned with the item types row

You also provide an example simulator input file to infer the exact header/column order.

## Item type mapping
```
circle = 0
pentagon = 1
trapezoid = 2
triangle = 3
star = 4
moon = 5
heart = 6
cross = 7
```

## What this generates
A simulator input CSV with:
- **one row per order**
- first column = conveyor assignment (`conv_num` in the example)
- remaining columns = item quantities for each item type

## Quick start
From the repo root:

```bash
# Generate an input file using a simple conveyor-assignment heuristic
PYTHONPATH=src python -m wareseq.generate_input \
  --order-itemtypes data/order_itemtypes.csv \
  --order-quantities data/order_quantities.csv \
  --order-totes data/orders_totes.csv \
  --example-input data/example_input.csv \
  --assign-method round_robin \
  --out outputs/simulator_input.csv
```

### Conveyor assignment heuristics (currently implemented)
- `round_robin`: assign orders 1,2,3,4,1,2,... to conveyors 1..4
- `balance_units`: greedy load balancing by total units per order

> Tote sequencing and within-tote item ordering heuristics are scaffolded in `src/wareseq/heuristics.py` and can be extended next.

## Repo layout
- `src/wareseq/` : python code
- `data/` : sample input files
- `outputs/` : generated simulator input CSVs

