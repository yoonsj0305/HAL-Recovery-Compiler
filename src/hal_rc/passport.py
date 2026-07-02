"""Functional passport score and evidence generation."""

from __future__ import annotations

from .models import (
    ChipMap,
    Constraints,
    FunctionalPassport,
    RecoveryProfile,
    SolverResult,
    Workload,
)

SCORE_FORMULA = (
    "100 * (0.30*non_defective_fraction + 0.30*assigned_workload_fraction "
    "+ 0.40*average_assigned_tile_score - 0.05*weak_used_fraction "
    "- 0.05*unassigned_high_or_safety_fraction), clamped to 0..100"
)


def build_functional_passport(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    result: SolverResult,
    profile: RecoveryProfile,
    *,
    baseline_comparison_available: bool = False,
    recommended_mode: str | None = None,
    recommendation_status: str | None = None,
) -> FunctionalPassport:
    total_tiles = len(chip.tiles)
    non_defective = [tile for tile in chip.tiles if tile.status != "defective"]
    assigned_tile_scores = [
        score for assignment in result.assignments for score in assignment.tile_scores
    ]
    used_count = len(assigned_tile_scores)

    non_defective_fraction = len(non_defective) / total_tiles
    assigned_fraction = len(result.assignments) / len(workloads)
    average_score = (
        sum(assigned_tile_scores) / used_count if assigned_tile_scores else 0.0
    )
    weak_fraction = len(profile.weak_tiles_used) / used_count if used_count else 0.0
    high_unassigned = sum(
        1
        for item in result.unassigned
        if item["criticality"] in {"high", "safety_critical"}
    )
    unassigned_high_fraction = high_unassigned / len(workloads)
    raw_score = 100.0 * (
        0.30 * non_defective_fraction
        + 0.30 * assigned_fraction
        + 0.40 * average_score
        - 0.05 * weak_fraction
        - 0.05 * unassigned_high_fraction
    )

    within_risk = [
        tile
        for tile in non_defective
        if tile.temp_risk <= constraints.max_temp_risk
        and tile.latency_penalty <= constraints.max_latency_penalty
        and tile.power_penalty <= constraints.max_power_penalty
    ]
    recovered_capacity = len(within_risk) / total_tiles
    evidence = (
        {
            "metric": "non_defective_tiles",
            "value": len(non_defective),
            "unit": "tiles",
            "total": total_tiles,
            "source": "synthetic_chip_map",
        },
        {
            "metric": "assigned_workloads",
            "value": len(result.assignments),
            "unit": "workloads",
            "total": len(workloads),
            "source": "deterministic_solver",
        },
        {
            "metric": "average_assigned_tile_score",
            "value": round(average_score, 6),
            "unit": "ratio_0_to_1",
            "source": "documented_tile_score_formula",
        },
        {
            "metric": "weak_tiles_used",
            "value": len(profile.weak_tiles_used),
            "unit": "tiles",
            "source": "candidate_profile",
        },
        {
            "metric": "functional_yield_score_formula",
            "value": SCORE_FORMULA,
            "unit": "score_0_to_100",
            "source": "compiler_v0.2_policy",
        },
        {
            "metric": "route_aware_placement",
            "placement_mode": result.placement_mode,
            "connected_assignments": all(
                route.connected for route in result.workload_routes if route.assigned
            ),
            "routable_assignments": all(
                route.routable for route in result.workload_routes if route.assigned
            ),
            "route_incomplete_assignments": sum(
                route.assigned and not route.routable
                for route in result.workload_routes
            ),
            "unassigned_no_safe_route": sum(
                route.reason == "no_connected_routable_tile_group"
                for route in result.workload_routes
            ),
            "candidate_only": True,
            "source": "bounded_route_aware_solver",
        },
    )
    if baseline_comparison_available:
        evidence += (
            {
                "metric": "baseline_comparison",
                "baseline_comparison_available": True,
                "comparison_modes": [
                    "strict_usable_only",
                    "no_route_awareness",
                    "route_aware",
                ],
                "recommended_mode": recommended_mode,
                "recommendation_status": recommendation_status,
                "recommendation_is_certification": False,
                "source": "deterministic_baseline_evaluators",
            },
        )
    return FunctionalPassport(
        chip_id=chip.chip_id,
        functional_yield_score=round(max(0.0, min(100.0, raw_score)), 2),
        recovered_capacity_estimate=round(recovered_capacity, 4),
        remaining_roles=profile.allowed_roles,
        blocked_roles=profile.blocked_roles,
        evidence=evidence,
    )
