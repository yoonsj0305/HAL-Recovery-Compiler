"""Machine-readable and standalone HTML reporting."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .models import (
    ChipMap,
    Constraints,
    FunctionalPassport,
    ArtifactValidationReport,
    RecoveryProfile,
    SolverReport,
    SolverResult,
    Workload,
)
from .comparison import ComparisonReport

ROUTE_WARNING = (
    "An accepted assignment has an incomplete route. This violates the v0.2.0 "
    "route-aware placement invariant and requires review."
)


def build_solver_report(
    chip: ChipMap,
    workloads: tuple[Workload, ...],
    constraints: Constraints,
    result: SolverResult,
    profile: RecoveryProfile,
    *,
    runtime_ms: float,
    solver_name: str,
    local_search_enabled: bool = False,
    local_search_iterations: int = 0,
    local_search_improvement_delta: float = 0.0,
) -> SolverReport:
    warnings: list[str] = []
    if result.unassigned:
        warnings.append(f"{len(result.unassigned)} workload(s) remain unassigned")
    if profile.weak_tiles_used:
        warnings.append(
            f"{len(profile.weak_tiles_used)} weak tile(s) used for low-criticality work"
        )
    assigned_routes = tuple(route for route in result.workload_routes if route.assigned)
    incomplete_routes = tuple(
        route for route in assigned_routes if not route.connected or not route.routable
    )
    route_lengths = tuple(
        route.route_length
        for route in assigned_routes
        if route.route_length is not None and route.routable
    )
    route_warnings: tuple[str, ...] = ()
    route_warning: str | None = None
    if incomplete_routes:
        route_warning = ROUTE_WARNING
        route_warnings = (ROUTE_WARNING,)
        warnings.append(ROUTE_WARNING)
    warnings.append("Candidate-only simulation output; human review is required")
    used_tile_ids = {
        tile_id for assignment in result.assignments for tile_id in assignment.tile_ids
    }
    used_tile_ids.update(
        tile_id for route in result.workload_routes for tile_id in route.route_tile_ids
    )
    ordered_used_tile_ids = tuple(sorted(used_tile_ids))
    ordered_blocked_tile_ids = tuple(
        sorted(
            tile.tile_id
            for tile in chip.tiles
            if tile.status == "defective"
            or (
                tile.status == "weak"
                and not constraints.allow_weak_tiles_for_low_priority
            )
            or tile.temp_risk > constraints.max_temp_risk
            or tile.latency_penalty > constraints.max_latency_penalty
            or tile.power_penalty > constraints.max_power_penalty
        )
    )
    return SolverReport(
        solver_name=solver_name,
        runtime_ms=round(runtime_ms, 3),
        total_tiles=len(chip.tiles),
        usable_tiles=sum(tile.status == "usable" for tile in chip.tiles),
        weak_tiles=sum(tile.status == "weak" for tile in chip.tiles),
        defective_tiles=sum(tile.status == "defective" for tile in chip.tiles),
        total_workloads=len(workloads),
        assigned_workloads=len(result.assignments),
        unassigned_workloads=len(result.unassigned),
        used_tiles_count=len(ordered_used_tile_ids),
        blocked_tiles_count=len(ordered_blocked_tile_ids),
        used_tile_ids=ordered_used_tile_ids,
        blocked_tile_ids=ordered_blocked_tile_ids,
        used_tiles=len(ordered_used_tile_ids),
        blocked_tiles=len(ordered_blocked_tile_ids),
        objective_score=result.objective_score,
        local_search_enabled=local_search_enabled,
        local_search_iterations=local_search_iterations,
        local_search_improvement_delta=round(
            max(0.0, local_search_improvement_delta), 6
        ),
        route_blocked_segments_count=len(incomplete_routes),
        route_warning=route_warning,
        route_warnings=route_warnings,
        placement_mode=result.placement_mode,
        route_anchor_tile_id=result.route_anchor_tile_id,
        route_aware_assignments=result.placement_mode == "route_aware",
        connected_assignment_required=result.placement_mode == "route_aware",
        routable_assignment_required=result.placement_mode == "route_aware",
        candidate_groups_evaluated=result.candidate_groups_evaluated,
        candidate_groups_rejected_connectivity=(
            result.candidate_groups_rejected_connectivity
        ),
        candidate_groups_rejected_routing=result.candidate_groups_rejected_routing,
        route_complete_assignments=sum(
            route.connected and route.routable for route in assigned_routes
        ),
        route_incomplete_assignments=len(incomplete_routes),
        average_route_length=(
            round(sum(route_lengths) / len(route_lengths), 6)
            if route_lengths
            else 0.0
        ),
        max_route_length=max(route_lengths, default=0),
        workload_routes=result.workload_routes,
        warnings=tuple(warnings),
    )


def render_summary_html(
    chip: ChipMap,
    profile: RecoveryProfile,
    passport: FunctionalPassport,
    report: SolverReport,
    artifact_validation: ArtifactValidationReport | None = None,
    comparison_report: ComparisonReport | None = None,
) -> str:
    def items(values: tuple[str, ...]) -> str:
        if not values:
            return "<li>None</li>"
        return "".join(f"<li>{escape(value)}</li>" for value in values)

    warning_html = items(report.warnings)
    remaining_html = items(passport.remaining_roles)
    blocked_html = items(passport.blocked_roles)
    unassigned_html = items(
        tuple(
            f"{item['workload_id']}: {item['reason']}"
            for item in profile.unassigned_workloads
        )
    )
    if artifact_validation is None:
        self_check_html = "<p><strong>Artifact self-check:</strong> not run</p>"
    else:
        status = "passed" if artifact_validation.passed else "failed"
        self_check_html = (
            f"<p><strong>Artifact self-check:</strong> {status} · "
            f"Passed: {artifact_validation.invariant_checks_passed} · "
            f"Failed: {artifact_validation.invariant_checks_failed}</p>"
        )
    if comparison_report is None:
        comparison_html = "<p><strong>Baseline comparison:</strong> not generated</p>"
    else:
        comparison_rows = "".join(
            f"<li>{escape(item.mode)}: assigned={item.assigned_workloads}, "
            f"functional_yield={item.functional_yield_score:.2f}, "
            f"incomplete_routes={item.route_incomplete_assignments}, "
            f"safety_violations={item.safety_violations_count}</li>"
            for item in comparison_report.baseline_results
        )
        gain = comparison_report.route_aware_gain_over_no_route_awareness
        comparison_html = (
            "<p><strong>Baseline comparison:</strong> available</p>"
            f"<p><strong>Highest raw mode:</strong> "
            f"{escape(comparison_report.best_raw_functional_yield_mode)} · "
            f"<strong>Best safe mode:</strong> "
            f"{escape(comparison_report.best_safe_functional_yield_mode or 'none')} · "
            f"<strong>Recommended mode:</strong> "
            f"{escape(comparison_report.recommended_mode or 'none')} · "
            f"<strong>Status:</strong> "
            f"{escape(comparison_report.recommendation_status)}</p>"
            f"<p>{escape(comparison_report.recommendation_reason)}</p>"
            f"<p>{escape(comparison_report.unsafe_best_raw_mode_warning or '')}</p>"
            f"<ul>{comparison_rows}</ul>"
            f"<p>Route-aware vs no-route-awareness: assigned delta="
            f"{gain['assigned_workloads_delta']}, incomplete-route delta="
            f"{gain['route_incomplete_assignments_delta']}, safety-violation delta="
            f"{gain['safety_violations_delta']}.</p>"
            "<p>This recommendation is simulation-only and is not silicon certification.</p>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HAL Recovery Summary — {escape(chip.chip_id)}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#5d6d7e; --line:#d5d8dc; --ok:#117864; --warn:#b03a2e; }}
    body {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; font: 16px/1.5 system-ui, sans-serif; color: var(--ink); }}
    h1, h2 {{ line-height: 1.2; }}
    .boundary {{ border-left: 5px solid var(--warn); padding: .8rem 1rem; background:#fdedec; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:1rem; }}
    .card {{ border:1px solid var(--line); border-radius:8px; padding:1rem; }}
    .number {{ font-size:1.8rem; font-weight:700; color:var(--ok); }}
    small {{ color:var(--muted); }}
  </style>
</head>
<body>
  <h1>HAL Recovery Compiler Summary</h1>
  <p><strong>Chip ID:</strong> {escape(chip.chip_id)}</p>
  <div class="boundary"><strong>Simulation only — not certified.</strong><br>
  Human review is required. This report does not authorize hardware or firmware action.</div>
  <h2>Candidate functional yield</h2>
  <div class="grid">
    <div class="card"><div class="number">{passport.functional_yield_score:.2f}</div><small>score / 100</small></div>
    <div class="card"><div class="number">{passport.recovered_capacity_estimate:.1%}</div><small>risk-screened tile capacity estimate</small></div>
    <div class="card"><div class="number">{report.assigned_workloads}/{report.total_workloads}</div><small>assigned workloads</small></div>
  </div>
  <h2>Tile status</h2>
  <p>Usable: {report.usable_tiles} · Weak: {report.weak_tiles} · Defective: {report.defective_tiles} · Used by placement or routing: {report.used_tiles_count}</p>
  <h2>Workload assignments</h2>
  <p>Assigned: {report.assigned_workloads} · Unassigned: {report.unassigned_workloads} · Preferred route records: {len(profile.preferred_routes)} · Blocked route summaries: {len(profile.blocked_routes)}</p>
  <p>Placement mode: <strong>{escape(report.placement_mode)}</strong> · Route anchor: {escape(report.route_anchor_tile_id or 'none')} · Complete routes: {report.route_complete_assignments} · Incomplete routes: {report.route_incomplete_assignments} · Average route length: {report.average_route_length:.3f} edges</p>
  <h2>Unassigned workload reasons</h2><ul>{unassigned_html}</ul>
  <div class="grid">
    <section class="card"><h2>Remaining roles</h2><ul>{remaining_html}</ul></section>
    <section class="card"><h2>Blocked roles</h2><ul>{blocked_html}</ul></section>
  </div>
  <h2>Warnings</h2><ul>{warning_html}</ul>
  <h2>Artifact verification</h2>{self_check_html}
  <h2>Functional-yield baseline comparison</h2>{comparison_html}
  <p><strong>Claim boundary:</strong> {escape(passport.claim_boundary)}</p>
  <p><strong>Human review required:</strong> {str(passport.human_review_required).lower()}</p>
  <p><strong>Hardware control enabled:</strong> {str(report.hardware_control_enabled).lower()}</p>
</body>
</html>
"""


def write_html(path: str | Path, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")
