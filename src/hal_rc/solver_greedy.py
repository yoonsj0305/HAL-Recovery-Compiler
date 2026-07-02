"""Bounded deterministic greedy workload assignment."""

from __future__ import annotations

from .models import (
    ChipMap,
    Constraints,
    SolverResult,
    Tile,
    Workload,
    WorkloadAssignment,
)

CRITICALITY_ORDER = {
    "safety_critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def tile_is_eligible(tile: Tile, workload: Workload, constraints: Constraints) -> bool:
    if tile.status == "defective":
        return False
    if tile.temp_risk > constraints.max_temp_risk:
        return False
    if tile.latency_penalty > constraints.max_latency_penalty:
        return False
    if tile.power_penalty > constraints.max_power_penalty:
        return False
    if tile.confidence < workload.reliability_required:
        return False

    if workload.criticality == "safety_critical":
        if tile.status != "usable":
            return False
        if constraints.forbid_safety_critical_on_weak_tiles and tile.status == "weak":
            return False
        if tile.confidence < max(workload.reliability_required, 0.90):
            return False
        safety_temp = min(constraints.max_temp_risk, 0.25)
        safety_latency = min(constraints.max_latency_penalty, 0.25)
        safety_power = min(constraints.max_power_penalty, 0.25)
        return (
            tile.temp_risk <= safety_temp
            and tile.latency_penalty <= safety_latency
            and tile.power_penalty <= safety_power
        )

    if tile.status == "weak":
        return (
            workload.criticality == "low"
            and constraints.allow_weak_tiles_for_low_priority
        )
    return True


def _tile_sort_key(tile: Tile) -> tuple[float, int, int, str]:
    return (-tile.score, tile.y, tile.x, tile.tile_id)


def solve_greedy(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
) -> SolverResult:
    """Assign whole workloads atomically; partial assignments are rejected."""
    available = {tile.tile_id: tile for tile in chip.tiles if tile.status != "defective"}
    assignments: list[WorkloadAssignment] = []
    unassigned: list[dict[str, str]] = []

    ordered_workloads = sorted(
        workloads,
        key=lambda item: (CRITICALITY_ORDER[item.criticality], item.workload_id),
    )
    for workload in ordered_workloads:
        candidates = sorted(
            (
                tile
                for tile in available.values()
                if tile_is_eligible(tile, workload, constraints)
            ),
            key=_tile_sort_key,
        )
        if len(candidates) < workload.compute_required:
            unassigned.append(
                {
                    "workload_id": workload.workload_id,
                    "role": workload.role,
                    "criticality": workload.criticality,
                    "reason": (
                        "insufficient_eligible_tiles:"
                        f"required={workload.compute_required},available={len(candidates)}"
                    ),
                }
            )
            continue
        selected = tuple(candidates[: workload.compute_required])
        assignment_score = sum(tile.score for tile in selected) / len(selected)
        assignments.append(
            WorkloadAssignment(
                workload_id=workload.workload_id,
                role=workload.role,
                criticality=workload.criticality,
                tile_ids=tuple(tile.tile_id for tile in selected),
                tile_scores=tuple(round(tile.score, 6) for tile in selected),
                assignment_score=round(assignment_score, 6),
            )
        )
        for tile in selected:
            del available[tile.tile_id]

    objective = sum(
        assignment.assignment_score * len(assignment.tile_ids)
        for assignment in assignments
    )
    return SolverResult(
        assignments=tuple(assignments),
        unassigned=tuple(unassigned),
        objective_score=round(objective, 6),
    )

