from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlannedOrder:
    order_id: int
    conveyor_id: int
    requirements: dict[int, int]


@dataclass
class ReleaseUnit:
    unit_id: int
    item_type_id: int
    tote_id: int
    source_order_id: int | None = None
    recirculations: int = 0


@dataclass
class SimulationResult:
    heuristic: str
    makespan_sec: float
    terminated_early: int
    total_picks: int
    total_recirculations: int
    mismatch_orders: int
    unfinished_orders: int
    order_start_sec: dict[int, float]
    order_completion_sec: dict[int, float]
    conveyor_completion_sec: dict[int, float]
    conveyor_idle_sec: dict[int, float]
    event_rows: list[dict[str, float | int]]
    order_rows: list[dict[str, float | int]]
    summary_rows: list[dict[str, float | int | str]]


class ConveyorSimulator:
    def __init__(
        self,
        orders: list[PlannedOrder],
        release_units: list[ReleaseUnit],
        *,
        heuristic_name: str,
        belt_time_sec: float = 2.0,
        induction_step_sec: float = 1.0,
        max_loop_items: int = 7,
        max_steps: int = 100000,
    ) -> None:
        if belt_time_sec <= 0 or induction_step_sec <= 0:
            raise ValueError("belt_time_sec and induction_step_sec must be positive.")

        self.heuristic_name = heuristic_name
        self.belt_time_sec = belt_time_sec
        self.step_sec = induction_step_sec
        self.max_loop_items = max_loop_items
        self.max_steps = max_steps

        self.time_sec = 0.0
        self.input_pipe: list[ReleaseUnit | None] = [None, None]
        self.belts: dict[int, list[ReleaseUnit | None]] = {1: [None, None], 2: [None, None], 3: [None, None], 4: [None, None]}
        self.release_queue = deque(release_units)

        schedules: dict[int, list[PlannedOrder]] = {1: [], 2: [], 3: [], 4: []}
        for order in orders:
            schedules[order.conveyor_id].append(
                PlannedOrder(
                    order_id=order.order_id,
                    conveyor_id=order.conveyor_id,
                    requirements=deepcopy(order.requirements),
                )
            )

        self.schedules = schedules
        self.active_orders: dict[int, PlannedOrder | None] = {
            conveyor_id: self.schedules[conveyor_id].pop(0) if self.schedules[conveyor_id] else None
            for conveyor_id in range(1, 5)
        }

        self.required_items = {
            order.order_id: sum(order.requirements.values())
            for order in orders
        }
        self.total_orders = len(orders)
        self.completed_orders: set[int] = set()
        self.order_start_sec: dict[int, float] = {}
        self.order_completion_sec: dict[int, float] = {}
        self.conveyor_completion_sec: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.conveyor_idle_sec: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.event_rows: list[dict[str, float | int]] = []

    def state_signature(self) -> tuple:
        def compact_requirements(order: PlannedOrder | None) -> tuple[tuple[int, int], ...] | None:
            if order is None:
                return None
            return tuple(sorted((item_type_id, qty) for item_type_id, qty in order.requirements.items() if qty > 0))

        belts = tuple(
            tuple(
                None if slot is None else (slot.item_type_id, slot.tote_id)
                for slot in self.belts[conveyor_id]
            )
            for conveyor_id in range(1, 5)
        )
        input_pipe = tuple(None if slot is None else (slot.item_type_id, slot.tote_id) for slot in self.input_pipe)
        active_orders = tuple(
            None
            if self.active_orders[conveyor_id] is None
            else (
                self.active_orders[conveyor_id].order_id,
                compact_requirements(self.active_orders[conveyor_id]),
                tuple(
                    (
                        queued.order_id,
                        compact_requirements(queued),
                    )
                    for queued in self.schedules[conveyor_id]
                ),
            )
            for conveyor_id in range(1, 5)
        )
        release_queue = tuple((unit.item_type_id, unit.tote_id) for unit in self.release_queue)
        return belts, input_pipe, active_orders, release_queue

    def items_in_loop(self) -> int:
        return sum(1 for slots in self.belts.values() for slot in slots if slot is not None)

    def items_in_system(self) -> int:
        return self.items_in_loop() + sum(1 for slot in self.input_pipe if slot is not None)

    def all_done(self) -> bool:
        return (
            len(self.completed_orders) == self.total_orders
            and not self.release_queue
            and self.items_in_system() == 0
        )

    def step(self) -> None:
        self.time_sec += self.step_sec

        next_map = {1: 2, 2: 3, 3: 4, 4: 1}

        # 1) Inter-belt transfer among picking conveyors.
        for current_conveyor in (4, 3, 2, 1):
            next_conveyor = next_map[current_conveyor]
            if self.belts[current_conveyor][1] is not None and self.belts[next_conveyor][0] is None:
                item = self.belts[current_conveyor][1]
                self.belts[next_conveyor][0] = item
                self.belts[current_conveyor][1] = None
                if current_conveyor == 4:
                    item.recirculations += 1

        # 2) Input conveyor transport into belt 1 midpoint.
        if self.input_pipe[1] is not None and self.belts[1][0] is None:
            self.belts[1][0] = self.input_pipe[1]
            self.input_pipe[1] = None

        if self.input_pipe[0] is not None and self.input_pipe[1] is None:
            self.input_pipe[1] = self.input_pipe[0]
            self.input_pipe[0] = None

        # 3) Diversion logic at midpoint / scanner.
        for conveyor_id in range(1, 5):
            item = self.belts[conveyor_id][0]
            active_order = self.active_orders[conveyor_id]
            if item is None or active_order is None:
                continue

            if active_order.requirements.get(item.item_type_id, 0) > 0:
                active_order.requirements[item.item_type_id] -= 1
                self.belts[conveyor_id][0] = None

                self.order_start_sec.setdefault(active_order.order_id, self.time_sec)
                self.event_rows.append(
                    {
                        "time_sec": round(self.time_sec, 6),
                        "conveyor_id": conveyor_id,
                        "order_id": active_order.order_id,
                        "item_type_id": item.item_type_id,
                        "tote_id": item.tote_id,
                        "unit_id": item.unit_id,
                        "recirculations": item.recirculations,
                    }
                )

                if sum(active_order.requirements.values()) == 0:
                    self.completed_orders.add(active_order.order_id)
                    self.order_completion_sec[active_order.order_id] = self.time_sec
                    self.conveyor_completion_sec[conveyor_id] = self.time_sec
                    self.active_orders[conveyor_id] = (
                        self.schedules[conveyor_id].pop(0) if self.schedules[conveyor_id] else None
                    )

        # 4) Internal movement midpoint -> end of each conveyor.
        for conveyor_id in range(1, 5):
            if self.belts[conveyor_id][0] is not None and self.belts[conveyor_id][1] is None:
                self.belts[conveyor_id][1] = self.belts[conveyor_id][0]
                self.belts[conveyor_id][0] = None

        # 5) Controlled induction onto input conveyor.
        if self.release_queue and self.input_pipe[0] is None and self.items_in_loop() < self.max_loop_items:
            self.input_pipe[0] = self.release_queue.popleft()

        # Approximate conveyor idle time while an order is active.
        for conveyor_id in range(1, 5):
            if self.active_orders[conveyor_id] is not None and self.belts[conveyor_id][0] is None and self.belts[conveyor_id][1] is None:
                self.conveyor_idle_sec[conveyor_id] += self.step_sec

    def build_result(
        self,
        *,
        terminated_early: int,
        override_makespan_sec: float | None = None,
    ) -> SimulationResult:
        picked_counts: dict[int, int] = {}
        for row in self.event_rows:
            order_id = int(row["order_id"])
            picked_counts[order_id] = picked_counts.get(order_id, 0) + 1

        mismatch_orders = 0
        order_rows: list[dict[str, float | int]] = []
        for order_id, required in sorted(self.required_items.items()):
            planned = picked_counts.get(order_id, 0)
            if planned != required:
                mismatch_orders += 1
            order_rows.append(
                {
                    "heuristic": self.heuristic_name,
                    "order_id": order_id,
                    "required_items": required,
                    "picked_items": planned,
                    "item_delta": planned - required,
                    "start_sec": round(self.order_start_sec.get(order_id, 0.0), 6),
                    "completion_sec": round(self.order_completion_sec.get(order_id, 0.0), 6),
                }
            )

        if terminated_early:
            makespan = self.time_sec if override_makespan_sec is None else override_makespan_sec
        else:
            makespan = max(self.order_completion_sec.values(), default=0.0)
        total_recirculations = sum(int(row["recirculations"]) for row in self.event_rows)
        completion_values = [float(row["completion_sec"]) for row in order_rows]
        avg_completion = sum(completion_values) / len(completion_values) if completion_values else 0.0

        summary_rows = [
            {"metric": "orders", "value": self.total_orders},
            {"metric": "total_picks", "value": len(self.event_rows)},
            {"metric": "terminated_early", "value": terminated_early},
            {"metric": "makespan_sec", "value": round(makespan, 6)},
            {"metric": "avg_completion_sec", "value": round(avg_completion, 6)},
            {"metric": "total_recirculations", "value": total_recirculations},
            {"metric": "mismatch_orders", "value": mismatch_orders},
            {"metric": "unfinished_orders", "value": self.total_orders - len(self.completed_orders)},
            {
                "metric": "conveyor_finish_spread_sec",
                "value": round(max(self.conveyor_completion_sec.values()) - min(self.conveyor_completion_sec.values()), 6),
            },
        ]

        return SimulationResult(
            heuristic=self.heuristic_name,
            makespan_sec=round(makespan, 6),
            terminated_early=terminated_early,
            total_picks=len(self.event_rows),
            total_recirculations=total_recirculations,
            mismatch_orders=mismatch_orders,
            unfinished_orders=self.total_orders - len(self.completed_orders),
            order_start_sec={k: round(v, 6) for k, v in self.order_start_sec.items()},
            order_completion_sec={k: round(v, 6) for k, v in self.order_completion_sec.items()},
            conveyor_completion_sec={k: round(v, 6) for k, v in self.conveyor_completion_sec.items()},
            conveyor_idle_sec={k: round(v, 6) for k, v in self.conveyor_idle_sec.items()},
            event_rows=self.event_rows,
            order_rows=order_rows,
            summary_rows=summary_rows,
        )

    def run(self) -> SimulationResult:
        steps = 0
        terminated_early = 0
        while not self.all_done():
            steps += 1
            if steps > self.max_steps:
                terminated_early = 1
                break
            self.step()

        return self.build_result(terminated_early=terminated_early)
