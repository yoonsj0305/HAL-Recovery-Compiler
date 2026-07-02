# Safety Boundary

## Simulation-only boundary

HAL Recovery Compiler operates on synthetic JSON evidence. It does not observe or control a live chip. Its outputs are simulation candidates.

## Candidate-only boundary

A recovery profile describes one candidate reassignment under the supplied model. It is not a command, certified configuration, production disposition, or physical guarantee.

## Human-review-required boundary

Every output requires qualified human review. The compiler does not authorize deployment or operational action.

## Prohibited capabilities

HAL Recovery Compiler provides:

- no hardware control;
- no firmware flashing or loading;
- no memory controller control;
- no voltage or timing control;
- no driver integration;
- no runtime loading;
- no certification claim;
- no production-readiness claim.

Recovery Runtime is intentionally a future separate project.

## Required safety fields

Every generated JSON report preserves:

```json
{
  "hardware_control_enabled": false,
  "human_review_required": true,
  "claim_boundary": "simulation_only_not_certified"
}
```

Input constraints that set `hardware_control_enabled` to `true` are rejected.

## Why unassigned workloads are a safety feature

A workload stays unassigned when the compiler cannot find enough eligible tiles, a connected compute group, or a complete safe route. Refusal prevents a plausible-looking but invalid placement from entering the candidate profile.

Unassigned does not necessarily mean the compiler failed. It means the current evidence and constraints do not support that candidate assignment.

## Why a high score can still be unsafe

`no_route_awareness` can assign individually strong tiles and achieve high raw coverage while those tiles remain fragmented or route-incomplete. Raw functional-yield score is descriptive. It does not override route completeness or safety violations.

The Safe Recommendation Layer recommends only modes that satisfy all safety requirements.

## Certification and production boundary

Artifact self-check verifies internal consistency, not silicon function. Baseline comparison quantifies model trade-offs, not measured performance. A recommended mode remains simulation-only and is not silicon certification.

