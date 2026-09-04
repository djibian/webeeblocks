# WebeeBlocks V4 development architecture

WebeeBlocks uses one healthy trunk and GitHub-native durable coordination.
Controller executions are stateless: 0, 1 or N may run concurrently without
knowing whether another execution exists.

The exact current main AGENTS.md is the operational contract. PRODUCT_VISION,
product issues and ROADMAP provide intent; Git/GitHub provide live workflow state.

## Daily pipeline

isolated short branch -> Draft while mutable -> Ready exact candidate ->
CI Gate + independent review -> main

main is the integrated state proven sufficiently by the automated contract and
independent review to remain a healthy base. It is not a claim that every main
commit has passed physical Windows acceptance.

## Concurrent Controllers

Each execution uses an isolated worktree/checkout. Branches and PRs belong to the
project, never to a Controller. Duplicate investigation or implementation is
acceptable. Before a durable write/review/transition/merge, reread GitHub; if
the useful equivalent action already happened, no-op.

Important knowledge that can alter a future decision must be written to the
relevant issue/PR/review/evidence. Session presence, ownership, handoffs,
heartbeats, relaunch state and agent pools do not exist.

## Draft / Ready

- Draft means the change may still be mutated.
- Ready means the exact HEAD is frozen for decision CI/review.
- Mutating a Ready PR requires returning it to Draft first.
- Every new HEAD requires a fresh decision CI and fresh independent review.
- An execution that mutates a PR cannot independently review that PR during the
  same execution.
- A Reviewer may record NO_GO, return the PR to Draft and repair it in the same
  execution; another execution supplies the next independent review.

## Healthy trunk

Small valid candidates converge rapidly toward main. Branch protection is
expected to require a PR, CI Gate and an up-to-date candidate.

If main is known unsuitable as a development base, ordinary merges pause until
health is restored. Other independent machine work may continue. A late
refutation of an already merged SHA is diagnosed against current main before a
fix-forward or narrow revert.

## CI topology

.github/workflows/ci.yml is the sole PR CI entry point and targets main. It
exposes CI Gate and invokes ci-runtime.yml and ci-webots.yml.

Daily PR selection remains conservative and path-scoped. Workflow/shared/unknown
changes force both suites. Scheduled/manual CI is full. A normal PR to main is
not automatically a release/promotion run.

There is no Candidate Evidence workflow. Deterministic evidence required to
integrate a PR belongs in CI Gate.

## Real-world checkpoint pipeline

Controllers never notify ntfy directly. A legitimate need is materialized by a
canonical request on a relevant GitHub issue/PR:

CHECKPOINT_REQUEST <40-char-sha> <test-profile> <checkpoint|release>
<actionable test instructions>

The trusted human-checkpoint workflow validates the target/request, runs full
Runtime + Webots evidence, requires the relevant built artifact, records
provenance/digest, serializes the publication step, refuses a second open human
test, then creates one durable [TEST_REQUIRED] issue and sends ntfy.

There is no human-test queue. Other needs remain silent in their original GitHub
context until the open request resolves. TEST_REQUIRED resolves as PASS, FAIL or
strictly NOT_NEEDED.

## Notifications

The only notification class is TEST_REQUIRED. CI, review, GO/NO_GO, Draft/Ready,
merges, Controller startup/termination/blocking and relaunch are silent.

## Repository protections

V4 requires main protected by PR + required CI Gate + up-to-date candidate, with
destructive force-push/deletion disabled. These administration settings are
outside Git and must be restored explicitly in a rollback.

A future merge queue is optional only if integration contention becomes real.
