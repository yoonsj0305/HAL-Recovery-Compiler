"""Optional bounded, deterministic, safety-preserving local search."""

from __future__ import annotations

from .models import (
    ChipMap,
    Constraints,
    SolverResult,
    Workload,
    WorkloadAssignment,
)
from .solver_greedy import tile_is_eligible


def improve_solution(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    initial: SolverResult,
    *,
    max_iterations: int = 100,
) -> SolverResult:
    if max_iterations < 0:
        raise ValueError("max_iterations must be >= 0")
    if initial.placement_mode == "route_aware":
        # v0.2.0 deliberately rejects tile-wise swaps because a single swap can
        # fragment a connected group or invalidate its anchor route. A bounded
        # route-aware move generator is deferred; preserving a valid placement
        # is safer than optimizing it with the placement-first neighborhood.
        return initial
    by_tile = {tile.tile_id: tile for tile in chip.tiles}
    by_workload = {workload.workload_id: workload for workload in workloads}
    mutable = [list(assignment.tile_ids) for assignment in initial.assignments]
    used = {tile_id for tile_ids in mutable for tile_id in tile_ids}

    for _ in range(max_iterations):
        best_move: tuple[float, int, int, str] | None = None
        for assignment_index, assignment in enumerate(initial.assignments):
            workload = by_workload[assignment.workload_id]
            current_ids = mutable[assignment_index]
            for position, old_id in enumerate(current_ids):
                old_tile = by_tile[old_id]
                for candidate in chip.tiles:
                    if candidate.tile_id in used:
                        continue
                    if not tile_is_eligible(candidate, workload, constraints):
                        continue
                    gain = candidate.score - old_tile.score
                    if gain <= 1e-12:
                        continue
                    move = (gain, assignment_index, position, candidate.tile_id)
                    if best_move is None or (
                        gain > best_move[0]
                        or (gain == best_move[0] and move[1:] < best_move[1:])
                    ):
                        best_move = move
        if best_move is None:
            break
        _, assignment_index, position, candidate_id = best_move
        old_id = mutable[assignment_index][position]
        mutable[assignment_index][position] = candidate_id
        used.remove(old_id)
        used.add(candidate_id)

    improved: list[WorkloadAssignment] = []
    for assignment, tile_ids in zip(initial.assignments, mutable):
        tiles = [by_tile[tile_id] for tile_id in tile_ids]
        score = sum(tile.score for tile in tiles) / len(tiles)
        improved.append(
            WorkloadAssignment(
                workload_id=assignment.workload_id,
                role=assignment.role,
                criticality=assignment.criticality,
                tile_ids=tuple(tile_ids),
                tile_scores=tuple(round(tile.score, 6) for tile in tiles),
                assignment_score=round(score, 6),
            )
        )
    objective = sum(item.assignment_score * len(item.tile_ids) for item in improved)
    return SolverResult(tuple(improved), initial.unassigned, round(objective, 6))
