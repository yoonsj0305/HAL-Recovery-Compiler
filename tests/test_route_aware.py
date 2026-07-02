from __future__ import annotations

from hal_rc.graph import build_graph
from hal_rc.models import ChipMap, Constraints, Tile, Workload
from hal_rc.passport import build_functional_passport
from hal_rc.profile import build_recovery_profile
from hal_rc.solver_local_search import improve_solution
from hal_rc.solver_route_aware import is_connected_group, solve_route_aware


def _tile(tile_id: str, x: int, status: str = "usable", *, y: int = 0) -> Tile:
    if status == "defective":
        return Tile(tile_id, x, y, status, 0.1, 0.9, 0.9, 0.9)
    if status == "weak":
        return Tile(tile_id, x, y, status, 0.7, 0.2, 0.2, 0.2)
    return Tile(tile_id, x, y, status, 0.95, 0.1, 0.1, 0.1)


def _constraints() -> Constraints:
    return Constraints(0.75, 0.70, 0.75, True, True, False)


def _workload(compute: int = 2, criticality: str = "medium") -> Workload:
    return Workload("W", "reduced_compute", criticality, compute, 0.5, 0.8)


def test_assigned_group_is_connected_and_has_anchor_route():
    chip = ChipMap("C", 4, 1, tuple(_tile(chr(65 + x), x) for x in range(4)))
    result = solve_route_aware(chip, (_workload(),), _constraints())
    assert result.placement_mode == "route_aware"
    assignment = result.assignments[0]
    route = result.workload_routes[0]
    assert is_connected_group(chip, assignment.tile_ids)
    assert route.connected is True
    assert route.routable is True
    assert route.route_tile_ids[0] == result.route_anchor_tile_id


def test_defective_tiles_never_appear_in_group_or_route():
    chip = ChipMap(
        "C", 4, 2,
        (_tile("A", 0), _tile("X", 1, "defective"), _tile("B", 2), _tile("C", 3),
         _tile("D", 0, y=1), _tile("E", 1, y=1), _tile("F", 2, y=1), _tile("G", 3, y=1)),
    )
    result = solve_route_aware(chip, (_workload(),), _constraints())
    defective = {"X"}
    assert defective.isdisjoint(result.assignments[0].tile_ids)
    assert defective.isdisjoint(result.workload_routes[0].route_tile_ids)


def test_safety_critical_never_uses_weak_or_defective_tiles():
    chip = ChipMap(
        "C", 5, 1,
        (_tile("A", 0), _tile("B", 1), _tile("C", 2),
         _tile("W", 3, "weak"), _tile("X", 4, "defective")),
    )
    result = solve_route_aware(chip, (_workload(2, "safety_critical"),), _constraints())
    used = set(result.assignments[0].tile_ids)
    assert "W" not in used
    assert "X" not in used


def test_unassigned_when_no_connected_group_exists():
    chip = ChipMap(
        "C", 4, 1,
        (_tile("A", 0), _tile("B", 1), _tile("X", 2, "defective"), _tile("D", 3)),
    )
    result = solve_route_aware(chip, (_workload(2),), _constraints())
    assert not result.assignments
    assert result.unassigned[0]["reason"] == "no_connected_routable_tile_group"
    assert result.candidate_groups_rejected_connectivity > 0


def test_unassigned_when_group_exists_but_no_route_to_anchor():
    chip = ChipMap(
        "C", 4, 1,
        (_tile("A", 0), _tile("X", 1, "defective"), _tile("B", 2), _tile("C", 3)),
    )
    result = solve_route_aware(chip, (_workload(2),), _constraints())
    assert not result.assignments
    assert result.unassigned[0]["reason"] == "no_connected_routable_tile_group"
    assert result.candidate_groups_rejected_routing > 0


def test_profile_and_passport_contain_route_aware_records():
    chip = ChipMap("C", 4, 1, tuple(_tile(chr(65 + x), x) for x in range(4)))
    workloads = (_workload(),)
    constraints = _constraints()
    result = solve_route_aware(chip, workloads, constraints)
    profile = build_recovery_profile(
        chip, workloads, constraints, result, build_graph(chip)
    )
    passport = build_functional_passport(
        chip, workloads, constraints, result, profile
    )
    route = profile.preferred_routes[0]
    assert route.route_id == "ROUTE_W"
    assert route.from_anchor == result.route_anchor_tile_id
    assert route.route_status == "candidate_simulated"
    evidence = next(item for item in passport.evidence if item["metric"] == "route_aware_placement")
    assert evidence["placement_mode"] == "route_aware"
    assert evidence["connected_assignments"] is True
    assert evidence["routable_assignments"] is True


def test_local_search_cannot_break_route_aware_connectivity_or_safety():
    chip = ChipMap("C", 5, 1, tuple(_tile(chr(65 + x), x) for x in range(5)))
    workloads = (_workload(2, "safety_critical"),)
    initial = solve_route_aware(chip, workloads, _constraints())
    improved = improve_solution(chip, workloads, _constraints(), initial, max_iterations=100)
    assert improved == initial
    assert is_connected_group(chip, improved.assignments[0].tile_ids)


def test_route_aware_solver_is_deterministic():
    chip = ChipMap("C", 6, 1, tuple(_tile(chr(65 + x), x) for x in range(6)))
    workloads = (_workload(2),)
    first = solve_route_aware(chip, workloads, _constraints())
    second = solve_route_aware(chip, workloads, _constraints())
    assert first == second

