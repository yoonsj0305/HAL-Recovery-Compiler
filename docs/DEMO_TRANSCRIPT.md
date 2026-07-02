# Demo Transcript

Copy and run these commands from the repository root. The demo uses synthetic data only.

## 1. Install

```bash
python -m pip install -e .
```

## 2. Validate sample

```bash
hal-rc validate samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json
```

Expected: the command reports chip/tile/workload counts and confirms `hardware_control_enabled: false`. It writes no artifacts.

## 3. Compile with self-check and comparison

```bash
hal-rc compile samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json --out artifacts/chip_001 --self-check --comparison-report
```

Expected: standard candidate artifacts, `artifact_validation_report.json`, and comparison JSON/HTML are created under `artifacts/chip_001`.

## 4. Verify artifacts

```bash
hal-rc verify-artifacts artifacts/chip_001 --chip samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json
```

Expected: internally consistent artifacts report `passed: true`. This is not physical validation.

## 5. Compare baselines

```bash
hal-rc compare-baselines samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json --out artifacts/chip_001_comparison
```

Expected: `strict_usable_only`, `no_route_awareness`, and `route_aware` are compared using deterministic metrics.

## 6. Interpret result

- Highest raw score is not automatically recommended.
- Recommended mode must satisfy safety constraints and have complete accepted routes.
- `route_aware` may assign fewer workloads but can be the recommended safe mode.
- Unassigned workloads can show that unsafe or unsupported placements were refused.

All results are simulation-only candidates requiring human review. No command controls hardware, flashes firmware, or certifies silicon.

