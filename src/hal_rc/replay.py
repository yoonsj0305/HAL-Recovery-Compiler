"""Logical replay comparison for deterministic compile outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .models import ReplayComparisonReport

CORE_COMPARISON_FILES = (
    "recovery_profile.json",
    "functional_passport.json",
    "solver_report.json",
)
IGNORED_FIELDS = (
    "runtime_ms",
    "generated_at",
    "created_at",
    "timestamp",
    "output_dir",
    "output_path",
)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize(child)
            for key, child in sorted(value.items())
            if key not in IGNORED_FIELDS and not key.endswith("_timestamp")
        }
    if isinstance(value, list):
        return [_normalize(child) for child in value]
    return value


def _first_difference(left: Any, right: Any, path: str = "$") -> str:
    if type(left) is not type(right):
        return f"{path}: type differs ({type(left).__name__} != {type(right).__name__})"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            missing_left = sorted(right.keys() - left.keys())
            missing_right = sorted(left.keys() - right.keys())
            return f"{path}: keys differ (only_a={missing_right}, only_b={missing_left})"
        for key in left:
            if left[key] != right[key]:
                return _first_difference(left[key], right[key], f"{path}.{key}")
    elif isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: list length differs ({len(left)} != {len(right)})"
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            if left_item != right_item:
                return _first_difference(left_item, right_item, f"{path}[{index}]")
    elif left != right:
        return f"{path}: value differs ({left!r} != {right!r})"
    return f"{path}: logical content differs"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_compile_outputs(
    artifact_dir_a: str | Path,
    artifact_dir_b: str | Path,
) -> ReplayComparisonReport:
    directory_a = Path(artifact_dir_a)
    directory_b = Path(artifact_dir_b)
    differences: list[str] = []
    compared: list[str] = []
    filenames = list(CORE_COMPARISON_FILES)
    comparison_a = directory_a / "comparison_report.json"
    comparison_b = directory_b / "comparison_report.json"
    if comparison_a.is_file() or comparison_b.is_file():
        filenames.append("comparison_report.json")
    for filename in filenames:
        path_a = directory_a / filename
        path_b = directory_b / filename
        if not path_a.is_file() or not path_b.is_file():
            missing = []
            if not path_a.is_file():
                missing.append("run_a")
            if not path_b.is_file():
                missing.append("run_b")
            differences.append(f"{filename}: missing from {', '.join(missing)}")
            continue
        try:
            left = _normalize(_read_json(path_a))
            right = _normalize(_read_json(path_b))
        except (OSError, json.JSONDecodeError) as exc:
            differences.append(f"{filename}: cannot compare JSON: {exc}")
            continue
        compared.append(filename)
        if left != right:
            differences.append(f"{filename}: {_first_difference(left, right)}")
    return ReplayComparisonReport(
        matched=not differences and len(compared) == len(filenames),
        files_compared=tuple(compared),
        differences=tuple(differences),
        ignored_fields=IGNORED_FIELDS,
        checked_at_version=__version__,
    )
