# Claims Boundary

## Allowed claims

| Allowed wording | Evidence boundary |
|---|---|
| “simulation-only PoC” | Describes an offline software demonstration. |
| “candidate recovery profile generation” | Describes JSON evidence, not execution. |
| “defect-aware workload placement on synthetic chip maps” | Applies only to supplied synthetic inputs. |
| “route-aware placement” | Describes four-neighbor candidate routing. |
| “artifact self-check” | Checks internal consistency only. |
| “baseline comparison” | Compares deterministic modeled policies. |
| “safe recommendation logic” | Recommends candidate review modes, not hardware action. |

These claims describe software behavior under synthetic inputs. They do not describe measured silicon performance.

## Forbidden claims

| Forbidden claim | Why forbidden |
|---|---|
| “repairs defective chips” | No physical repair occurs. |
| “certifies chips” | No certification process exists. |
| “improves real silicon performance” | No real silicon is measured or controlled. |
| “controls memory controllers” | Memory-controller integration is absent. |
| “flashes firmware” | Firmware integration is absent. |
| “production-ready” | This release is a public PoC. |
| “fab-qualified” | No fab qualification exists. |
| “safety-certified” | Self-check is not safety certification. |
| “guarantees yield improvement” | Modeled functional yield is not a physical guarantee. |

## Required wording

When describing outputs, use terms such as `candidate`, `simulation-only`, `not certified`, `evidence`, and `human review required`.

Do not convert a passing artifact self-check into a physical validation claim. Internal consistency is not proof of hardware behavior.

## Runtime boundary

Recovery Runtime is not part of this repository. Any future runtime must be a separate project with its own safety, security, hardware, validation, and governance review.
