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

Durability does not imply trust. Decision facts are authoritative only when their
provenance satisfies the V4 trust contract: `CI Gate` must be identified through
the canonical workflow/run/attempt below, not just a context name or App;
Controller GO/NO_GO/UNPROVEN and human PASS/FAIL/NOT_NEEDED
must come from repository owner `djibian` and bind the exact applicable SHA or
request. External comments/reviews are evidence to inspect, not decision authority.

Resolve main before decisions. Complete immutable contract/vision/roadmap content
already available in the same execution may be reused only when its Git blob is
identical at newly resolved main. Reconstruct relevant mutable PRs, reviews,
checks, refs, issues and protections. Lost context requires a fresh read; a local
recollection is not proof of object identity.

## Draft / Ready

- Draft means the change may still be mutated.
- Ready offers the exact HEAD as stable for decision CI/review; it is not a lock.
- Draft runs may perform policy checks, but only a Ready candidate may publish
  the required `CI Gate` check context.
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

`check_ci_gate.py` requires explicit string selections `"true"`/`"false"` for
both suites and observed results for `select`, `runtime` and `webots`. A selected
suite must succeed; an unselected suite must be skipped. Missing/malformed or
duplicate JSON input fails the gate. Documentation-only selection remains valid.
The topology contract inventories both `.yml` and `.yaml` workflow files.

### Authority changes

Evaluate a candidate under AGENTS.md on current main, including when the PR
proposes changing that file. Review workflow additions/deletions/renames, local
actions, selectors, gates and contract tests against the existing obligations.
Also inspect changed assertions, configuration and dependencies used by the CI;
the named paths in AGENTS.md are review triggers, not a complete dependency list.

A technical repair or new test preserving those obligations may use the normal
independent review. That review examines the counterexample and a healthy control;
the candidate's own green CI alone cannot justify changing its oracle. Changing
obligations, trust, permissions or human boundaries requires the applicable
governance authorization, which an explicit owner request may already supply.
Ordinary product PRs and technical test extensions need no additional human
decision or second review. These are Controller obligations, not server access
controls against an actor that ignores the contract.

### Identify decision CI

Use native GitHub reads, not a new check or stored eligibility record:

1. Read PR N and exact HEAD H. List runs for H and `event=pull_request`, following
   pagination as needed to establish the complete relevant set. Identify the
   approved `.github/workflows/ci.yml` workflow in this repository by workflow ID
   and path, and establish its association with N and H. Do not trust a job's
   freely chosen name as workflow identity. An installation's workflow ID is
   repository-specific; it must not be copied to a new repository.
2. Among those runs, choose the greatest `run_number`, then server ID if tied,
   before filtering on conclusion. Read that run R and current `run_attempt` A.
   Require `status=completed` and `conclusion=success`.
3. Read the jobs of R's effective current attempt and require its final `CI Gate`
   job to have succeeded. `CI Gate (Draft)` is insufficient. Recheck R if these
   reads may have crossed a rerun; a changed attempt requires reconstruction.
   Partial reruns may inherit jobs: do not invent their provenance or require a
   full rerun when native evidence already establishes the effective result.

The REST surfaces are `GET pulls/N`, `GET actions/runs?head_sha=H&event=pull_request`,
`GET actions/runs/R` and `GET actions/runs/R/attempts/A/jobs`, under
`/repos/djibian/webeeblocks`. A newer pending/failed/cancelled run cannot be replaced
with an older success. Missing association, pagination or attempt evidence means
UNKNOWN, not permission to fall back to a homonymous green check. Read metadata
for a healthy run; logs are for diagnosis. No historical negative run poisons H.

## Real-world checkpoint pipeline

Controllers never notify ntfy directly. A legitimate need is materialized by a
canonical request on a relevant GitHub issue/PR:

CHECKPOINT_REQUEST <40-char-sha> <test-profile> <checkpoint|release>
<actionable test instructions>

The trusted human-checkpoint workflow validates the target/request, runs full
Runtime + Webots evidence, requires the relevant built artifact, records
provenance/digest, serializes the publication step, refuses a second open human
test, then creates one durable [TEST_REQUIRED] issue and sends ntfy.

The enabled profiles are `windows-low-end`, backed by the
`WebeeBlocks-Windows-R2025a` artifact, and `s3-props-off`, backed by
`experimental-s3-surface-offset-2026-08` and restricted to purpose `checkpoint`.
Unknown profiles fail closed until their deterministic preparation is explicitly
implemented. A props-off checkpoint never authorizes motorized flight.

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
