# #157 — local revocation during exact waits

This is machine evidence and a bounded software repair, not a flight procedure
or physical qualification. No checkpoint, TEST_REQUIRED, hardware operation or
motorized run is requested. The full operator-abort and physical containment
preconditions remain open.

## Demonstrated gap and repair

The trusted host's `CallerLifetime` receives ordinary IPC on its own thread and
records EOF even while the main host thread executes a blocking program under
`lifecycle_lock`. The caller-bound bridge rejects new current-program assertions
after that loss. Nevertheless, the previous `_execute_exact_wait` checked only
watchdog liveness and connection epoch. An unchanged epoch/live watchdog could
leave a cancelled run waiting its entire remaining student duration before the
next current-program assertion triggered recovery.

The trusted production composition now passes the existing local
`CallerLifetime.assert_open` through static/dynamic dispatch to exact waits.
The helper checks it before waiting, between its existing 50 ms slices and at
completion, including a loss during the final slice. The assertion reads only a
local Event and raises on terminal caller loss. It performs no browser, radio,
logging or effect operation and creates no teacher authority. A lost caller
is rejected at wait and current-program assertion boundaries. Existing exact-AST,
current-program, watchdog and epoch checks remain in place.

The same existing failure path revokes the exact teacher program and attempts
one eligible controlled recovery while maintaining watchdog liveness. There is
no concurrent radio client, duplicate landing, command resend, reset or effect
mutation. When effect/ACK/epoch/altitude/landing certainty is absent, the existing
recovery veto remains authoritative.

## Evidence and limits

`test_physical_host_inflight_sequence.py` exercises real socket EOF and the
production CallerLifetime with a deterministic monotonic clock: preclosed,
20-second remaining wait interrupted after its first slice, and EOF during the
last 20 ms slice. Production `serve_physical_host.py` is also executed through
both static and shared-interpreter activation paths. EOF is sent after wait
entry; cancellation is rejected at the first slice, ordinary landing does not
progress, and the production controller reports one confirmed recovery with the
live watchdog. Only external hardware/action observations and clock passage are
modeled, not the cancellation decision. The separate abort-landing suite retains
the real authority/transport/completion-domain uncertainty and no-retry oracles.

The 50 ms is a host pacing slice **after local loss has been observed**, not a
real-time bound from an operator gesture to touchdown. OS scheduling, socket EOF
arrival, an earlier blocking operation, acknowledgement/completion reads and
physical excursions are not bounded by it. A callback supplied to this internal
helper must be local and nonblocking; the production root supplies exactly the
existing CallerLifetime assertion. Standalone trusted fixture use may omit it;
ordinary IPC cannot select or replace it.

Additional machine oracles in `test_physical_caller_loss_races.py` exercise six
real-socket static/dynamic host schedules: loss in the first slice, after the
pacer's final check but before the enclosing wait completes, and simultaneous
epoch loss. The enclosing assertion rejects the post-pacer loss; epoch loss
vetoes recovery. Four separate schedules use real authority/effect/ACK domains:
EOF before ACK, missing ACK, during effect completion, and concurrent epoch loss.
Known accepted effects finish before eligible one-shot recovery; ambiguous
outcomes forbid recovery emission. These fixtures establish no physical bounds.
EOF observation and effect emission are not one atomic operation: this repair
does not close every pre-send race or promise immediate interruption of an
operation already in progress.

| Boundary | Status after this software change |
| --- | --- |
| Caller loss during a pure AST wait | Local loss aborts the wait at its next existing slice; terminal recovery reused |
| Loss during range/parameter/supervisor observation | Existing bounded observer and post-observation authority checks; no new interruption guarantee |
| Loss while an effect/ACK/completion is in progress | Existing uncertainty/no-retry rules preserved; no new command injected |
| Operator gesture while launcher awaits execution | No new live input or dedicated trusted abort channel delivered here |
| Ctrl-C, process kill, reset, radio unplug or watchdog expiry | Not qualified as a guaranteed controlled landing |
| Physical descent/containment/margins | Unproven; no numerical excursion or touchdown guarantee |

The one-shot teacher decision channel still seals after APPROVE/DENY. A future
explicit operator mechanism needs a terminal, host-owned signal independent of
the blocking launcher request and lifecycle lock; it must preserve the above
uncertainty gates, retain outcomes without making diagnostic output a recovery
prerequisite, and receive independent review. This bounded wait repair is useful
without claiming that whole mechanism exists or removing the flight blockers.

## Voluntary teacher abandonment through the existing caller channel

The launcher candidate adds a local `request_abandon()` operation and one-shot
console input. The reader is armed before transmitting APPROVE. The teacher can
type **ABANDON**, then Enter, while the launcher waits for a host reply. EOF or
failure of this trusted input also requests terminal abandonment. This is a
trusted launcher control, outside Blockly, the browser, AST and radio authority.

The signal is exactly one `shutdown(SHUT_WR)` on the existing ordinary socket.
No abort JSON, second host endpoint, teacher receipt, radio client, landing
command, emergency stop, reset or keepalive change is introduced. The read side
remains available for the original correlated host response. The host receives
the existing EOF and reuses its local caller guard and terminal recovery.
The input thread performs no output and does not take a socket-read, execution
or host lifecycle lock. An already blocked ordinary write cannot block this
local signal behind such a lock.

A short local lock serializes **three irreversible claims**: operator
abandonment, the teacher APPROVE/DENY decision commitment, and the one-shot
ordinary socket write-half-close shared by abandonment and cleanup. Preparation
and serialization of the teacher reply happen before the claim; the last local
check and the one-shot decision claim occur atomically against abandonment.
An approval already committed before the gesture remains transport-uncertain,
but an unclaimed approval can never be committed after terminal intent.
Each ordinary execution request similarly passes a short atomic terminal check
at commitment. Normal teardown also marks the launcher closing before it
releases that lock, forbidding newly committed decisions.

No lock surrounds socket sends, shutdown, host reads, ordinary I/O or cleanup
waits. Duplicate/concurrent gestures become no-ops. Unknown signal delivery
remains uncertain and is never resent, **including by cleanup**, which consumes
the same half-close claim before fallible socket I/O. Intent vetoes subsequent
approval, requests and normal-success reporting; a positive response arriving
after the gesture is not promoted to completion. A decision or effect already
committed before the gesture is not retroactively cancelled by assertion.
Known complete execution and abandonment serialize their local terminal
decisions; a gesture after that completion is a no-op. The host-wait rule never
kills a possibly authorized host.

The stdin reader is a daemon confined to this single-use CLI process: stopping
it suppresses a later line, but cannot interrupt a blocked OS stdin read. This
does not supply a reusable console service or change supported classroom UI.
The prompt is printed before approval; no diagnostic write precedes signalling.
The existing overall IPC deadlines remain unchanged. Terminal cleanup now has
a **single local owner** claimed under the same short lock: `not_started` →
`in_progress` → either `complete` or `failed`. A second concurrent close
cannot touch any resource while the first owner performs sockets, host waits,
Webots shutdown or local asset cleanup. It explicitly raises an unresolved
cleanup error instead; after failure it raises with the original exception as
its cause, **without repeating** a potentially uncertain close, wait, signal
or process termination. Only a fully completed teardown is idempotent. The single-use session
also rejects a subsequent `start()` after cleanup: otherwise reacquired host
resources could never be cleaned by the already-consumed owner. This is a
sequential one-shot invariant, not a new supported concurrent start/close API.

Normal shutdown of the caller write half remains exactly one claim shared with
abandonment. Even a failed/unknown normal SHUT_WR is now reported as an uncertain
teardown, not silent success. Abandonment consumed while cleanup owns this
attempt still records terminal intent, but neither retries the half-close nor
claims EOF was delivered. An approval claimed **before** cleanup retains its
true uncertainty; the teardown snapshots that authority under the same lock
and never terminates a possibly authorized host.

If the host's 10-second wait times out after teacher-decision commitment, the
host and dependent Webots/bridge/window resources remain held for safe host-owned
recovery. The session's cleanup is terminally `failed`: a later `close()` may
not opportunistically repeat the wait or tear down those resources, even if
later evidence shows the process exited. External recovery/observation and any
subsequent disposal of retained handles require a separately justified
procedure; this repair does not assert one. If a bridge/window close reports an
uncertain result after safe host termination, its reference remains inspectable
and the other independent asset close is still attempted once. The first
causal failure is propagated; no software cleanup state establishes physical
landing, drift margins or confinement.

Adversarial launcher tests use real sockets and the production
CallerLifetime for static/dynamic pending replies, eight concurrent gestures,
positive replies racing abandonment, pre-approval abandonment, settled
completion and late input. The repaired candidate adds an actual-thread
pre-commit approval race using the **real** PostResetTeacherDecisionChannel and
TrustedTeacherAuthorizer: an abandonment intent consumed while approval is
still in fallible preparation must not mint a receipt, even when ordinary EOF
is deliberately delayed or its outcome is unknown. Separate overlapping-thread
tests race cleanup against abandonment in **both claim orders**, and verify
one SHUT_WR attempt for delivered/uncertain results. Another test holds
non-emitting execution-request preparation across the gesture. No second
authority, resend or opportunistic reset is introduced. EOF on the console and
ignored input followed by ABANDON are covered. The existing canonical
production-lifecycle test invokes this whole launcher suite; the #585 real-host
wait/effect/ACK/epoch race suites remain unchanged. These are machine-only
fixtures without radio, motors or physical contact.

This does **not** establish a hard input-to-EOF or input-to-touchdown bound.
An in-progress radio effect retains its existing ACK/completion uncertainty;
EOF/emission is still non-atomic. Range/PARAM/supervisor operations and other
diagnostic sinks retain their existing limitations. Unknown state/epoch,
attempted landing, lost watchdog certainty or unavailable completed altitude
still veto recovery; no success is inferred from sending the signal. Usable
console/focus/input behavior, actual gesture-to-recovery timing, physical
margins and independent containment remain unqualified. Flight, hardware access,
new checkpoint and #70 research stay unauthorized. Fresh canonical CI and an
independent execution's exact-HEAD review are required for this candidate.
