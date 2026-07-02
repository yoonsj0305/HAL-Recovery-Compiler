from __future__ import annotations

from zipfile import ZipFile

from scripts.package_release import DEFAULT_OUTPUT, create_release


def test_default_release_name_is_github_ready():
    assert DEFAULT_OUTPUT.name == "hal-recovery-compiler-v0.3.1-public-poc-github.zip"


def test_release_zip_uses_posix_paths_and_excludes_generated_state(tmp_path):
    output = create_release(tmp_path / "release.zip")
    with ZipFile(output) as archive:
        names = archive.namelist()
    assert names
    assert all("\\" not in name for name in names)
    assert "hal-recovery-compiler/src/hal_rc/cli.py" in names
    assert "hal-recovery-compiler/samples/chip_001.json" in names
    assert "hal-recovery-compiler/tests/test_route_aware.py" in names
    assert "hal-recovery-compiler/docs/ARCHITECTURE.md" in names
    assert "hal-recovery-compiler/docs/SAFETY_BOUNDARY.md" in names
    assert "hal-recovery-compiler/docs/GITHUB_REPO_SETUP.md" in names
    assert "hal-recovery-compiler/docs/PORTFOLIO_BRIEF.md" in names
    assert "hal-recovery-compiler/docs/DEMO_TRANSCRIPT.md" in names
    assert "hal-recovery-compiler/.github/workflows/ci.yml" in names
    assert "hal-recovery-compiler/.github/ISSUE_TEMPLATE/bug_report.md" in names
    assert "hal-recovery-compiler/.github/ISSUE_TEMPLATE/feature_request.md" in names
    assert "hal-recovery-compiler/.github/pull_request_template.md" in names
    assert "hal-recovery-compiler/RELEASE_NOTES_v0.3.1-public-poc.md" in names
    assert "hal-recovery-compiler/SECURITY.md" in names
    assert "hal-recovery-compiler/CITATION.cff" in names
    assert "hal-recovery-compiler/README.md" in names
    assert "hal-recovery-compiler/pyproject.toml" in names
    assert "hal-recovery-compiler/scripts/package_release.py" in names
    assert not any("/artifacts/" in name for name in names)
    assert not any(
        excluded in name
        for name in names
        for excluded in ("__pycache__", ".venv", "/venv/", "/build/", "/dist/")
    )
