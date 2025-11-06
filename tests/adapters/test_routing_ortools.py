from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("ortools")

from backend.src.app.services.stage_12_routing import impl


def _scenario() -> dict[str, object]:
    distance_matrix = [
        [0, 9, 9, 12, 7],
        [9, 0, 4, 6, 3],
        [9, 4, 0, 5, 4],
        [12, 6, 5, 0, 6],
        [7, 3, 4, 6, 0],
    ]
    demands = [0, 4, 6, 5, 3]
    time_windows = [(0, 60) for _ in distance_matrix]
    service_times = [0, 2, 2, 2, 2]
    vehicle_capacities = [10, 10]
    return {
        "distance_matrix": distance_matrix,
        "demands": demands,
        "time_windows": time_windows,
        "service_times": service_times,
        "vehicle_capacities": vehicle_capacities,
        "depot": 0,
        "horizon": 80,
    }


def test_ortools_route_respects_capacity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_EXT_VRPTW_SOLVER", "1")
    scenario = _scenario()
    result = impl.run(
        run_id="routing_test",
        inputs=scenario,
        config={"artifacts_root": tmp_path.as_posix()},
    )

    assert result["status"] in {"PASS", "WARN"}
    assert result["method"] == "adapter"

    plan_path = Path(result["outputs"]["route_plan"])
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert plan["method"] == "adapter"
    routes = plan.get("routes", [])
    assert routes, "expected at least one route"

    visited = []
    for route in routes:
        stops = route["stops"]
        assert stops[0] == 0 and stops[-1] == 0
        load = route["load"]
        assert load <= route["capacity"]
        visited.extend(stop for stop in stops[1:-1])

    non_depot = {idx for idx in range(len(scenario["distance_matrix"])) if idx != 0}
    assert set(visited) == non_depot
    assert plan.get("unassigned") == []
