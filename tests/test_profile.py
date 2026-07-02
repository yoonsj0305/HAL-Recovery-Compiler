from __future__ import annotations

from hal_rc.graph import build_graph
from hal_rc.models import ChipMap, Constraints, Tile, Workload, to_dict
from hal_rc.profile import build_recovery_profile
from hal_rc.solver_route_aware import solve_route_aware


def _profile():
    chip = ChipMap(
        "C", 2, 2,
        (Tile("A", 0, 0, "usable", 0.95, 0.1, 0.1, 0.1),
         Tile("B", 1, 0, "weak", 0.7, 0.2, 0.2, 0.2),
         Tile("X", 0, 1, "defective", 0.1, 0.9, 0.9, 0.9),
         Tile("D", 1, 1, "usable", 0.9, 0.1, 0.1, 0.1)),
    )
    workloads = (Workload("W", "reduced_compute", "high", 2, 0.5, 0.8),)
    constraints = Constraints(0.75, 0.70, 0.75, True, True, False)
    result = solve_route_aware(chip, workloads, constraints)
    return build_recovery_profile(chip, workloads, constraints, result, build_graph(chip))


def test_recovery_profile_contains_required_safety_fields():
    data = to_dict(_profile())
    assert data["human_review_required"] is True
    assert data["claim_boundary"] == "simulation_only_not_certified"


def test_recovery_profile_hardware_control_is_false():
    assert _profile().hardware_control_enabled is False


def test_recovery_profile_disables_defective_tile():
    assert _profile().disabled_tiles == ("X",)


def test_recovery_profile_records_policy_blocked_route():
    profile = _profile()
    assert profile.blocked_routes
    assert profile.blocked_routes[0].claim_boundary == "simulation_only_not_certified"


def test_low_priority_route_does_not_cross_weak_tile_when_policy_forbids_it():
    chip = ChipMap(
        "C", 3, 1,
        (Tile("A", 0, 0, "usable", 0.95, 0.1, 0.1, 0.1),
         Tile("W", 1, 0, "weak", 0.7, 0.2, 0.2, 0.2),
         Tile("B", 2, 0, "usable", 0.9, 0.1, 0.1, 0.1)),
    )
    workloads = (Workload("LOW", "test_debug_only", "low", 2, 0.2, 0.8),)
    constraints = Constraints(0.75, 0.70, 0.75, False, True, False)
    result = solve_route_aware(chip, workloads, constraints)
    profile = build_recovery_profile(chip, workloads, constraints, result, build_graph(chip))
    assert profile.blocked_routes
