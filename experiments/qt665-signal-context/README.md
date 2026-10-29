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
