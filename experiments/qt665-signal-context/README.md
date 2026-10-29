# #665 — living original Webots signal context (NON-GATE)

One bounded experiment on product source c0cb8c1873d48b26a0f67976c65fa92ca5d54f52,
official immutable R2025a OCI f0023e30..., upstream c6793d8....
No product edit, candidate promotion, CI Gate, flight or hardware action.

Question: does the original Webots POSIX SIGTERM callback perform allocator
calls even though its Qt simulationQuitRequested connection is queued?

Competing observations: no allocator event at positive handler depth refutes
allocation for this occurrence only; an allocator event between entry and exit
on the same PID/TID establishes allocation in this actual handler. Neither
observation establishes corruption or explains the historical Qt console crash.

The runner uses the existing unavailable/seed0/side2 native test, internal
controllers, world, AST, result checks, EOF collector, retirement and seal audit.
Only Webots receives LD_PRELOAD. The observer forwards original handlers and
glibc allocator functions unchanged. Initial-exec TLS and fixed-size writes
avoid the observer's own lazy TLS/formatting allocation inside handlers.
One same-image synthetic signal/direct-call pair checks context detection;
these controls are not Webots qualification. The actual ELF SHA256 is pinned;
its device/inode are compared with /proc/self/exe observed in the constructor.
Loader maps and Qt library hashes are retained, without QPA or full ABI claims.

Stop after one native trial, including failure or absence of allocation. Do not
retry unchanged. Missing/partial trace or uncertain subject fails the experiment.
The trace is outside each native mission's seal, and uploaded after Docker exits.
Instrumentation can perturb timing; malloc reentrancy/interruption, heap damage,
console lifetime and historical #665 causality remain UNPROVEN.

Original upstream source: src/webots/gui/main.cpp quitApplication ->
WbApplication::simulationQuit -> simulationQuitRequested, connected in
WbMainWindow with Qt::QueuedConnection. Qt's Unix-signal guidance:
https://doc.qt.io/qt-6/unix-signals.html

## Retained result, 29 October 2026

Execution source b012c038f443322030aaef13b5dde35b18425c01, NON-GATE
run 40887021809 completed/success, artifact 12902559249. The original ZIP is
preserved here as native-evidence.zip, 398470 bytes, SHA256
62d9708f2a0954e4d38f99d25b7aa5b534febb6fc54da4d8cd677526dc46f8f8.
All 27 ZIP entries passed CRC; all 12 mission seal hashes passed, as did the
existing strict capture verifier. The workflow is now manual-only to avoid an
unchanged repeat when publishing evidence. No new native run is required.

Actual Webots PID/TID 135/135, inode6732497/dev44. Two SIGTERM handler entries
each contain malloc(120), successful return, malloc(4), successful return, then
handler exit at TLS depth1. Positive synthetic context control records one
allocation; direct-call control records zero context allocations. The original
callback address 0x563c90f62830 minus image base 0x563c909cb000 is 0x597830,
matching the exact official ELF: tail call WbApplication::simulationQuit at
0x597840 -> simulationQuitRequested -> QMetaObject::activate at0x65ff00.
The queued Qt connection therefore does not exclude allocator use during the
POSIX callback. Historical crash causality and interrupted allocator: UNPROVEN.

The native unavailable negative remains not-achieved/runtime at8.936s, same AST
89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d.
Both internal controllers emit Terminating; no fatal marker is logged. Wrapper
PID118 returns -15, nodePID156 returns0; these are not Webots PID135 exit status.
Events SHA256 a91a7cde8f069d55a26ed422d91d4cd041a70b25b4539673dc30f4de0d423904
is byte-identical to the previously archived paired native cases.

Initial run40886554911/commit9138429 failed host read/upload EACCES because
root-created files were0600. No native/context PASS is claimed for that run.
The only experimental repair for b012c03 is explicit0644 on trace/maps.
