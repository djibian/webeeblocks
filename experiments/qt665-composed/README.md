# Experimental combined Qt parent-safe + POSIX signal-safe R2025a (NON-GATE)

Runs on candidate parent `79370071ff99b871da0e3a9b4c0be6104074783e` (PR #701 still Draft) but changes **none** of
its 48 Qt paths or four merged #754 native CI observer files. Only a dedicated
experiment workflow, independently pinned upstream single-file self-pipe patch,
and original `LD_PRELOAD` observer are added.

Webots upstream `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, official OCI `cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099`, unchanged Qt6.5.3
runtime, QProgressDialog patch and `repair_parent_shutdown.py` from #701, plus
self-pipe process-lifetime FD patch SHA256
`e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8`.

The exact existing real full-application builder is copied **inside CI** to a
disposable sibling script and one `git apply` statement is added after the
original guarded-progress patch but before the unchanged parent shutdown repair.
No product file is modified in this branch. The resulting full Webots
`webots-bin` must link, start via the authentic installed launcher, and run
one unchanged `unavailable/seed0/side2` real native world with internal
controllers, actual Webots/WWI/AST and existing seal/audit under Xvfb. The real
signal callback is attested from the `webots-bin` symbol and same-process
`LD_PRELOAD` signal/allocator trace. The native witness must reject
unexpected allocations, missing SIGTERM, wrong ELF mapping, mismatched Qt DSOs,
result or unsealed/native terminal failure.

**One bounded sample is not** full Linux adoption or proof of repair of the
historic Qt-console SIGSEGV. This is not a canonical Ready gate and does not
qualify all RESET/positives/LAND exactly 210000 ms, the Windows executable,
redistribution or hardware. Initial and subsequent failures are retained.

## Correcting the missing-PROTO experiment without rebuilding Webots (29 October 2026)

**Previous red is real:** [run 40907399724](https://github.com/djibian/webeeblocks/actions/runs/40907399724) built and linked the full composed Webots binary, but **native READY failed**. Its original [archive #12912812964](https://github.com/djibian/webeeblocks/actions/runs/40907399724/artifacts/12912812964) (ZIP SHA256 `6297921abe863099702661f2353e4f880b06c8510fadc5538713aa450548bddd`) shows missing R2025a PROTO definitions `Crazyflie`, `TexturedBackground`, `TexturedBackgroundLight`, `Floor`; the evaluator raises `StopIteration`. Its teardown-failures.json correctly rejects sealing. There is **no Webots SIGSEGV evidence** in that failed trace. The outer native driver is what usually checks out and mounts those pinned projects read-only; the direct `--native` invocation inside the full-link development overlay did not.

**Bounded repair, no rebuild:** this branch's `replay_prebuilt.py` references **the exact original failed-run ELF**, `webots-bin` SHA256 **`2742d90041fccb4b24fba4558662ecf17d15c092bf28dd93bf014f748cf01c9f`** (202096064 bytes), downloaded by run-id and artifact ID **12912812964** with digest validation. It uses the pre-existing shared **outer** native driver to clone the exact source `cyberbotics/webots@c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b` assets and bind-mount `projects/` read-only, while keeping the original unavailable/seed0/side2 oracle and the exact composed ELF. The executable runtime image now comes from the pinned #701 Qt OCI `ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca`, rather than the previous full-link development image. **Both the assets and runtime OCI environment differ** from the failed run, not just one variable.

**Green native evidence:** [NON-GATE run #40911770252](https://github.com/djibian/webeeblocks/actions/runs/40911770252), exact HEAD `8be7d3608352b08463c56ff91c251424cdebb6ed`, `completed/success`. [Artifact #12914516568](https://github.com/djibian/webeeblocks/actions/runs/40911770252/artifacts/12914516568) **406197 bytes**, SHA256 `a027bcd50bd1b6510a271b05833a1abb401e92521688ae431320ddbd75366c84`, **22/22 CRC**. The archive was independently opened and the **12/12 native seal hashes** recalculated byte-for-byte.

The *actual installed composed ELF* has **PID/TID 132/132**, device **47**, inode **9050321**, four registered handlers and **two** `SIGTERM` entries/exits in `trace.bin` (**19 native 48-byte records**, exact `trace.json` correspondence), with **zero interposed allocator events at positive signal depth**. `R-P` matches the native callback symbol offset `0x54b220`. Core/Gui/Widgets loaded libraries retain official SHA256 `ac391204…`/`f8396f49…`/`868b516d…`. `WEBEEBLOCKS_RUNTIME_V2 READY` and both `INFO: … Terminating.` records appear, no native terminal-fatal marker. The world has SHA256 `4b17c32951fa76627e73485dc41c7ef30ef91f76b950b0525bf78a0f7322ef5a`, events `a91a7cde8f069d55a26ed422d91d4cd041a70b25b4539673dc30f4de0d423904`, and AST `89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d`, matching the earlier genuine pair. Negative `not-achieved/runtime` at **8.904 simulated seconds**, strict capture audit PASS, group after cleanup empty. Direct wrapper exits `-15/0` are not asserted as Webots PID132 exit status.

**Failures preserved, not requalified:** [40910939288](https://github.com/djibian/webeeblocks/actions/runs/40910939288) aborted before native launch on a pinned OCI expectation mismatch, [40911484047](https://github.com/djibian/webeeblocks/actions/runs/40911484047) likewise on an overstrict parent-commit ancestry check; neither supplied a native result. The corrected attempt did not waive these guards: exact #701 OCI digest and Git ancestry remain checked.

**Boundary:** This shows the exact combined ELF can start, use its real SIGTERM handler without the prior interposed allocations, and retain this ONE strict unavailable negative when projects are present in the pinned Qt OCI. It does **not** prove that missing assets alone caused all previous trouble (OCI also differs), guarantee GUI close on every ordering, repair the historical `QRawFont/malloc` core, restore #637 collision RESET, qualify positive/other negatives/LAND exactly 210000ms, or satisfy Ready CI, independent GO, Windows and product OCI/install adoption.

After this one meaningful result the workflow changes from automatic `push` to explicit `workflow_dispatch` to prevent repetition; no additional native replay should be run without a new discriminating question.
