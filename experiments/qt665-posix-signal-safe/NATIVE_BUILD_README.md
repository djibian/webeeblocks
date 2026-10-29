# POSIX quit notifier — isolated native full-link diagnostic

This evidence branch is based on exact #701 Draft `79370071ff99b871da0e3a9b4c0be6104074783e`, NOT a new product PR. It combines the unchanged existing Qt parent-safety source overlays with the separately published `d14be0c...` POSIX self-pipe patch on official upstream `c6793d8...`.

The historical full-link recipe is preserved, with only an exact-blob check and an additional `git apply --check` / `git apply` before building. An upstream mismatch, dependency mismatch, compilation/link failure or launcher failure is a FAIL; no fallback or waiver is permitted. The original Qt/Windows packaged distribution and all mission oracles remain unchanged.

This run can prove actual C++/Qt6.5.3 compilation, linkage and basic executable invocation only. A completed native live signal/allocator contrast, original post-READY crash-cause proof, Windows install, CI Gate and V5 merge are strictly **UNPROVEN** until independently demonstrated. No physical actions.
