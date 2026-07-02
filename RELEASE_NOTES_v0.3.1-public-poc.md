# HAL Recovery Compiler v0.3.1-public-poc

## What this release is

The first frozen public proof-of-concept package for HAL Recovery Compiler. It demonstrates deterministic, defect-aware, route-aware candidate workload placement on synthetic chip maps, with artifact verification, policy comparison, and safety-bounded recommendation.

## What this release is not

This release is not silicon repair, hardware control, firmware or driver integration, Recovery Runtime, chip certification, production qualification, or a yield guarantee.

## Core capabilities

- Strict JSON input validation
- Four-neighbor route-aware placement
- Candidate recovery profile and functional passport generation
- Artifact invariant self-check
- Deterministic replay comparison
- Baseline comparison across three policies
- Safe Recommendation Layer separating raw score from safe recommendation

## CLI commands

- `hal-rc validate`
- `hal-rc compile`
- `hal-rc compile --self-check --comparison-report`
- `hal-rc verify-artifacts`
- `hal-rc compare-artifacts`
- `hal-rc compare-baselines`

See `README.md` and `docs/DEMO_TRANSCRIPT.md` for complete commands.

## Output artifacts

- `recovery_profile.json`
- `functional_passport.json`
- `solver_report.json`
- `summary_report.html`
- `artifact_validation_report.json`
- `comparison_report.json`
- `comparison_report.html`

## Safety boundary

All generated reports preserve:

```json
{
  "hardware_control_enabled": false,
  "human_review_required": true,
  "claim_boundary": "simulation_only_not_certified"
}
```

The package is simulation-only and candidate-only. Human review is mandatory.

## Known limitations

- Synthetic sample data only
- No real ATE/BIST adapter
- No hardware control
- No Recovery Runtime
- No production certification
- No guarantee of real silicon improvement
- Route-aware solver is a deterministic PoC, not a global optimum
- No explicit open-source license has been selected yet

## Future work

Documentation-only improvements and additional synthetic examples may continue. Recovery Runtime, ATE/BIST adapters, solver plugins, and package/chiplet planning belong to future separate projects and require independent safety review.

