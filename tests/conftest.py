from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def write_json(tmp_path):
    def write(name: str, value: object) -> Path:
        path = tmp_path / name
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        return path
    return write


@pytest.fixture
def valid_chip_data():
    return {
        "chip_id": "TEST_CHIP",
        "width": 2,
        "height": 2,
        "tiles": [
            {"tile_id": "A", "x": 0, "y": 0, "status": "usable", "confidence": 0.95, "temp_risk": 0.1, "latency_penalty": 0.1, "power_penalty": 0.1},
            {"tile_id": "B", "x": 1, "y": 0, "status": "weak", "confidence": 0.7, "temp_risk": 0.2, "latency_penalty": 0.2, "power_penalty": 0.2},
            {"tile_id": "C", "x": 0, "y": 1, "status": "defective", "confidence": 0.1, "temp_risk": 0.9, "latency_penalty": 0.9, "power_penalty": 0.9},
            {"tile_id": "D", "x": 1, "y": 1, "status": "usable", "confidence": 0.85, "temp_risk": 0.15, "latency_penalty": 0.15, "power_penalty": 0.15},
        ],
    }


@pytest.fixture
def constraints():
    from hal_rc.models import Constraints
    return Constraints(0.75, 0.70, 0.75, True, True, False)

