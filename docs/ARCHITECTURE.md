# Architecture

## System overview

HAL Recovery Compiler is an offline, simulation-only Python CLI. It transforms a synthetic chip map, workload set, and safety policy into candidate recovery artifacts for human review.

It has no hardware output path. Runtime is not included.

```text
JSON inputs
  -> strict ingest and validation
  -> 2D tile graph
  -> bounded route-aware placement
  -> candidate profile and reports
  -> artifact invariant validation
  -> baseline comparison
  -> safe recommendation
```

## Input files

### `samples/chip_001.json`

Defines a 16×16 synthetic tile map. Each tile has an ID, coordinate, status (`usable`, `weak`, or `defective`), confidence, and temperature/latency/power penalties.

### `samples/workloads.json`

Defines workload IDs, roles, criticality, required tile counts, latency sensitivity, and reliability requirements.

### `samples/constraints.json`

Defines risk ceilings and weak-tile policy. `hardware_control_enabled` must be `false`; `true` is rejected during ingest.

## Core pipeline

1. **Ingest** — load JSON and reject malformed fields, duplicate IDs, invalid ranges, and out-of-bounds tiles.
2. **Validation** — enforce the simulation-only safety boundary before solving.
3. **Graph construction** — build a deterministic four-neighbor grid graph without defective tiles.
4. **Route-aware placement** — find connected eligible groups and a valid path from the reserved anchor before accepting an assignment.
5. **Recovery profile generation** — record assigned/unassigned workloads, disabled tiles, safe roles, and candidate routes.
6. **Artifact self-check** — cross-check JSON outputs against the original inputs and route/safety invariants.
7. **Baseline comparison** — compare `strict_usable_only`, `no_route_awareness`, and `route_aware` policies.
8. **Safe recommendation** — separate the highest raw score from the highest safe score and recommend only a safe candidate mode.

## Main modules

- `ingest.py` — strict input loading and validation.
- `models.py` — typed dataclasses for inputs, assignments, routes, profiles, and reports.
- `graph.py` — grid graph construction and deterministic BFS.
- `solver_greedy.py` — placement-first comparison baseline.
- `solver_route_aware.py` — bounded connected-group placement and anchor routing.
- `solver_local_search.py` — bounded compatibility interface; route-aware mode conservatively preserves valid groups.
- `profile.py` — `recovery_profile.json` construction.
- `passport.py` — `functional_passport.json` and transparent functional-yield evidence.
- `report.py` — solver JSON and standalone HTML summary.
- `invariants.py` — cross-artifact safety, tile, workload, connectivity, score, and preferred-route validation.
- `replay.py` — deterministic logical comparison across compile runs.
- `baseline.py` — deterministic baseline evaluators.
- `comparison.py` — comparison models, deltas, trade-offs, and HTML.
- `recommendation.py` — safe-mode filtering, ranking, recommendation, and validation.
- `cli.py` — command-line orchestration only.

## Route-aware placement

An accepted workload receives exactly `compute_required` exclusive compute tiles. The selected tiles must be internally connected using only up, down, left, and right adjacency. Diagonals do not count.

Defective tiles cannot be assigned or crossed. Risk and criticality policies filter compute tiles. At least one selected tile must be reachable by deterministic BFS from the reserved top-left safe usable anchor.

Candidate search is bounded by 64 seeds and 256 expansions per seed. It is deterministic, not mathematically optimal.

## Artifact validator

The invariant validator reopens the logical contract after compilation. It verifies hard safety fields, tile existence, defective-tile exclusion, workload exclusivity, criticality policy, group connectivity, path adjacency, anchor origin, preferred-route agreement, report totals, score telemetry, and optional recommendation safety.

Self-check proves internal consistency only. It does not prove physical chip behavior.

## Baseline comparison

- `strict_usable_only` refuses weak regions and still requires connectivity and routing.
- `no_route_awareness` approximates the older placement-first policy and reports incomplete routes honestly.
- `route_aware` is the default compiler policy.

The comparison reports coverage, capacity, route completeness, safety violations, gains, and trade-offs. Metrics are simulation evidence, not production benchmarks.

## Safe recommendation layer

The raw best mode is selected by score. Safe modes must have zero safety violations, zero incomplete accepted routes, passing invariants, hardware control disabled, and the simulation-only claim boundary. Only a safe mode can be recommended.

## Runtime boundary

Runtime is not included. A future, separate HAL Recovery Runtime project may consume `recovery_profile.json`, but this repository does not load profiles, modify firmware, control memory, or operate hardware.

