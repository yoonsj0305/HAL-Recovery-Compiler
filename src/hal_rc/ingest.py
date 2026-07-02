"""Strict JSON loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ChipMap, Constraints, Tile, Workload


class InputValidationError(ValueError):
    """Raised when a supplied input violates the v0.1 contract."""


def _load_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputValidationError(f"Cannot read {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputValidationError(
            f"Malformed JSON in {source} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, dict):
        raise InputValidationError(f"{source} must contain a top-level JSON object")
    return raw


def _required(data: dict[str, Any], fields: set[str], context: str) -> None:
    missing = sorted(fields - data.keys())
    if missing:
        raise InputValidationError(f"{context} missing required fields: {', '.join(missing)}")


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InputValidationError(f"{field} must be an integer >= {minimum}")
    return value


def _unit_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputValidationError(f"{field} must be a number from 0.0 to 1.0")
    converted = float(value)
    if not 0.0 <= converted <= 1.0:
        raise InputValidationError(f"{field} must be from 0.0 to 1.0")
    return converted


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise InputValidationError(f"{field} must be boolean")
    return value


def load_chip(path: str | Path) -> ChipMap:
    data = _load_object(path)
    _required(data, {"chip_id", "width", "height", "tiles"}, "chip map")
    chip_id = _string(data["chip_id"], "chip_id")
    width = _integer(data["width"], "width", minimum=1)
    height = _integer(data["height"], "height", minimum=1)
    if not isinstance(data["tiles"], list):
        raise InputValidationError("tiles must be a list")

    required = {
        "tile_id", "x", "y", "status", "confidence", "temp_risk",
        "latency_penalty", "power_penalty",
    }
    tiles: list[Tile] = []
    seen_ids: set[str] = set()
    seen_coordinates: set[tuple[int, int]] = set()
    for index, item in enumerate(data["tiles"]):
        context = f"tiles[{index}]"
        if not isinstance(item, dict):
            raise InputValidationError(f"{context} must be an object")
        _required(item, required, context)
        tile_id = _string(item["tile_id"], f"{context}.tile_id")
        if tile_id in seen_ids:
            raise InputValidationError(f"duplicate tile_id: {tile_id}")
        x = _integer(item["x"], f"{context}.x")
        y = _integer(item["y"], f"{context}.y")
        if x >= width or y >= height:
            raise InputValidationError(
                f"tile {tile_id} coordinate ({x}, {y}) is outside {width}x{height} bounds"
            )
        if (x, y) in seen_coordinates:
            raise InputValidationError(f"duplicate tile coordinate: ({x}, {y})")
        status = item["status"]
        if status not in {"usable", "weak", "defective"}:
            raise InputValidationError(f"{context}.status has invalid value: {status!r}")
        tiles.append(
            Tile(
                tile_id=tile_id,
                x=x,
                y=y,
                status=status,
                confidence=_unit_float(item["confidence"], f"{context}.confidence"),
                temp_risk=_unit_float(item["temp_risk"], f"{context}.temp_risk"),
                latency_penalty=_unit_float(
                    item["latency_penalty"], f"{context}.latency_penalty"
                ),
                power_penalty=_unit_float(item["power_penalty"], f"{context}.power_penalty"),
            )
        )
        seen_ids.add(tile_id)
        seen_coordinates.add((x, y))
    if not tiles:
        raise InputValidationError("chip map must include at least one tile")
    return ChipMap(chip_id=chip_id, width=width, height=height, tiles=tuple(tiles))


def load_workloads(path: str | Path) -> tuple[Workload, ...]:
    data = _load_object(path)
    _required(data, {"workloads"}, "workloads document")
    if not isinstance(data["workloads"], list):
        raise InputValidationError("workloads must be a list")
    required = {
        "workload_id", "role", "criticality", "compute_required",
        "latency_sensitivity", "reliability_required",
    }
    output: list[Workload] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(data["workloads"]):
        context = f"workloads[{index}]"
        if not isinstance(item, dict):
            raise InputValidationError(f"{context} must be an object")
        _required(item, required, context)
        workload_id = _string(item["workload_id"], f"{context}.workload_id")
        if workload_id in seen_ids:
            raise InputValidationError(f"duplicate workload_id: {workload_id}")
        criticality = item["criticality"]
        if criticality not in {"low", "medium", "high", "safety_critical"}:
            raise InputValidationError(
                f"{context}.criticality has invalid value: {criticality!r}"
            )
        output.append(
            Workload(
                workload_id=workload_id,
                role=_string(item["role"], f"{context}.role"),
                criticality=criticality,
                compute_required=_integer(
                    item["compute_required"], f"{context}.compute_required", minimum=1
                ),
                latency_sensitivity=_unit_float(
                    item["latency_sensitivity"], f"{context}.latency_sensitivity"
                ),
                reliability_required=_unit_float(
                    item["reliability_required"], f"{context}.reliability_required"
                ),
            )
        )
        seen_ids.add(workload_id)
    if not output:
        raise InputValidationError("workloads document must include at least one workload")
    return tuple(output)


def load_constraints(path: str | Path) -> Constraints:
    data = _load_object(path)
    fields = {
        "max_temp_risk", "max_latency_penalty", "max_power_penalty",
        "allow_weak_tiles_for_low_priority", "forbid_safety_critical_on_weak_tiles",
        "hardware_control_enabled",
    }
    _required(data, fields, "constraints document")
    hardware_enabled = _boolean(data["hardware_control_enabled"], "hardware_control_enabled")
    if hardware_enabled:
        raise InputValidationError(
            "hardware_control_enabled=true is forbidden in HAL Recovery Compiler v0.1"
        )
    return Constraints(
        max_temp_risk=_unit_float(data["max_temp_risk"], "max_temp_risk"),
        max_latency_penalty=_unit_float(
            data["max_latency_penalty"], "max_latency_penalty"
        ),
        max_power_penalty=_unit_float(data["max_power_penalty"], "max_power_penalty"),
        allow_weak_tiles_for_low_priority=_boolean(
            data["allow_weak_tiles_for_low_priority"],
            "allow_weak_tiles_for_low_priority",
        ),
        forbid_safety_critical_on_weak_tiles=_boolean(
            data["forbid_safety_critical_on_weak_tiles"],
            "forbid_safety_critical_on_weak_tiles",
        ),
        hardware_control_enabled=False,
    )
