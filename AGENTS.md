# WebeeBlocks Agent Instructions

## Mission

WebeeBlocks is the production-oriented educational robotics project. Its priority is reliable pedagogical behavior and incremental product progress on evidence-backed foundations.

## Core doctrine: validated engineering only

WebeeBlocks is **not** the laboratory for cross-project engineering mechanisms.

When a new agent workflow, security mechanism, CI/oracle strategy, governance mechanism, trust-boundary pattern, or other reusable engineering practice is uncertain, it must first be investigated and validated in PolaCore.

The normal transfer direction is:

`PolaCore experiment -> independent falsification/review -> explicit PROMOTABLE decision -> WebeeBlocks adoption`

WebeeBlocks may send requirements, observed failures, constraints, and research questions to PolaCore. It must not treat a candidate mechanism as validated merely because it seems useful here.

### What this gate does not mean

Product-specific WebeeBlocks development does not move to PolaCore. Blockly behavior, Webots/Crazyflie physics, pedagogical UX, missions, curriculum behavior, and other domain-specific product questions remain investigated and developed in WebeeBlocks.

The PolaCore gate applies when we want to introduce or change a **reusable engineering mechanism or doctrine** whose validity is not already established.

## Promotion evidence required

Before adopting such a mechanism, record the PolaCore promotion evidence in the WebeeBlocks issue or PR:

- PolaCore issue/PR or retained promotion record;
- exact validated artifact/commit where relevant;
- promoted claim and permitted scope;
- evidence classification;
- remaining uncertainty;
- why the pattern applies to WebeeBlocks without silently extending the claim.

`HYPOTHESIS`, `INFERENCE`, `UNPROVEN`, `REFUTED`, misleading SKIP, or merely green CI are not sufficient.

## Repository governance

`main` is not a development target. Do not commit directly to `main` or promote work there without Emmanuel's explicit authorization.

`webots-ci` is the current integration branch for validated Webots R2025a migration and Crazyflie work. Use short-lived branches and focused pull requests.

## GitHub is shared memory

Do not rely on chat history as project state. Before work, read:

1. this `AGENTS.md`;
2. `[Lead] WebeeBlocks state & priorities`;
3. the assigned issue;
4. relevant Lab and Verification evidence;
5. related PRs and current CI evidence;
6. any PolaCore promotion evidence required by the change.

Write important conclusions back to GitHub.

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
Use additional independent adversarial/reviewer scrutiny. If the required mechanism is reusable and not already validated, send that mechanism to PolaCore first rather than inventing it inside WebeeBlocks.

## Lead

The Lead owns the problem and the current bottleneck, not implementation details. Keep one causal bottleneck active. Split work when a PR discovers a genuinely new experimental question rather than indefinitely expanding the same PR.

## Lab / Experimenter

Optimize for information gain. Design the smallest discriminating experiment. Measure before tuning. Separate observed behavior from inference. Product-specific experiments belong here; reusable unvalidated engineering mechanisms belong in PolaCore.

## Builder / Engineering

Implement only the authorized increment. Prefer causal fixes, minimal reversible changes, and tests that would fail before the fix. Do not weaken an oracle, safety guard, or acceptance criterion to obtain green CI. Do not silently introduce a new engineering doctrine that has not crossed the PolaCore validation gate.

## Verification

Try to falsify the claimed behavior. Verify that tests exercise the stated property, distinguish product behavior from harness behavior, and identify false-positive oracles. Do not assume a green workflow proves the product claim.

## Pull requests

Each substantial PR should state:

- issue/objective;
- scope and non-goals;
- tests/evidence;
- remaining uncertainty;
- PolaCore promotion reference when the PR adopts a reusable engineering mechanism covered by the validation gate.

If the causal question changes materially, prefer a new issue/PR rather than turning one PR into an unbounded investigation.

## Definition of done

Work is done only when the scoped objective is met, relevant gates exercise the intended behavior, Verification has no blocking contradiction, regressions are addressed, and remaining uncertainty is explicit.
