# Demo

This demo uses only synthetic files included in the repository.

## 1. Install

```bash
python -m pip install -e ".[test]"
```

## 2. Validate sample input

```bash
hal-rc validate samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json
```

Validation checks schema, coordinate, value-range, workload, constraint, and hard hardware-control boundaries. It writes no artifacts.

## 3. Compile with self-check and comparison

```bash
hal-rc compile samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json --out artifacts/chip_001 --self-check --comparison-report
```

This generates the candidate recovery profile, passport, solver telemetry, invariant report, baseline comparison, and standalone HTML summaries.

## 4. Verify artifacts

```bash
hal-rc verify-artifacts artifacts/chip_001 --chip samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json
```

Verification should report `passed: true`. A manually corrupted route, safety field, or workload assignment should fail with a nonzero exit status.

## 5. Compare baselines separately

```bash
hal-rc compare-baselines samples/chip_001.json --workloads samples/workloads.json --constraints samples/constraints.json --out artifacts/chip_001_comparison
```

Open `artifacts/chip_001_comparison/comparison_report.html` in a browser if desired.

## 6. Interpret the expected result

- `no_route_awareness` may assign more workloads because it selects strong-looking tiles before requiring complete connected routes.
- `route_aware` is recommended when it has zero safety violations and complete accepted routes.
- A workload left unassigned is not necessarily a failure; it can show that the compiler refused an unsafe or unsupported candidate.
- Highest raw score and recommended safe mode can differ.

All results are simulation-only candidates, not silicon certification or hardware instructions.

