# WebeeBlocks development architecture

## Purpose

This document describes the small GitHub-native control plane used to develop
WebeeBlocks through productive manual sessions without maintaining a second
workflow state.

## Branches

| Branch | Purpose | Authority |
| --- | --- | --- |
| `develop` | current integrated product | Controller through reviewed PRs |
| `main` | stable classroom/release line | Emmanuel only |
| `feature/<issue>-<slug>` | one vertical slice | deleted after merge |

Archive tags or `archive/*` references preserve pre-migration and unique
historical heads. They are evidence, not active development branches.

`main` and `develop` must remain reconcilable. A human hotfix on `main` is
merged back into `develop`; a release is promoted from `develop` to `main`.

## Unit of delivery

A pull request delivers the smallest complete vertical outcome, not the
smallest possible code edit. It includes its acceptance oracle and any human or
physical boundary. Several coherent implementation commits are preferable to
several CI-only pull requests for the same outcome.

Only one integration PR is active. Worker and Reviewer-Integrator remain fresh,
separate launches for the same head. Waiting for CI does not split one mode into
several launches.

## CI topology

`.github/workflows/ci.yml` is the single PR entry point and exposes the final
`CI Gate` job. It calls two reusable suites:

- `ci-runtime.yml`: Runtime, Blockly, project-file and Windows contracts;
- `ci-webots.yml`: Webots, Crazyflie and retained legacy regression contracts.

The selector is conservative:

- documentation-only changes run policy checks only;
- isolated Runtime UI/AST changes run the Runtime suite;
- controller/world/legacy changes run the Webots suite and Runtime when the
  shared execution path may be affected;
- workflow, selector, shared or unknown changes run both suites;
- scheduled runs and PRs to `main` run both suites.

The final gate fails when selection fails, when any selected suite is skipped,
cancelled or fails, or when its result cannot be interpreted. Individual jobs
remain visible for diagnosis, but branch protection requires only `CI Gate`.

There is no post-merge duplicate suite on `develop`. A current merge-ref plus
the protected up-to-date requirement is the pre-merge integration proof.

## Productive waiting

A manual Controller launch is a productive session of about 60 minutes. Within
its current mode it waits for `CI Gate`, polls moderately and resumes from the
settled result. It uses recent comparable durations when readily available;
otherwise the first wait is four minutes, followed by checks about every minute.

The trusted workflow on the default branch still observes completion without
checkout or candidate execution and sends one ntfy message containing the PR,
full head, result and link. This is the fallback when no session is active or a
session reaches its limit; it is not workflow state.

Issue comments, Draft/Ready and notification payloads are not controller state.

## Repository protections

`develop` requires a PR, the `CI Gate`, an up-to-date branch and resolved
blocking conversations. Force-push and branch deletion are disabled.

`main` requires a promotion PR, the full gate and Emmanuel's explicit merge.
It cannot be pushed, force-pushed or deleted by the Controller.

If GitHub operations use the same account for human and automation, procedural
human-only authority cannot be distinguished cryptographically. A separate
least-privilege GitHub App is required before granting unattended release
authority; it is not required for the current manual-release model.

## Operational targets

- two launches for a green slice: one continuous Worker, then one fresh
  Reviewer-Integrator;
- no additional launch merely because CI is pending;
- no network-caused rerun of a behavioral oracle;
- one required check and at most one active integration PR;
- two permanent development branches and automatic feature-branch deletion;
- full regression nightly and before human promotion.

The full gate also builds the Windows classroom ZIP with the official Webots
R2025a toolchain. Runtime-only PRs retain the fast Windows AST and project-file
contract; nightly runs and promotions rebuild the complete offline artifact.
