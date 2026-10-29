# Webots R2025a — POSIX signal-safe quit candidate (NON-GATE)

## Defect demonstrated by native evidence
Upstream exact commit: `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. `src/webots/gui/main.cpp:91-93` directly invokes Qt through `WbApplication::simulationQuit` from POSIX signal handler registered for SIGINT/SIGTERM/SIGQUIT/SIGHUP. The unchanged GUI emits a queued Qt signal synchronously **inside the handler**; Qt::QueuedConnection only moves its receiver. Original live Webots official ELF `1445efb...`, [run 40887021809](https://github.com/djibian/webeeblocks/actions/runs/40887021809), native [artifact 12902559249](https://github.com/djibian/webeeblocks/actions/runs/40887021809/artifacts/12902559249): two SIGTERM entries and four positive malloc() calls from handler depth=1, independently verified in [issue #665](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6498866861).

## Proposed upstream-only repair
`webots-r2025a-posix-quit-selfpipe.patch` modifies **only** `src/webots/gui/main.cpp`. POSIX handler saves/restores errno and calls only async-signal-safe write() into pre-created non-blocking, close-on-exec self-pipe; it makes no Qt call, no allocation and no lock. A Qt6 `QSocketNotifier` drains the pipe on the GUI event loop and emits `simulationQuit(EXIT_SUCCESS)` once. A full pipe means a pending byte already exists; repeated signals coalesce. Initialization failures refuse a silently unprotected runtime. Windows Ctrl+C and its original source branch remain unchanged in this scoped repair (not yet separately qualified).

**This is an experimental source patch, not an installed Webots executable or a claim of a #665 fix.** New C++/Qt compilation, actual Webots linking/packaging, real signal delivery, concurrent SIGTERM/GUI close, full native world/oracles, Windows and source-composed #701 integration are still **NOT_TESTED** until separate native evidence. The historical Qt console malloc SIGSEGV is NOT proven caused by this signal-safety defect. Avoid changing timeouts, RESET, LAND exactly 210000ms, negative tests or hardware boundaries.

## Static fail-closed source qualification
Use a disposable exact upstream checkout and:
```bash
python3 experiments/qt665-posix-signal-safe/qualify_signal_safe_source.py --upstream-tree /path/to/webots-R2025a
```
The qualification requires upstream SHA `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, exact original main.cpp blob `d578afa7cbd27ea13fd9ca0583f5e12170c6fba3`, a clean checkout and an applicable patch. It checks the post-patch POSIX handler and Qt boundary without mutating the upstream checkout; a successful static result is **SOURCE_ONLY**, never a native GO. The experimental push workflow tests it once, without presenting the required `CI Gate`.

## First source-only verification — 29 October 2026

GitHub Actions [NON-GATE 40889913028](https://github.com/djibian/webeeblocks/actions/runs/40889913028), exact execution HEAD `b9c90ab3750a070c3b20138aefab8da646708506`, **completed/success** (one job). Upstream checkout is `cyberbotics/webots@c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, original `src/webots/gui/main.cpp` Git blob `d578afa7cbd27ea13fd9ca0583f5e12170c6fba3`. The patch is `d14be0c1f1906d019d0e6998b1977a18ac15953e7c0e2db953238276debe7359` (SHA256) and changes that single upstream file. The Git apply check and the POSIX/Windows static boundary tests actually completed successfully.

Original [artifact #12904648172](https://github.com/djibian/webeeblocks/actions/runs/40889913028/artifacts/12904648172) downloaded and verified: ZIP **553 bytes**, SHA256 `131f611765d4b25fe964ad4316fb274a8faaacf123565af3a460018448291bf8`, **2/2 CRC**; manifest explicitly `verdict=SOURCE_ONLY`, `native_binary=NOT_TESTED`. Never promote this static result to a real Webots C++/Qt binary qualification, patch adoption, full native regression or a Ready/GO for #701.

The push trigger was removed after this exact useful result; workflow is now manual-only. The next test must **compile the actual patched R2025a C++/Qt6.5.3** and verify event-loop delivery and absence of signal-context allocation on the *loaded* ELF with a live SIGTERM. Include repeated SIGTERM and failure/teardown guards, test Windows branch semantics separately, and retain RESET and LAND at exactly 210000ms and all negative oracles. No robot/hardware actions are justified.
