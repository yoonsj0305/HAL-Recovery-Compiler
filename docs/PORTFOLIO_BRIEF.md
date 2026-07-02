# Portfolio Brief

## Project title

HAL Recovery Compiler

## One-sentence summary

A simulation-only Python compiler that converts synthetic chip defect maps, workload requirements, and safety constraints into connected, route-aware candidate recovery profiles with verifiable evidence.

## Problem

Conventional pass/fail handling can discard a partially functional system without asking which functions remain usable. The engineering problem is to distinguish usable, weak, and defective regions, then determine whether remaining resources can support a safe, connected workload arrangement.

## Insight

The project explores whether physical yield loss can be partially converted into usable functional yield through evidence-based workload reassignment and safety-bounded recovery profiles.

The key constraint is that a good-looking tile is not useful when it is isolated, unreachable, or inappropriate for a workload’s criticality.

## System design

The compiler validates three JSON inputs, constructs a four-neighbor tile graph, searches bounded connected groups, verifies anchor routes, emits candidate artifacts, self-checks their invariants, compares policy baselines, and recommends only a safe candidate mode.

## What I built

- Typed Python domain models and strict input validation
- Deterministic graph and BFS routing
- Bounded route-aware placement
- Candidate profile, passport, solver, and HTML reporting
- Cross-artifact invariant validation
- Deterministic output replay comparison
- Functional-yield baseline and trade-off analysis
- Safety-filtered recommendation logic
- Tests, CI, public documentation, and clean release packaging

## Why simulation-only matters

The system does not control or measure hardware. Keeping the scope simulation-only prevents an evidence prototype from being mistaken for firmware, a memory-controller feature, a physical repair mechanism, or certification.

## Key outputs

`recovery_profile.json`, `functional_passport.json`, `solver_report.json`, `artifact_validation_report.json`, `comparison_report.json`, and standalone HTML summaries.

## Technical keywords

Python 3.11, dataclasses, deterministic algorithms, BFS, grid graphs, constraint validation, defect tolerance, functional yield, invariant checking, reproducibility, CLI design, pytest, GitHub Actions.

## Future direction

Possible separate work includes more synthetic maps, a stable profile schema, ATE/BIST adapters, solver comparison plugins, package/chiplet planning, and a separately governed Recovery Runtime.

This public PoC remains candidate-only, human-review-required, and `simulation_only_not_certified`.

