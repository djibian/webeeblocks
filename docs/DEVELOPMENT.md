# WebeeBlocks development architecture

## Purpose

WebeeBlocks uses a small GitHub-native control plane. A manual Controller session
protects the current integration critical path and uses unavoidable external
waits for useful independent work without creating a second workflow state.

The operational authority is the exact-`develop` `AGENTS.md`. Product objectives
come from `docs/PRODUCT_VISION.md` and GitHub issues. `docs/ROADMAP.md` is a
rolling, derived dependency projection used only to choose useful work.

## Branches and integration lane

| Branch | Purpose | Authority |
| --- | --- | --- |
| `develop` | current integrated product | Controller through reviewed PRs |
| `main` | stable classroom/release line | Emmanuel only |
| short-lived branch | one integration candidate or bounded preparation | Controller under `AGENTS.md` |

`main` and `develop` remain reconcilable. A release is promoted from `develop`
to `main` only with Emmanuel's explicit authorization for that exact operation.

Only one integration PR toward `develop` is active. At most one additional
independent preparatory context may exist. It may contain research, diagnosis or
a preparatory branch, but it cannot become a concurrent integration PR. If
`develop` moves, preparatory code must be reconstructed and revalidated against
the new base before publication.

A reserve PR is not allowed to become a priority inversion. If it was opened
only because higher-priority work was externally blocked and new human/external
evidence makes that higher-priority work executable, the Controller yields the
reserve PR at the next safe checkpoint. It may finish the reserve PR first only
when that is immediate and does not violate independent review or materially
delay the priority path. Otherwise it closes the reserve PR without merge,
retains its branch as the one preparatory context, and revalidates it on the
future `develop` before reopening or publishing it again.

## Unit of delivery

An integration PR delivers the smallest complete vertical product outcome or
other complete governed change, not the smallest code edit. It contains its
acceptance proof and any human boundary. Research that requires no product code
may instead conclude through issue evidence and roadmap reconciliation.

The launch that writes a candidate HEAD never independently reviews or merges
that HEAD. A fresh Reviewer-Integrator falsifies it. Conversely, after a
Reviewer merges an unchanged candidate it did not write, that same launch may
continue as Worker on a different roadmap atom.

## Critical-path scheduling

The Controller optimizes project throughput, not session length.

1. An active priority PR owns the integration lane.
2. If the current launch can safely advance it, that work has priority.
3. If it is waiting only for CI or a human/manual test, the Controller may use
   the wait for one demonstrably independent roadmap atom.
4. If a reserve PR is open and newly settled external evidence makes a
   higher-priority atom executable, the reserve PR yields at a safe checkpoint;
   close it without merge when necessary rather than making the critical path
   wait behind reserve integration.
5. If progress on the priority PR requires a fresh Controller launch, the
   current session stops and requests that relaunch instead of producing
   secondary busywork.
6. Reserve work is preempted only at a safe checkpoint when the priority path
   becomes actionable again.

No explicit queue or scheduler state is stored. The Controller reconstructs the
active PR, exact HEAD, gate, reviews, issue evidence and current roadmap after
material transitions.

## Roadmap

`docs/ROADMAP.md` is deliberately compact and rolling. It records near-term
atoms, dependencies and exit proofs only far enough to choose the next useful
work. New technical evidence may add, remove or rewrite a local dependency.
Completed atoms can be condensed into the baseline; Git history and issues
preserve the evidence.

The roadmap never overrides a newer product decision and does not contain
manual `TODO/READY/BLOCKED/DONE` workflow status.

## CI topology

`.github/workflows/ci.yml` is the single PR entry point and exposes the final
`CI Gate` job. It calls two reusable suites:

- `ci-runtime.yml`: Runtime, Blockly, project-file and Windows contracts;
- `ci-webots.yml`: Webots, Crazyflie and retained legacy regression contracts.

The selector remains conservative: documentation-only changes run policy
checks; isolated Runtime changes run Runtime; controller/world/legacy changes
run Webots and Runtime when shared behavior is affected; workflow/shared/unknown
changes run both suites; scheduled runs and PRs to `main` run both suites.

The final gate fails when selection fails, when a selected suite is skipped,
cancelled or fails, or when its result cannot be interpreted. Branch protection
requires only `CI Gate`.

## Productive waiting

A manual launch is one productive session. Around 60 minutes it reconstructs
state and makes a progress checkpoint; elapsed time alone is not a stop reason.
A pending CI is not a stop reason either.

When no independent work is useful, the session waits and polls moderately,
using recent comparable durations when readily available. When reserve work is
useful, CI is checked at safe reserve checkpoints rather than interrupting that
work tightly.

The Controller stops `BLOCKED` after roughly 30 minutes without material
progress or after the same causal correction cycle repeats twice without new
evidence. Blind reruns are forbidden.

## Human actions and notifications

ntfy is deliberately narrower than GitHub evidence. It alerts Emmanuel only
for two kinds of action:

1. a concrete human/manual or physical **test/evidence step**;
2. a **Controller relaunch** that is the next useful action.

CI, `GO`, merges, roadmap changes, context switches, ordinary comments and
`UNPROVEN` by itself are silent.

`HUMAN_REQUIRED` is reserved for a precise test/manual evidence action and may
be non-terminal: once the handoff is published, the Controller may continue on
one independent atom. Relaunch events use `READY_FOR_REVIEW`, `NO_GO`,
`BLOCKED` or `SESSION_LIMIT` only when the current session truly must stop and a
fresh Controller launch is useful.

The trusted default-branch relay validates the repository owner and exact
current PR HEAD/base or exact `develop` SHA before accessing the ntfy secret.
The handoff is notification transport, never workflow state.

## Repository protections

`develop` requires a PR, `CI Gate`, an up-to-date branch and resolved blocking
conversations. Force-push and branch deletion are disabled.

`main` requires a promotion PR, the full gate and Emmanuel's explicit merge. It
cannot be written or merged by the Controller without exact human authority.

## Operational targets

- one active integration PR and at most one independent preparatory context;
- no priority inversion from a reserve PR after higher-priority external
  evidence settles;
- no extra launch merely because CI or a human test is pending;
- immediate fresh launch when independent review/repair is the critical-path
  requirement;
- no network-caused rerun of a behavioral oracle;
- one required decision check (`CI Gate`);
- full regression nightly and before human promotion;
- no queue, role token, agent fleet or duplicated workflow-state database.

The full gate also builds the Windows classroom ZIP with the official Webots
R2025a toolchain. Runtime-only PRs retain the fast Windows AST/project-file
contract; full runs rebuild the complete offline artifact.
