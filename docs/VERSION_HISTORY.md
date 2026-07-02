# Version History

Every release in this history is simulation-only, candidate-only, hardware-control-disabled, and subject to human review. No version certifies silicon or authorizes production use.

## v0.1.0

- First working compiler.
- Generated recovery profile, functional passport, solver report, and summary report.

## v0.1.1

- Interface hardening.
- Added `validate`.
- Added clearer solver-report fields, local-search telemetry, and release hygiene.

## v0.2.0

- Added route-aware placement.
- Required connected and routable tile groups.

## v0.2.1

- Added artifact self-check.
- Added `verify-artifacts`, `compare-artifacts`, and `artifact_validation_report.json`.

## v0.2.2

- Added preferred-route invariant hotfix.
- Validated `recovery_profile.preferred_routes` against grid and solver routes.

## v0.3.0

- Added baseline comparison.
- Compared `strict_usable_only`, `no_route_awareness`, and `route_aware`.
- Added functional-yield trade-off reports.

## v0.3.1

- Added Safe Recommendation Layer.
- Separated highest raw score from recommended safe mode.

## v0.3.1-public-poc

- Documentation and public PoC packaging freeze.
- Added public architecture, safety, functional-yield, demo, output, claims, history, and roadmap documents.
- No new solver behavior.
