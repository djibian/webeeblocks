# #665 / #701 — full combined Webots R2025a native evidence (NON-GATE)

**Completed native witness:** [GitHub Actions #40910261173](https://github.com/djibian/webeeblocks/actions/runs/40910261173), exact execution HEAD `7bb4a51b7ec39ba845897f2b2e115eb393a23ceb`, attempt 1, `completed/success`. **Not a Ready CI Gate.** This source branch is an experiment and is not a product installation.

The experiment reuses, without rebuilding, the complete Webots R2025a Linux ELF assembled by [full-link run #40906375132](https://github.com/djibian/webeeblocks/actions/runs/40906375132), full `webots-bin` SHA256 `e95dee5feb8503269eb75cf1d729596a2e1fd9f40e993e59e162742c86617699`. This ELF combines the #701 parent-safe Qt source repair with the process-lifetime-FD POSIX signal repair patch SHA256 `e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8`, from exact `cyberbotics/webots@c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. The prior candidate patch `d14be0c1...` has a demonstrated FD close/reuse race and **MUST NOT be adopted** ([counterexample](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6499906005)).

## Independent exact-artifact checks

Original [GitHub Actions archive #12914601160](https://github.com/djibian/webeeblocks/actions/runs/40910261173/artifacts/12914601160), ZIP **29 765 957 bytes**, SHA256 `17911985d6ea47be33b133fd70b9adf5dcfb8d5a157aaeb69e5e6744e0a49767` (identical to Actions digest), **325/325 entries CRC valid**. This is a live Actions artifact with limited retention; this README **does not represent its raw contents as retained indefinitely in Git**.

- **20 distinct Webots consumers**, 20 independent process IDs and **20/20 native `sha256.json` manifests**, with **226/226 files rehashed byte-for-byte**. No missing/changed sealed evidence.
- **20 `trace.bin` files**, 19 fixed 48-byte records each. All **380/380 decoded records** match the original `trace.json` data, and each trace digest matches the `RESULT.json` reference.
- **40 real SIGTERM handler invocations**, exactly two entries and two exits per consumer at one signal depth, with **zero observed interposed allocator events** within each handler. This is specific to the instrumented paths; it is not a proof that no unseen glibc allocation or race can exist elsewhere.
- **16 top-level campaign records** (do not confuse with 20 consumers): **8 achieved**, including seven witness configurations and one RESET with a second attempt; **8 rejected**, modes `short`, `timeout`, `timeout-gate`, `wrong-landing`, `low-outside`, `collision`, `reverse`, `unavailable`. The `timeout` and `timeout-gate` results preserve `seconds=210.0` with `reason=time-limit`. Twenty sealed world files represent eight distinct `world.wbt` hashes.
- No `Segmentation fault`, `core dumped`, `malloc(): corrupted`, or `SIGABRT` markers in the twenty native Webots logs. Existing native startup and teardown captures are sealed with the original `sha256.json` manifests.

**Independent technical audit:** [issue #665 comment 6502541803](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6502541803) documents the exact downloaded ZIP, trace alignment and limitations. This run is distinct from the previous **red** composed-world run [#40907399724](https://github.com/djibian/webeeblocks/actions/runs/40907399724), which lacked required upstream PROTO assets and stays a historical **FAIL**. Here the pinned Cyberbotics `projects/` mount supplies those unmodified assets; the oracles did not change.

## Strict qualification limits and repeat policy

The combined Linux ELF is **NOT an adopted OCI, installer, or classroom distribution**. No Windows-native qualification of this combined artifact, no canonical exact-Ready-HEAD `CI Gate`, no independent product GO or owner checkpoint is conferred. This run does **NOT demonstrate the cause or cure of the historical post-READY Qt console `QRawFont/malloc` SIGSEGV**; that crash was not reproduced. The collision RESET_TIMEOUT and wall-clock stall in #637 remain open. No physical drone, flash or `TEST_REQUIRED` is authorized.

After successful evidence capture, the workflow is changed to `workflow_dispatch` only: do **not** automatically rerun the same 20 native cases for a documentation-only commit. A future run requires a **new falsifiable question or changed relevant source/dependency**. The original run's exact HEAD and artifact URL remain the decision referents; this README's later documentation commit is **not** a new tested candidate.
