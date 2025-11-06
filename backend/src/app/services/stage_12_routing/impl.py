from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

FLAG_TRUE_VALUES = {"1", "true", "yes", "on", "t", "y"}


def _is_flag_enabled(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip().lower() in FLAG_TRUE_VALUES)


@dataclass
class RoutingScenario:
    distance_matrix: List[List[int]]
    demands: List[int]
    time_windows: List[Tuple[int, int]]
    service_times: List[int]
    vehicle_capacities: List[int]
    depot: int = 0
    horizon: Optional[int] = None

    @property
    def vehicle_count(self) -> int:
        return len(self.vehicle_capacities)

    @property
    def location_count(self) -> int:
        return len(self.distance_matrix)

    def validate(self) -> None:
        n = self.location_count
        if any(len(row) != n for row in self.distance_matrix):
            raise ValueError("distance_matrix must be square")
        if len(self.demands) != n:
            raise ValueError("demands length must match distance matrix size")
        if len(self.service_times) != n:
            raise ValueError("service_times length must match distance matrix size")
        if len(self.time_windows) != n:
            raise ValueError("time_windows length must match distance matrix size")
        if not self.vehicle_capacities:
            raise ValueError("at least one vehicle capacity is required")
        if self.depot < 0 or self.depot >= n:
            raise ValueError("depot index out of bounds")
        if self.horizon is None:
            upper = max(end for _, end in self.time_windows)
            self.horizon = upper + max((max(row) for row in self.distance_matrix), default=0) + 60


def _as_int_pairs(values: Iterable[Sequence[Any]]) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for entry in values:
        start, end = entry
        pairs.append((int(start), int(end)))
    return pairs


def _load_scenario(inputs: Mapping[str, Any], config: Mapping[str, Any]) -> RoutingScenario:
    if "scenario_path" in inputs:
        scenario_path = Path(str(inputs["scenario_path"])).expanduser().resolve()
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
    elif "scenario" in inputs:
        data = dict(inputs["scenario"])  # type: ignore[arg-type]
    else:
        data = dict(inputs)

    distance_matrix = [[int(value) for value in row] for row in data.get("distance_matrix", [])]
    demands = [int(value) for value in data.get("demands", [])]
    time_windows_raw = data.get("time_windows") or []
    if not time_windows_raw:
        horizon = data.get("horizon") or 24 * 60
        time_windows_raw = [(0, horizon) for _ in range(len(distance_matrix))]
    time_windows = _as_int_pairs(time_windows_raw)
    service_times_raw = data.get("service_times") or [0] * len(distance_matrix)
    service_times = [int(value) for value in service_times_raw]
    vehicle_capacities = [int(value) for value in data.get("vehicle_capacities", [])]
    depot = int(data.get("depot", 0))
    horizon = data.get("horizon")
    scenario = RoutingScenario(
        distance_matrix=distance_matrix,
        demands=demands,
        time_windows=time_windows,
        service_times=service_times,
        vehicle_capacities=vehicle_capacities,
        depot=depot,
        horizon=int(horizon) if horizon is not None else None,
    )
    scenario.validate()
    return scenario


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_logs(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _solve_greedy(scenario: RoutingScenario) -> Dict[str, Any]:
    pending = {idx for idx in range(scenario.location_count) if idx != scenario.depot}
    routes: List[Dict[str, Any]] = []
    for vehicle_id, capacity in enumerate(scenario.vehicle_capacities):
        if not pending:
            routes.append({"vehicle_id": vehicle_id, "stops": [scenario.depot, scenario.depot], "load": 0, "capacity": capacity})
            continue
        load = 0
        route = [scenario.depot]
        while pending:
            next_idx = None
            for candidate in sorted(pending):
                demand = scenario.demands[candidate]
                if load + demand <= capacity:
                    next_idx = candidate
                    break
            if next_idx is None:
                break
            route.append(next_idx)
            load += scenario.demands[next_idx]
            pending.remove(next_idx)
        if route[-1] != scenario.depot:
            route.append(scenario.depot)
        routes.append(
            {
                "vehicle_id": vehicle_id,
                "stops": route,
                "load": load,
                "capacity": capacity,
            }
        )
    if pending and routes:
        tail = routes[-1]
        for candidate in sorted(pending):
            tail["stops"].insert(-1, candidate)
            tail["load"] += scenario.demands[candidate]
        pending.clear()
    return {"routes": routes, "unassigned": []}


def _solve_with_ortools(scenario: RoutingScenario) -> Dict[str, Any]:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore

    manager = pywrapcp.RoutingIndexManager(
        scenario.location_count,
        scenario.vehicle_count,
        scenario.depot,
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(scenario.distance_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index: int) -> int:
        node = manager.IndexToNode(from_index)
        return int(scenario.demands[node])

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_index,
        0,
        [int(cap) for cap in scenario.vehicle_capacities],
        True,
        "Capacity",
    )

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        travel = scenario.distance_matrix[from_node][manager.IndexToNode(to_index)]
        service = scenario.service_times[from_node]
        return int(service + travel)

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    horizon = scenario.horizon or max(end for _, end in scenario.time_windows) + 60
    routing.AddDimension(
        time_callback_index,
        30,
        int(horizon),
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    for node, (start, end) in enumerate(scenario.time_windows):
        index = manager.NodeToIndex(node)
        time_dimension.CumulVar(index).SetRange(int(start), int(end))

    for vehicle_id in range(scenario.vehicle_count):
        start_index = routing.Start(vehicle_id)
        end_index = routing.End(vehicle_id)
        depot_window = scenario.time_windows[scenario.depot]
        time_dimension.CumulVar(start_index).SetRange(int(depot_window[0]), int(depot_window[1]))
        time_dimension.CumulVar(end_index).SetRange(int(depot_window[0]), int(depot_window[1]))
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(start_index))
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(end_index))

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_parameters)
    if solution is None:
        raise RuntimeError("OR-Tools failed to find a feasible routing plan")

    time_dimension = routing.GetDimensionOrDie("Time")
    routes: List[Dict[str, Any]] = []
    unassigned: List[int] = []

    for vehicle_id in range(scenario.vehicle_count):
        index = routing.Start(vehicle_id)
        vehicle_route: List[int] = [manager.IndexToNode(index)]
        load = 0
        arrival_times: List[int] = [int(solution.Value(time_dimension.CumulVar(index)))]
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            if node_index != scenario.depot:
                load += scenario.demands[node_index]
            index = solution.Value(routing.NextVar(index))
            vehicle_route.append(manager.IndexToNode(index))
            arrival_times.append(int(solution.Value(time_dimension.CumulVar(index))))
        routes.append(
            {
                "vehicle_id": vehicle_id,
                "stops": vehicle_route,
                "load": load,
                "capacity": scenario.vehicle_capacities[vehicle_id],
                "arrival_times": arrival_times,
            }
        )

    for node_index in range(scenario.location_count):
        if node_index == scenario.depot:
            continue
        index = manager.NodeToIndex(node_index)
        if routing.IsStart(index) or routing.IsEnd(index):
            continue
        if solution.Value(routing.NextVar(index)) == index:
            unassigned.append(node_index)

    return {"routes": routes, "unassigned": unassigned}


def run(run_id: str, inputs: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    scenario = _load_scenario(inputs, config)
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    out_dir = artifacts_root / run_id / "stage_12_routing"
    out_dir.mkdir(parents=True, exist_ok=True)

    logs: List[Dict[str, Any]] = []
    plan = _solve_greedy(scenario)
    method = "baseline"

    if _is_flag_enabled("USE_EXT_VRPTW_SOLVER"):
        try:
            plan = _solve_with_ortools(scenario)
            method = "adapter"
        except Exception as exc:
            logs.append({"event": "routing_adapter_warning", "message": str(exc)})
            plan = _solve_greedy(scenario)
            method = "baseline"

    plan_payload = {**plan, "method": method}
    plan_path = out_dir / "route_plan.json"
    _write_json(plan_path, plan_payload)

    logs.append(
        {
            "event": "routing_plan",
            "method": method,
            "vehicles": len(plan_payload.get("routes", [])),
            "unassigned": len(plan_payload.get("unassigned", [])),
        }
    )
    log_path = out_dir / "logs.jsonl"
    _write_logs(log_path, logs)

    outputs = {"route_plan": plan_path.as_posix(), "logs": log_path.as_posix()}
    status = "PASS" if not plan_payload.get("unassigned") else "WARN"
    return {"run_id": run_id, "status": status, "method": method, "outputs": outputs}
