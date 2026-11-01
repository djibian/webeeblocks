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

Pending the single paired run. No native success is claimed from preparation or
workflow presence. Final report will retain the first attempt and any failure.

The temporary NON-GATE workflow is experiment-specific and does not alter any
required CI or acceptance oracle. Its addition is expected to be refused by the
unchanged canonical workflow-inventory check; that refusal must be retained.
It will be archived outside `.github/workflows` after this one experiment, never
made into a new CI authority.
