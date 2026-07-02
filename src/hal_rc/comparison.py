"""Transparent baseline comparison models, deltas, and HTML rendering."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from . import __version__

COMPARISON_MODES = (
    "strict_usable_only",
    "no_route_awareness",
    "route_aware",
)


@dataclass(frozen=True, slots=True)
class BaselineResult:
    mode: str
    assigned_workloads: int
    unassigned_workloads: int
    total_workloads: int
    assigned_workload_ids: tuple[str, ...]
    unassigned_workload_ids: tuple[str, ...]
    used_tiles_count: int
    weak_tiles_used_count: int
    defective_tiles_used_count: int
    route_complete_assignments: int
    route_incomplete_assignments: int
    average_route_length: float
    max_route_length: int
    workload_coverage: float
    functional_yield_score: float
    recovered_capacity_estimate: float
    criticality_weighted_coverage: float
    safety_violations_count: int
    invariant_passed: bool
    claim_boundary: str = "simulation_only_not_certified"
    hardware_control_enabled: bool = False
    human_review_required: bool = True


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    chip_id: str
    compiler_version: str
    comparison_modes: tuple[str, ...]
    baseline_results: tuple[BaselineResult, ...]
    best_mode_by_functional_yield: str
    best_mode_by_safety: str
    best_raw_functional_yield_mode: str
    best_safe_functional_yield_mode: str | None
    recommended_mode: str | None
    recommendation_status: str
    recommendation_reason: str
    unsafe_best_raw_mode_warning: str | None
    safe_mode_requirements: dict[str, object]
    route_aware_gain_over_strict_usable_only: dict[str, object]
    route_aware_gain_over_no_route_awareness: dict[str, object]
    tradeoff_summary: dict[str, bool]
    warnings: tuple[str, ...]
    claim_boundary: str = "simulation_only_not_certified"
    hardware_control_enabled: bool = False
    human_review_required: bool = True


def _delta(route_aware: BaselineResult, baseline: BaselineResult) -> dict[str, object]:
    return {
        "assigned_workloads_delta": route_aware.assigned_workloads - baseline.assigned_workloads,
        "workload_coverage_delta": round(
            route_aware.workload_coverage - baseline.workload_coverage, 6
        ),
        "criticality_weighted_coverage_delta": round(
            route_aware.criticality_weighted_coverage
            - baseline.criticality_weighted_coverage,
            6,
        ),
        "functional_yield_score_delta": round(
            route_aware.functional_yield_score - baseline.functional_yield_score, 6
        ),
        "route_incomplete_assignments_delta": (
            route_aware.route_incomplete_assignments
            - baseline.route_incomplete_assignments
        ),
        "safety_violations_delta": (
            route_aware.safety_violations_count - baseline.safety_violations_count
        ),
    }


def build_comparison_report(
    chip_id: str,
    results: tuple[BaselineResult, ...],
) -> ComparisonReport:
    by_mode = {result.mode: result for result in results}
    route_aware = by_mode["route_aware"]
    strict = by_mode["strict_usable_only"]
    no_route = by_mode["no_route_awareness"]

    strict_gain = _delta(route_aware, strict)
    strict_gain["weak_tiles_used_delta"] = (
        route_aware.weak_tiles_used_count - strict.weak_tiles_used_count
    )
    no_route_gain = _delta(route_aware, no_route)
    no_route_gain["explanation"] = (
        "Positive assignment delta means route-aware preserved more accepted workloads; "
        "negative delta means it refused placement-first assignments that lacked complete "
        "connected routes."
    )
    warnings: list[str] = []
    if route_aware.assigned_workloads < no_route.assigned_workloads:
        warnings.append(
            "Route-aware mode assigned fewer workloads than no-route-awareness because "
            "disconnected or unroutable placements were refused."
        )
    if no_route.route_incomplete_assignments:
        warnings.append(
            f"No-route-awareness accepted {no_route.route_incomplete_assignments} "
            "workload(s) without complete connected routes."
        )
    best_functional = max(
        results,
        key=lambda result: (
            result.functional_yield_score,
            -result.safety_violations_count,
            result.mode == "route_aware",
        ),
    ).mode
    best_safety = min(
        results,
        key=lambda result: (
            result.safety_violations_count,
            result.mode != "route_aware",
        ),
    ).mode
    from .recommendation import select_recommendation

    recommendation = select_recommendation(results)
    return ComparisonReport(
        chip_id=chip_id,
        compiler_version=__version__,
        comparison_modes=COMPARISON_MODES,
        baseline_results=results,
        best_mode_by_functional_yield=best_functional,
        best_mode_by_safety=best_safety,
        best_raw_functional_yield_mode=(
            recommendation.best_raw_functional_yield_mode
        ),
        best_safe_functional_yield_mode=(
            recommendation.best_safe_functional_yield_mode
        ),
        recommended_mode=recommendation.recommended_mode,
        recommendation_status=recommendation.recommendation_status,
        recommendation_reason=recommendation.recommendation_reason,
        unsafe_best_raw_mode_warning=(
            recommendation.unsafe_best_raw_mode_warning
        ),
        safe_mode_requirements=recommendation.safe_mode_requirements,
        route_aware_gain_over_strict_usable_only=strict_gain,
        route_aware_gain_over_no_route_awareness=no_route_gain,
        tradeoff_summary={
            "route_aware_may_assign_fewer_workloads_than_placement_first": (
                route_aware.assigned_workloads < no_route.assigned_workloads
            ),
            "route_aware_prioritizes_connected_routable_assignments": True,
            "unassigned_workloads_are_safety_feature": True,
            "not_certification": True,
        },
        warnings=tuple(warnings),
    )


def render_comparison_html(report: ComparisonReport) -> str:
    rows = []
    for result in report.baseline_results:
        rows.append(
            "<tr>"
            f"<td>{escape(result.mode)}</td>"
            f"<td>{result.assigned_workloads}</td>"
            f"<td>{result.unassigned_workloads}</td>"
            f"<td>{result.workload_coverage:.3f}</td>"
            f"<td>{result.criticality_weighted_coverage:.3f}</td>"
            f"<td>{result.functional_yield_score:.2f}</td>"
            f"<td>{result.recovered_capacity_estimate:.3f}</td>"
            f"<td>{result.weak_tiles_used_count}</td>"
            f"<td>{result.route_complete_assignments}</td>"
            f"<td>{result.route_incomplete_assignments}</td>"
            f"<td>{result.safety_violations_count}</td>"
            f"<td>{str(result.mode == report.recommended_mode).lower()}</td>"
            f"<td>{str(result.invariant_passed).lower()}</td>"
            "</tr>"
        )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report.warnings) or "<li>None</li>"
    tradeoffs = "".join(
        f"<li>{escape(key)}: {str(value).lower()}</li>"
        for key, value in report.tradeoff_summary.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HAL Baseline Comparison — {escape(report.chip_id)}</title>
<style>body{{max-width:1200px;margin:2rem auto;padding:0 1rem;font:15px/1.5 system-ui,sans-serif;color:#17202a}}table{{border-collapse:collapse;width:100%;overflow:auto}}th,td{{border:1px solid #d5d8dc;padding:.5rem;text-align:right}}th:first-child,td:first-child{{text-align:left}}.boundary{{border-left:5px solid #b03a2e;background:#fdedec;padding:.8rem 1rem}}.recommendation{{border-left:5px solid #117864;background:#e8f8f5;padding:.8rem 1rem;margin:1rem 0}}</style></head>
<body><h1>HAL Recovery Baseline Comparison</h1>
<p><strong>Chip:</strong> {escape(report.chip_id)} · <strong>Compiler:</strong> {escape(report.compiler_version)}</p>
<div class="boundary">This comparison is simulation-only and is not silicon certification. Human review is required.</div>
<div class="recommendation"><h2>Safe recommendation</h2>
<p><strong>Highest raw functional yield:</strong> {escape(report.best_raw_functional_yield_mode)}</p>
<p><strong>Best safe functional yield:</strong> {escape(report.best_safe_functional_yield_mode or 'none')}</p>
<p><strong>Recommended mode:</strong> {escape(report.recommended_mode or 'none')} · <strong>Status:</strong> {escape(report.recommendation_status)}</p>
<p>{escape(report.recommendation_reason)}</p>
<p>{escape(report.unsafe_best_raw_mode_warning or '')}</p>
<p><strong>Highest raw score is not automatically the recommended mode.</strong></p>
<p>HAL recommends only modes with zero safety violations and complete accepted routes.</p>
<p>This recommendation is simulation-only and is not silicon certification.</p></div>
<table><thead><tr><th>Mode</th><th>Assigned</th><th>Unassigned</th><th>Workload coverage</th><th>Weighted coverage</th><th>Functional yield</th><th>Recovered capacity</th><th>Weak tiles</th><th>Complete routes</th><th>Incomplete routes</th><th>Safety violations</th><th>Recommended</th><th>Invariant passed</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>Trade-offs</h2><ul>{tradeoffs}</ul><h2>Warnings</h2><ul>{warnings}</ul>
<p><strong>Claim boundary:</strong> {escape(report.claim_boundary)}</p></body></html>
"""
