from __future__ import annotations

from pathlib import Path

from hal_rc import __release_label__, __version__


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    "ARCHITECTURE.md",
    "SAFETY_BOUNDARY.md",
    "FUNCTIONAL_YIELD.md",
    "VERSION_HISTORY.md",
    "ROADMAP.md",
    "DEMO.md",
    "OUTPUTS.md",
    "CLAIMS.md",
    "GITHUB_REPO_SETUP.md",
    "PORTFOLIO_BRIEF.md",
    "DEMO_TRANSCRIPT.md",
)

ROOT_FILES = (
    "README.md",
    "SECURITY.md",
    "CITATION.cff",
    "RELEASE_NOTES_v0.3.1-public-poc.md",
)

GITHUB_FILES = (
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/pull_request_template.md",
)


def test_public_release_identity_is_frozen():
    assert __version__ == "0.3.1"
    assert __release_label__ == "v0.3.1-public-poc"


def test_readme_is_public_facing_and_preserves_boundaries():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme.lower()
    assert "HAL Recovery Compiler" in readme
    assert "simulation-only" in lowered
    assert "does not repair silicon" in lowered
    assert "Recovery Runtime" in readme
    assert "out of scope" in lowered
    assert "recovery runtime is intentionally out of scope" in lowered
    assert (
        "hal-rc validate samples/chip_001.json --workloads "
        "samples/workloads.json --constraints samples/constraints.json"
    ) in readme
    assert (
        "hal-rc compile samples/chip_001.json --workloads samples/workloads.json "
        "--constraints samples/constraints.json --out artifacts/chip_001 "
        "--self-check --comparison-report"
    ) in readme


def test_required_public_documents_exist():
    for filename in DOCS:
        assert (ROOT / "docs" / filename).is_file(), filename


def test_github_release_files_exist():
    for filename in (*ROOT_FILES, *GITHUB_FILES):
        assert (ROOT / filename).is_file(), filename


def test_ci_runs_required_public_checks_without_publishing():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.11"' in ci
    assert 'pip install -e ".[test]"' in ci
    assert "python -m pytest -q" in ci
    assert "hal-rc validate" in ci
    assert "hal-rc compile" in ci
    assert "hal-rc verify" in ci
    assert "hal-rc compare-baselines" in ci
    assert "upload-artifact" not in ci


def test_safety_document_contains_required_hard_boundary():
    safety = (ROOT / "docs" / "SAFETY_BOUNDARY.md").read_text(encoding="utf-8")
    assert '"hardware_control_enabled": false' in safety
    assert '"human_review_required": true' in safety
    assert '"claim_boundary": "simulation_only_not_certified"' in safety


def test_claims_document_separates_forbidden_claims():
    claims = (ROOT / "docs" / "CLAIMS.md").read_text(encoding="utf-8")
    assert "## Allowed claims" in claims
    assert "## Forbidden claims" in claims
    for phrase in (
        "repairs defective chips",
        "certifies chips",
        "improves real silicon performance",
        "controls memory controllers",
        "flashes firmware",
        "production-ready",
        "fab-qualified",
        "safety-certified",
        "guarantees yield improvement",
        "simulation-only PoC",
        "candidate recovery profile generation",
        "safe recommendation logic",
    ):
        assert phrase in claims


def test_citation_uses_public_version_without_invented_publication_metadata():
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert 'title: "HAL Recovery Compiler"' in citation
    assert 'version: "0.3.1-public-poc"' in citation
    assert "doi:" not in citation.lower()


def test_version_history_and_roadmap_name_public_poc():
    history = (ROOT / "docs" / "VERSION_HISTORY.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "v0.3.1-public-poc" in history
    assert "v0.3.1-public-poc" in roadmap
    assert "No runtime included" in roadmap
