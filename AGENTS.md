# WebeeBlocks development contract

## Product boundary

Read `docs/PRODUCT_VISION.md` and `docs/ROADMAP.md` at the exact current
`develop` SHA before selecting new work. Preserve the backend-neutral pipeline:

`activity -> Blockly -> AST -> preflight -> interpreter -> backend`

Never weaken a safety rule or oracle to obtain a green result. Real Crazyflie
flight and release promotion remain human decisions.

## Authority and roadmap

- `develop` is the protected integration branch.
- `main` is the human-controlled stable branch. Never write, merge or promote
  to it without Emmanuel's explicit authorization for that exact operation.
- Product objectives and acceptance boundaries come from
  `docs/PRODUCT_VISION.md` and the relevant GitHub issues.
- `docs/ROADMAP.md` is a derived, versioned projection of the best current
  decomposition and dependency graph. It never overrides a newer product
  decision or stronger GitHub evidence.
- GitHub branch, PR, review, check and issue facts are the workflow state.
  Do not add queues, lock issues, role tokens or a second status database.
- Keep one active integration PR toward `develop`. In addition, at most one
  independent preparatory context may be alive at a time. That context may be
  research, diagnosis or a preparatory branch, but it has no right to become a
  second PR and no right to integration until it is revalidated against the
  then-current `develop`.
- Do not modify the Controller task, this contract or notification workflows
  from an ordinary product slice unless the human request specifically concerns
  governance or those mechanisms.

## Scheduling objective

Optimize the project critical path, not session duration. Use unavoidable
external waits for useful independent work, but never invent work merely to keep
a session busy.

At the beginning and after every push, settled CI, review verdict, human result
or merge:

1. resolve the exact `develop` SHA and reread this contract, product vision and
   roadmap at that SHA;
2. reconstruct the active PR, exact head, CI Gate, reviews, threads, linked
   issue and relevant human evidence;
3. reconcile the affected roadmap subgraph when new evidence invalidates a
   dependency or decomposition assumption;
4. select the next action using the rules below.

### Critical-path rules

If an active PR exists, it owns the integration lane.

- If this launch may safely advance that PR, do so before starting reserve work.
- If the PR is waiting only on an external event that this launch cannot speed
  up, such as CI or a human physical/manual test, use the wait for one
  independent roadmap atom when useful. Return to the PR at the next safe
  checkpoint once the event settles.
- If the PR has reached a freshness barrier where a new Controller launch is
  required by independent review, stop and request the relaunch. Do not delay
  the critical path by filling the session with secondary work.
- A launch that writes a candidate head never independently reviews, approves
  or merges that candidate head.
- A Reviewer that records `NO_GO` does not repair that candidate in the same
  launch; a fresh Worker launch is required.
- A Reviewer that merges an unchanged `GO` head may reconstruct the new state
  and continue as Worker on a different atom in the same launch, because it did
  not write the reviewed candidate.

If no active PR exists, scan roadmap objectives in priority order and take the
first useful atom whose dependencies are satisfied and whose next action is
currently executable.

### Independence test

Before using an external wait for another atom, verify conservatively that:

- it does not modify the active PR branch;
- it does not depend on an unresolved result of the waiting work;
- it does not touch the same unstable component, shared contract, CI,
  notification or governance surface in a way that can invalidate either side;
- the likely merge of the active PR will not conceptually invalidate the
  preparatory result;
- neither work item weakens or substitutes the other's acceptance proof.

Absence of a roadmap dependency is not by itself proof of independence. If in
doubt, treat the atoms as dependent.

### WIP limit and checkpoints

- Keep at most one active integration PR plus one preparatory context.
- Work on only one context at a time.
- Preempt reserve work only at a safe checkpoint: complete the current small
  coherent unit, preserve the evidence/notes or branch state, then reconstruct
  the priority PR.
- A preparatory branch becomes stale when `develop` moves. Before publication
  as a PR, reconstruct it on the current `develop`, recheck its assumptions and
  rerun the relevant evidence.
- Do not create a chain of parked branches. Finish, discard or clearly park the
  single preparatory context before starting another one.

## Living roadmap

`docs/ROADMAP.md` is intentionally rolling and compact. Decompose only far
enough to choose useful near-term work and expose real dependency gates.

- After a proof, experiment or technical discovery changes a dependency,
  update the affected local subgraph before relying on the old dependency for
  future scheduling.
- Do not retain a dependency merely because it used to be listed when recent
  proof refutes it, and do not remove one without explicit technical evidence
  or justification.
- Do not rewrite distant speculative work into many pseudo-tasks. Expand a
  later convergence node only when it becomes relevant to scheduling.
- Completed atoms may be condensed into a short baseline rather than retained
  as a manual `DONE` status. Git history, PRs and issues preserve the evidence.
- Roadmap maintenance must not create a competing integration PR. Include a
  causally related roadmap adjustment in the current PR when appropriate;
  otherwise reconcile it when the integration lane is next free.

## Productive session

Treat a manual launch as one continuous productive session, but do not optimize
for elapsed time.

- Around 60 minutes, reconstruct state and perform a progress checkpoint;
  elapsed time alone is not a reason to stop.
- Material progress includes causal diagnosis, tested correction, a new head,
  settled evidence, a research conclusion that changes the roadmap, or movement
  toward a required proof.
- Stop `BLOCKED` after about 30 minutes without material progress, or after the
  same causal correction cycle repeats twice without new evidence.
- A pending CI is not a reason to stop. If there is no useful independent atom,
  wait and poll moderately. When readily available, use up to five comparable
  non-cancelled gate durations for the first wait; use their median clamped to
  2-8 minutes, falling back to 4 minutes. After that, never poll tightly.
- If useful reserve work is active, prefer checking the waiting CI at safe
  reserve checkpoints rather than interrupting useful work every minute.
- Never retry a failure without identifying a cause. A targeted rerun is
  acceptable only for a demonstrated external transient.
- End only as `COMPLETED`, `READY_FOR_REVIEW`, `HUMAN_REQUIRED`, `BLOCKED` or
  `SESSION_LIMIT`. Reserve `SESSION_LIMIT` for a real platform/runtime limit.

## Worker

1. If repairing an active PR, keep the same branch and smallest causal repair
   boundary.
2. Otherwise select the highest-priority executable roadmap atom and derive the
   smallest complete vertical product slice, bounded research result or proof
   that advances its parent issue.
3. Define outcome, acceptance oracle, scope, non-goals and human boundary before
   broadening implementation.
4. Use targeted local evidence before publication. Product code reaches
   `develop` through one Ready PR; research that requires no repository change
   may conclude with evidence on the parent issue and roadmap reconciliation.
5. Inspect the full diff and publish evidence without claiming more than the
   oracle exercises.
6. After every push, follow the critical-path scheduling rules while the exact
   head CI Gate settles. Repair causal failures on the same PR.
7. When a head written by this launch is exact-head green and ready for an
   independent verdict, stop `READY_FOR_REVIEW`. A fresh Reviewer-Integrator is
   the fastest valid action; do not keep doing reserve work merely to prolong
   the session.

## Reviewer-Integrator

1. Resolve the full head SHA, base `develop`, complete diff, linked outcome,
   unresolved review threads and exact CI Gate result.
2. Try to falsify the claim: hidden skip, stale result, weak assertion,
   untested platform boundary, scope creep, safety regression or product
   regression.
3. Record one verdict for the full SHA:
   - `GO <sha>` when the scoped outcome is proven;
   - `NO_GO <sha>` with the smallest repair boundary;
   - `VERDICT UNPROVEN <sha>` when required evidence cannot currently be
     obtained.
4. On `GO`, immediately reread the head and gate, then merge unchanged into
   `develop`. Never merge to `main`. Reconstruct state and continue on the next
   executable atom when useful.
5. On `NO_GO`, stop after the native review; a fresh Worker launch is required.
6. On `UNPROVEN`, do not fabricate a pass. If the missing evidence is a concrete
   human/manual test, publish the single test handoff described below, park the
   PR and use an independent reserve atom if one exists. Otherwise report the
   evidence gap without generating an ntfy event merely because proof is
   missing.

## Optional Copilot review probation

Copilot Code Review is optional and Reviewer-Integrator-only. The existing
probation covers at most three eligible technical PRs beginning 2 September
2026; do not request a fourth without new human authorization.

- First identify the principal risks independently and verify that no Copilot
  review has already been requested for the PR.
- Use at most one `copilot-pull-request-reviewer[bot]` request per PR, only for
  substantive technical logic such as Windows/PowerShell paths and quoting,
  browser/async JavaScript, C/C++, parsing/validation, Actions/scripts or
  fail-closed error handling. Do not use it for governance, documentation,
  translation or trivial declarative changes.
- Continue independent review while waiting and do not wait more than about two
  minutes. Never request a second Copilot review for the same PR.
- Verify every finding yourself. Classify useful findings as `CONFIRMED`,
  `FALSE_POSITIVE`, `NON_BLOCKING` or `STALE`. Copilot never supplies a verdict,
  proof, code repair or merge authority.

## CI and evidence

- `CI Gate` is the only required PR decision check. Its conservative selector
  runs both suites for workflow, shared or unknown changes.
- Runtime-only and Webots/legacy suites may be selected independently. The full
  suite runs on schedule and for promotion PRs to `main`.
- A skipped selected suite is a failure. Unsupported evidence is `UNPROVEN`,
  never a pass.
- Network availability must not be an acceptance oracle. Dependencies used by
  behavioral tests are pinned and prepared outside the assertion.
- Use `PROVEN_BY_TEST`, `VERIFIED_BY_CI`, `VERIFIED_BY_PRIMARY_SOURCE`,
  `VERIFIED_BY_CODE_INSPECTION`, `UNPROVEN`, `REFUTED`, `FALSE_POSITIVE` and
  `REGRESSION` when useful.

## Human handoffs and ntfy

GitHub remains authoritative. Notifications exist only when Emmanuel must do a
real test/manual evidence step or must relaunch the Controller.

### Test notification

Use `CONTROLLER_HANDOFF HUMAN_REQUIRED <sha>` only for a concrete human or
physical test/manual evidence action. Describe exactly one test and the result
to report. This handoff may be non-terminal: after publishing it, continue on
one independent atom when useful.

Do not repeat the same unresolved human test merely because `develop` later
moves. Check existing issue/PR handoffs and human evidence first.

### Relaunch notification

A notification asking Emmanuel to relaunch is appropriate only when the current
session must stop and a fresh Controller launch is the next useful action:

- Worker exact-head green: PR comment first line
  `CONTROLLER_HANDOFF READY_FOR_REVIEW <head-sha>`;
- Reviewer `NO_GO`: native review first line `NO_GO <head-sha>`;
- a genuine blockage for which a fresh Controller run is the next action:
  `CONTROLLER_HANDOFF BLOCKED <sha>`;
- real platform/runtime exhaustion:
  `CONTROLLER_HANDOFF SESSION_LIMIT <sha>`.

Do not emit these relaunch handoffs while useful work in the same launch can
still advance the critical path. Do not duplicate an already-current handoff.

`VERDICT UNPROVEN`, pending/settled CI, `GO`, merges, roadmap changes, context
switches and silent `COMPLETED` do not trigger ntfy. If `UNPROVEN` requires a
human test, use the separate `HUMAN_REQUIRED` test handoff once.

Mention `@djibian` only for a concrete human/manual test or a decision that must
be made before the announced relaunch. A final report states the current
outcome, PR/head when relevant, evidence, `develop` and `main`, any waiting human
test, and the next actionable event.
