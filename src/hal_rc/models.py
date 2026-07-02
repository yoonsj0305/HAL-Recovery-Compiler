"""Typed domain models for HAL Recovery Compiler."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TileStatus = Literal["usable", "weak", "defective"]
Criticality = Literal["low", "medium", "high", "safety_critical"]


@dataclass(frozen=True, slots=True)
class Tile:
    tile_id: str
    x: int
    y: int
    status: TileStatus
    confidence: float
    temp_risk: float
    latency_penalty: float
    power_penalty: float

    @property
    def score(self) -> float:
        return (
            0.45 * self.confidence
            + 0.20 * (1.0 - self.temp_risk)
            + 0.20 * (1.0 - self.latency_penalty)
            + 0.15 * (1.0 - self.power_penalty)
        )


@dataclass(frozen=True, slots=True)
class ChipMap:
    chip_id: str
    width: int
    height: int
    tiles: tuple[Tile, ...]


@dataclass(frozen=True, slots=True)
class Workload:
    workload_id: str
    role: str
    criticality: Criticality
    compute_required: int
    latency_sensitivity: float
    reliability_required: float


@dataclass(frozen=True, slots=True)
class Constraints:
    max_temp_risk: float
    max_latency_penalty: float
    max_power_penalty: float
    allow_weak_tiles_for_low_priority: bool
    forbid_safety_critical_on_weak_tiles: bool
    hardware_control_enabled: bool = False


@dataclass(frozen=True, slots=True)
class TileClassification:
    tile_id: str
    classification: str
    eligible_for_routing: bool
    reason: str


@dataclass(frozen=True, slots=True)
class WorkloadAssignment:
    workload_id: str
    role: str
    criticality: Criticality
    tile_ids: tuple[str, ...]
    tile_scores: tuple[float, ...]
    assignment_score: float


@dataclass(frozen=True, slots=True)
class Route:
    workload_id: str
    start_tile_id: str
    end_tile_id: str
    tile_ids: tuple[str, ...]
    status: str = "preferred"
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PreferredRouteRecord:
    workload_id: str
    route_id: str
    from_anchor: str
    to_tiles: tuple[str, ...]
    route_tile_ids: tuple[str, ...]
    route_status: str = "candidate_simulated"


@dataclass(frozen=True, slots=True)
class BlockedRouteRecord:
    workload_id: str
    reason: str
    claim_boundary: str = "simulation_only_not_certified"


@dataclass(frozen=True, slots=True)
class WorkloadRoute:
    workload_id: str
    assigned: bool
    connected: bool
    routable: bool
    route_length: int | None
    tile_ids: tuple[str, ...]
    route_tile_ids: tuple[str, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryProfile:
    chip_id: str
    compiler_version: str
    disabled_tiles: tuple[str, ...]
    weak_tiles_used: tuple[str, ...]
    assigned_workloads: tuple[WorkloadAssignment, ...]
    unassigned_workloads: tuple[dict[str, str], ...]
    preferred_routes: tuple[PreferredRouteRecord, ...]
    blocked_routes: tuple[BlockedRouteRecord, ...]
    allowed_roles: tuple[str, ...]
    blocked_roles: tuple[str, ...]
    timing_policy: dict[str, Any]
    voltage_policy: dict[str, Any]
    runtime_loader_hint: str
    hardware_control_enabled: bool = False
    human_review_required: bool = True
    claim_boundary: str = "simulation_only_not_certified"


@dataclass(frozen=True, slots=True)
class FunctionalPassport:
    chip_id: str
    functional_yield_score: float
    recovered_capacity_estimate: float
    remaining_roles: tuple[str, ...]
    blocked_roles: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    artifact_self_check_available: bool = True
    hardware_control_enabled: bool = False
    human_review_required: bool = True
    validation_status: str = "candidate_only"
    claim_boundary: str = "simulation_only_not_certified"


@dataclass(frozen=True, slots=True)
class SolverReport:
    solver_name: str
    runtime_ms: float
    total_tiles: int
    usable_tiles: int
    weak_tiles: int
    defective_tiles: int
    total_workloads: int
    assigned_workloads: int
    unassigned_workloads: int
    used_tiles_count: int
    blocked_tiles_count: int
    used_tile_ids: tuple[str, ...]
    blocked_tile_ids: tuple[str, ...]
    used_tiles: int
    blocked_tiles: int
    objective_score: float
    local_search_enabled: bool
    local_search_iterations: int
    local_search_improvement_delta: float
    route_blocked_segments_count: int
    route_warning: str | None
    route_warnings: tuple[str, ...]
    placement_mode: str
    route_anchor_tile_id: str | None
    route_aware_assignments: bool
    connected_assignment_required: bool
    routable_assignment_required: bool
    candidate_groups_evaluated: int
    candidate_groups_rejected_connectivity: int
    candidate_groups_rejected_routing: int
    route_complete_assignments: int
    route_incomplete_assignments: int
    average_route_length: float
    max_route_length: int
    workload_routes: tuple[WorkloadRoute, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    hardware_control_enabled: bool = False
    human_review_required: bool = True
    claim_boundary: str = "simulation_only_not_certified"


@dataclass(frozen=True, slots=True)
class SolverResult:
    assignments: tuple[WorkloadAssignment, ...]
    unassigned: tuple[dict[str, str], ...]
    objective_score: float
    workload_routes: tuple[WorkloadRoute, ...] = ()
    placement_mode: str = "placement_first"
    route_anchor_tile_id: str | None = None
    candidate_groups_evaluated: int = 0
    candidate_groups_rejected_connectivity: int = 0
    candidate_groups_rejected_routing: int = 0


@dataclass(frozen=True, slots=True)
class ArtifactValidationReport:
    passed: bool
    invariant_checks_total: int
    invariant_checks_passed: int
    invariant_checks_failed: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    checked_at_version: str
    claim_boundary: str = "simulation_only_not_certified"
    hardware_control_enabled: bool = False
    human_review_required: bool = True


@dataclass(frozen=True, slots=True)
class ReplayComparisonReport:
    matched: bool
    files_compared: tuple[str, ...]
    differences: tuple[str, ...]
    ignored_fields: tuple[str, ...]
    checked_at_version: str
    claim_boundary: str = "simulation_only_not_certified"
    hardware_control_enabled: bool = False
    human_review_required: bool = True


def to_dict(value: Any) -> Any:
    """Convert dataclass output into JSON-safe deterministic containers."""
    return asdict(value)
