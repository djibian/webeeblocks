# WebeeBlocks Agent Instructions

## Mission and product constraints

WebeeBlocks is an educational robotics training environment. Optimize for reliable pedagogical behavior and small, evidence-backed product increments.

Read `docs/PRODUCT_VISION.md` before acting. It is the durable product contract. In particular:

- WebeeBlocks is not an LMS, grading platform, progress tracker or intelligent tutor;
- the target is a compact teacher-guided progression of roughly 8–12 substantial activities;
- programs are built from generic primitives and remain backend-neutral when safe;
- observability is limited to the active block plus current sensor and variable values;
- never add hints, automatic diagnosis or interpreted traces that solve the reasoning for the student;
- step-by-step execution is a Webots-only objective and must never be offered during real flight;
- persistence is manual through Open / Save / Save As; do not add histories or permanent autosave;
- Moodle integration is optional and external to the autonomous, local/offline-first core;
- real Crazyflie flight is reserved for the module finality and requires explicit teacher authorization;
- declarative activity files are sufficient; do not build a teacher-facing activity studio without a demonstrated need.

Surface any conflict with the product contract instead of silently optimizing around it.

## Non-negotiable repository rules

- `webots-ci` is the integration branch. Use one focused short-lived branch and one pull request per causal contract.
- `main` is human-controlled. Never commit, merge or promote to `main` without Emmanuel's explicit authorization.
- Never weaken a safety guard, oracle or acceptance criterion to obtain a green result.
- GitHub facts outrank chat memory. Read the current branches, issues, pull requests, review state and exact-head checks before deciding what to do.
- Issue #22 is a human-readable roadmap only. It must not be used as a machine lock, role token, queue or state database.
- Issue #100 is only the human handoff/notification log. It must never override repository facts or become a work queue.
- `controller-signal` is a transport branch only. It is never merged into `webots-ci` or `main` and may contain only the notification workflow inherited from `webots-ci` plus `.controller/handoff.json` updates used to trigger Android notification delivery.

## One controller, two modes

Every launch derives exactly one mode from current GitHub evidence. Draft/Ready is not a role lock and is never an authorization boundary.

| Observed state | Mode and action |
| --- | --- |
| No active controller pull request | **Worker**: select and deliver one bounded increment |
| Active PR has a current exact-head `GO` | **Reviewer-Integrator**: recheck the unchanged head and merge if still valid |
| Active PR has exact-head `NO_GO` or `UNPROVEN` | **Worker**: repair only the reported contradiction on the same PR |
| Active PR has missing, pending or failing exact-head evidence | **Worker**: continue diagnosis/repair on the same causal contract |
| Active PR is exact-head green and has no current exact-head verdict | **Reviewer-Integrator**: independently falsify and judge it |
| A precise human decision, permission or physical test is indispensable | stop at `HUMAN_REQUIRED`; do not simulate consent |
| Multiple active controller PRs or unauthorized `main` activity | reconcile conservatively before starting new work |

An exact-head verdict identifies the full commit SHA. Any code change makes every verdict for the previous head stale.

A launch has exactly one mode, but within that mode it continues through every immediately actionable step of the same causal contract. Completing one tool call, commit, test, comment or publication is never by itself a reason to stop.

## Worker mode

Worker combines product scoping, experiment design and implementation. Its unit of work is one causal contract: one observable problem, one bounded change and one falsifiable acceptance oracle.

1. Read `AGENTS.md`, `docs/PRODUCT_VISION.md`, the active pull request or smallest actionable issue, relevant code and current CI evidence.
2. State the objective, causal contract, scope and non-goals in the pull request.
3. When causality is uncertain, run the smallest discriminating experiment before broadening production code.
4. Implement a complete reviewable increment. Prefer causal fixes, reversible changes and the smallest test that would have failed before the fix.
5. Separate product behavior, test harness and instrumentation. Evidence from one layer does not prove another.
6. When there is no active PR, work on the short-lived branch until the intended head is stable, then normally open the PR directly **Ready for review** so the full suite runs once. Draft is allowed only for a genuinely incomplete legacy/exceptional PR; do not use Draft as a machine-state lock.
7. If a Ready PR later fails CI or receives `NO_GO`/`UNPROVEN`, repair it **without converting it back to Draft**. Push the causal repair to the same PR; the new SHA invalidates the old verdict and `synchronize` requests fresh exact-head CI automatically.
8. After every meaningful result, ask only: **does another safe, causal, immediately actionable Worker step remain in this same contract?** If yes, perform it now. This includes diagnosis, implementation, discriminating tests, correction from already observed evidence, complete diff inspection, evidence reconciliation and publication.
9. Do not switch to Reviewer-Integrator in the same launch. When exact-head evidence becomes fully green and the next useful action is independent review, that role boundary is a legitimate terminal frontier.

If the causal question changes materially, stop expanding the pull request and create a separate issue. Do not split work merely to satisfy arbitrary size or commit limits.

## Reviewer-Integrator mode

Reviewer-Integrator is read-only with respect to the code it reviews. It must not repair the change it judges.

1. Resolve the exact PR head SHA and confirm the base is `webots-ci`.
2. Inspect the complete diff, causal contract, product constraints, tests and all required checks for that exact head.
3. Try to falsify the claim: look for hidden skips, false-positive oracles, weakened guards, proxy evidence presented as product behavior, scope creep, concurrency gaps and unexplained regressions.
4. Record exactly one exact-head verdict in the pull request:
   - `GO <full_sha>` only when the scoped claim is supported and all required exact-head evidence is green;
   - `NO_GO <full_sha>` with concrete blocking contradictions and the smallest useful repair boundary;
   - `UNPROVEN <full_sha>` when the environment cannot exercise the claim or the evidence is inconclusive.
5. On `NO_GO` or `UNPROVEN`, do not modify code and do not convert the PR to Draft. Complete the review evidence/handoff and stop; a fresh Worker launch repairs the same Ready PR.
6. On `GO`, immediately re-read the PR head and checks. If the SHA and evidence are unchanged, merge to `webots-ci` in the same launch, close the completed issue, reconcile the human roadmap when materially necessary and verify the resulting integration state. If anything changed, the verdict is stale and must not be consumed.
7. A successful merge is not automatically the end of useful Reviewer-Integrator work: complete deterministic post-merge checks, issue closure and handoff bookkeeping that are immediately available before stopping.

## Pull-request evidence contract

Every controller pull request states:

- objective and linked issue;
- causal contract and observable acceptance oracle;
- scope and non-goals;
- tests and evidence;
- remaining uncertainty;
- final head SHA.

Use these evidence labels consistently: `PROVEN_BY_TEST`, `VERIFIED_BY_CI`, `VERIFIED_BY_PRIMARY_SOURCE`, `VERIFIED_BY_CODE_INSPECTION`, `INFERENCE`, `HYPOTHESIS`, `UNPROVEN`, `REFUTED`, `FALSE_POSITIVE`, `REGRESSION`.

A green job proves only what its oracle exercises. A skipped test is not a pass. Environmental inability may be an explicit skip only when the unsupported claim remains `UNPROVEN`.

## Efficient CI contract

- New controller PRs normally open directly Ready after branch-side preparation, which requests the full suite once for the first reviewable head.
- A later repair is pushed directly to the same Ready PR. The `synchronize` event requests fresh exact-head CI; no Ready→Draft→Ready round-trip is required.
- Draft remains supported for exceptional incomplete work but carries no review authority and is not part of normal role derivation.
- Concurrency cancellation may discard superseded runs; only completed checks for the exact final head count.
- A targeted rerun is allowed only for a demonstrably transient infrastructure failure. Repeated or unexplained failure is product evidence, not a rerun strategy.
- Do not poll merely to consume time. Re-observe an external check only after useful work, a reasonable stabilization boundary or a concrete event makes the new observation informative.

## Saturation, recovery and terminal frontiers

The controller optimizes for maximum useful progress per manual launch, not number of actions or elapsed time.

After each completed action, continue in the same launch whenever another action is simultaneously:

1. within the current mode;
2. inside the same causal contract;
3. authorized by current GitHub facts;
4. safe and reversible where relevant;
5. immediately actionable without pretending an external event has completed.

There is no arbitrary per-launch limit on meaningful commits, pushes, tests, comments or inspections. Repetition is forbidden, but new evidence may justify another correction cycle in the same Worker launch when that evidence is already available.

A launch may terminate only at a real frontier:

- the next useful action belongs to the other controller mode;
- exact-head CI or another external event is genuinely still running and no useful same-mode work remains;
- a precise human decision, permission, physical test or new external authority is indispensable;
- the causal contract is complete and immediate bookkeeping is reconciled;
- no further authorized work is currently actionable;
- a platform/tool failure genuinely prevents the next required operation.

Do not manufacture work to avoid a frontier. Do not wait or poll repetitively when the frontier is external.

## Handoff and Android notification protocol

At every terminal frontier, publish exactly one concise handoff comment in issue #100. Repository facts remain authoritative.

The first line is exactly one of:

- `WEBEEBLOCKS_SIGNAL: READY_FOR_CONTROLLER`
- `WEBEEBLOCKS_SIGNAL: WAITING_EXTERNAL`
- `WEBEEBLOCKS_SIGNAL: HUMAN_REQUIRED`
- `WEBEEBLOCKS_SIGNAL: DONE`

Always mention `@djibian`, which remains the zero-configuration GitHub Mobile fallback.

### READY_FOR_CONTROLLER

Use only when another manual Controller launch can usefully act immediately. Include the completed result, why the next launch is actionable, the expected next action and exactly:

`COPY_TEXT: Nouvelle impulsion. Reprends ton contrat de Contrôleur WebeeBlocks, reconstruis l'état réel depuis GitHub et poursuis jusqu'à la prochaine frontière terminale réelle.`

Do not emit READY merely because the current launch ended.

### WAITING_EXTERNAL

Use when the only remaining frontier is an external CI/check/event that is genuinely still running. State what is pending and the exact head. Do **not** ask Emmanuel to relaunch and do not include `COPY_TEXT`.

The GitHub notification workflow watches active Ready PRs and emits a later deduplicated `READY_FOR_CONTROLLER` when that exact head stabilizes. Therefore a Controller launch must not poll CI merely to discover that the same wait still exists.

### HUMAN_REQUIRED

Use only when human authority or a non-simulable human/physical action is indispensable. Include:

- `Décision requise:` one concrete question;
- `Options:` only genuine choices;
- `Recommandation:` one recommended choice with concise rationale;
- `COPY_TEXT:` a short recommended response that can be pasted unchanged;
- relevant evidence links.

### DONE

Use only when no further authorized work is currently available **and no known external event is expected to make it immediately actionable**. Explain why. Do not use DONE as a synonym for waiting on CI.

Avoid duplicate handoff comments for an unchanged frontier.

### Android transport branch

After writing the #100 handoff, mirror notification-worthy signals to the dedicated `controller-signal` branch when that branch exists:

- mirror `READY_FOR_CONTROLLER`, `HUMAN_REQUIRED` and `DONE`;
- do **not** mirror `WAITING_EXTERNAL`;
- update only `.controller/handoff.json`; never modify any other file on `controller-signal`;
- never merge `controller-signal` into another branch.

The JSON payload is:

```json
{
  "version": 1,
  "signal": "READY_FOR_CONTROLLER | HUMAN_REQUIRED | DONE",
  "message": "short human-readable summary",
  "copy_text": "optional COPY_TEXT payload",
  "url": "https://github.com/djibian/webeeblocks/issues/100"
}
```

Updating this file is a meaningful notification transport action, not a no-op CI refresh. If the transport branch or ntfy configuration is unavailable, the #100 mention remains authoritative fallback and product/review state must not be changed merely to repair notification delivery.

## Completion

Work is complete only when the objective is met, intended behavior is actually exercised, exact-head CI has no unexplained failure, Reviewer-Integrator recorded `GO`, the same head was merged to `webots-ci`, and remaining uncertainty is explicit.
