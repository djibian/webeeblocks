# Manual controller policy — G4-H0

## Purpose

The WebeeBlocks controller is manually triggered. Each run reconstructs GitHub,
selects exactly one logical role, advances that role to a stable handoff or wait,
records the resulting state, and stops.

G4-H0 is intentionally read-only and non-event-driven. It adds no scheduler,
webhook, permission, secret, ruleset, merge authority, or mutation engine.

## Operational source

Resolve `webots-ci` and read repository policy from its exact head before using
repository files. The default branch `main` is not an operational fallback.

Separate authority from facts:

- current GitHub PR, branch, head, base, and CI observations outrank stale state;
- recent, explicitly bounded authority from Emmanuel outranks historical authority;
- `AGENTS.md`, `docs/PRODUCT_VISION.md`, and the governance contracts on the
  exact `webots-ci` head define current policy;
- the machine block in #22 is the canonical declared state and must be
  reconciled with observed facts before work starts.

## Routing

`expected_role` is a consistency assertion, not the sole router input.

The deterministic router applies these priorities:

1. fail closed on concurrent integration WIP or unauthorized `main` PRs;
2. consume a valid G3 recovery decision when a failure is active;
3. route a coherent active stage to its required role;
4. route a fully neutral state with no open integration PR to `Lead / PLAN`;
5. wait without inventing work when a human gate is the only transition;
6. fail explicitly when facts, authority, stage, or declared role are ambiguous.

One run never changes logical role. A role may perform all safe actions within
one causal contract until it reaches a handoff, blocker, explicit wait, or
neutral state.

## Economy

Use one initial observation and one final revalidation. Do not poll CI. After a
mutation, observe CI once; if it is still running, record `CI_RUNNING` and stop.
Use at most one targeted G3 retry per controller run. Do not create presence
comments, repeat evidence, or audit unrelated backlog and history.

## Verification boundary

Verification runs separately from Engineering, reconstructs the exact head from
GitHub, treats Engineering claims as claims to falsify, and never repairs the
product it is reviewing. A single controller provides procedural separation,
not guaranteed model independence; governance, permission, and physical-safety
changes therefore retain stronger review or human gates when required.

## Authority boundary

`webots-ci` is the integration branch. `main` remains forbidden without a
distinct, recent, explicit authorization from Emmanuel. The controller must not
weaken permissions, protections, tests, oracles, acceptance criteria, product
invariants, or physical-safety barriers to obtain progress.
