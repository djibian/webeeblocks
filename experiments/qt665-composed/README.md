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
