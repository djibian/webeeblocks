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
| Active PR with pending evidence | wait, then reconstruct before selecting or resuming a mode |
| Active PR exact-head green without a current verdict | **Reviewer-Integrator** |
| Active PR with `GO <head>` | **Reviewer-Integrator** rechecks and merges |
| Human authority or physical evidence required | stop and ask one precise question |

A launch may wait, but it has one mode after selection. The launch that writes
a head never independently approves that head.

## Productive session

- Treat a manual launch as one continuous productive session. Around 60
  minutes, perform a progress checkpoint; elapsed time alone is not a reason
  to stop.
- At that checkpoint, reconstruct the exact GitHub state and continue while
  the current mode is making safe, material progress. Material progress
  includes a causal diagnosis, a tested correction, a new head, a settled gate
  analysis, or movement toward the mode's required handoff.
- Stop as `BLOCKED` when about 30 minutes produce no material progress, or
  when the same causal correction cycle repeats twice without new evidence.
  Do not count bounded CI waiting as lack of progress.
- A pending `CI Gate` is not a reason to stop. Wait idly, poll moderately, then
  continue from the result while the current mode can still progress safely.
- When readily available, use up to five recent comparable non-cancelled gate
  durations for the first wait. Use their median, clamped to 2–8 minutes; fall
  back to 4 minutes. After that, check about every 60 seconds, never tightly.
- After each significant transition—push, settled gate, review verdict or
  merge—re-read the PR head, exact gate and relevant GitHub state.
- End only as `COMPLETED`, `READY_FOR_REVIEW`, `HUMAN_REQUIRED`, `BLOCKED` or
  `SESSION_LIMIT`. Reserve `SESSION_LIMIT` for an actual platform/runtime
  limit; never choose it solely because about 60 minutes elapsed. ntfy remains
  the fallback when no session is active.

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
6. After every push, wait for the exact-head `CI Gate`. On failure, identify a
   cause before changing code or retrying; a targeted rerun is acceptable only
   for a demonstrated external transient. Repair the same PR and repeat.
7. When the exact head is green, stop as `READY_FOR_REVIEW`. Do not review,
   approve or merge a candidate written by this launch.

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
5. On `NO_GO` or `UNPROVEN`, stop without repairing the candidate in the same
   launch. After a merge, stop as `COMPLETED`; do not start another slice.

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
- A final report begins with its terminal status and states the mode, outcome
  or reviewed SHA, tests, PR/commit, `develop` state, `main` state and the next
  actionable event.
