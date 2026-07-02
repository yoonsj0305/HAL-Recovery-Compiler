from __future__ import annotations

from hal_rc.models import ChipMap, Constraints, Tile, Workload
from hal_rc.solver_greedy import solve_greedy
from hal_rc.solver_local_search import improve_solution


def _tile(tile_id, x, status="usable", confidence=0.9, risk=0.1):
    return Tile(tile_id, x, 0, status, confidence, risk, risk, risk)


def _workload(criticality, compute=1, reliability=0.5, workload_id="W"):
    return Workload(workload_id, "role", criticality, compute, 0.5, reliability)


def _constraints(allow_weak=True):
    return Constraints(0.75, 0.70, 0.75, allow_weak, True, False)


def test_high_criticality_uses_best_strong_tile():
    chip = ChipMap("C", 2, 1, (_tile("A", 0, confidence=0.8), _tile("B", 1, confidence=0.95)))
    result = solve_greedy(chip, (_workload("high"),), _constraints())
    assert result.assignments[0].tile_ids == ("B",)


def test_safety_critical_never_assigned_to_weak_tile():
    chip = ChipMap("C", 2, 1, (_tile("W", 0, "weak", 0.99), _tile("A", 1, "usable", 0.95)))
    result = solve_greedy(chip, (_workload("safety_critical", reliability=0.9),), _constraints())
    assert result.assignments[0].tile_ids == ("A",)


def test_safety_critical_never_assigned_to_defective_tile():
    chip = ChipMap("C", 1, 1, (_tile("X", 0, "defective", 0.99),))
    result = solve_greedy(chip, (_workload("safety_critical", reliability=0.9),), _constraints())
    assert not result.assignments
    assert result.unassigned


def test_low_priority_can_use_weak_tile_when_allowed():
    chip = ChipMap("C", 1, 1, (_tile("W", 0, "weak", 0.7),))
    result = solve_greedy(chip, (_workload("low", reliability=0.6),), _constraints(True))
    assert result.assignments[0].tile_ids == ("W",)


def test_weak_tile_rejected_when_policy_forbids_it():
    chip = ChipMap("C", 1, 1, (_tile("W", 0, "weak", 0.7),))
    result = solve_greedy(chip, (_workload("low", reliability=0.6),), _constraints(False))
    assert not result.assignments


def test_workload_assignment_is_atomic_when_capacity_is_short():
    chip = ChipMap("C", 1, 1, (_tile("A", 0),))
    result = solve_greedy(chip, (_workload("medium", compute=2),), _constraints())
    assert not result.assignments
    assert "required=2,available=1" in result.unassigned[0]["reason"]


def test_solver_is_deterministic():
    chip = ChipMap("C", 2, 1, (_tile("A", 0), _tile("B", 1)))
    workload = (_workload("medium"),)
    assert solve_greedy(chip, workload, _constraints()) == solve_greedy(chip, workload, _constraints())


def test_local_search_is_bounded_and_preserves_safety():
    chip = ChipMap("C", 2, 1, (_tile("A", 0, confidence=0.92), _tile("W", 1, "weak", 0.99)))
    workloads = (_workload("safety_critical", reliability=0.9),)
    initial = solve_greedy(chip, workloads, _constraints())
    improved = improve_solution(chip, workloads, _constraints(), initial, max_iterations=100)
    assert improved.assignments[0].tile_ids == ("A",)

