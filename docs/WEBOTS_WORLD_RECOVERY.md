# Webots R2025a — separate world reload recovery (#637)

A failed strict RESET is still a failure. **Reconstruire** persists the
unsaved Blockly workspace and activity ID to browser localStorage, then
revokes old WWI commands and invokes the official Webots world reload via
the native Supervisor. The old process cannot acknowledge reconstruction.

A new Robot Window restores the program, verifies two nonce-correlated
**unchanged strict RESETs** bracketing scene restoration and independent
scene acknowledgements, checks the Blockly serialization unchanged,
clears its checkpoint and allows an **explicit** new execution. All
remaining errors leave Run locked. No .wbb disk file is modified.
After restart the lost in-memory Save file handle requires
**Enregistrer sous** to persist recovered unsaved changes.

Strict RESET remains 5s/250ms; existing collision negatives and LAND
rules remain. The new native CI test forces the separate recovery path
after a *real* unsafe/collision program; it does not claim to reproduce
the historical intermittent RESET_TIMEOUT. It must demonstrate a new
world, postconditions, restored Blockly and an actual second colliding
Blockly execution. Failure to preserve browser localStorage origin is
a refutation, not a reason to relax the gate. Windows remains separately
unproven by a Linux run. #637/#665 stay open.

Debt is locally removable: delete RELOAD_WORLD, correlated recovery
RESET extension, checkpoint/UI code and recovery-only test after a
future official Webots release makes the original strict RESET reliable.
No Webots or physical backend is modified. V5 exact-HEAD CI, independent
review and explicit owner permission are prerequisites to merge.

## Native Linux research evidence and remaining fail-closed gap (2026-10-30)

PR #757, Webots R2025a native run `41074106931`, demonstrated one reload,
restoration of an unsaved Blockly program, strict RESET and a second real
unsafe/colliding execution (22,208 ms observed). PR #758 control, run
`41075623035`, removed only the explicit CI Chrome profile and restored the
failure. CI's headless browser must therefore reuse the same *isolated test*
profile on both sides of the reload. This is a CI environment fix, not a
Webots change or evidence of persistent storage in Windows Robot Window.

**NO_GO for production until resolved:** if localStorage disappears across
reincarnation, the new Robot Window cannot distinguish a lost recovery
checkpoint from a legitimate first launch. Under that condition the unsaved
pupil program is lost and the default clean interface may permit execution.
A successful CI profile does not eliminate this safety/data-loss boundary.
Qualification requires a durable cross-incarnation intent signal and a
negative test where browser profile/checkpoint disappears, or an equivalent
provable fail-closed contract, plus Windows user-path evidence.

## Native recovery witness: boundary and protocol (2026-10-30)

PR #759 experimental run 41089006268 demonstrated a one-file per-user/per-world
native witness written and flushed before the official Webots world reload.
With the witness pending, a browser that loses or corrupts its Blockly
checkpoint must stay locked even if Webots reports READY. Tests also cover a
stale witness at legitimate boot. The witness contains only a random recovery
token, NOT a second copy of Blockly. Total browser-profile loss therefore
causes **explicit data loss + fail-closed**, not guaranteed program recovery.

The status response intentionally never discloses the witness token: a new
browser without the saved checkpoint may observe PENDING but cannot learn the
token needed to clear it. A matching checkpoint must prove possession in the
status query. This improves stale-browser isolation but is not a native proof
that the caller completed RESET/SCENE; the UI verifies those postconditions.
The gap between consuming the native witness and clearing browser storage is
also a fail-closed interrupted-transaction case, not a reason to auto-discard.

Canonical Ready-HEAD CI, Windows native/GUI qualification, native stale-ACK
interception and interrupted-transaction fault injection are still required.
A Linux Draft experiment is never authorization to merge or claim Windows GO.

## Native commit gate against premature witness removal

The controller enforces two nonce-correlated strict RESET completions with
two confirmed scene selections in that order before accepting RECOVERY_CLEAR.
A direct raw-WWI clear attempt with the correct known token before the
physical sequence is a negative test (`early_clear`) and must be rejected.
The counter resets on failed RESET, rejected scene, STOP and incompatible
sequence transitions. This strengthens fail-closed enforcement independently
of browser correctness; it does not change RESET/LAND physics or timeouts.

## Bounded native status handshake (2026-10-30)

The browser must never unlock merely on READY. Native run 41094229271
captured a real first RECOVERY_STATUS request dropped after READY while the
subsequent request was answered. Only the nonce-correlated recovery-status
query has up to three bounded 2.5-second attempts; each retry advances the
WWI numeric request ID and uses a new random nonce. Old responses cannot
complete a new probe and exhaustion remains fail-closed. Strict RESET,
LAND, physical oracles and action timeouts are untouched.

## Native browser lifecycle contrast, research PR #761 (2026-10-30)

PR #761's exact native A/B run 41098578681 yielded 3/3 verified full
reconstructions with --new-window, and 3/3 with the old control launcher.
The later stable_exit/control run 41100024546 also completed successfully,
3/3 in each arm. No causal advantage for either launch flag or a 15-second
Chrome SingletonLock wait has been established. Neither is shipped as a
production workaround. An independent native failure in PR #761's
lost_checkpoint test (run 41100024625) reproduced two browser launcher calls
and a native READY but no second-document browser event. The intermittent
lifecycle defect remains open, and successful samples are not a proof of
reliability.

The CI launchers now capture *passive* timestamps, PID/PPID,
Chrome SingletonLock and process snapshots, and Chrome stderr into separate
artifacts. Browser flags, same-profile preservation, Webots world reload,
strict RESET/LAND and all negative acceptance criteria are unchanged.
A future failing run should establish whether the second Chrome process
forwarded to a shutting-down singleton or loaded a document that failed to
connect. Experimental job termination / retry is not an acceptance oracle.


## Chromium ProcessSingleton handoff: causal native discrimination (#762)

At pinned Webots R2025a, a spontaneous guard-negative failure on exact
#755 head `9e9d56c0` occurred in native run `41103223478`
(`corrupt_checkpoint`, artifact `12999394928`): the second launcher
was invoked, the new native controller was READY, but no new Blockly
document was observed. Chrome stderr included
`process_singleton_posix.cc:349 ... SingletonLock: File exists (17)`.
That message alone does **not** prove the failure mechanism.

Research #762 independently caught a second, *unmodified* native
`lost_checkpoint` failure (`41110822361`, artifact `13002729667`)
with the second Chromium process exiting **21** and no post-reload
document event. For a discriminating intervention, #762 froze the old
Chromium profile owner for 7 seconds on an actual Webots second launch
and guaranteed its resumption. In the same exact native research run
`41113877775` at SHA `d03341fff8d7e7b43ae87888d044d29ab3627335`:

- Unmodified second-Chrome launch under injected contention: **0/2**
  (process exit 21, no second document).
- One explicit CDP creation of a document in the *existing profile
  owner*, triggered only after exit 21: **2/2**, with the independently
  observed `NEGATIVE_LOCKED` after missing checkpoint.
- Full collision, real `world_reload`, two nonce-correlated strict
  RESET/scene cycles, byte-identical Blockly/AST, explicit new colliding
  run under the same injected exit-21 fault: **3/3** (artifacts
  `13004029557`, `13005302016`, `13004862905`). All five
  unchanged native recovery negatives passed. The research workflow's
  overall conclusion is deliberately FAILURE because its two negative
  *control* jobs failed as expected. This is not a green CI Gate.
- Measured full reconstruction times: 22.149, 17.245, and 16.835 s,
  **including** the deliberately injected 7-second freeze, not a
  production latency estimate.

The joint observations establish **one actual causal class**: Chrome's
same-profile ProcessSingleton handoff can fail to create a new page
even with functioning Webots HTTP and a new native controller. They do
not prove that all possible Robot Window startup failures have this
cause.

**Integration decision: NO_GO for #762's raw CDP rescue.** Its
`--remote-debugging-port=9222` exposes browser-debugging power on a
fixed local port, is Chromium-specific and unqualified on Windows; it
is suitable only in isolated research CI. The native observer's early
HTML marker and synthetic SIGSTOP are also research-only. Do not import
these into the classroom launcher or #755.

### Production-design acceptance boundary

A replacement should explicitly create a new document in an *already
running browser owner* on failed same-profile handoff, without a
publicly listening unauthenticated DevTools endpoint. One candidate
is a lifecycle-bound per-Webots-session browser broker with
same-user authenticated local IPC and a private Chromium debugging
pipe; it needs a bounded process lifetime, URL/origin allowlisting,
single-use request correlation, preservation of the actual Blockly
profile, cleanup after Webots exits, and an independently specified
Windows implementation. This is a **candidate architecture, not a
validated solution**. A native Webots/browser API offering the same
private new-document action would be preferable if demonstrated.

Required before any GO: reproduce the exact exit-21 counterexample
against the production candidate; show failed untreated control and
passing treatment on identical faults; repeat real full reload/Blockly
restoration and the five native negatives; demonstrate fail-closed
behavior on broker failure, unauthorized URL, wrong/stale session and
missing profile; qualify Windows and the canonical Ready exact-HEAD
CI; obtain independent review and owner approval. In particular, a
new browser profile without a preserved Blockly checkpoint must
**never** be treated as successful recovery. The per-world native
witness currently stores only the authorization token, **not**
unsaved Blockly bytes.

Current #755 `main` merge verdict remains **NO_GO** and reliable
classroom reconstruction **UNPROVEN** despite the mechanistic Linux
research GO. No Webots/ODE, physical RESET/LAND, GP tests or program
serialization are changed by this documentation.

## R1/R2 checkpoint integrity — experimental V3 (2026-10-31)

The browser captures the **exact JSON string** returned by Blockly serialization and
the exact activity `profileId`. The SHA-256 input is byte-encoded as:

`UTF8("WEBEEBLOCKS_RECOVERY_V3\\0") || UINT32_BE(len(profile_utf8)) ||
profile_utf8 || UINT32_BE(len(workspace_utf8)) || workspace_utf8`.

The `len` fields count **bytes**, not JavaScript code units. Only a native
`WEBEEBLOCKS_RECOVERY_V2 token64 digest64\\n` record is valid; V1, truncated,
oversized, malformed and corrupted witnesses fail closed without silent removal.
The record is persisted *before* world reload; `RECOVERY_CLEAR` is admitted
only after two separate strict native RESET/SCENE pairs and matching token and
SHA-256 digest. WWI request IDs and per-request fresh challenges still bind
the native acknowledgments. The hash is recomputed from the restored workspace,
not trusted from a browser checkpoint. Browser `crypto.subtle` unavailability
prevents arm/clear; no hash-only bypass exists.

The producer holds the same browser-partition Web Lock as the consumer across
the absence check, durable checkpoint write, tab renewal arm and irreversible
native RELOAD_WORLD request. Existing records, *even invalid ones*, cannot be
overwritten. Missing/late locks fail closed. The 10 s lock acquisition, 30 s
HTTP renewal deadline, 5 s RESET and 250 ms stability window are unchanged.

**Threat boundary:** protects against browser checkpoint corruption while the
native witness remains independent and intact. It cannot defeat an attacker
with arbitrary ability to replace the witness file (or native/controller code)
and is not a backup of an unsaved project if the profile disappears. Different
browser storage partitions do not share Web Locks; native atomic witness access
remains a separate matter to audit. This experimental branch is not an
authorization for Windows classroom use.
