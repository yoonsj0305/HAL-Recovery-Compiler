"""Internal-consistency and safety invariant checks for generated artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from . import __version__
from .models import (
    ArtifactValidationReport,
    ChipMap,
    Constraints,
    Tile,
    Workload,
)
from .recommendation import recommendation_invariant_checks


@dataclass(slots=True)
class _CheckAccumulator:
    total: int = 0
    passed: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def check(self, condition: bool, message: str) -> None:
        self.total += 1
        if condition:
            self.passed += 1
        else:
            self.errors.append(message)

    def report(self) -> ArtifactValidationReport:
        failed = self.total - self.passed
        return ArtifactValidationReport(
            passed=failed == 0,
            invariant_checks_total=self.total,
            invariant_checks_passed=self.passed,
            invariant_checks_failed=failed,
            errors=tuple(self.errors),
            warnings=tuple(self.warnings),
            checked_at_version=__version__,
        )


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]


def _claim_boundaries(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "claim_boundary":
                yield child
            yield from _claim_boundaries(child)
    elif isinstance(value, list):
        for child in value:
            yield from _claim_boundaries(child)


def _contains_positive_production_or_certification_claim(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = key.lower().replace("-", "_").replace(" ", "_")
            if child is True and (
                "production_ready" in normalized_key
                or "certified" in normalized_key
                or "certification" in normalized_key
            ):
                return True
            if _contains_positive_production_or_certification_claim(child):
                return True
    elif isinstance(value, list):
        return any(_contains_positive_production_or_certification_claim(item) for item in value)
    elif isinstance(value, str):
        normalized = value.lower().replace("-", "_")
        if "not_certified" in normalized or "not certified" in normalized:
            return False
        forbidden = (
            "production_ready",
            "production ready",
            "certified for production",
            "safety certified",
            "silicon certified",
            "certification passed",
        )
        return any(term in normalized for term in forbidden)
    return False


def _connected(tile_ids: list[str], tile_by_id: dict[str, Tile]) -> bool:
    if not tile_ids or any(tile_id not in tile_by_id for tile_id in tile_ids):
        return False
    selected = set(tile_ids)
    stack = [tile_ids[0]]
    visited = {tile_ids[0]}
    while stack:
        current = tile_by_id[stack.pop()]
        for candidate_id in selected - visited:
            candidate = tile_by_id[candidate_id]
            if abs(current.x - candidate.x) + abs(current.y - candidate.y) == 1:
                visited.add(candidate_id)
                stack.append(candidate_id)
    return visited == selected


def _valid_path(tile_ids: list[str], tile_by_id: dict[str, Tile]) -> bool:
    if not tile_ids or any(tile_id not in tile_by_id for tile_id in tile_ids):
        return False
    return all(
        abs(tile_by_id[left].x - tile_by_id[right].x)
        + abs(tile_by_id[left].y - tile_by_id[right].y)
        == 1
        for left, right in zip(tile_ids, tile_ids[1:])
    )


def _first_path_jump(
    tile_ids: list[str],
    tile_by_id: dict[str, Tile],
) -> tuple[str, str] | None:
    for left, right in zip(tile_ids, tile_ids[1:]):
        if left not in tile_by_id or right not in tile_by_id:
            continue
        left_tile = tile_by_id[left]
        right_tile = tile_by_id[right]
        if abs(left_tile.x - right_tile.x) + abs(left_tile.y - right_tile.y) != 1:
            return left, right
    return None


def _constraint_blocked(tile: Tile, constraints: Constraints) -> bool:
    return (
        tile.status == "defective"
        or (
            tile.status == "weak"
            and not constraints.allow_weak_tiles_for_low_priority
        )
        or tile.temp_risk > constraints.max_temp_risk
        or tile.latency_penalty > constraints.max_latency_penalty
        or tile.power_penalty > constraints.max_power_penalty
    )


def validate_artifacts(
    chip_map: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    recovery_profile: dict[str, Any],
    functional_passport: dict[str, Any],
    solver_report: dict[str, Any],
    comparison_report: dict[str, Any] | None = None,
) -> ArtifactValidationReport:
    """Validate generated JSON artifacts against inputs and v0.2.2 invariants."""
    checks = _CheckAccumulator()
    artifacts = (recovery_profile, functional_passport, solver_report)

    # Hard safety boundary.
    checks.check(
        recovery_profile.get("hardware_control_enabled") is False,
        "recovery_profile.hardware_control_enabled must be false",
    )
    checks.check(
        recovery_profile.get("human_review_required") is True,
        "recovery_profile.human_review_required must be true",
    )
    checks.check(
        functional_passport.get("hardware_control_enabled") is False,
        "functional_passport.hardware_control_enabled must be false",
    )
    checks.check(
        functional_passport.get("human_review_required") is True,
        "functional_passport.human_review_required must be true",
    )
    checks.check(
        solver_report.get("hardware_control_enabled") is False,
        "solver_report.hardware_control_enabled must be false",
    )
    checks.check(
        solver_report.get("human_review_required") is True,
        "solver_report.human_review_required must be true",
    )
    checks.check(
        recovery_profile.get("claim_boundary") == "simulation_only_not_certified",
        "recovery_profile.claim_boundary must be simulation_only_not_certified",
    )
    checks.check(
        functional_passport.get("claim_boundary") == "simulation_only_not_certified",
        "functional_passport.claim_boundary must be simulation_only_not_certified",
    )
    checks.check(
        solver_report.get("claim_boundary") == "simulation_only_not_certified",
        "solver_report.claim_boundary must be simulation_only_not_certified",
    )
    checks.check(
        functional_passport.get("artifact_self_check_available") is True,
        "functional_passport must advertise artifact_self_check_available=true",
    )
    boundaries = [boundary for artifact in artifacts for boundary in _claim_boundaries(artifact)]
    checks.check(bool(boundaries), "artifacts must expose claim_boundary")
    checks.check(
        all(boundary == "simulation_only_not_certified" for boundary in boundaries),
        "every claim_boundary must be simulation_only_not_certified",
    )
    checks.check(
        not any(_contains_positive_production_or_certification_claim(a) for a in artifacts),
        "artifacts must not claim production readiness or certification",
    )

    tile_by_id = {tile.tile_id: tile for tile in chip_map.tiles}
    workload_by_id = {workload.workload_id: workload for workload in workloads}
    assigned = _dict_list(recovery_profile.get("assigned_workloads"))
    unassigned = _dict_list(recovery_profile.get("unassigned_workloads"))
    workload_routes = _dict_list(solver_report.get("workload_routes"))
    preferred_routes = _dict_list(recovery_profile.get("preferred_routes"))
    assigned_ids = [str(item.get("workload_id", "")) for item in assigned]
    unassigned_ids = [str(item.get("workload_id", "")) for item in unassigned]
    assigned_tiles = {
        item.get("workload_id"): _string_list(item.get("tile_ids")) for item in assigned
    }
    route_by_workload = {
        item.get("workload_id"): item
        for item in workload_routes
        if item.get("assigned") is True
    }
    assignment_tile_ids = [
        tile_id for tile_ids in assigned_tiles.values() for tile_id in tile_ids
    ]
    route_tile_ids = [
        tile_id
        for route in workload_routes
        for tile_id in _string_list(route.get("route_tile_ids"))
    ]
    route_tile_ids.extend(
        tile_id
        for route in preferred_routes
        for tile_id in _string_list(route.get("route_tile_ids"))
    )
    referenced_ids = (
        assignment_tile_ids
        + route_tile_ids
        + _string_list(solver_report.get("used_tile_ids"))
        + _string_list(solver_report.get("blocked_tile_ids"))
    )

    # Tile validity.
    checks.check(
        all(tile_id in tile_by_id for tile_id in assignment_tile_ids),
        "every assigned tile_id must exist in the chip map",
    )
    checks.check(
        all(tile_id in tile_by_id for tile_id in route_tile_ids),
        "every route_tile_id must exist in the chip map",
    )
    checks.check(
        all(tile_by_id[tile_id].status != "defective" for tile_id in assignment_tile_ids if tile_id in tile_by_id),
        "defective tiles must not appear in assigned workload tile IDs",
    )
    checks.check(
        all(tile_by_id[tile_id].status != "defective" for tile_id in route_tile_ids if tile_id in tile_by_id),
        "defective tiles must not appear in route_tile_ids",
    )
    checks.check(
        all(
            0 <= tile_by_id[tile_id].x < chip_map.width
            and 0 <= tile_by_id[tile_id].y < chip_map.height
            for tile_id in referenced_ids
            if tile_id in tile_by_id
        ),
        "artifact tile references must remain inside chip bounds",
    )
    blocked_ids = _string_list(solver_report.get("blocked_tile_ids"))
    checks.check(
        all(
            tile_id in tile_by_id and _constraint_blocked(tile_by_id[tile_id], constraints)
            for tile_id in blocked_ids
        ),
        "blocked_tile_ids must be defective or blocked by constraints",
    )

    # Workload identity and exclusivity.
    checks.check(
        all(workload_id in workload_by_id for workload_id in assigned_ids),
        "every assigned workload must exist in workloads input",
    )
    checks.check(
        all(workload_id in workload_by_id for workload_id in unassigned_ids),
        "every unassigned workload must exist in workloads input",
    )
    checks.check(
        set(assigned_ids).isdisjoint(unassigned_ids),
        "a workload cannot be both assigned and unassigned",
    )
    checks.check(
        len(assigned) == solver_report.get("assigned_workloads"),
        "assigned_workloads count must match solver_report",
    )
    checks.check(
        len(unassigned) == solver_report.get("unassigned_workloads"),
        "unassigned_workloads count must match solver_report",
    )
    checks.check(
        len(assignment_tile_ids) == len(set(assignment_tile_ids)),
        "compute tiles cannot be reused across workload assignments",
    )
    checks.check(
        all(
            len(assigned_tiles.get(workload_id, [])) == workload_by_id[workload_id].compute_required
            for workload_id in assigned_ids
            if workload_id in workload_by_id
        ),
        "each assignment must contain compute_required tiles",
    )

    # Safety-critical placement and route constraints.
    safety_ids = {
        workload_id
        for workload_id in assigned_ids
        if workload_id in workload_by_id
        and workload_by_id[workload_id].criticality == "safety_critical"
    }
    safety_assignment_tiles = [
        tile_id for workload_id in safety_ids for tile_id in assigned_tiles.get(workload_id, [])
    ]
    safety_route_tiles = [
        tile_id
        for workload_id in safety_ids
        for tile_id in _string_list(route_by_workload.get(workload_id, {}).get("route_tile_ids"))
    ]
    checks.check(
        all(tile_by_id[tile_id].status != "weak" for tile_id in safety_assignment_tiles if tile_id in tile_by_id),
        "safety_critical workloads must not use weak compute tiles",
    )
    checks.check(
        all(tile_by_id[tile_id].status != "defective" for tile_id in safety_assignment_tiles if tile_id in tile_by_id),
        "safety_critical workloads must not use defective compute tiles",
    )
    checks.check(
        all(tile_by_id[tile_id].status != "defective" for tile_id in safety_route_tiles if tile_id in tile_by_id),
        "safety_critical routes must not pass through defective tiles",
    )
    checks.check(
        not constraints.forbid_safety_critical_on_weak_tiles
        or all(tile_by_id[tile_id].status != "weak" for tile_id in safety_route_tiles if tile_id in tile_by_id),
        "safety_critical routes must not pass through weak tiles under current policy",
    )

    # Connectivity and anchor routing.
    checks.check(
        all(_connected(tile_ids, tile_by_id) for tile_ids in assigned_tiles.values()),
        "each assigned tile group must be internally 4-neighbor connected",
    )
    checks.check(
        all(workload_id in route_by_workload for workload_id in assigned_ids),
        "each assigned workload must have route telemetry",
    )
    anchor = solver_report.get("route_anchor_tile_id")
    assigned_route_paths = {
        workload_id: _string_list(route_by_workload.get(workload_id, {}).get("route_tile_ids"))
        for workload_id in assigned_ids
    }
    checks.check(
        all(path and path[0] == anchor for path in assigned_route_paths.values()),
        "each assigned route must start at route_anchor_tile_id",
    )
    checks.check(
        all(_valid_path(path, tile_by_id) for path in assigned_route_paths.values()),
        "route_tile_ids must form a contiguous 4-neighbor path",
    )
    checks.check(
        all(
            set(path).intersection(assigned_tiles.get(workload_id, []))
            for workload_id, path in assigned_route_paths.items()
        ),
        "each route must reach at least one assigned tile for its workload",
    )
    checks.check(
        solver_report.get("route_incomplete_assignments") == 0,
        "route_incomplete_assignments must be 0 for accepted assignments",
    )

    # Preferred route truthfulness and cross-artifact agreement.
    preferred_route_ids = [str(route.get("route_id", "")) for route in preferred_routes]
    preferred_by_workload: dict[str, list[dict[str, Any]]] = {}
    required_preferred_fields = {
        "workload_id",
        "route_id",
        "from_anchor",
        "to_tiles",
        "route_tile_ids",
        "route_status",
    }
    for preferred in preferred_routes:
        route_id = str(preferred.get("route_id") or "<missing_route_id>")
        workload_id = str(preferred.get("workload_id") or "")
        preferred_by_workload.setdefault(workload_id, []).append(preferred)
        missing_fields = sorted(required_preferred_fields - preferred.keys())
        checks.check(
            not missing_fields,
            f"preferred_route {route_id} missing required fields: {', '.join(missing_fields)}",
        )
        checks.check(
            workload_id in workload_by_id,
            f"preferred_route {route_id} references unknown workload {workload_id}",
        )
        checks.check(
            workload_id in assigned_ids,
            f"preferred_route {route_id} workload {workload_id} is not assigned",
        )
        checks.check(
            preferred_route_ids.count(str(preferred.get("route_id", ""))) == 1,
            f"preferred_route {route_id} route_id is duplicated",
        )

        from_anchor = preferred.get("from_anchor")
        checks.check(
            from_anchor == anchor,
            f"preferred_route {route_id} from_anchor {from_anchor} does not match route anchor {anchor}",
        )
        checks.check(
            isinstance(from_anchor, str) and from_anchor in tile_by_id,
            f"preferred_route {route_id} from_anchor {from_anchor} does not exist in chip map",
        )
        to_tiles = _string_list(preferred.get("to_tiles"))
        unknown_to_tiles = [tile_id for tile_id in to_tiles if tile_id not in tile_by_id]
        checks.check(
            not unknown_to_tiles,
            f"preferred_route {route_id} to_tiles contains unknown tile {unknown_to_tiles[0] if unknown_to_tiles else ''}",
        )
        path = _string_list(preferred.get("route_tile_ids"))
        unknown_path_tiles = [tile_id for tile_id in path if tile_id not in tile_by_id]
        checks.check(
            not unknown_path_tiles,
            f"preferred_route {route_id} route_tile_ids contains unknown tile {unknown_path_tiles[0] if unknown_path_tiles else ''}",
        )
        defective_path_tiles = [
            tile_id
            for tile_id in path
            if tile_id in tile_by_id and tile_by_id[tile_id].status == "defective"
        ]
        checks.check(
            not defective_path_tiles,
            f"preferred_route {route_id} uses defective tile {defective_path_tiles[0] if defective_path_tiles else ''}",
        )
        outside_path_tiles = [
            tile_id
            for tile_id in path
            if tile_id in tile_by_id
            and not (
                0 <= tile_by_id[tile_id].x < chip_map.width
                and 0 <= tile_by_id[tile_id].y < chip_map.height
            )
        ]
        checks.check(
            not outside_path_tiles,
            f"preferred_route {route_id} uses out-of-bounds tile {outside_path_tiles[0] if outside_path_tiles else ''}",
        )
        jump = _first_path_jump(path, tile_by_id)
        checks.check(
            jump is None,
            (
                f"preferred_route {route_id} jumps from {jump[0]} to {jump[1]}"
                if jump is not None
                else f"preferred_route {route_id} path is 4-neighbor contiguous"
            ),
        )
        checks.check(
            bool(path) and path[0] == from_anchor,
            f"preferred_route {route_id} does not start at route anchor {from_anchor}",
        )
        checks.check(
            bool(set(path).intersection(to_tiles)),
            f"preferred_route {route_id} does not reach any assigned tile",
        )
        checks.check(
            preferred.get("route_status") == "candidate_simulated",
            f"preferred_route {route_id} route_status must be candidate_simulated",
        )
        checks.check(
            "claim_boundary" not in preferred
            or preferred.get("claim_boundary") == "simulation_only_not_certified",
            f"preferred_route {route_id} claim_boundary must be simulation_only_not_certified",
        )

        solver_route = route_by_workload.get(workload_id)
        checks.check(
            solver_route is not None,
            f"preferred_route {route_id} has no matching solver_report workload_route",
        )
        solver_tile_ids = _string_list(
            solver_route.get("tile_ids") if solver_route is not None else None
        )
        checks.check(
            set(to_tiles) == set(solver_tile_ids),
            f"preferred_route {route_id} to_tiles differ from solver_report workload_routes",
        )
        solver_path = _string_list(
            solver_route.get("route_tile_ids") if solver_route is not None else None
        )
        checks.check(
            path == solver_path,
            f"preferred_route {route_id} route_tile_ids differ from solver_report workload_routes",
        )
        checks.check(
            solver_route is not None
            and solver_route.get("assigned") is True
            and solver_route.get("routable") is True,
            f"preferred_route {route_id} disagrees with solver_report routability",
        )
        checks.check(
            set(to_tiles) == set(assigned_tiles.get(workload_id, [])),
            f"preferred_route {route_id} to_tiles differ from recovery_profile assigned_workloads",
        )

    for workload_id in assigned_ids:
        matches = preferred_by_workload.get(workload_id, [])
        checks.check(
            len(matches) == 1,
            f"assigned workload {workload_id} must have exactly one preferred_route",
        )
        solver_route = route_by_workload.get(workload_id)
        checks.check(
            solver_route is not None,
            f"assigned workload {workload_id} must have a matching solver_report workload_route",
        )
        if solver_route is not None:
            checks.check(
                set(_string_list(solver_route.get("tile_ids")))
                == set(assigned_tiles.get(workload_id, [])),
                f"assigned workload {workload_id} tile_ids differ from solver_report workload_routes",
            )

    # Deterministic representation.
    checks.check(
        all(tile_ids == sorted(tile_ids) for tile_ids in assigned_tiles.values()),
        "assigned workload tile_id lists must be sorted",
    )
    checks.check(
        all(len(tile_ids) == len(set(tile_ids)) for tile_ids in assigned_tiles.values()),
        "a workload assignment must not contain duplicate tile IDs",
    )
    checks.check(
        _string_list(solver_report.get("used_tile_ids"))
        == sorted(_string_list(solver_report.get("used_tile_ids"))),
        "used_tile_ids must be sorted",
    )
    checks.check(
        blocked_ids == sorted(blocked_ids),
        "blocked_tile_ids must be sorted",
    )
    checks.check(
        all(
            _string_list(route.get("to_tiles")) == sorted(_string_list(route.get("to_tiles")))
            for route in preferred_routes
        ),
        "preferred route to_tiles must be sorted",
    )

    # Score and report consistency.
    used_ids = _string_list(solver_report.get("used_tile_ids"))
    checks.check(
        solver_report.get("used_tiles_count") == len(used_ids),
        "used_tiles_count must equal len(used_tile_ids)",
    )
    checks.check(
        solver_report.get("blocked_tiles_count") == len(blocked_ids),
        "blocked_tiles_count must equal len(blocked_tile_ids)",
    )
    assigned_route_records = [route for route in workload_routes if route.get("assigned") is True]
    complete_count = sum(route.get("routable") is True for route in assigned_route_records)
    incomplete_count = sum(route.get("routable") is not True for route in assigned_route_records)
    checks.check(
        solver_report.get("route_complete_assignments") == complete_count,
        "route_complete_assignments must match routable workload_routes",
    )
    checks.check(
        solver_report.get("route_incomplete_assignments") == incomplete_count,
        "route_incomplete_assignments must match incomplete workload_routes",
    )
    route_lengths = [
        float(route["route_length"])
        for route in assigned_route_records
        if route.get("routable") is True and isinstance(route.get("route_length"), (int, float))
    ]
    expected_average = sum(route_lengths) / len(route_lengths) if route_lengths else 0.0
    reported_average = solver_report.get("average_route_length")
    checks.check(
        isinstance(reported_average, (int, float))
        and abs(float(reported_average) - expected_average) <= 1e-6,
        "average_route_length must match workload route lengths",
    )
    checks.check(
        solver_report.get("max_route_length") == int(max(route_lengths, default=0)),
        "max_route_length must match workload route lengths",
    )
    candidate_count = solver_report.get("candidate_groups_evaluated")
    checks.check(
        isinstance(candidate_count, int) and candidate_count >= len(assigned),
        "candidate_groups_evaluated must be >= assigned_workloads",
    )

    if comparison_report is not None:
        for condition, message in recommendation_invariant_checks(comparison_report):
            checks.check(condition, message)

    return checks.report()
