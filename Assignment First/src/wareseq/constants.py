from __future__ import annotations

# Item type mapping provided by you
ITEM_ID_TO_NAME = {
    0: "circle",
    1: "pentagon",
    2: "trapezoid",
    3: "triangle",
    4: "star",
    5: "moon",
    6: "heart",
    7: "cross",
}

ITEM_NAME_TO_ID = {v: k for k, v in ITEM_ID_TO_NAME.items()}

# Conveyors in the physical system (1..4 looping)
CONVEYORS = [1, 2, 3, 4]
