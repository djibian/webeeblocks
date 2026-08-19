# WebeeBlocks Agent Instructions

## Mission

WebeeBlocks is an educational robotics project. Its priority is reliable pedagogical behavior and incremental product progress supported by evidence.

## Organizational doctrine

WebeeBlocks should standardize **organizational mechanisms only after they have demonstrated their value in real AI-assisted engineering work**.

Do not introduce a major new coordination, review, escalation, automation, or decision pattern here merely because it appears promising. Prefer mechanisms whose benefits, costs, and failure modes have already been observed in practice.

This is an organizational rule only. WebeeBlocks is fully self-contained and must remain operationally independent from other repositories.

## Strict repository independence

Do not create cross-project workflows. WebeeBlocks must not:

- send requirements, issues, failures, tasks, or research questions to another repository;
- depend on another repository's issues, branches, PRs, commits, artifacts, CI, or current state;
- create automated hand-offs across repositories;
- import product decisions from another project;
- require another project to perform work before WebeeBlocks work can proceed;
- use another repository as shared memory.

If an organizational pattern is judged mature enough to reproduce here, it becomes a **local WebeeBlocks rule** with its own documentation and no continuing external dependency.

## Repository governance

`main` is not a development target. Do not commit directly to `main` or promote work there without Emmanuel's explicit authorization.

`webots-ci` is the current integration branch for Webots R2025a migration and Crazyflie work. Use short-lived branches and focused pull requests.

## GitHub is WebeeBlocks shared memory

Do not rely on chat history or another repository as project state. Before work, read:

1. this `AGENTS.md`;
2. `[Lead] WebeeBlocks state & priorities`;
3. the assigned WebeeBlocks issue;
4. relevant WebeeBlocks Lab and Verification evidence;
5. related WebeeBlocks PRs and current CI evidence.

Write important conclusions back to this repository.

## Evidence vocabulary

Use consistently:

- `PROVEN_BY_TEST`
- `VERIFIED_BY_CI`
- `VERIFIED_BY_PRIMARY_SOURCE`
- `VERIFIED_BY_CODE_INSPECTION`
- `INFERENCE`
- `HYPOTHESIS`
- `UNPROVEN`
- `REFUTED`
- `FALSE_POSITIVE`
- `REGRESSION`

Green CI is evidence only for what its oracle actually exercises. A skipped test is not a pass. A synthetic marker is not proof of physical or user-visible behavior unless the claim is specifically about that marker.

## Adaptive roles

Use the smallest trustworthy pipeline.

### Normal product increment
`Lead -> Builder/Engineering -> Verification`

### Product uncertainty
`Lead -> Lab/Experimenter -> Builder/Engineering -> Verification`

### High-risk claim
Add independent adversarial or reviewer scrutiny only when the cost of a false conclusion justifies it.

Roles are epistemic functions, not ceremony. Do not add an agent merely to make the organization look complete.

## Lead

The Lead owns the problem and the current bottleneck, not implementation details. Keep one causal bottleneck active. Split work when a PR discovers a genuinely new experimental question rather than indefinitely expanding the same PR.

## Lab / Experimenter

Optimize for information gain. Design the smallest discriminating experiment. Measure before tuning. Separate observed behavior from inference. Do not broaden product architecture while the causal question is still unresolved.

## Builder / Engineering

Implement only the authorized increment. Prefer causal fixes, minimal reversible changes, and tests that would fail before the fix. Do not weaken an oracle, safety guard, or acceptance criterion to obtain green CI.

## Verification

Try to falsify the claimed behavior. Verify that tests exercise the stated property, distinguish product behavior from harness behavior, and identify false-positive oracles. Do not assume a green workflow proves the product claim.

## Independent review

Whenever practical, the agent/model performing Verification or adversarial review should be different from the agent/model that implemented the change. Automated GitHub review may be used as an additional Reviewer-0, but not as the sole authority for a non-trivial claim.

## Pull requests

Each substantial PR should state:

- issue/objective;
- scope and non-goals;
- tests/evidence;
- remaining uncertainty.

If the causal question changes materially, prefer a new issue/PR rather than turning one PR into an unbounded investigation.

## Organizational changes

Treat changes to the agent organization as real engineering changes. Before making a new coordination mechanism standard in WebeeBlocks, require prior practical evidence that it reduces one or more of:

- human relay work;
- duplicated agent effort;
- false-positive conclusions;
- time spent on non-causal fixes;
- unbounded PR cycles;

without degrading evidence quality or project clarity.

The decision to introduce such a mechanism is made outside the day-to-day WebeeBlocks workflow after reviewing prior real-world experience. Do not create a live dependency on the project where that experience was gathered.

Once adopted here, the mechanism must be documented locally and evaluated from WebeeBlocks' own subsequent results.

## Definition of done

Work is done only when the scoped objective is met, relevant gates exercise the intended behavior, Verification has no blocking contradiction, regressions are addressed, and remaining uncertainty is explicit.