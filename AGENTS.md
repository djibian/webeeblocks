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

## One controller, two modes

Every launch derives its mode from GitHub. Do not persist a parallel controller state.

| Observed state | Mode and action |
| --- | --- |
| No active controller pull request | **Worker**: select and deliver one bounded increment |
| Active pull request is Draft | **Worker**: continue the same causal contract |
| Ready pull request has missing or failing exact-head evidence | **Worker**: return it to Draft before changing code, then repair |
| Ready pull request is green and has no exact-head verdict | **Reviewer-Integrator**: independently verify it |
| Exact-head `NO_GO` verdict | **Worker**: return to Draft if needed and repair only the reported contradiction |
| Exact-head `GO` verdict | **Reviewer-Integrator**: recheck the head and merge to `webots-ci` in the same launch |
| A human decision is explicitly required | Wait and report the exact decision; do not simulate consent |
| Multiple active controller pull requests or unauthorized `main` activity | Reconcile conservatively before starting new work |

An exact-head verdict must identify the full commit SHA. A verdict for an older head is stale.

## Worker mode

Worker combines product scoping, experiment design and implementation. Its unit of work is one causal contract: one observable problem, one bounded change and one falsifiable acceptance oracle.

1. Read `AGENTS.md`, `docs/PRODUCT_VISION.md`, the active pull request or the smallest actionable product issue, relevant code and current CI evidence.
2. State the objective, causal contract, scope and non-goals in the pull request.
3. When causality is uncertain, run the smallest discriminating experiment before broadening production code.
4. Implement a complete reviewable increment. Prefer causal fixes, reversible changes and the smallest test that would have failed before the fix.
5. Separate product behavior, test harness and instrumentation. Evidence from one layer does not prove another.
6. Run the cheapest relevant checks locally, then push the final intended head once. Do not create no-op commits or use pushes to refresh CI.
7. Keep the pull request Draft while code is changing. Mark it Ready only after the final head is stable and fast checks pass. This transition requests the full CI suite.
8. Stop after publishing the evidence. Review and merge belong to a fresh Reviewer-Integrator launch.

If the causal question changes materially, stop expanding the pull request and create a separate issue. Do not split work merely to satisfy arbitrary size or commit limits.

## Reviewer-Integrator mode

Reviewer-Integrator is read-only with respect to product code. It must not repair the change it reviews.

1. Resolve the exact pull-request head SHA and confirm the base is `webots-ci`.
2. Inspect the complete diff, causal contract, product constraints, tests and all required checks for that exact head.
3. Try to falsify the claim: look for hidden skips, false-positive oracles, weakened guards, proxy evidence presented as product behavior, scope creep and unexplained regressions.
4. Record exactly one exact-head verdict in the pull request:
   - `GO <full_sha>` only when the scoped claim is supported and all required exact-head evidence is green;
   - `NO_GO <full_sha>` with concrete blocking contradictions and the smallest useful repair boundary;
   - `UNPROVEN <full_sha>` when the environment cannot exercise the claim or the evidence is inconclusive.
5. On `NO_GO` or `UNPROVEN`, return the pull request to Draft and stop. Do not modify code.
6. On `GO`, re-read the head immediately. If the SHA and checks are unchanged, merge to `webots-ci` in the same launch, close the completed issue and update the human roadmap. If anything changed, the verdict is stale: do not merge.

## Pull-request evidence contract

Every controller pull request must state:

- objective and linked issue;
- causal contract and observable acceptance oracle;
- scope and non-goals;
- tests and evidence;
- remaining uncertainty;
- final head SHA.

Use these evidence labels consistently: `PROVEN_BY_TEST`, `VERIFIED_BY_CI`, `VERIFIED_BY_PRIMARY_SOURCE`, `VERIFIED_BY_CODE_INSPECTION`, `INFERENCE`, `HYPOTHESIS`, `UNPROVEN`, `REFUTED`, `FALSE_POSITIVE`, `REGRESSION`.

A green job proves only what its oracle exercises. A skipped test is not a pass. Environmental inability may be an explicit skip only when the unsupported claim remains `UNPROVEN`.

## Efficient CI contract

- Draft pushes execute only fast, path-relevant checks; full-suite jobs stay skipped.
- The normal Draft-to-Ready transition runs the full pull-request suite once for the stable head. Opening a pull request directly as Ready is also supported.
- Any code change after Ready requires returning to Draft, then marking Ready again after repair.
- Concurrency cancellation may discard superseded runs; only completed checks for the exact final head count.
- One targeted rerun is allowed for a demonstrably transient infrastructure failure. Repeated or unexplained failure is product evidence, not a rerun strategy.

## Bounded recovery and completion

Never loop on CI, reviews or GitHub state. In one launch, use at most one implementation push, one Ready transition, one targeted transient rerun and one merge attempt. If the work cannot advance safely within those bounds, record the blocker and stop.

Work is complete only when the objective is met, the intended behavior is actually exercised, exact-head CI has no unexplained failure, Reviewer-Integrator recorded `GO`, the same head was merged to `webots-ci`, and remaining uncertainty is explicit.
