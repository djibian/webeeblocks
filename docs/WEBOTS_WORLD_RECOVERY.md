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
