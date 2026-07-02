from __future__ import annotations

from hal_rc.graph import build_graph
from hal_rc.models import ChipMap, Constraints, Tile, Workload
from hal_rc.passport import SCORE_FORMULA, build_functional_passport
from hal_rc.profile import build_recovery_profile
from hal_rc.solver_greedy import solve_greedy


def _passport():
    chip = ChipMap("C", 1, 1, (Tile("A", 0, 0, "usable", 0.95, 0.1, 0.1, 0.1),))
    workloads = (Workload("W", "monitoring_only", "medium", 1, 0.5, 0.8),)
    constraints = Constraints(0.75, 0.70, 0.75, True, True, False)
    result = solve_greedy(chip, workloads, constraints)
    profile = build_recovery_profile(chip, workloads, constraints, result, build_graph(chip))
    return build_functional_passport(chip, workloads, constraints, result, profile)


def test_functional_passport_requires_human_review():
    passport = _passport()
    assert passport.hardware_control_enabled is False
    assert passport.human_review_required is True


def test_functional_passport_is_candidate_only():
    passport = _passport()
    assert passport.validation_status == "candidate_only"
    assert passport.claim_boundary == "simulation_only_not_certified"


def test_functional_yield_score_is_bounded_and_formula_is_evidenced():
    passport = _passport()
    assert 0.0 <= passport.functional_yield_score <= 100.0
    assert any(item["value"] == SCORE_FORMULA for item in passport.evidence)
