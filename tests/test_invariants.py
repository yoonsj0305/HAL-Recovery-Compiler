from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hal_rc.cli import main
from hal_rc.replay import compare_compile_outputs


ROOT = Path(__file__).resolve().parents[1]


def _compile(out: Path, *, self_check: bool = False) -> int:
    arguments = [
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
        arguments.append("--self-check")
    return main(arguments)


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


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def base_artifacts(tmp_path_factory):
    out = tmp_path_factory.mktemp("invariant-base") / "artifacts"
    assert _compile(out) == 0
    return out


def _corrupt_copy(base: Path, tmp_path: Path) -> Path:
    out = tmp_path / "corrupt"
    shutil.copytree(base, out)
    return out


def test_verify_artifacts_succeeds_after_compile(base_artifacts):
    assert _verify(base_artifacts) == 0


def test_verify_fails_if_hardware_control_is_enabled(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["hardware_control_enabled"] = True
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_defective_tile_is_assigned(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["assigned_workloads"][0]["tile_ids"][0] = "T_2_2"
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_route_jumps_between_tiles(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "solver_report.json"
    report = _read(path)
    route = next(item for item in report["workload_routes"] if item["assigned"])
    route["route_tile_ids"] = [report["route_anchor_tile_id"], "T_15_15"]
    route["route_length"] = 1
    _write(path, report)
    assert _verify(out) == 1


def test_verify_fails_if_safety_critical_uses_weak_tile(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    assignment = next(
        item for item in profile["assigned_workloads"]
        if item["criticality"] == "safety_critical"
    )
    assignment["tile_ids"][0] = "T_5_1"
    assignment["tile_ids"].sort()
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_workload_is_assigned_and_unassigned(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    assignment = profile["assigned_workloads"][0]
    profile["unassigned_workloads"].append({
        "workload_id": assignment["workload_id"],
        "role": assignment["role"],
        "criticality": assignment["criticality"],
        "reason": "corrupted_duplicate_state",
    })
    _write(path, profile)
    assert _verify(out) == 1


def test_compile_self_check_writes_passing_validation_report(tmp_path):
    out = tmp_path / "self-check"
    assert _compile(out, self_check=True) == 0
    validation = _read(out / "artifact_validation_report.json")
    assert validation["passed"] is True
    assert validation["invariant_checks_total"] > 49
    assert validation["invariant_checks_failed"] == 0
    assert validation["checked_at_version"] == "0.3.1"
    assert validation["claim_boundary"] == "simulation_only_not_certified"
    assert validation["hardware_control_enabled"] is False
    assert validation["human_review_required"] is True
    assert "Artifact self-check:</strong> passed" in (
        out / "summary_report.html"
    ).read_text(encoding="utf-8")


def test_compare_artifacts_matches_repeated_compiles_and_ignores_runtime(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    assert _compile(run_a) == 0
    assert _compile(run_b, self_check=True) == 0
    report_b_path = run_b / "solver_report.json"
    report_b = _read(report_b_path)
    report_b["runtime_ms"] = float(report_b["runtime_ms"]) + 9999.0
    _write(report_b_path, report_b)
    comparison = compare_compile_outputs(run_a, run_b)
    assert comparison.matched is True
    assert main(["compare-artifacts", str(run_a), str(run_b)]) == 0


def test_compare_artifacts_fails_when_preferred_routes_differ(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    assert _compile(run_a) == 0
    shutil.copytree(run_a, run_b)
    profile_path = run_b / "recovery_profile.json"
    profile = _read(profile_path)
    profile["preferred_routes"][0]["route_status"] = "corrupted"
    _write(profile_path, profile)
    comparison = compare_compile_outputs(run_a, run_b)
    assert comparison.matched is False
    assert any("preferred_routes" in difference for difference in comparison.differences)
    assert main(["compare-artifacts", str(run_a), str(run_b)]) == 1


def test_verify_fails_if_preferred_route_jumps_across_grid(
    base_artifacts, tmp_path, capsys
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    route = profile["preferred_routes"][0]
    route["route_tile_ids"] = [route["from_anchor"], "T_15_15"]
    _write(path, profile)
    assert _verify(out) == 1
    error = capsys.readouterr().err
    assert f"preferred_route {route['route_id']} jumps from T_0_0 to T_15_15" in error


def test_verify_fails_if_preferred_route_does_not_start_at_anchor(
    base_artifacts, tmp_path, capsys
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    route = profile["preferred_routes"][0]
    route["route_tile_ids"] = route["route_tile_ids"][1:]
    _write(path, profile)
    assert _verify(out) == 1
    assert (
        f"preferred_route {route['route_id']} does not start at route anchor T_0_0"
        in capsys.readouterr().err
    )


def test_verify_fails_if_preferred_route_does_not_reach_to_tiles(
    base_artifacts, tmp_path, capsys
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    route = profile["preferred_routes"][0]
    route["route_tile_ids"] = [route["from_anchor"]]
    _write(path, profile)
    assert _verify(out) == 1
    assert (
        f"preferred_route {route['route_id']} does not reach any assigned tile"
        in capsys.readouterr().err
    )


def test_verify_fails_if_preferred_route_uses_defective_tile(
    base_artifacts, tmp_path, capsys
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    route = profile["preferred_routes"][0]
    route["route_tile_ids"] = [route["from_anchor"], "T_2_2"]
    _write(path, profile)
    assert _verify(out) == 1
    assert (
        f"preferred_route {route['route_id']} uses defective tile T_2_2"
        in capsys.readouterr().err
    )


def test_verify_fails_if_preferred_route_id_is_duplicated(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["preferred_routes"][1]["route_id"] = profile["preferred_routes"][0]["route_id"]
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_preferred_route_workload_is_unknown(base_artifacts, tmp_path):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["preferred_routes"][0]["workload_id"] = "WL_UNKNOWN"
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_preferred_route_workload_is_not_assigned(
    base_artifacts, tmp_path
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["preferred_routes"][0]["workload_id"] = profile["unassigned_workloads"][0]["workload_id"]
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_preferred_to_tiles_differ_from_solver_route(
    base_artifacts, tmp_path
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    profile["preferred_routes"][0]["to_tiles"] = profile["preferred_routes"][0]["to_tiles"][:-1]
    _write(path, profile)
    assert _verify(out) == 1


def test_verify_fails_if_preferred_path_differs_from_solver_route(
    base_artifacts, tmp_path
):
    out = _corrupt_copy(base_artifacts, tmp_path)
    path = out / "recovery_profile.json"
    profile = _read(path)
    route = profile["preferred_routes"][0]
    route["route_tile_ids"] = route["route_tile_ids"][:-1]
    _write(path, profile)
    assert _verify(out) == 1
