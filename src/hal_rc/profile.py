"""Candidate recovery profile generation."""

from __future__ import annotations

from . import __version__
from .graph import GridGraph
from .models import (
    BlockedRouteRecord,
    ChipMap,
    Constraints,
    PreferredRouteRecord,
    RecoveryProfile,
    SolverResult,
    Workload,
)

ALWAYS_BLOCKED_ROLES = (
    "financial_record_storage",
    "mission_critical_compute",
    "primary_filesystem_metadata",
    "safety_critical_control",
)


def build_recovery_profile(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    result: SolverResult,
    graph: GridGraph,
) -> RecoveryProfile:
    del constraints, graph
    by_id = {tile.tile_id: tile for tile in chip.tiles}
    used_ids = {
        tile_id for assignment in result.assignments for tile_id in assignment.tile_ids
    }
    weak_used = tuple(
        sorted(tile_id for tile_id in used_ids if by_id[tile_id].status == "weak")
    )

    preferred_routes = tuple(
        PreferredRouteRecord(
            workload_id=route.workload_id,
            route_id=f"ROUTE_{route.workload_id}",
            from_anchor=result.route_anchor_tile_id or "NO_ROUTE_ANCHOR",
            to_tiles=route.tile_ids,
            route_tile_ids=route.route_tile_ids,
        )
        for route in result.workload_routes
        if route.assigned and route.routable
    )
    blocked_routes = tuple(
        BlockedRouteRecord(
            workload_id=route.workload_id,
            reason=route.reason or "no_connected_routable_tile_group",
        )
        for route in result.workload_routes
        if not route.assigned
    )

    unassigned_roles = {item["role"] for item in result.unassigned}
    blocked_roles = tuple(sorted(set(ALWAYS_BLOCKED_ROLES) | unassigned_roles))
    allowed_roles = tuple(
        sorted(
            {
                assignment.role
                for assignment in result.assignments
                if assignment.role not in blocked_roles
            }
        )
    )
    return RecoveryProfile(
        chip_id=chip.chip_id,
        compiler_version=__version__,
        disabled_tiles=tuple(
            sorted(tile.tile_id for tile in chip.tiles if tile.status == "defective")
        ),
        weak_tiles_used=weak_used,
        assigned_workloads=result.assignments,
        unassigned_workloads=result.unassigned,
        preferred_routes=preferred_routes,
        blocked_routes=blocked_routes,
        allowed_roles=allowed_roles,
        blocked_roles=blocked_roles,
        timing_policy={
            "mode": "candidate_advisory_only",
            "derating_required_for_weak_tiles": bool(weak_used),
            "measured_timing_closure": False,
        },
        voltage_policy={
            "mode": "no_voltage_control",
            "voltage_changes_allowed": False,
        },
        runtime_loader_hint=(
            "Offline candidate profile only; do not load into hardware or firmware."
        ),
    )
