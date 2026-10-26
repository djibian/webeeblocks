# #665 — Webots R2025a Qt lifetime candidate (NOT QUALIFIED)

**Status: SOURCE CANDIDATE ONLY — native repair UNPROVEN.** This directory
contains a *source patch*, not a rebuilt Webots application, not a classroom
release, not a modified CI image and not an integration authorization.

## Anchors and bounded claim

- Upstream Webots R2025a commit: `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.
- Original blobs (pinned by `qualify_source_patch.py`):
  `WbMainWindow.hpp=53806f899578622f9da956d06e8a2a2ab96c6a98`,
  `WbMainWindow.cpp=55e5f8afad696d43ad9be425743861cec73fad21`,
  `WbApplication.cpp=65dfca226077bd0c0f97f8996d5acd04fc572e57`.
- Historical official runtime image:
  `cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099`.
- Causal native witness: #665 comment `6411895724`; independently reasoned
  design `6412714514`; binary consumption boundary `6413208368`.
  Reuse those archives; do not repeat the baseline acquisition.

In Webots, `QProgressDialog::setValue` may process nested events and return to
`QProgressBar::maximum`. A download-completion callback can currently call
`WbMainWindow::deleteWorldLoadingProgressDialog` and synchronously destroy
the same dialog/bar *inside* the active `setValue` frame.

The patch retains the same modal loading UI, cancel intent and event processing.
It makes the active pointer nullable **before** disconnect/hide, protects
creation/progress/status/hide operations with a nested depth counter, and
schedules deletion of detached dialogs **only when the last guarded operation
has returned**. It also moves the `mWorldLoadingProgressDialogCreated=true`
assignment *before* emitting the reentrant creation signal. A former dialog
must not be reused when a new load starts inside an old call.

This is a candidate architecture, not a proof that *all* destruction paths are
protected. In particular, parent `WbMainWindow` destruction while a protected
dialog frame runs and stale downloader callbacks are further adversarial cases
to examine. No claim of independent runtime repair is made.

## Executable offline source qualification (not a compiled Qt test)

With a local clone of `cyberbotics/webots` checked out at the exact commit:

```sh
git -C /path/to/webots checkout --detach c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
python3 experiments/webots-qt-665/qualify_source_patch.py --webots-tree /path/to/webots
```

The script fails closed on a different commit, mismatched source blobs,
unexpected patch paths, non-applicable patch or absent guarded-retirement
structure. It applies the patch **only in a temporary directory**, leaves the
upstream checkout unchanged, prints both original and patched blob IDs and the
patch SHA-256, and marks all unexecuted native/CI obligations `NOT_TESTED`.
It makes **no network request**.

For an actual upstream build, in a *separate expendable clean worktree*:

```sh
git -C /path/to/webots-experiment apply /path/to/webeeblocks/experiments/webots-qt-665/webots-r2025a-guarded-progress-retirement.patch
```

Use the R2025a upstream build instructions, record compiler/flags and all
linked Qt/Mesa libraries, and archive the resulting `webots-bin` SHA-256.
A successful `git apply` or source-only smoke test is **not** a C++ compile,
link test, Qt regression test, or proof that the binary is shipped.

## Required falsification before Ready / production adoption

1. **Compile the actual patched R2025a.** Bind source SHA, patch SHA,
   compiler, Qt 6.5.3 library digests and application binary SHA. Reject an
   unpatched official binary offered as a patched binary.
2. **Targeted Qt reentrance tests using the patched compiled implementation:**
   retire mid-`setValue` while modal event processing is active, and independently
   during creation/`show`/`setValue(0)`, status, download/cancel/close,
   duplicate retire, nested creation, old/new generations and window shutdown.
   Assert `QProgressBar::maximum` occurs while the old bar is **alive**, old
   destruction after last protected return, no double destruction, cancel
   preserved, no stale update and eventual drain of retired dialogs.
3. **Native A/B on the identical world/staging/image stack**, using the
   already-qualified GDB breakpoint strategy from #665 / run 40293916941.
   No `--minimize` in the causal arm. Baseline demonstrates the invalid
   lifetime; candidate must actually traverse a retirement-inside-`setValue`
   followed by `maximum`-before-destruction. No SIGSEGV alone is insufficient;
   absence of the discriminating event is `UNPROVEN`. Avoid repeated blind runs.
4. **Adopt the identified candidate binary in the *real* consumers.**
   The ordinary Grand Prix runner imports `IMAGE` from
   `tools/ci/run_grand_prix_u_geometry.py` and still starts the *official*
   pinned image. Other `.github/workflows/ci-runtime.yml` jobs use an official
   `R2025a-ubuntu22.04` tag. Inventory progression, deadlines, Windows/native
   classroom packaging separately. No silent tag fallback or treating patched
   Webots source/assets as a patched `webots-bin`. Record image digest,
   executable sha256 **inside every actual container/launcher**, Qt library
   hashes and the exact binary exercised; test unavailable paths fail closed.
   Keep `--minimize` mitigation analytically separate from this repair.
5. **Full unchanged product oracles:** all native Grand Prix scenarios and
   negatives, READY ≤30 s, RESET freshness, LAND/210 s, startup/Windows and
   other applicable CI jobs. No retry, suppressions, modified world/AST,
   relaxed deadlines or shortened tests. Do not touch #637/#700. A failure in
   LAND remains its own independent refutation.
6. **Governance:** PR Ready HEAD exact, latest completed successful canonical
   `.github/workflows/ci.yml` pull-request run and *real* final `CI Gate`,
   then independent V5 review by a different execution resolving applicable
   findings and recording GO exact SHA. No integration before all conditions.

### Evidence obtained in this branch

A connector-side replay of the unified diff against exact pinned upstream
sources verified all 8 hunks, 3 files and a matching source context (static
patch-application PASS). This does **not** establish the executable script was
run on a full checkout, binary compilation, patched runtime behavior, production
adoption, CI Gate, or pedagogical acceptance. The issue #665 must remain open.

**Never promote this experiment simply because ordinary CI uses `--minimize`
or a standalone Qt model succeeds.**
