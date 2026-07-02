# GitHub Repository Setup

## Recommended metadata

**Repository description**

> Simulation-only functional recovery profile compiler for defect-aware, route-aware workload placement on imperfect chip maps.

**Suggested short tagline**

> HAL connects what still works.

**Suggested topics**

- `functional-yield`
- `semiconductor`
- `defect-tolerance`
- `compiler`
- `chiplet`
- `route-aware-placement`
- `reliability`
- `recovery-profile`
- `simulation`
- `python`

## Recommended release

**Title**

> HAL Recovery Compiler v0.3.1-public-poc

**Summary**

> First public proof-of-concept release of HAL Recovery Compiler, a simulation-only functional recovery profile compiler for defect-aware, route-aware workload placement on imperfect chip maps.

Attach `hal-recovery-compiler-v0.3.1-public-poc-github.zip` and its SHA-256 digest. Link to the release notes and safety boundary.

## Repository settings

- Use `main` as the protected default branch if that matches the repository convention.
- Require the `CI / test` check before merging.
- Enable pull requests and issue templates.
- Do not enable generated-artifact publication by default.
- Keep synthetic examples public; do not upload proprietary chip maps.

## Claims guardrail

Do not describe this repository as production-ready, certified, hardware-controlling, or silicon-repairing. It is simulation-only, candidate-only, hardware-control-disabled, and human-review-required.

Required output boundary:

```json
{
  "hardware_control_enabled": false,
  "human_review_required": true,
  "claim_boundary": "simulation_only_not_certified"
}
```

