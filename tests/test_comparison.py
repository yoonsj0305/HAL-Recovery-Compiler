from __future__ import annotations

import json
from pathlib import Path

from hal_rc.cli import main
from hal_rc.replay import compare_compile_outputs


ROOT = Path(__file__).resolve().parents[1]


def _compile(out: Path, *, comparison: bool = False, self_check: bool = False) -> int:
    args = [
        "compile",
        str(ROOT / "samples" / "chip_001.json"),
        "--workloads",
        str(ROOT / "samples" / "workloads.json"),
        "--constraints",
        str(ROOT / "samples" / "constraints.json"),
        "--out",
        str(out),
    ]
    if self_check:
        args.append("--self-check")
    if comparison:
        args.append("--comparison-report")
    return main(args)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _verify(out: Path) -> int:
    return main([
        "verify-artifacts",
        str(out),
        "--chip",
        str(ROOT / "samples" / "chip_001.json"),
        "--workloads",
        str(ROOT / "samples" / "workloads.json"),
        "--constraints",
        str(ROOT / "samples" / "constraints.json"),
    ])


def test_compare_baselines_cli_creates_complete_safe_reports(tmp_path):
    out = tmp_path / "comparison"
    assert main([
        "compare-baselines",
        str(ROOT / "samples" / "chip_001.json"),
        "--workloads",
        str(ROOT / "samples" / "workloads.json"),
        "--constraints",
        str(ROOT / "samples" / "constraints.json"),
        "--out",
        str(out),
    ]) == 0
    assert (out / "comparison_report.json").is_file()
    assert (out / "comparison_report.html").is_file()
    report = _read(out / "comparison_report.json")
    assert report["comparison_modes"] == [
        "strict_usable_only", "no_route_awareness", "route_aware"
    ]
    assert {item["mode"] for item in report["baseline_results"]} == set(
        report["comparison_modes"]
    )
    route_aware = next(
        item for item in report["baseline_results"] if item["mode"] == "route_aware"
    )
    assert route_aware["hardware_control_enabled"] is False
    assert route_aware["claim_boundary"] == "simulation_only_not_certified"
    assert route_aware["safety_violations_count"] == 0
    for result in report["baseline_results"]:
        assert 0.0 <= result["workload_coverage"] <= 1.0
        assert 0.0 <= result["criticality_weighted_coverage"] <= 1.0
        assert 0.0 <= result["functional_yield_score"] <= 100.0
    assert "route_aware_gain_over_strict_usable_only" in report
    assert "route_aware_gain_over_no_route_awareness" in report
    assert report["tradeoff_summary"]["unassigned_workloads_are_safety_feature"] is True
    assert report["best_raw_functional_yield_mode"] == "no_route_awareness"
    assert report["best_safe_functional_yield_mode"] == "route_aware"
    assert report["recommended_mode"] == "route_aware"
    assert report["recommendation_status"] == "recommended"
    assert report["recommendation_reason"]
    assert report["unsafe_best_raw_mode_warning"]
    assert "no_route_awareness" in report["unsafe_best_raw_mode_warning"]
    assert report["recommended_mode"] != "no_route_awareness"
    recommended = next(
        item for item in report["baseline_results"]
        if item["mode"] == report["recommended_mode"]
    )
    assert recommended["safety_violations_count"] == 0
    assert recommended["route_incomplete_assignments"] == 0
    assert recommended["invariant_passed"] is True
    html = (out / "comparison_report.html").read_text(encoding="utf-8")
    assert "This comparison is simulation-only and is not silicon certification." in html
    assert "Highest raw score is not automatically the recommended mode." in html


def test_compile_comparison_report_updates_passport_and_summary(tmp_path):
    out = tmp_path / "compile-comparison"
    assert _compile(out, comparison=True) == 0
    assert (out / "comparison_report.json").is_file()
    assert (out / "comparison_report.html").is_file()
    passport = _read(out / "functional_passport.json")
    comparison_evidence = next(
        item for item in passport["evidence"]
        if item.get("metric") == "baseline_comparison"
    )
    assert comparison_evidence["baseline_comparison_available"] is True
    assert comparison_evidence["comparison_modes"] == [
        "strict_usable_only", "no_route_awareness", "route_aware"
    ]
    assert comparison_evidence["recommended_mode"] == "route_aware"
    assert comparison_evidence["recommendation_status"] == "recommended"
    assert comparison_evidence["recommendation_is_certification"] is False
    summary = (out / "summary_report.html").read_text(encoding="utf-8")
    assert "Baseline comparison:</strong> available" in summary
    assert "Recommended mode:</strong> route_aware" in summary


def test_compile_without_comparison_does_not_claim_comparison_available(tmp_path):
    out = tmp_path / "normal"
    assert _compile(out) == 0
    passport = _read(out / "functional_passport.json")
    assert not any(
        item.get("baseline_comparison_available") is True
        for item in passport["evidence"]
    )
    assert not any("recommended_mode" in item for item in passport["evidence"])
    assert not (out / "comparison_report.json").exists()


def test_compile_self_check_and_comparison_pass_together(tmp_path):
    out = tmp_path / "combined"
    assert _compile(out, comparison=True, self_check=True) == 0
    validation = _read(out / "artifact_validation_report.json")
    assert validation["passed"] is True
    assert (out / "comparison_report.json").is_file()
    assert _verify(out) == 0


def test_compare_artifacts_compares_optional_comparison_report(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    assert _compile(run_a, comparison=True) == 0
    assert _compile(run_b, comparison=True) == 0
    solver_b_path = run_b / "solver_report.json"
    solver_b = _read(solver_b_path)
    solver_b["runtime_ms"] += 999.0
    _write(solver_b_path, solver_b)
    assert compare_compile_outputs(run_a, run_b).matched is True

    comparison_b_path = run_b / "comparison_report.json"
    comparison_b = _read(comparison_b_path)
    comparison_b["baseline_results"][2]["functional_yield_score"] += 1.0
    _write(comparison_b_path, comparison_b)
    result = compare_compile_outputs(run_a, run_b)
    assert result.matched is False
    assert any("comparison_report.json" in item for item in result.differences)


def test_compare_artifacts_mismatches_when_only_one_run_has_comparison(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    assert _compile(run_a, comparison=True) == 0
    assert _compile(run_b) == 0
    assert compare_compile_outputs(run_a, run_b).matched is False


def test_verify_fails_if_recommended_mode_is_unsafe(tmp_path):
    out = tmp_path / "unsafe-recommendation"
    assert _compile(out, comparison=True) == 0
    path = out / "comparison_report.json"
    report = _read(path)
    report["recommended_mode"] = "no_route_awareness"
    _write(path, report)
    assert _verify(out) == 1


def test_verify_fails_if_recommended_mode_is_unknown(tmp_path):
    out = tmp_path / "unknown-recommendation"
    assert _compile(out, comparison=True) == 0
    path = out / "comparison_report.json"
    report = _read(path)
    report["recommended_mode"] = "unknown_mode"
    _write(path, report)
    assert _verify(out) == 1


def test_compare_artifacts_detects_recommendation_field_difference(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    assert _compile(run_a, comparison=True) == 0
    assert _compile(run_b, comparison=True) == 0
    path = run_b / "comparison_report.json"
    report = _read(path)
    report["recommendation_reason"] = "corrupted recommendation reason"
    _write(path, report)
    result = compare_compile_outputs(run_a, run_b)
    assert result.matched is False
    assert any("recommendation_reason" in item for item in result.differences)
