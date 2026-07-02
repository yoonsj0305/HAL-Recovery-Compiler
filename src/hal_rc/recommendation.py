"""Deterministic safe recommendation logic for baseline comparison reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .comparison import BaselineResult

MODE_PRIORITY = {
    "route_aware": 3,
    "strict_usable_only": 2,
    "no_route_awareness": 1,
}

SAFE_MODE_REQUIREMENTS: dict[str, object] = {
    "safety_violations_count": 0,
    "route_incomplete_assignments": 0,
    "invariant_passed": True,
    "hardware_control_enabled": False,
    "claim_boundary": "simulation_only_not_certified",
}


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    best_raw_functional_yield_mode: str
    best_safe_functional_yield_mode: str | None
    recommended_mode: str | None
    recommendation_status: str
    recommendation_reason: str
    unsafe_best_raw_mode_warning: str | None
    safe_mode_requirements: dict[str, object]


def is_safe_mode(result: BaselineResult) -> bool:
    return (
        result.safety_violations_count == 0
        and result.route_incomplete_assignments == 0
        and result.invariant_passed is True
        and result.hardware_control_enabled is False
        and result.claim_boundary == "simulation_only_not_certified"
    )


def _raw_rank(result: BaselineResult) -> tuple[float, float, float, int, int, int]:
    return (
        result.functional_yield_score,
        result.criticality_weighted_coverage,
        result.workload_coverage,
        -result.safety_violations_count,
        -result.route_incomplete_assignments,
        MODE_PRIORITY.get(result.mode, 0),
    )


def _safe_rank(result: BaselineResult) -> tuple[float, float, float, int]:
    return (
        result.functional_yield_score,
        result.criticality_weighted_coverage,
        result.workload_coverage,
        MODE_PRIORITY.get(result.mode, 0),
    )


def select_recommendation(
    results: tuple[BaselineResult, ...],
) -> RecommendationDecision:
    raw_best = max(results, key=_raw_rank)
    safe_modes = tuple(result for result in results if is_safe_mode(result))
    safe_best = max(safe_modes, key=_safe_rank) if safe_modes else None
    route_aware = next(
        (result for result in results if result.mode == "route_aware"), None
    )

    if safe_best is None:
        recommended = None
        status = "no_safe_mode_available"
        reason = (
            "No comparison mode satisfies every safe-mode requirement; all modes "
            "require manual review and none is recommended."
        )
    elif route_aware is not None and is_safe_mode(route_aware):
        score_gap = safe_best.functional_yield_score - route_aware.functional_yield_score
        if score_gap <= 10.0:
            recommended = route_aware
            status = "recommended"
            reason = (
                "route_aware is recommended because it has zero safety violations, "
                "complete accepted routes, and remains within 10 percentage points "
                "of the best safe functional-yield score."
            )
        else:
            recommended = safe_best
            status = "manual_review_required"
            reason = (
                f"{safe_best.mode} is the highest-scoring safe mode; route_aware is "
                "safe but falls more than 10 percentage points below it, so manual "
                "review is required."
            )
    else:
        recommended = safe_best
        status = "manual_review_required"
        reason = (
            f"{safe_best.mode} is the highest-scoring safe mode. route_aware did not "
            "satisfy every safe-mode requirement, so manual review is required."
        )

    warning = None
    recommended_mode = recommended.mode if recommended is not None else None
    if raw_best.mode != recommended_mode:
        warning = (
            f"The highest raw functional yield mode is {raw_best.mode}, but it is not "
            f"recommended because it has {raw_best.safety_violations_count} safety "
            f"violations and {raw_best.route_incomplete_assignments} route-incomplete "
            "assignments."
        )
    return RecommendationDecision(
        best_raw_functional_yield_mode=raw_best.mode,
        best_safe_functional_yield_mode=(safe_best.mode if safe_best else None),
        recommended_mode=recommended_mode,
        recommendation_status=status,
        recommendation_reason=reason,
        unsafe_best_raw_mode_warning=warning,
        safe_mode_requirements=dict(SAFE_MODE_REQUIREMENTS),
    )


def _mapping_is_safe(result: dict[str, Any]) -> bool:
    return (
        result.get("safety_violations_count") == 0
        and result.get("route_incomplete_assignments") == 0
        and result.get("invariant_passed") is True
        and result.get("hardware_control_enabled") is False
        and result.get("claim_boundary") == "simulation_only_not_certified"
    )


def recommendation_invariant_checks(
    report: dict[str, Any],
) -> tuple[tuple[bool, str], ...]:
    modes = report.get("comparison_modes")
    mode_list = modes if isinstance(modes, list) else list(modes or ())
    results_value = report.get("baseline_results")
    results = results_value if isinstance(results_value, (list, tuple)) else ()
    by_mode = {
        item.get("mode"): item for item in results if isinstance(item, dict)
    }
    recommended = report.get("recommended_mode")
    raw_best = report.get("best_raw_functional_yield_mode")
    safe_best = report.get("best_safe_functional_yield_mode")
    status = report.get("recommendation_status")
    warning = report.get("unsafe_best_raw_mode_warning")
    recommended_result = by_mode.get(recommended)
    return (
        (
            report.get("claim_boundary") == "simulation_only_not_certified",
            "comparison_report.claim_boundary must be simulation_only_not_certified",
        ),
        (
            report.get("hardware_control_enabled") is False,
            "comparison_report.hardware_control_enabled must be false",
        ),
        (
            report.get("human_review_required") is True,
            "comparison_report.human_review_required must be true",
        ),
        (
            recommended is None or recommended in mode_list,
            "comparison_report.recommended_mode must be null or exist in comparison_modes",
        ),
        (
            raw_best in mode_list,
            "comparison_report.best_raw_functional_yield_mode must exist in comparison_modes",
        ),
        (
            safe_best is None or safe_best in mode_list,
            "comparison_report.best_safe_functional_yield_mode must be null or exist in comparison_modes",
        ),
        (
            recommended is None or (
                isinstance(recommended_result, dict)
                and _mapping_is_safe(recommended_result)
            ),
            "comparison_report.recommended_mode must satisfy every safe-mode requirement",
        ),
        (
            raw_best == recommended or isinstance(warning, str) and bool(warning.strip()),
            "comparison_report must warn when highest raw mode differs from recommended_mode",
        ),
        (
            status in {
                "recommended",
                "no_safe_mode_available",
                "manual_review_required",
            },
            "comparison_report.recommendation_status is invalid",
        ),
        (
            report.get("safe_mode_requirements") == SAFE_MODE_REQUIREMENTS,
            "comparison_report.safe_mode_requirements must match compiler safety policy",
        ),
    )
