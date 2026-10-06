# Physical FAIL #554: causal evidence and repair boundaries

## Historical subject and limits

The owner-authoritative [FAIL](https://github.com/djibian/webeeblocks/issues/554#issuecomment-5997718319)
applies to `main@0229ac7232c67acbe8dbe3baac5d580c86718c39`, not a later candidate.
The exact verified artifact was `WebeeBlocks-Physical-Qualification`, id
`11281029448`, digest
`sha256:b811a36773d72c59018fa45804aab90d1863c608bc8b81f1485ea679e7600ddd`,
prepared by evidence run `37145314076`. Hardware: Crazyflie 2.1, Flow Deck V2,
Multi-ranger; no Color LED Deck. The report establishes normal takeoff to 0.5 m,
brief hover, no observed subsequent motion, fall/impact, and one failed execution
with no retry. Profile: `reactive-obstacle-v2`; post-reset epoch:
`be832b0896768729358f19f5238de720`.

`tools/ci/fixtures/physical_fail_554_ast.json` reconstructs the reported canonical
AST. Excluding the file's trailing newline, its SHA-256 is exactly
`55b78da087a11730328e7be7d2616420881cbadcbd9d7d604b76250eb3e6dc99`.
This verifies program identity; it cannot reconstruct a sensor reading, radio
reply, supervisor transition or exception that was not recorded.

The historical *initiating exception is not identifiable from the retained
record*. Dynamic dispatch sends the entire post-takeoff interpreter run as one
caller request. `step 1` therefore names neither the first AST statement nor the
first effect. At that SHA, the worker, host response and launcher discarded
causal details. Deterministic fault injection at distinct call sites reproduces
the same outer failure. No available evidence distinguishes unavailable range,
provenance loss, observer setup/freshness failure, transport rejection, watchdog
loss or another internal exception. Values >=8000 mm are unavailable in pinned
cflib Multi-ranger semantics; their occurrence in #554 is **unproven**.

## Established defects and bounded repairs

| Boundary | Reproducible defect | Repair and proof |
| --- | --- | --- |
| Worker → host → launcher | Internal exceptions/activation failures collapse to generic `step 1`; a failed error write can mask its cause | [#555](https://github.com/djibian/webeeblocks/pull/555): bounded cause chain, source location, shared-interpreter call ID/node path, binding hash/profile/epoch, raw unavailable-range evidence and persistent packaged terminal log. Fatal Node stderr is drained into a bounded tail; validation causes and explicit truncation markers survive. Actual worker/host/launcher tests verify propagation. |
| Aborted known flight → teardown | Static/dynamic exceptions revoke watchdog before any controlled abort landing; cflib `close_link()` sends a zero commander setpoint | [#556](https://github.com/djibian/webeeblocks/pull/556): revoke ordinary authority, retain the exact live powered bundle for one narrowly eligible command-10 landing and fresh completion, then teardown. Real domains with injected radio prove packet count, altitude, authority revocation and watchdog ordering. This is a demonstrated avoidable-cut path consistent with #554, not retrospective proof of its exact motor-cut instant. |
| Static sequencing | A definitively rejected step releases its sequence claim and accepts a later ordinary retry | #556 makes the activated static run terminal on rejection/error, matching dynamic one-shot semantics. Rejection never becomes permission to continue or skip. |
| Fresh yaw | A callback entering before `read()` but finishing later can masquerade as fresh; coerced strings/bools accepted | [#557](https://github.com/djibian/webeeblocks/pull/557): callback-entry generation fence and exact numeric/timestamp types. A synchronized delayed-callback regression rejects the stale sample. |
| Observer lifecycle | Uncertain yaw cleanup allows reopen; unexpected supervisor cleanup errors fail without poisoning the untagged epoch | #557 poisons uncertain teardown, attempts remaining cleanup, and prevents replacement-reader reuse. Range/yaw/supervisor also reject NaN/infinite/bool/non-numeric deadlines before effects. |
| HighLevel effect lifecycle | Callback-removal errors are swallowed in takeoff, motion, static and dynamic landing; exceptions after acceptance abandon a live completion permit | #557 poisons acknowledgement correlation across instances; exceptional accepted transactions invalidate their completion permit. All four transport regressions prove no success/retry after cleanup failure. |
| Dynamic preflight | Repeat expansion can grow exponentially; a program exceeding the existing shared 1000-step budget can be admitted before takeoff | [#558](https://github.com/djibian/webeeblocks/pull/558): bounded physical-proof work plus conservative budget proof in the shared interpreter itself. Tests cover 20^18 repetition, exact budget boundaries including expressions/branches/land, and pre-effect rejection. No second language evaluator. |
| Qualification lifecycle | Whole-program IPC can be replayed after ambiguity; per-byte timeout prolongs a message; caller EOF is invisible during dynamic execution; launcher kills a potentially airborne watchdog owner | [#559](https://github.com/djibian/webeeblocks/pull/559): consume before write, one finite message deadline, bounded negative-only caller-lifetime observation, host-before-browser teardown. After the unchanged 10-second teardown deadline, unresolved authorized host stays alive for recovery and failure is reported. Original error survives cleanup failure; `HOST_TEARDOWN` survives lost IPC. |

## Recovery invariant

Recovery is a private host safety action, never another student-program step or
renewed teacher authorization. It requires all of the following: causally
established `FLYING` with no pending/unknown effect; original powered-session
identity; same live radio epoch; live watchdog; fresh healthy flying/finished
supervisor state; SafeLink; unpoisoned acknowledgement correlation; completed
nominal altitude within the existing 0.2–1.5 m envelope; no prior terminal-landing
attempt. It uses the existing landing packet, timeout and non-flying completion
oracle. An acknowledgement alone never means landed. Ordinary authority is
revoked before recovery and never restored. A recovered abort remains a failed
program.

Unknown takeoff/effect outcome, pending completion, lost epoch/watchdog,
blocking fault or a previously attempted landing blocks automatic recovery.
Neither reset, reconnect, inferred ground contact, stale altitude nor a second
landing attempt can manufacture missing evidence. Firmware watchdog remains the
terminal fallback. Landing cannot be guaranteed after radio/power failure,
process death or genuinely ambiguous physical state. The launcher does not
claim teardown succeeded merely because its local waiting deadline expired.

## Systemic coverage

| Layer | Reviewed invariant and deterministic evidence |
| --- | --- |
| Blockly/profile → AST | Generic profile bounds, supported directions/units, exact canonical serialization, optional decks derived from actual intent, unchanged simulation/physical vocabulary. Capability contract/submission tests and exact #554 digest regression. |
| AST → static/dynamic preflight | Static exact order/altitude and dynamic all-path bounds, shared expression/variable validation, pre-reset rejection, new finite proof/execution budgets. No range substitution or branch oracle. |
| Shared interpreter → backend | One language engine, sequential private RPC IDs/arity, host-bound exact AST, takeoff verification of completed host takeoff, one-shot execution, both branches of #554 and faults at every backend call. |
| Range/yaw observations | Same live object/epoch, post-request freshness, baseline-only first sample, timestamp wrap/duplicates, exact range TOC/units, >=8000 unavailable, malformed/disconnect/cleanup failure, no command authority. |
| Transports | Exact command 9/10/GO_TO and Color LED PARAM semantics, one plain send, SafeLink, acknowledgement correlation, post-read provenance recheck, private completion permit, no retries. All four HighLevel cleanup variants tested; Color LED already has poison-on-listener-cleanup and exact readback. |
| Authority/watchdog | Exact teacher binding, separate teacher channel, fresh browser assertions, reset-established powered identity distinct from radio epoch, keepalive deadline and poisoned powered identity across reconnect. Existing watchdog/powered-session/teacher/host tests retained. |
| Completion/recovery | Positive ack is insufficient, fresh supervisor completion, effect/reset exclusion, nominal altitude only after completed vertical effect, exception/rejection terminal, abort landing eligibility and no resend. |
| Reconnect/reset | Unknown flight cannot authorize reset; ordinary reconnect never resets a poisoned firmware watchdog identity; full reset/postconditions and new teacher decision remain necessary. |
| Qualification/package | Verified exact source/runtime/generated assets, distinct channels, one-shot approval and execution, EOF/timeout/partial-write handling, preserve host recovery, deterministic package tests and canonical CI. Checkpoint/notification mechanism unchanged. |
| Evidence/diagnostics | Durable FAIL, exact reconstructed AST, causes rather than generic errors, AST call location, raw sensor unavailable evidence, stderr/stdout log, terminal phase even after caller loss. No local variables or authority tokens logged by the diagnostic formatter. |

The firmware/cflib API review used the repository-pinned cflib commit
`45fdb784c9d13074c42835f3b5ac1d12133bf873`, including LogConfig/TOC,
Multi-ranger conversion, high-level callback API and `close_link()`. No API
mismatch was established as the historical trigger. The tests inject hardware;
they are not physical flight evidence.

## Reproduction and independent review

Run, without hardware:

```sh
python tools/ci/test_physical_fail_554.py
python tools/ci/test_physical_shared_interpreter.py
python tools/ci/test_physical_dynamic_preflight.py
python tools/ci/test_physical_yaw_observer.py
python tools/ci/test_physical_range_observer.py
python tools/ci/test_physical_supervisor_state.py
python tools/ci/test_physical_execution_domain.py
python tools/ci/test_physical_abort_landing.py
python tools/ci/test_production_takeoff_run.py
python tools/ci/test_dynamic_physical_run.py
python tools/ci/test_physical_qualification_launcher.py
```

`test_physical_abort_landing.py` is introduced by #556. All new regressions are
reached by existing canonical Runtime CI entry points. CI Gate on every exact
Ready candidate, and fresh CI after integration/rebase, remain mandatory.
Integration of #556/#557 must retain the shared base transport's cleanup checks
while removing the duplicated dynamic landing implementation. Additive test
conflicts between diagnostics/budget/launcher repairs must retain both sets of
oracles. No automatic merge or independent GO is supplied by the authoring
execution. A combined local tree is integration evidence only, never acceptance
of a later `main` SHA.

## Conditions for a future checkpoint

No new `APPROVE`, real flight, retry or `TEST_REQUIRED` is authorized by this
review. #554 remains resolved **FAIL**, with its artifact/fingerprint historical.
A future request is ineligible while any applicable repair or refutation is
unresolved. It requires independent Controller review of all affected boundaries,
integration on a newly reconstructed exact main SHA, successful applicable
canonical CI and deterministic qualification preparation, executable diagnostic
capture and recovery regressions, plus the trusted checkpoint mechanism's fresh
artifact digest/provenance and global one-open/deduplication checks. The remaining
hardware evidence must be indispensable and the procedure explicitly human-owned.
Never reuse #554's artifact/approval or call a recovered abort PASS.

The initiating exception of #554 must remain recorded as unknown unless genuinely
new historical evidence identifies it. A later successful flight cannot prove
that historical exception, and a later failure must retain its exact program,
call site, causal error and terminal physical-state evidence. The 30-second
launcher request deadline is unchanged: an overlong execution fails closed and
revokes ordinary continuation; it is not silently extended. Representative
physical safety and capability acceptance remain unproven until a separately
authorized exact-artifact checkpoint supplies that evidence.
