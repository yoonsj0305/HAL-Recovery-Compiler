"""Bounded deterministic route-aware placement for v0.2.0."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .models import (
    ChipMap,
    Constraints,
    SolverResult,
    Tile,
    Workload,
    WorkloadAssignment,
    WorkloadRoute,
)
from .solver_greedy import CRITICALITY_ORDER, tile_is_eligible

DEFAULT_MAX_CANDIDATE_SEEDS = 64
DEFAULT_MAX_BFS_EXPANSIONS_PER_SEED = 256
# v0.1.x routes could traverse tiles assigned to another workload. v0.2.0 keeps
# that explicit shared-transit behavior while compute ownership remains exclusive.
SHARED_ROUTE_TRANSIT_ALLOWED = True


@dataclass(frozen=True, slots=True)
class _CandidateGroup:
    tile_ids: tuple[str, ...]
    tile_scores: tuple[float, ...]
    average_tile_score: float
    route_tile_ids: tuple[str, ...]
    route_length: int
    weak_tile_count: int
    placement_score: float


def _tile_score_key(tile: Tile) -> tuple[float, int, int, str]:
    return (-tile.score, tile.y, tile.x, tile.tile_id)


def _workload_key(workload: Workload) -> tuple[int, float, float, int, str]:
    return (
        CRITICALITY_ORDER[workload.criticality],
        -workload.reliability_required,
        -workload.latency_sensitivity,
        -workload.compute_required,
        workload.workload_id,
    )


def _within_global_route_constraints(tile: Tile, constraints: Constraints) -> bool:
    return (
        tile.status != "defective"
        and tile.temp_risk <= constraints.max_temp_risk
        and tile.latency_penalty <= constraints.max_latency_penalty
        and tile.power_penalty <= constraints.max_power_penalty
    )


def select_route_anchor(chip: ChipMap, constraints: Constraints) -> str | None:
    """Reserve the top-left globally safe usable tile as routing infrastructure."""
    candidates = sorted(
        (
            tile
            for tile in chip.tiles
            if tile.status == "usable"
            and _within_global_route_constraints(tile, constraints)
        ),
        key=lambda tile: (tile.y, tile.x, tile.tile_id),
    )
    return candidates[0].tile_id if candidates else None


def _coordinate_index(chip: ChipMap) -> dict[tuple[int, int], Tile]:
    return {(tile.x, tile.y): tile for tile in chip.tiles}


def _neighbors(
    tile: Tile,
    by_coordinate: dict[tuple[int, int], Tile],
) -> tuple[Tile, ...]:
    output = []
    for coordinate in (
        (tile.x, tile.y - 1),
        (tile.x - 1, tile.y),
        (tile.x + 1, tile.y),
        (tile.x, tile.y + 1),
    ):
        neighbor = by_coordinate.get(coordinate)
        if neighbor is not None:
            output.append(neighbor)
    return tuple(output)


def is_connected_group(
    chip: ChipMap,
    tile_ids: tuple[str, ...],
) -> bool:
    if not tile_ids:
        return False
    selected = set(tile_ids)
    by_id = {tile.tile_id: tile for tile in chip.tiles}
    by_coordinate = _coordinate_index(chip)
    if not selected.issubset(by_id):
        return False
    queue: deque[str] = deque([min(selected)])
    visited = {queue[0]}
    while queue:
        current = by_id[queue.popleft()]
        for neighbor in _neighbors(current, by_coordinate):
            if neighbor.tile_id in selected and neighbor.tile_id not in visited:
                visited.add(neighbor.tile_id)
                queue.append(neighbor.tile_id)
    return visited == selected


def _expand_connected_group(
    seed: Tile,
    eligible_by_id: dict[str, Tile],
    by_coordinate: dict[tuple[int, int], Tile],
    required: int,
    max_expansions: int,
) -> tuple[Tile, ...] | None:
    queue: deque[Tile] = deque([seed])
    queued = {seed.tile_id}
    selected: list[Tile] = []
    expansions = 0
    while queue and len(selected) < required and expansions < max_expansions:
        current = queue.popleft()
        selected.append(current)
        expansions += 1
        neighbors = sorted(
            (
                neighbor
                for neighbor in _neighbors(current, by_coordinate)
                if neighbor.tile_id in eligible_by_id
                and neighbor.tile_id not in queued
            ),
            key=_tile_score_key,
        )
        for neighbor in neighbors:
            queued.add(neighbor.tile_id)
            queue.append(neighbor)
    if len(selected) != required:
        return None
    return tuple(selected)


def _route_allows_tile(
    tile: Tile,
    workload: Workload,
    constraints: Constraints,
    assigned_tile_ids: set[str],
    anchor_tile_id: str,
) -> bool:
    if tile.tile_id == anchor_tile_id:
        return _within_global_route_constraints(tile, constraints)
    if tile.tile_id in assigned_tile_ids and not SHARED_ROUTE_TRANSIT_ALLOWED:
        return False
    if not _within_global_route_constraints(tile, constraints):
        return False
    if tile.status == "weak":
        return (
            workload.criticality == "low"
            and constraints.allow_weak_tiles_for_low_priority
        )
    return True


def find_route_to_group(
    chip: ChipMap,
    constraints: Constraints,
    workload: Workload,
    anchor_tile_id: str,
    group_tile_ids: tuple[str, ...],
    assigned_tile_ids: set[str],
) -> tuple[str, ...] | None:
    """Find the shortest deterministic safe BFS path from anchor to the group."""
    by_id = {tile.tile_id: tile for tile in chip.tiles}
    if anchor_tile_id not in by_id:
        return None
    targets = set(group_tile_ids)
    by_coordinate = _coordinate_index(chip)
    queue: deque[str] = deque([anchor_tile_id])
    previous: dict[str, str | None] = {anchor_tile_id: None}
    while queue:
        current_id = queue.popleft()
        if current_id in targets:
            path = [current_id]
            cursor = previous[current_id]
            while cursor is not None:
                path.append(cursor)
                cursor = previous[cursor]
            return tuple(reversed(path))
        current = by_id[current_id]
        for neighbor in _neighbors(current, by_coordinate):
            if neighbor.tile_id in previous:
                continue
            if neighbor.tile_id in targets:
                allowed = True
            else:
                allowed = _route_allows_tile(
                    neighbor,
                    workload,
                    constraints,
                    assigned_tile_ids,
                    anchor_tile_id,
                )
            if not allowed:
                continue
            previous[neighbor.tile_id] = current_id
            queue.append(neighbor.tile_id)
    return None


def _candidate_sort_key(candidate: _CandidateGroup) -> tuple[object, ...]:
    return (
        -candidate.placement_score,
        -candidate.average_tile_score,
        candidate.route_length,
        candidate.weak_tile_count,
        candidate.tile_ids,
    )


def solve_route_aware(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    *,
    max_candidate_seeds: int = DEFAULT_MAX_CANDIDATE_SEEDS,
    max_bfs_expansions_per_seed: int = DEFAULT_MAX_BFS_EXPANSIONS_PER_SEED,
) -> SolverResult:
    if max_candidate_seeds < 1 or max_bfs_expansions_per_seed < 1:
        raise ValueError("route-aware search bounds must be positive")

    anchor = select_route_anchor(chip, constraints)
    by_coordinate = _coordinate_index(chip)
    assigned_tile_ids: set[str] = set()
    assignments: list[WorkloadAssignment] = []
    unassigned: list[dict[str, str]] = []
    workload_routes: list[WorkloadRoute] = []
    evaluated = 0
    rejected_connectivity = 0
    rejected_routing = 0

    for workload in sorted(workloads, key=_workload_key):
        eligible = sorted(
            (
                tile
                for tile in chip.tiles
                if tile.tile_id != anchor
                and tile.tile_id not in assigned_tile_ids
                and tile_is_eligible(tile, workload, constraints)
            ),
            key=_tile_score_key,
        )
        if anchor is None:
            reason = "no_route_anchor"
        elif len(eligible) < workload.compute_required:
            reason = (
                "insufficient_eligible_tiles:"
                f"required={workload.compute_required},available={len(eligible)}"
            )
        else:
            eligible_by_id = {tile.tile_id: tile for tile in eligible}
            candidates: list[_CandidateGroup] = []
            for seed in eligible[:max_candidate_seeds]:
                group = _expand_connected_group(
                    seed,
                    eligible_by_id,
                    by_coordinate,
                    workload.compute_required,
                    max_bfs_expansions_per_seed,
                )
                if group is None:
                    rejected_connectivity += 1
                    continue
                evaluated += 1
                ordered_ids = tuple(sorted(tile.tile_id for tile in group))
                route = find_route_to_group(
                    chip,
                    constraints,
                    workload,
                    anchor,
                    ordered_ids,
                    assigned_tile_ids,
                )
                if route is None:
                    rejected_routing += 1
                    continue
                average_score = sum(tile.score for tile in group) / len(group)
                weak_count = sum(tile.status == "weak" for tile in group)
                route_length = len(route) - 1
                placement_score = (
                    average_score - 0.03 * route_length - 0.10 * weak_count
                )
                score_by_id = {tile.tile_id: tile.score for tile in group}
                candidates.append(
                    _CandidateGroup(
                        tile_ids=ordered_ids,
                        tile_scores=tuple(
                            round(score_by_id[tile_id], 6) for tile_id in ordered_ids
                        ),
                        average_tile_score=round(average_score, 6),
                        route_tile_ids=route,
                        route_length=route_length,
                        weak_tile_count=weak_count,
                        placement_score=round(placement_score, 6),
                    )
                )
            if candidates:
                best = min(candidates, key=_candidate_sort_key)
                assignments.append(
                    WorkloadAssignment(
                        workload_id=workload.workload_id,
                        role=workload.role,
                        criticality=workload.criticality,
                        tile_ids=best.tile_ids,
                        tile_scores=best.tile_scores,
                        assignment_score=best.placement_score,
                    )
                )
                assigned_tile_ids.update(best.tile_ids)
                workload_routes.append(
                    WorkloadRoute(
                        workload_id=workload.workload_id,
                        assigned=True,
                        connected=True,
                        routable=True,
                        route_length=best.route_length,
                        tile_ids=best.tile_ids,
                        route_tile_ids=best.route_tile_ids,
                    )
                )
                continue
            reason = "no_connected_routable_tile_group"

        unassigned.append(
            {
                "workload_id": workload.workload_id,
                "role": workload.role,
                "criticality": workload.criticality,
                "reason": reason,
            }
        )
        workload_routes.append(
            WorkloadRoute(
                workload_id=workload.workload_id,
                assigned=False,
                connected=False,
                routable=False,
                route_length=None,
                tile_ids=(),
                route_tile_ids=(),
                reason=reason,
            )
        )

    objective = sum(
        assignment.assignment_score * len(assignment.tile_ids)
        for assignment in assignments
    )
    return SolverResult(
        assignments=tuple(assignments),
        unassigned=tuple(unassigned),
        objective_score=round(objective, 6),
        workload_routes=tuple(workload_routes),
        placement_mode="route_aware",
        route_anchor_tile_id=anchor,
        candidate_groups_evaluated=evaluated,
        candidate_groups_rejected_connectivity=rejected_connectivity,
        candidate_groups_rejected_routing=rejected_routing,
    )
