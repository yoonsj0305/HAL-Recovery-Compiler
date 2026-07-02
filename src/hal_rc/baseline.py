"""Deterministic baseline evaluators for functional-yield trade-off evidence."""

from __future__ import annotations

from dataclasses import replace

from .comparison import BaselineResult, build_comparison_report, ComparisonReport
from .graph import build_graph
from .models import ChipMap, Constraints, SolverResult, Workload
from .passport import build_functional_passport
from .profile import build_recovery_profile
from .solver_greedy import solve_greedy
from .solver_route_aware import (
    find_route_to_group,
    is_connected_group,
    select_route_anchor,
    solve_route_aware,
)

CRITICALITY_WEIGHTS = {
    "safety_critical": 5.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}


def _summarize(
    mode: str,
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    result: SolverResult,
    *,
    route_aware_score: float | None = None,
    route_aware_capacity: float | None = None,
) -> BaselineResult:
    workload_by_id = {item.workload_id: item for item in workloads}
    tile_by_id = {tile.tile_id: tile for tile in chip.tiles}
    assigned_ids = tuple(sorted(item.workload_id for item in result.assignments))
    unassigned_ids = tuple(sorted(item["workload_id"] for item in result.unassigned))
    assigned_tiles = {
        assignment.workload_id: assignment.tile_ids for assignment in result.assignments
    }

    if mode == "no_route_awareness":
        anchor = select_route_anchor(chip, constraints)
        route_records: list[tuple[str, bool, tuple[str, ...], int | None]] = []
        for assignment in result.assignments:
            workload = workload_by_id[assignment.workload_id]
            route = (
                find_route_to_group(
                    chip,
                    constraints,
                    workload,
                    anchor,
                    assignment.tile_ids,
                    set(),
                )
                if anchor is not None
                else None
            )
            connected = is_connected_group(chip, assignment.tile_ids)
            complete = connected and route is not None
            route_records.append(
                (
                    assignment.workload_id,
                    complete,
                    route or (),
                    len(route) - 1 if complete and route is not None else None,
                )
            )
    else:
        route_records = [
            (
                route.workload_id,
                route.assigned and route.connected and route.routable,
                route.route_tile_ids,
                route.route_length,
            )
            for route in result.workload_routes
            if route.assigned
        ]

    complete_routes = sum(complete for _, complete, _, _ in route_records)
    incomplete_routes = len(result.assignments) - complete_routes
    route_lengths = [
        float(length)
        for _, complete, _, length in route_records
        if complete and length is not None
    ]
    assignment_tile_ids = {
        tile_id for tile_ids in assigned_tiles.values() for tile_id in tile_ids
    }
    route_tile_ids = {
        tile_id for _, _, path, _ in route_records for tile_id in path
    }
    used_tile_ids = assignment_tile_ids | route_tile_ids
    defective_assigned = sum(
        tile_by_id[tile_id].status == "defective"
        for tile_id in assignment_tile_ids
        if tile_id in tile_by_id
    )
    defective_routed = sum(
        tile_by_id[tile_id].status == "defective"
        for tile_id in route_tile_ids
        if tile_id in tile_by_id
    )
    safety_tile_ids = {
        tile_id
        for workload_id, tile_ids in assigned_tiles.items()
        if workload_by_id[workload_id].criticality == "safety_critical"
        for tile_id in tile_ids
    }
    safety_weak = sum(
        tile_by_id[tile_id].status == "weak"
        for tile_id in safety_tile_ids
        if tile_id in tile_by_id
    )
    safety_defective = sum(
        tile_by_id[tile_id].status == "defective"
        for tile_id in safety_tile_ids
        if tile_id in tile_by_id
    )
    safety_violations = (
        defective_assigned
        + defective_routed
        + safety_weak
        + safety_defective
        + int(constraints.hardware_control_enabled)
        + incomplete_routes
    )
    total = len(workloads)
    workload_coverage = len(result.assignments) / total if total else 0.0
    total_weight = sum(CRITICALITY_WEIGHTS[item.criticality] for item in workloads)
    assigned_weight = sum(
        CRITICALITY_WEIGHTS[workload_by_id[workload_id].criticality]
        for workload_id in assigned_ids
    )
    weighted_coverage = assigned_weight / total_weight if total_weight else 0.0
    non_defective_count = sum(tile.status != "defective" for tile in chip.tiles)
    fallback_capacity = (
        min(1.0, len(used_tile_ids) / non_defective_count)
        if non_defective_count
        else 0.0
    )
    recovered_capacity = (
        route_aware_capacity
        if route_aware_capacity is not None
        else fallback_capacity
    )
    route_completeness = (
        complete_routes / len(result.assignments) if result.assignments else 0.0
    )
    calculated_score = 100.0 * (
        0.40 * workload_coverage
        + 0.35 * weighted_coverage
        + 0.15 * recovered_capacity
        + 0.10 * route_completeness
    )
    functional_score = (
        route_aware_score if route_aware_score is not None else calculated_score
    )
    return BaselineResult(
        mode=mode,
        assigned_workloads=len(result.assignments),
        unassigned_workloads=len(result.unassigned),
        total_workloads=total,
        assigned_workload_ids=assigned_ids,
        unassigned_workload_ids=unassigned_ids,
        used_tiles_count=len(used_tile_ids),
        weak_tiles_used_count=sum(
            tile_by_id[tile_id].status == "weak"
            for tile_id in assignment_tile_ids
            if tile_id in tile_by_id
        ),
        defective_tiles_used_count=defective_assigned,
        route_complete_assignments=complete_routes,
        route_incomplete_assignments=incomplete_routes,
        average_route_length=round(
            sum(route_lengths) / len(route_lengths) if route_lengths else 0.0, 6
        ),
        max_route_length=int(max(route_lengths, default=0)),
        workload_coverage=round(workload_coverage, 6),
        functional_yield_score=round(max(0.0, min(100.0, functional_score)), 6),
        recovered_capacity_estimate=round(
            max(0.0, min(1.0, recovered_capacity)), 6
        ),
        criticality_weighted_coverage=round(weighted_coverage, 6),
        safety_violations_count=safety_violations,
        invariant_passed=safety_violations == 0,
    )


def evaluate_baselines(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
) -> tuple[BaselineResult, ...]:
    strict_constraints = replace(
        constraints, allow_weak_tiles_for_low_priority=False
    )
    strict_result = solve_route_aware(chip, workloads, strict_constraints)
    placement_first_result = solve_greedy(chip, workloads, constraints)
    route_aware_result = solve_route_aware(chip, workloads, constraints)

    profile = build_recovery_profile(
        chip,
        workloads,
        constraints,
        route_aware_result,
        build_graph(chip),
    )
    passport = build_functional_passport(
        chip, workloads, constraints, route_aware_result, profile
    )
    return (
        _summarize(
            "strict_usable_only",
            chip,
            workloads,
            strict_constraints,
            strict_result,
        ),
        _summarize(
            "no_route_awareness",
            chip,
            workloads,
            constraints,
            placement_first_result,
        ),
        _summarize(
            "route_aware",
            chip,
            workloads,
            constraints,
            route_aware_result,
            route_aware_score=passport.functional_yield_score,
            route_aware_capacity=passport.recovered_capacity_estimate,
        ),
    )


def run_baseline_comparison(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
) -> ComparisonReport:
    return build_comparison_report(
        chip.chip_id,
        evaluate_baselines(chip, workloads, constraints),
    )
