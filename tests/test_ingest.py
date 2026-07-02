from __future__ import annotations

import pytest

from hal_rc.ingest import InputValidationError, load_chip, load_constraints, load_workloads


def test_valid_input_loads_successfully(write_json, valid_chip_data):
    chip = load_chip(write_json("chip.json", valid_chip_data))
    assert chip.chip_id == "TEST_CHIP"
    assert len(chip.tiles) == 4


def test_malformed_chip_json_rejected(write_json):
    with pytest.raises(InputValidationError, match="Malformed JSON"):
        load_chip(write_json("bad.json", "{"))


def test_duplicate_tile_ids_rejected(write_json, valid_chip_data):
    valid_chip_data["tiles"][1]["tile_id"] = "A"
    with pytest.raises(InputValidationError, match="duplicate tile_id"):
        load_chip(write_json("chip.json", valid_chip_data))


def test_tile_outside_bounds_rejected(write_json, valid_chip_data):
    valid_chip_data["tiles"][0]["x"] = 2
    with pytest.raises(InputValidationError, match="outside"):
        load_chip(write_json("chip.json", valid_chip_data))


def test_invalid_status_rejected(write_json, valid_chip_data):
    valid_chip_data["tiles"][0]["status"] = "unknown"
    with pytest.raises(InputValidationError, match="status"):
        load_chip(write_json("chip.json", valid_chip_data))


def test_invalid_float_range_rejected(write_json, valid_chip_data):
    valid_chip_data["tiles"][0]["confidence"] = 1.01
    with pytest.raises(InputValidationError, match="confidence"):
        load_chip(write_json("chip.json", valid_chip_data))


def test_hardware_control_enabled_true_rejected(write_json):
    data = {
        "max_temp_risk": 0.75,
        "max_latency_penalty": 0.70,
        "max_power_penalty": 0.75,
        "allow_weak_tiles_for_low_priority": True,
        "forbid_safety_critical_on_weak_tiles": True,
        "hardware_control_enabled": True,
    }
    with pytest.raises(InputValidationError, match="forbidden"):
        load_constraints(write_json("constraints.json", data))


def test_duplicate_workload_ids_rejected(write_json):
    item = {"workload_id": "W", "role": "test", "criticality": "low", "compute_required": 1, "latency_sensitivity": 0.2, "reliability_required": 0.5}
    with pytest.raises(InputValidationError, match="duplicate workload_id"):
        load_workloads(write_json("workloads.json", {"workloads": [item, item]}))
