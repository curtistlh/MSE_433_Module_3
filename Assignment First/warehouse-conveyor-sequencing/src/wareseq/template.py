from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd


@dataclass(frozen=True)
class InputTemplate:
    """Simulator input template.

    The simulator expects a CSV with one row per order, first column the conveyor id,
    and the remaining columns item-type quantities.

    We infer the exact column names and order from a provided example template file.
    """

    columns: List[str]  # includes first column (conveyor)
    conveyor_col: str


def load_template_from_example(example_input_csv: str | Path) -> InputTemplate:
    p = Path(example_input_csv)
    df = pd.read_csv(p)
    cols = list(df.columns)
    if not cols:
        raise ValueError("Example input file has no columns")
    conveyor_col = cols[0]
    return InputTemplate(columns=cols, conveyor_col=conveyor_col)
