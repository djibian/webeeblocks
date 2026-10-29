# POSIX quit notifier — isolated native full-link diagnostic

This evidence branch is based on exact #701 Draft `79370071ff99b871da0e3a9b4c0be6104074783e`, NOT a new product PR. It combines the unchanged existing Qt parent-safety source overlays with the **repaired** POSIX self-pipe patch `e9a6d936...` (lifetime-of-process FDs, bounded one-shot GUI read) on official upstream `c6793d8...`. The earlier experiment parent `d62e286...` built an *obsolete, teardown-refuted* patch `d14be0c...`; it is retained as historic evidence only and must **never** be adopted.

The historical full-link recipe is preserved, with only an exact-blob check and an additional `git apply --check` / `git apply` before building. An upstream mismatch, dependency mismatch, compilation/link failure or launcher failure is a FAIL; no fallback or waiver is permitted. The original Qt/Windows packaged distribution and all mission oracles remain unchanged.

This run can prove actual C++/Qt6.5.3 compilation, linkage and basic executable invocation only. A completed native live signal/allocator contrast, original post-READY crash-cause proof, Windows install, CI Gate and V5 merge are strictly **UNPROVEN** until independently demonstrated. No physical actions.

This updated candidate runs the repaired patch's own independent source validator **before** the expensive build. It explicitly rejects revoking/closing an already-published FD, and still checks immutable upstream identity, single-file patching, nonblocking/CLOEXEC FDs, bounded notifier and Windows source separation. A static PASS is not transferred as a native result. A passing full build proves composition and launcher smoke only: signal-context behavior of the **combined** executable and full mission campaign are NOT_TESTED.
