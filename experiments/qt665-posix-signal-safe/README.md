# Webots R2025a POSIX self-pipe candidate — source + bounded native Linux proof

The original live signal allocation evidence is in #665 comment6498840117.
This experiment changes only upstream src/webots/gui/main.cpp at
c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b (original blob d578afa7...).
It is not a product Webots distribution, a #701 GO or a historical crash repair.

## Repaired ownership and bounded GUI delivery

The nonblocking/CLOEXEC self-pipe is created before installing signal callbacks.
The callback only preserves errno and writes one byte; its body is unchanged
from the previous candidate. Both pipe ends now live for the entire process,
including GUI/application destruction. They are closed by process exit or exec,
not by return from app.exec. A fixed pair is not an accumulating resource leak.
A failed initialization still closes its private FDs before any handler uses them.

The GUI activation now sets the one-shot flag, disables QSocketNotifier, performs
one bounded read and then calls simulationQuit. It never drains an unbounded
stream of new signals before requesting quit. Windows retains its original
Ctrl+C branch; no Windows safety or compilation claim follows.

## Refutation retained: the previous teardown was unsafe

Previous source-only candidate b8116937179da1a840d8ece9ac15bd3f3323c4fa,
patch SHA256 d14be0c1f1906d019d0e6998b1977a18ac15953e7c0e2db953238276debe7359,
passed git-apply/static checks in run40889913028. It was never compiled as Webots.
That historical SOURCE_ONLY result did not validate FD retirement.

The exact old handler/configurator are compiled in fd-retirement-counterexample/.
A real pthread_kill(SIGTERM) enters it. A write wrapper pauses the thread after
its local FD has been sampled and before the actual kernel write, imposing a
legal scheduling interleaving. Only owned temporary pipes/files are used.

- keep: global revoked, handler disposition reset, both FDs retained; byte15
  reaches the original pipe and the distinct file stays empty.
- full: same retained pair filled to EAGAIN; handler returns without blocking,
  preserves errno and a notification byte is already pending; distinct file empty.
- retire: old teardown closes FDs and dup2 reuses old number4 for an owned file;
  the resumed handler successfully writes byte15 to that distinct file.

This is an actual POSIX kernel counterexample, not a Qt/Webots execution.
Resetting the global or signal disposition cannot recall an entered handler.
The process-lifetime repair removes close/reuse from that interval. All original
inputs, extracted handler, source hashes, compiler warning/log/version and raw
JSON are retained. Reproduce: python3 fd-retirement-counterexample/run_counterexample.py.

## Source qualification, with its negative control

The revised qualifier still requires clean exact upstream and original main blob,
one-file patch applicability, no Qt/allocation in the POSIX handler and the
Windows branch. It additionally refuses close/reset/global reassignment after
publication, and requires one-shot disabled/bounded GUI notification.

The fixed source passed the qualifier; the exact old patch is rejected by the
new FD-lifetime condition. source-qualification.json preserves both outputs.
The old checker required the unsafe reset/close, so retaining that requirement
would have enforced the refuted lifecycle. No mission oracle was relaxed.

Actual full Qt6.5.3 Webots compilation/linking and a loaded native consumer contrast
are now demonstrated for this SAME e9a6d936 patch: [run40897930515](https://github.com/djibian/webeeblocks/actions/runs/40897930515),
execution HEAD929ce783..., [durable evidence at1a00b901](https://github.com/djibian/webeeblocks/tree/1a00b901a415163d32b0a9f270260ddda3983536/experiments/qt665-posix-signal-safe/native-build).
Two complete rebuilt ELF files were actually installed/launched in a disposable
runtime, not substituted by a Qt double: baseline b9657239... PID135 records
four allocator calls during two SIGTERM handlers; self-pipe6839dab7... PID195
records zero. World/AST/events and negative not-achieved/runtime9.288s match;
24 native seal hashes and both strict capture audits pass. Exact normal-handler
disassembly corroborates no Qt call in the corrected path. This is the later
native phase; source-qualification.json retains the earlier SOURCE_ONLY phase.

Full native regression, Windows, product OCI adoption, combination with #701's
pre-READY repair and exact Ready CI Gate/independent GO remain NOT_TESTED.
Historical console SIGSEGV causality remains UNPROVEN. See the native evidence
README for complete hashes, development-overlay limits and original artifact
retention; this bounded contrast is not general platform qualification.
No historical memory corruption, #637 RESET repair, hardware action or
TEST_REQUIRED is claimed. Preserve all negatives and LAND exactly210000ms.

Current patch SHA256: e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8
