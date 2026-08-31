# WebeeBlocks development contract

## Product boundary

Read `docs/PRODUCT_VISION.md` before selecting a new product slice. Preserve the
backend-neutral pipeline:

`activity -> Blockly -> AST -> preflight -> interpreter -> backend`

Never weaken a safety rule or oracle to obtain a green result. Real Crazyflie
flight and release promotion remain human decisions.

## Repository authority

- `develop` is the protected integration branch.
- `main` is the human-controlled stable branch. Never write, merge or promote
  to it without Emmanuel's explicit authorization for that operation.
- Use one short-lived branch and one active pull request toward `develop`.
- GitHub branch, PR, review and check facts are the only workflow state.
- Issues describe product outcomes; they are not queues, locks or role tokens.
- Do not modify the Controller task, this contract or notification workflows
  from a product slice unless the human request is specifically about them.

## One controller, two fresh modes

| Current GitHub state | Mode |
| --- | --- |
| No active PR | **Worker** delivers one vertical product slice |
| Active PR with failing evidence or requested changes | **Worker** repairs that PR |
| Active PR with pending evidence | no Controller launch is useful |
| Active PR exact-head green without a current verdict | **Reviewer-Integrator** |
| Active PR with `GO <head>` | **Reviewer-Integrator** rechecks and merges |
| Human authority or physical evidence required | stop and ask one precise question |

A launch has one mode. The run that writes a head never independently approves
that head.

## Worker

1. Select one user-observable, releasable or otherwise complete vertical slice.
   A standalone CI gate or governance adjustment is not a product slice.
2. Define the linked issue, outcome, acceptance oracle, scope, non-goals and
   human boundary.
3. Diagnose before broadening. Use local or targeted tests before publication.
4. Implement the complete slice on one branch and open one Ready PR to
   `develop`. Keep repairs on that same PR.
5. Inspect the full diff and publish evidence without claiming more than the
   oracle exercises.
6. When `CI Gate` is pending and no same-mode work remains, stop. Do not poll,
   sleep or spend Work waiting.

## Reviewer-Integrator

1. Resolve the full head SHA, base `develop`, complete diff, linked outcome,
   unresolved review threads and the exact `CI Gate` result.
2. Try to falsify the claim: hidden skip, stale result, weak assertion,
   untested platform boundary, scope creep or product regression.
3. Record one verdict for the full SHA:
   - `GO <sha>` when the scoped outcome is proven;
   - `NO_GO <sha>` with the smallest repair boundary;
   - `UNPROVEN <sha>` when the required evidence cannot be obtained.
4. On `GO`, immediately re-read the head and gate, then merge unchanged into
   `develop`. Never merge to `main`.

## CI and evidence

- `CI Gate` is the only required PR check. Its conservative selector runs both
  suites for workflow, shared or unknown changes.
- Runtime-only and Webots/legacy suites may be selected independently.
- The full suite runs on schedule and for promotion PRs to `main`.
- A skipped selected suite is a failure. A genuine unsupported environment is
  `UNPROVEN`, never a pass.
- Network availability must not be an acceptance oracle. Dependencies used by
  tests are pinned and prepared outside the behavioral assertion.
- Use `PROVEN_BY_TEST`, `VERIFIED_BY_CI`, `VERIFIED_BY_CODE_INSPECTION`,
  `UNPROVEN`, `REFUTED`, `FALSE_POSITIVE` and `REGRESSION` when useful.

## Terminal handoff

Repository facts remain authoritative. Do not create a parallel state log.

- CI settlement is transported by the trusted default-branch ntfy workflow.
- Mention `@djibian` only when a human decision or physical action is required.
- A final report states the mode, outcome or reviewed SHA, tests, PR/commit,
  `develop` state, `main` state and the next actionable event.
