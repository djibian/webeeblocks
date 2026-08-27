# WebeeBlocks Agent Instructions

## Mission

WebeeBlocks is an educational robotics project. Its priority is reliable pedagogical behavior and incremental product progress supported by evidence.

## Product vision

The validated product direction is documented in `docs/PRODUCT_VISION.md`. Treat it as a durable product constraint, not as optional background.

In particular:
- WebeeBlocks is a focused **training environment**, not an LMS, tracking platform, grading system or intelligent tutor;
- target a compact guided progression of roughly **8–12 substantial activities**;
- progression is teacher-guided, but WebeeBlocks itself does not need student accounts or per-student unlock/progress state;
- activities must support pedagogical progression rather than only changing scenery;
- the student solution is built from generic primitives; the activity defines the problem, constraints, success/failure, optional timing/score and available capabilities;
- student execution observability is limited to the active block plus current sensor and variable values;
- do **not** add hints, strategy suggestions, automatic mistake diagnosis, interpreted decision traces or other assistance that solves the reasoning for the student;
- a simple step-by-step debug mode is a product objective **for Webots simulation only**;
- do not add sophisticated developer-debugger features (user breakpoints, watch expressions, call stacks, etc.) without a new explicit pedagogical requirement;
- step-by-step/debug execution must **never** be offered during real Crazyflie flight;
- the student Blockly program should remain backend-neutral and transferable from simulation to real hardware when safe and supported;
- student project persistence is **manual** through clear Open / Save / Save As actions; do not add permanent autosave, attempt history, success/failure history, score history or student progress tracking without a new explicit requirement;
- use Blockly native Undo/Redo if adequate; do not build bespoke version history by default;
- Moodle may distribute resources or receive a submitted project file, but core WebeeBlocks remains autonomous/local/offline-first;
- real Crazyflie flight is reserved for the final activity/finality of the module and requires explicit teacher authorization; assume one physical drone and no software flight-request queue;
- WebeeBlocks does not need an integrated assessment subsystem. A saved project file may be submitted and evaluated externally when required;
- do not build a teacher-facing graphical activity studio unless a separate demonstrated need appears; declarative activity files are sufficient for the current owner-assisted authoring workflow.

When a technical choice conflicts with `docs/PRODUCT_VISION.md`, surface the contradiction to Lead rather than silently optimizing for implementation convenience.

## Repository governance

`main` is not a development target. Do not commit directly to `main` or promote work there without Emmanuel's explicit authorization.

`webots-ci` is the integration branch for the current Webots R2025a migration and Crazyflie work. Use short-lived branches and focused pull requests.

## GitHub is the shared project memory

Do not rely on chat history as authoritative project state. Before starting work, read:

1. this `AGENTS.md`;
2. `docs/PRODUCT_VISION.md`;
3. `[Lead] WebeeBlocks state & priorities`;
4. the assigned issue;
5. relevant Lab and Verification evidence;
6. related pull requests and current CI evidence.

Write important conclusions, contradictions, decisions, evidence and remaining uncertainty back to GitHub.

## Evidence vocabulary

Use these terms consistently:

- `PROVEN_BY_TEST`
- `VERIFIED_BY_CI`
- `VERIFIED_BY_PRIMARY_SOURCE`
- `VERIFIED_BY_CODE_INSPECTION`
- `INFERENCE`
- `HYPOTHESIS`
- `UNPROVEN`
- `REFUTED`
- `FALSE_POSITIVE`
- `REGRESSION`

A green CI result proves only what its oracle actually exercises. A skipped test is not a pass. A synthetic marker is not proof of physical or user-visible behavior unless the claim is specifically about that marker.

## Roles

Use the smallest trustworthy process for the current question.

### Lead

The Lead owns the problem, scope and current causal bottleneck, not implementation details.

- keep one causal bottleneck active;
- define what must be demonstrated before authorizing implementation;
- prevent scope creep while the causal question is unresolved;
- arbitrate contradictions between evidence and implementation;
- split work when a genuinely new causal question appears.

### Lab / Experimenter

Use Lab only when behavior, causality or the right measurement is uncertain.

- optimize for information gain rather than production completeness;
- design the smallest discriminating experiment;
- measure before tuning or redesigning;
- distinguish observation from inference and hypothesis;
- do not broaden product architecture while the causal question is unresolved.

### Engineering / Builder

Engineering is responsible for implementing the authorized increment.

- implement only the scoped objective;
- prefer causal fixes over workarounds;
- prefer small reversible changes;
- add the smallest useful test that would have failed before the fix;
- do not weaken an oracle, safety guard or acceptance criterion to obtain green CI;
- do not silently invent new architecture when evidence contradicts the current design.

### Verification

Verification tries to falsify the claimed result rather than finish the implementation.

- verify that tests exercise the stated property;
- distinguish product behavior from harness and instrumentation behavior;
- look for false-positive oracles, hidden skips and non-causal fixes;
- challenge claims that exceed the produced evidence;
- record blocking contradictions explicitly.

Whenever practical, Verification should be performed by an agent or model different from the one that implemented the change.

## Default flow

For a well-understood product increment:

`Lead -> Engineering -> CI -> Verification`

When the causal question is unresolved:

`Lead -> Lab -> Engineering -> CI -> Verification`

Additional adversarial or specialist review may be added when the cost of a false conclusion justifies it, but roles must add information rather than ceremony.

## Causal discipline

Work on one causal bottleneck at a time.

Before modifying behavior, collect the smallest evidence capable of distinguishing the plausible causes. Prefer an observed state from the real system over an indirect or synthetic proxy when practical.

Do not tune parameters, add delays or expand architecture merely because a gate is red. First determine what the failing gate actually demonstrates.

## Product, harness and instrumentation

Keep these three layers conceptually separate:

1. **product behavior** — what WebeeBlocks/Webots/Blockly/Crazyflie actually does;
2. **test harness** — how the behavior is exercised and asserted;
3. **instrumentation** — diagnostics added only to make internal state observable.

Evidence from one layer must not be silently presented as evidence from another.

Instrumentation should not change the product behavior being measured. Diagnostic changes must remain distinguishable from behavioral fixes.

## Pull requests and scope

Each substantial pull request should state:

- issue or objective;
- scope;
- non-goals;
- tests and evidence;
- remaining uncertainty.

A pull request may pass through several Engineering <-> Verification cycles while the same causal contract remains active.

If the causal question changes materially, stop expanding the pull request and open a separate issue or work item unless keeping the work together is clearly more informative and still reviewable.

Do not use arbitrary commit-count limits; split by causal contract and reviewability.

## Tests and CI

Tests should fail loudly when the claimed behavior cannot actually be exercised.

Do not convert environmental inability to test into PASS. A visible SKIP may be appropriate only when the limitation is explicit and the unsupported claim remains `UNPROVEN`.

Do not relax assertions merely to make CI green. When an old gate conflicts with newly demonstrated behavior, determine whether the gate or the product contract is wrong before changing either.

## Definition of done

Work is done only when:

1. the scoped objective is met;
2. relevant tests exercise the intended behavior;
3. CI contains no unexplained failure or misleading pass/skip;
4. Verification has no blocking contradiction;
5. regressions are addressed;
6. remaining uncertainty is explicit.
