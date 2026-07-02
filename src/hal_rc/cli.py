"""Command-line entry point for HAL Recovery Compiler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Sequence

from .baseline import run_baseline_comparison
from .comparison import render_comparison_html
from .graph import build_graph
from .ingest import InputValidationError, load_chip, load_constraints, load_workloads
from .invariants import validate_artifacts
from .models import to_dict
from .passport import build_functional_passport
from .profile import build_recovery_profile
from .report import build_solver_report, render_summary_html, write_html
from .replay import compare_compile_outputs
from .solver_local_search import improve_solution
from .solver_route_aware import solve_route_aware


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hal-rc")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="validate inputs and the safety boundary without writing artifacts"
    )
    validate_parser.add_argument("chip_json", type=Path)
    validate_parser.add_argument("--workloads", type=Path, required=True)
    validate_parser.add_argument("--constraints", type=Path, required=True)

    compile_parser = subparsers.add_parser(
        "compile", help="generate a candidate recovery profile"
    )
    compile_parser.add_argument("chip_json", type=Path)
    compile_parser.add_argument("--workloads", type=Path, required=True)
    compile_parser.add_argument("--constraints", type=Path, required=True)
    compile_parser.add_argument("--out", type=Path, required=True)
    compile_parser.add_argument(
        "--local-search",
        action="store_true",
        help="run a bounded 100-iteration score-improvement pass",
    )
    compile_parser.add_argument(
        "--self-check",
        action="store_true",
        help="validate generated JSON artifacts and write artifact_validation_report.json",
    )
    compile_parser.add_argument(
        "--comparison-report",
        action="store_true",
        help="generate baseline comparison JSON and HTML reports",
    )

    verify_parser = subparsers.add_parser(
        "verify-artifacts", help="verify generated artifacts against their source inputs"
    )
    verify_parser.add_argument("artifact_dir", type=Path)
    verify_parser.add_argument("--chip", type=Path, required=True)
    verify_parser.add_argument("--workloads", type=Path, required=True)
    verify_parser.add_argument("--constraints", type=Path, required=True)

    compare_parser = subparsers.add_parser(
        "compare-artifacts", help="compare two compile outputs for logical equality"
    )
    compare_parser.add_argument("artifact_dir_a", type=Path)
    compare_parser.add_argument("artifact_dir_b", type=Path)

    baseline_parser = subparsers.add_parser(
        "compare-baselines", help="compare strict, placement-first, and route-aware policies"
    )
    baseline_parser.add_argument("chip_json", type=Path)
    baseline_parser.add_argument("--workloads", type=Path, required=True)
    baseline_parser.add_argument("--constraints", type=Path, required=True)
    baseline_parser.add_argument("--out", type=Path, required=True)
    return parser


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputValidationError(f"Cannot read artifact {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputValidationError(
            f"Malformed artifact JSON in {path} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(value, dict):
        raise InputValidationError(f"Artifact {path} must contain a JSON object")
    return value


def validate_inputs(args: argparse.Namespace) -> int:
    chip = load_chip(args.chip_json)
    workloads = load_workloads(args.workloads)
    constraints = load_constraints(args.constraints)
    print(f"chip_id: {chip.chip_id}")
    print(f"total_tiles: {len(chip.tiles)}")
    print(f"usable_tiles: {sum(tile.status == 'usable' for tile in chip.tiles)}")
    print(f"weak_tiles: {sum(tile.status == 'weak' for tile in chip.tiles)}")
    print(f"defective_tiles: {sum(tile.status == 'defective' for tile in chip.tiles)}")
    print(f"total_workloads: {len(workloads)}")
    print("safety_boundary: simulation_only_not_certified")
    print(f"hardware_control_enabled: {str(constraints.hardware_control_enabled).lower()}")
    return 0


def compile_candidate(args: argparse.Namespace) -> int:
    chip = load_chip(args.chip_json)
    workloads = load_workloads(args.workloads)
    constraints = load_constraints(args.constraints)
    graph = build_graph(chip)

    started = perf_counter()
    result = solve_route_aware(chip, workloads, constraints)
    greedy_objective = result.objective_score
    solver_name = "bounded_route_aware_greedy"
    local_search_iterations = 0
    if args.local_search:
        result = improve_solution(
            chip, workloads, constraints, result, max_iterations=100
        )
        solver_name += "+bounded_local_search"
        local_search_iterations = 100
    runtime_ms = (perf_counter() - started) * 1000.0

    profile = build_recovery_profile(chip, workloads, constraints, result, graph)
    comparison = (
        run_baseline_comparison(chip, workloads, constraints)
        if args.comparison_report
        else None
    )
    passport = build_functional_passport(
        chip,
        workloads,
        constraints,
        result,
        profile,
        baseline_comparison_available=comparison is not None,
        recommended_mode=(comparison.recommended_mode if comparison else None),
        recommendation_status=(
            comparison.recommendation_status if comparison else None
        ),
    )
    report = build_solver_report(
        chip,
        workloads,
        constraints,
        result,
        profile,
        runtime_ms=runtime_ms,
        solver_name=solver_name,
        local_search_enabled=args.local_search,
        local_search_iterations=local_search_iterations,
        local_search_improvement_delta=result.objective_score - greedy_objective,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    profile_data = to_dict(profile)
    passport_data = to_dict(passport)
    report_data = to_dict(report)
    comparison_data = to_dict(comparison) if comparison is not None else None
    _write_json(args.out / "recovery_profile.json", profile_data)
    _write_json(args.out / "functional_passport.json", passport_data)
    _write_json(args.out / "solver_report.json", report_data)
    validation = None
    validation_path = args.out / "artifact_validation_report.json"
    if args.self_check:
        validation = validate_artifacts(
            chip,
            workloads,
            constraints,
            profile_data,
            passport_data,
            report_data,
            comparison_data,
        )
        _write_json(validation_path, to_dict(validation))
    elif validation_path.exists():
        validation_path.unlink()
    comparison_json_path = args.out / "comparison_report.json"
    comparison_html_path = args.out / "comparison_report.html"
    if comparison is not None:
        _write_json(comparison_json_path, comparison_data)
        write_html(comparison_html_path, render_comparison_html(comparison))
    else:
        comparison_json_path.unlink(missing_ok=True)
        comparison_html_path.unlink(missing_ok=True)
    write_html(
        args.out / "summary_report.html",
        render_summary_html(
            chip, profile, passport, report, validation, comparison
        ),
    )
    print(
        f"HAL Recovery Compiler: chip={chip.chip_id} "
        f"assigned={len(result.assignments)}/{len(workloads)} "
        f"placement_mode={result.placement_mode} "
        f"functional_yield_score={passport.functional_yield_score:.2f} "
        f"out={args.out}"
    )
    print("Boundary: simulation_only_not_certified; human review required")
    if validation is not None:
        print(
            f"Artifact self-check: passed={str(validation.passed).lower()} "
            f"checks={validation.invariant_checks_passed}/"
            f"{validation.invariant_checks_total}"
        )
        if not validation.passed:
            print(
                f"error: artifact self-check failed with "
                f"{validation.invariant_checks_failed} invariant violation(s)",
                file=sys.stderr,
            )
            return 1
    return 0


def verify_artifact_directory(args: argparse.Namespace) -> int:
    chip = load_chip(args.chip)
    workloads = load_workloads(args.workloads)
    constraints = load_constraints(args.constraints)
    profile = _read_json_object(args.artifact_dir / "recovery_profile.json")
    passport = _read_json_object(args.artifact_dir / "functional_passport.json")
    report = _read_json_object(args.artifact_dir / "solver_report.json")
    comparison_path = args.artifact_dir / "comparison_report.json"
    comparison = (
        _read_json_object(comparison_path) if comparison_path.is_file() else None
    )
    validation = validate_artifacts(
        chip, workloads, constraints, profile, passport, report, comparison
    )
    print(f"passed: {str(validation.passed).lower()}")
    print(f"invariant_checks_total: {validation.invariant_checks_total}")
    print(f"invariant_checks_passed: {validation.invariant_checks_passed}")
    print(f"invariant_checks_failed: {validation.invariant_checks_failed}")
    print(f"errors: {len(validation.errors)}")
    print(f"warnings: {len(validation.warnings)}")
    print("safety_boundary: simulation_only_not_certified")
    if validation.errors:
        for error in validation.errors:
            print(f"error: {error}", file=sys.stderr)
    return 0 if validation.passed else 1


def compare_artifact_directories(args: argparse.Namespace) -> int:
    comparison = compare_compile_outputs(args.artifact_dir_a, args.artifact_dir_b)
    print(f"matched: {str(comparison.matched).lower()}")
    print(f"files_compared: {len(comparison.files_compared)}")
    print(f"differences: {len(comparison.differences)}")
    print("safety_boundary: simulation_only_not_certified")
    for difference in comparison.differences:
        print(f"difference: {difference}", file=sys.stderr)
    return 0 if comparison.matched else 1


def compare_baselines(args: argparse.Namespace) -> int:
    chip = load_chip(args.chip_json)
    workloads = load_workloads(args.workloads)
    constraints = load_constraints(args.constraints)
    comparison = run_baseline_comparison(chip, workloads, constraints)
    args.out.mkdir(parents=True, exist_ok=True)
    _write_json(args.out / "comparison_report.json", to_dict(comparison))
    write_html(
        args.out / "comparison_report.html",
        render_comparison_html(comparison),
    )
    for result in comparison.baseline_results:
        _write_json(args.out / f"baseline_{result.mode}.json", to_dict(result))
    print(
        f"HAL baseline comparison: chip={chip.chip_id} "
        f"modes={len(comparison.baseline_results)} out={args.out}"
    )
    print("Boundary: simulation_only_not_certified; human review required")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return validate_inputs(args)
        if args.command == "compile":
            return compile_candidate(args)
        if args.command == "verify-artifacts":
            return verify_artifact_directory(args)
        if args.command == "compare-artifacts":
            return compare_artifact_directories(args)
        if args.command == "compare-baselines":
            return compare_baselines(args)
    except InputValidationError as exc:
        parser.exit(2, f"error: {exc}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
