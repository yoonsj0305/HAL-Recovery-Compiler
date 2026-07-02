# Functional Yield

## Philosophy

**Physical yield may fail, but functional yield can still be recovered.**

Physical yield asks whether a manufactured object is fully defect-free against its original specification. Functional yield asks a narrower evidence-based question: which functions remain usable, which must be blocked, and whether the usable parts can form a safe candidate system.

HAL Recovery Compiler does not make bad silicon good; it identifies candidate ways to safely use what still works.

## Defective does not mean “pretend normal”

A defective tile is excluded from compute assignment and routing. Recovery never relabels it as healthy. The compiler instead restructures candidate workload placement around unavailable regions.

## Usable, weak, and defective are distinct

- `usable` tiles can serve workloads when confidence and risk constraints pass.
- `weak` tiles are conditional resources and may serve only allowed low-criticality work.
- `defective` tiles are unavailable.

Collapsing these states would hide evidence and weaken the safety boundary.

## Unsafe roles must be blocked

Not every surviving capability is appropriate for every role. Safety-critical control, mission-critical computation, primary filesystem metadata, and financial records remain blocked candidate roles. A partial chip may still support monitoring, reduced compute, background inference, cache, test, or debug roles.

## Reassigning remaining function

The compiler searches for connected tile groups with enough modeled compute capacity and a complete anchor route. It prefers high-confidence, lower-risk candidates and rejects fragmented or unreachable placements.

This is evidence-based recovery planning, not magic repair. The result depends on the supplied synthetic map, workload model, constraints, and scoring policy.

## Verification is part of recovery

Generated profiles are checked against their inputs. Verification confirms tile existence, defective-tile exclusion, criticality constraints, four-neighbor connectivity, route adjacency, anchor origin, report consistency, and recommendation safety.

Verification can find contradictions in an artifact. It cannot certify physical silicon.

## Relationship to the HAL layers

- **YieldOS Shadow** asks: what still works, under what evidence?
- **HAL Recovery Compiler** asks: where should roles and workloads be safely reassigned in a candidate profile?
- **Future HAL Recovery Runtime** may consume reviewed profiles in a separate project.

Runtime is intentionally not included here.

