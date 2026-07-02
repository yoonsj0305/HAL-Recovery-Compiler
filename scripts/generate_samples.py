"""Generate the deterministic 16x16 synthetic demonstration inputs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"

DEFECTIVE = (
    {(x, 8) for x in range(16) if x != 7}
    | {(2, 2), (2, 3), (3, 2), (3, 3)}
    | {(12, 12), (13, 12), (12, 13)}
)
WEAK = {
    (7, 8),
    (5, 1), (10, 1), (15, 1),
    (1, 5), (6, 5), (11, 5),
    (3, 10), (8, 10), (14, 10),
    (1, 14), (5, 14), (9, 14), (14, 14),
    (4, 7), (10, 7), (15, 12),
}
SAFETY_CLUSTER = {
    (1, 0), (2, 0), (3, 0), (4, 0),
    (1, 1), (2, 1), (3, 1), (4, 1),
}


def _tile(x: int, y: int) -> dict[str, object]:
    coordinate = (x, y)
    if coordinate in DEFECTIVE:
        status = "defective"
        confidence = 0.12 + ((x + y) % 8) / 100
        temp_risk = 0.82 + ((x * 3 + y) % 12) / 100
        latency = 0.80 + ((x + y * 2) % 15) / 100
        power = 0.79 + ((x * 2 + y * 3) % 16) / 100
    elif coordinate in SAFETY_CLUSTER:
        status = "usable"
        confidence = 0.99
        temp_risk = 0.04
        latency = 0.04
        power = 0.04
    elif coordinate in WEAK:
        status = "weak"
        confidence = 0.55 + ((x * 7 + y * 11) % 20) / 100
        temp_risk = 0.25 + ((x * 3 + y * 5) % 24) / 100
        latency = 0.23 + ((x * 5 + y * 2) % 24) / 100
        power = 0.24 + ((x * 2 + y * 7) % 24) / 100
    else:
        status = "usable"
        confidence = 0.80 + ((x * 7 + y * 11) % 19) / 100
        temp_risk = 0.05 + ((x * 3 + y * 5) % 19) / 100
        latency = 0.06 + ((x * 5 + y * 2) % 17) / 100
        power = 0.07 + ((x * 2 + y * 7) % 17) / 100
    return {
        "tile_id": f"T_{x}_{y}",
        "x": x,
        "y": y,
        "status": status,
        "confidence": round(confidence, 2),
        "temp_risk": round(temp_risk, 2),
        "latency_penalty": round(latency, 2),
        "power_penalty": round(power, 2),
    }


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    chip = {
        "chip_id": "CHIP_001_SYNTHETIC",
        "width": 16,
        "height": 16,
        "tiles": [_tile(x, y) for y in range(16) for x in range(16)],
    }
    workloads = {
        "workloads": [
            {"workload_id": "WL_SC_01", "role": "monitoring_only", "criticality": "safety_critical", "compute_required": 8, "latency_sensitivity": 0.95, "reliability_required": 0.97},
            {"workload_id": "WL_SC_02", "role": "safety_diagnostic_candidate", "criticality": "safety_critical", "compute_required": 12, "latency_sensitivity": 0.98, "reliability_required": 0.995},
            {"workload_id": "WL_HIGH_01", "role": "reduced_compute", "criticality": "high", "compute_required": 28, "latency_sensitivity": 0.80, "reliability_required": 0.78},
            {"workload_id": "WL_HIGH_02", "role": "reduced_compute", "criticality": "high", "compute_required": 28, "latency_sensitivity": 0.78, "reliability_required": 0.78},
            {"workload_id": "WL_HIGH_03", "role": "background_inference", "criticality": "high", "compute_required": 28, "latency_sensitivity": 0.74, "reliability_required": 0.76},
            {"workload_id": "WL_MED_01", "role": "background_inference", "criticality": "medium", "compute_required": 28, "latency_sensitivity": 0.58, "reliability_required": 0.72},
            {"workload_id": "WL_MED_02", "role": "low_priority_cache", "criticality": "medium", "compute_required": 28, "latency_sensitivity": 0.50, "reliability_required": 0.70},
            {"workload_id": "WL_MED_03", "role": "test_debug_only", "criticality": "medium", "compute_required": 28, "latency_sensitivity": 0.42, "reliability_required": 0.68},
            {"workload_id": "WL_LOW_01", "role": "low_priority_cache", "criticality": "low", "compute_required": 30, "latency_sensitivity": 0.30, "reliability_required": 0.52},
            {"workload_id": "WL_LOW_02", "role": "test_debug_only", "criticality": "low", "compute_required": 20, "latency_sensitivity": 0.20, "reliability_required": 0.50},
        ]
    }
    constraints = {
        "max_temp_risk": 0.75,
        "max_latency_penalty": 0.70,
        "max_power_penalty": 0.75,
        "allow_weak_tiles_for_low_priority": True,
        "forbid_safety_critical_on_weak_tiles": True,
        "hardware_control_enabled": False,
    }
    for name, value in (
        ("chip_001.json", chip),
        ("workloads.json", workloads),
        ("constraints.json", constraints),
    ):
        (SAMPLES / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
