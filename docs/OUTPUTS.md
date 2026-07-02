# Output Artifacts

All generated JSON artifacts preserve `hardware_control_enabled: false`, `human_review_required: true`, and `claim_boundary: simulation_only_not_certified`.

## `recovery_profile.json`

- Candidate workload assignment and route plan
- Disabled and conditionally used tiles
- Assigned and unassigned workloads
- Preferred anchor routes and summarized blocked routes
- Allowed and blocked roles
- Explicit no-control voltage/timing policies

This is a review artifact, not a runtime instruction.

## `functional_passport.json`

- Functional-yield summary
- Recovered-capacity estimate
- Remaining and blocked roles
- Transparent scoring evidence
- Route-aware and optional baseline-comparison evidence
- `validation_status: candidate_only`

## `solver_report.json`

- Solver identity and measured runtime
- Route-aware placement mode and anchor
- Candidate-group evaluation/rejection counts
- Assigned/unassigned workload totals
- Used and blocked tile IDs
- Per-workload route telemetry
- Route completeness and length metrics
- Bounded local-search telemetry

## `artifact_validation_report.json`

- Invariant self-check pass/fail
- Total, passed, and failed checks
- Specific errors and warnings
- Compiler version used for checking

This artifact is written only when `--self-check` is used.

## `comparison_report.json`

- `strict_usable_only`, `no_route_awareness`, and `route_aware` results
- Workload and criticality-weighted coverage
- Functional-yield and capacity estimates
- Route completeness and safety-violation counts
- Raw best versus safe best
- Recommended candidate mode and reason
- Gain and trade-off summaries

## `summary_report.html`

Human-readable chip, workload, safety, self-check, and optional comparison summary. It contains no JavaScript or external assets.

## `comparison_report.html`

Human-readable baseline table and Safe Recommendation Layer summary. It highlights that the highest raw score is not automatically recommended.

