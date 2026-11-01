# #665 — one Supervisor normal-quit contrast (research only)

No main integration, no Webots patch, no production qualification. One targeted
A/B pair is authorized: official pinned R2025a, seed 0, unavailable negative,
unchanged world/AST/oracles. No retry on a native failure.

## Static relevance and minimal protocol

`stop_groups` sends SIGTERM to the Webots process group. The existing evaluator
is already a Supervisor. Its ordinary `simulationQuit(0)` request reaches the
same WbApplication / queued WbMainWindow::closeEvent as the signal path, without
calling the POSIX handler from the runner.

The runner remains the sole requester: only after all existing trial checks,
optional second RESET, required terminal LAND, exact deadline and AST checks,
it additionally requires complete finite pose/velocity diagnostics for every
attempt. It freezes the host result, native results, diagnostics and Node events,
then atomically publishes an attempt-bound request with a per-trial token.
The evaluator does not infer quit from success/failure; it requires this request
and an already published native result for the same current attempt. The CI
artifact directory is newly created per trial, and pupils have no filesystem
command in their block vocabulary. This is a cooperative local qualification
protocol, not isolation against arbitrary native code sharing the host.

An ACK precedes the API call and proves only acceptance. NORMAL success requires
matching ACK, wrapper exit 0, pipe EOF, unchanged fatal-log oracle, no remaining
Webots-group process, and all frozen proofs unchanged. Only then is the already
dead Webots group omitted from signal cleanup. Every refusal/timeout/unknown
outcome keeps the original SIGTERM then SIGKILL fallback; it never establishes
normal success. The original final fatal-exit/log checks, diagnostic collection,
capture seal and verification stay in place. Existing failures keep their primary
error and cannot reach the quit request site.

The contrast instruments this runner's actual killpg calls. It does not instrument
native handler entry or prove absence of signals from any external actor. Its
claims are limited to successful ordinary exit, omission of this runner's POSIX
signal route in B, and the unchanged scenario outcome. It cannot establish
elimination of the historical QRawFont/malloc crash; both routes still close Qt.

## Checks before native contrast

Host refusal checks passed: missing second diagnostic forbids a request; bad ACK,
nonzero exit, timeout, pipe not at EOF, fatal malloc output, surviving process and
post-validation proof mutation all forbid normal success. Static ordering check
keeps the request after existing RESET/LAND/oracle sites. Existing capture-seal
and deadline tests passed. These are host checks, not Webots evidence.

## Native results

**One pair actually completed; no repeat.** Exact experiment HEAD
`55743a2d6667fc70ef7e5c661f33c3dd3525271e`, official unchanged Webots/ODE/Qt.
[NON-GATE run 41292810029](https://github.com/djibian/webeeblocks/actions/runs/41292810029),
attempt 1, job 124807377166, completed/success. The flight controller was compiled
once from the same current source for both arms; Webots was not rebuilt.

| Observation | A: current SIGTERM | B: Supervisor API |
|---|---|---|
| World SHA-256 | `4b17c32951fa76627e73485dc41c7ef30ef91f76b950b0525bf78a0f7322ef5a` | identical |
| AST SHA-256 | `89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d` | identical |
| Mission result | not-achieved / runtime / 0 crossings | identical semantic result |
| Reported simulated duration | 9.160 s | 8.648 s |
| Webots/Xvfb wrapper PID | 102 | 149 |
| Wrapper exit status | -15 (requested SIGTERM) | 0 |
| SIGTERM actually sent by runner to Webots group | 1 | 0 |
| SIGKILL fallback | 0 | 0 |
| Remaining Webots group members | 0 | 0 |
| Visible container processes after cleanup | original docker-init + Python harness | same two original identities |
| Final pipe EOF / no fatal diagnostic / seal | passed | passed |
| Attempt-bound ACK + four frozen proof hashes | not applicable | byte-for-byte verified |

The two earlier mission timestamps differ. This is not an exact trajectory/time
equivalence claim. Both runs use the same asynchronous controller/scenario and
the same rejection oracle. The new request is made strictly after the existing
decision, and B's accepted result, native result, diagnostics and events are
unchanged through exit. No later outcome is substituted for the native negative.

The stdout acceptance marker from the evaluator is NOT present in the final
console log (the controller calls quit immediately after printing). This marker
is not an acceptance condition. The actual ACK file matches the request bytes;
wrapper exit, group retirement, EOF and hashes independently confirm the bounded
exit claim. We do not infer successful exit from a printed marker or ACK alone.

The original archive [13077808420](https://github.com/djibian/webeeblocks/actions/runs/41292810029/artifacts/13077808420)
was downloaded and checked on its bytes: ZIP SHA-256
`b87ccb715cb55cf2861802137d5adead80f82074373bd888caf7c28c8980c1a3`,
36/36 CRC entries, 35/35 root manifest hashes, plus 12/12 A and 15/15 B per-trial
seal hashes. All four B frozen proofs match after retirement. Both post-cleanup
cgroup snapshots are complete, untruncated, have zero scan errors, and restore
the same two PID/start-time identities as before the trial. This supplies
stronger evidence than the empty owned process group alone. No residual Webots,
controller, Node or Xvfb process is present in that visible container snapshot.

`evidence/` retains selected original JSONs and full console logs, plus the
original archive manifest and a verification result. It is explicitly a subset:
large raw trace CSVs remain in the original Actions archive. The manifest is the
manifest of that original full archive, not an assertion that every listed file
is reproduced under this Git evidence subset.

The fixed official `webots-bin` hash is
`1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb`;
full engine/ODE/Qt identities are retained in `evidence/engine.json`.

### Three separate verdicts

1. **Ordinary exit: PROVEN_IN_THIS_PAIR.** Supervisor request, ACK, zero exit,
   EOF, unchanged proofs, no visible residual trial processes.
2. **Runner POSIX shutdown route: ELIMINATED_IN_B.** The observed runner sends
   no signal to B's Webots group, which has already exited. No native handler
   entry counter was installed; no universal claim about other signal senders.
3. **Historical post-READY QRawFont/malloc crash: UNPROVEN.** Neither arm crashed
   in this pair. Same closeEvent, no demonstrated historical cause or eradication.

The pair covers Linux seed-0 unavailable only. RESET's second attempt and forced
LAND are protected by unchanged static call ordering and host refusal checks,
but were not additional native scenarios in this experiment. No Windows claim,
pedagogical acceptance, representative flight or production GO follows.

### Canonical CI history and final scope

The first Draft canonical run [41292839030](https://github.com/djibian/webeeblocks/actions/runs/41292839030)
is **failure**, not reclassified: unchanged workflow inventory and no-push checks
correctly refuse the temporary experiment workflow. Its subsequent expected
draft capture upload also had no files. Required guards were not modified.

The temporary NON-GATE workflow is experiment-specific and does not alter any
required CI or acceptance oracle. Its addition is expected to be refused by the
unchanged canonical workflow-inventory check; that refusal must be retained.
It will be archived outside `.github/workflows` after this one experiment, never
made into a new CI authority.

The workflow is now archived as `workflow.yml.archive`; no second native run is
requested. The tested runner/evaluator/protocol code is unchanged. Final commits
only preserve evidence and retire the one-shot workflow. This remains Draft /
RESEARCH ONLY / DO NOT MERGE pending independent review and any later separately
justified integration qualification. Neither #637 nor #665 is closed.

## Product decision

This is a useful, bounded way to remove the current runner's normal shutdown via
SIGTERM, without rebuilding Webots. Prefer independent review of this small
protocol before broader use, rather than another contrast or a new generic engine
repair. The single-pair limit has been respected. Research into #637 and the
historical #665 root causes remains separate; this result does not replace the
ongoing exact-candidate reconstruction work.
