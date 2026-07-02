from __future__ import annotations

import json
from pathlib import Path

import pytest

from hal_rc.cli import main


def test_cli_creates_all_expected_output_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "artifacts"
    result = main([
        "compile", str(root / "samples" / "chip_001.json"),
        "--workloads", str(root / "samples" / "workloads.json"),
        "--constraints", str(root / "samples" / "constraints.json"),
        "--out", str(out),
    ])
    assert result == 0
    expected = {
        "recovery_profile.json", "functional_passport.json",
        "solver_report.json", "summary_report.html",
    }
    assert {path.name for path in out.iterdir()} == expected
    report = json.loads((out / "solver_report.json").read_text(encoding="utf-8"))
    assert "runtime_ms" in report
    assert report["local_search_enabled"] is False
    assert report["local_search_iterations"] == 0
    assert report["local_search_improvement_delta"] == 0.0


def test_cli_validate_succeeds_without_creating_artifacts(tmp_path, monkeypatch, capsys):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    result = main([
        "validate", str(root / "samples" / "chip_001.json"),
        "--workloads", str(root / "samples" / "workloads.json"),
        "--constraints", str(root / "samples" / "constraints.json"),
    ])
    assert result == 0
    assert list(tmp_path.iterdir()) == []
    output = capsys.readouterr().out
    assert "chip_id: CHIP_001_SYNTHETIC" in output
    assert "total_tiles: 256" in output
    assert "safety_boundary: simulation_only_not_certified" in output
    assert "hardware_control_enabled: false" in output


def test_cli_validate_rejects_hardware_control_enabled(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    source = json.loads(
        (root / "samples" / "constraints.json").read_text(encoding="utf-8")
    )
    source["hardware_control_enabled"] = True
    unsafe = tmp_path / "unsafe_constraints.json"
    unsafe.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([
            "validate", str(root / "samples" / "chip_001.json"),
            "--workloads", str(root / "samples" / "workloads.json"),
            "--constraints", str(unsafe),
        ])
    assert exc.value.code == 2
    assert "hardware_control_enabled=true is forbidden" in capsys.readouterr().err


def test_solver_report_exposes_explicit_deterministic_tile_telemetry(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "output"
    assert main([
        "compile", str(root / "samples" / "chip_001.json"),
        "--workloads", str(root / "samples" / "workloads.json"),
        "--constraints", str(root / "samples" / "constraints.json"),
        "--out", str(out),
    ]) == 0
    report = json.loads((out / "solver_report.json").read_text(encoding="utf-8"))
    assert report["used_tiles_count"] == len(report["used_tile_ids"])
    assert report["blocked_tiles_count"] == len(report["blocked_tile_ids"])
    assert report["used_tile_ids"] == sorted(report["used_tile_ids"])
    assert report["blocked_tile_ids"] == sorted(report["blocked_tile_ids"])
    assert report["route_blocked_segments_count"] == 0
    assert report["route_warnings"] == []
    assert report["route_warning"] is None
    assert report["placement_mode"] == "route_aware"
    assert report["route_aware_assignments"] is True
    assert report["connected_assignment_required"] is True
    assert report["routable_assignment_required"] is True
    assert report["route_incomplete_assignments"] == 0
    assert report["candidate_groups_evaluated"] > 0
    assert "candidate_groups_rejected_connectivity" in report
    assert "candidate_groups_rejected_routing" in report
    assert all(route["connected"] and route["routable"] for route in report["workload_routes"] if route["assigned"])
    assert report["hardware_control_enabled"] is False
    assert report["human_review_required"] is True
    assert report["claim_boundary"] == "simulation_only_not_certified"


def test_local_search_report_includes_deterministic_telemetry(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "local-search-output"
    assert main([
        "compile", str(root / "samples" / "chip_001.json"),
        "--workloads", str(root / "samples" / "workloads.json"),
        "--constraints", str(root / "samples" / "constraints.json"),
        "--out", str(out),
        "--local-search",
    ]) == 0
    report = json.loads((out / "solver_report.json").read_text(encoding="utf-8"))
    assert report["local_search_enabled"] is True
    assert report["local_search_iterations"] == 100
    assert report["local_search_improvement_delta"] >= 0.0


def test_compile_does_not_read_pre_generated_artifacts(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    original_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if "artifacts" in path.parts:
            raise AssertionError("compile must not read pre-generated artifacts")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    assert main([
        "compile", str(root / "samples" / "chip_001.json"),
        "--workloads", str(root / "samples" / "workloads.json"),
        "--constraints", str(root / "samples" / "constraints.json"),
        "--out", str(tmp_path / "fresh-output"),
    ]) == 0


def test_readme_documents_validate_and_compile_commands():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "hal-rc validate samples/chip_001.json" in readme
    assert "hal-rc compile samples/chip_001.json" in readme
    assert "Writes no artifacts" in readme or "without solving or writing artifacts" in readme
