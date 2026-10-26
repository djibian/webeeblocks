# #665 — Webots R2025a Qt lifetime repair candidate (NOT DEPLOYED)

**V5 status, 26 October 2026: #701 Draft, #665 OPEN; no Ready CI Gate, independent GO or merge.**
The original source-only description and chronological experiments below are
historical. A real complete **Linux** parent-shutdown-safe `webots-bin` was
built and launched; its SHA-256 is
`e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545`.
It is preserved as [artifact 12666096845](https://github.com/djibian/webeeblocks/actions/runs/40354624966/artifacts/12666096845).

**CRITICAL: the first `.patch` file alone is NOT the safe final candidate.**
The earlier complete binary `d3140f65e361a109efd9ca3e7b5cac48594eb1fe87ccc35099a58ed117116fa9`
was refuted by the native Qt parent-shutdown counterprobe
[40352255637](https://github.com/djibian/webeeblocks/actions/runs/40352255637).
The parent-safe binary requires the *additional* fail-closed
`repair_parent_shutdown.py` transformation, as applied by
`build_full_application.sh`. Do not deploy or propose the base patch alone.

**Proven, bounded:** real compiled Webots Linux ELF / original Qt6.5.3;
method-level Qt reentrance, parent deletion and late-cancel regression
[40358835107](https://github.com/djibian/webeeblocks/actions/runs/40358835107);
four real Linux runner scenarios with *temporary* identified ELF substitution
[40357331972](https://github.com/djibian/webeeblocks/actions/runs/40357331972).
The [full-native-GDB experiment 40376559561](https://github.com/djibian/webeeblocks/actions/runs/40376559561)
proves the lifetime ordering during the real `QProgressBar::maximum()` frame,
**only under an explicit debugger-injected retirement**. It is NOT a natural
download-completion callback.

**Still UNPROVEN / NOT DONE:** equivalent nested callback caused naturally by
the download manager on the new full executable; permanent official Linux
consumer/image adoption; authentic patched Windows `webots-bin.exe` build,
Qt DLL attestations, packaging and reference-PC validation; complete native
oracles; exact successful **Ready** `CI Gate`; independent V5 GO and conditional
squash integration. The existing `timeout-gate` native `low-outside-zone` FAIL
is unchanged, even though independent LAND at 210 s was observed. No oracle or
safety threshold may be weakened to hide it.

**Fail-closed boundary added in #701:** `attest_and_install_candidate.py`
accepts only the exact parent-safe ELF digest above, not an arbitrary SHA-256
supplied by the caller. `tools/ci/test_repository_hygiene.py` falsifies attempts
to authorize the known-unsafe previous ELF and the unmodified official image.
The attester operates on disposable Linux installations only and constitutes
neither official Linux adoption nor Windows qualification.

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

The isolated GitHub Actions source-only experiment
[run 40311761613](https://github.com/djibian/webeeblocks/actions/runs/40311761613)
completed successfully at candidate `b600712b4555cd6828589254c83e86bc2d3f997a`.
It checked out exactly the 3 pinned upstream source blobs, ran the executable
offline checker on a sparse R2025a checkout and archived the manifest
[artifact 12645231418](https://github.com/djibian/webeeblocks/actions/runs/40311761613/artifacts/12645231418),
GitHub ZIP digest `sha256:653532502645b353e9748eed315102bb2c067534d0d7e084e4fc685aa4ef3725`.
The patch content SHA-256 was `7a3603eaef1d6addc59175c6ed3363bc51497827fa39a699c8ee6af073280e94`.
Manifest result **SOURCE_PATCH_APPLIES_ONLY**, post-patch blobs:
`WbApplication.cpp=404ac1269f022ff4bde41801cdb79b2015c8ac65`,
`WbMainWindow.cpp=c7aa1815851a9eb7453a534b0cf96c5b43ecd65f`,
`WbMainWindow.hpp=af25aca90c2ad2ac0dfa456928f9f4162fca6ff2`.
The transient push workflow that acquired this evidence was removed from the
candidate after the canonical V5 workflow-contract test rejected adding
unauthorized workflow filenames/push triggers. The *historical artifact* remains
valid for the identical patch blob; it does not become candidate CI Gate.
**Neither compilation, Qt lifetime A/B, production binary adoption nor
pedagogical acceptance are proven.** #665 must remain open.

**Never promote this experiment simply because ordinary CI uses `--minimize`
or a standalone Qt model succeeds.**


## New bounded build evidence — 26 October 2026 (native C++ *objects*, no executable)

A distinct, isolated push-only **NON-GATE** experiment on
[`evidence/665-qt-compile-probe-20261026`](https://github.com/djibian/webeeblocks/tree/evidence/665-qt-compile-probe-20261026)
reached the first actual native C++ compilation of this candidate. The
[final run 40318579548](https://github.com/djibian/webeeblocks/actions/runs/40318579548)
at exact evidence HEAD `62525a859580a21d91433b33f766d71ae3af44f9`
completed **success**, with preserved
[archive 12648036935](https://github.com/djibian/webeeblocks/actions/runs/40318579548/artifacts/12648036935)
(ZIP SHA-256 `7d5365bdd93b4c137f259de0a86eaf404ac4d65bb80959a562903bf29c7d9962`).

Actual `g++ -std=c++17 -DQT_NO_DEBUG -fPIC -c` on **both** real
R2025a translation units `src/webots/gui/WbMainWindow.cpp` and
`src/webots/app/WbApplication.cpp` succeeded before and after applying
the unchanged source patch. Upstream SHA `c6793d8f...` and original
blob identities were prechecked. GCC was Ubuntu 11.4.0. The build
container derived from pinned official image
`cyberbotics/webots@sha256:f0023e30...` with **development-only**
Ubuntu GL headers (`libgl-dev`, `libglu1-mesa-dev`,
`libassimp-dev`, `libfreetype6-dev`). The exact Qt 6.5.3 runtime
library hashes stayed `Widgets=868b516dde6d...`,
`Core=ac391204135f...`; missing non-used Qt headers
QtOpenGLWidgets, QtQml and QtXml were recorded. Earlier failed trials
[40318043186](https://github.com/djibian/webeeblocks/actions/runs/40318043186),
[40318242058](https://github.com/djibian/webeeblocks/actions/runs/40318242058)
and [40318423220](https://github.com/djibian/webeeblocks/actions/runs/40318423220)
establish precondition corrections (headers/OpenGL/include path), **not**
C++ regressions.

Resulting object SHA-256 (byte identities, **not** a linked or loaded Webots binary):

| Unit | Original R2025a | Guarded candidate |
| --- | --- | --- |
| `WbMainWindow.o` | `a4c96ace2c6e0c9b7870d5250a4e7a136e9e6003f0467d8629dbb92a4a34c124` | `cd451c144d58a73afda5f43442fbd29c17f4d55afd58825b909cab462d3645d3` |
| `WbApplication.o` | `32060bb5993fdd4b4eae8027978cc9d3e91248cca1c261de83cc725211aebe48` | `4bbbe340e4ed0fa5c43e902f7113733c3f2223df181f0471333fe9747f3aef20` |

**Interpretation strictly bounded:** both modified units are syntactically
and semantically accepted by a real C++ compiler against the pinned source
and Qt headers/libraries in this environment. No full Webots link, Qt
adversarial harness on the patched implementation, modal A/B in the actual
simulator, product binary adoption, or canonical **Ready** CI has occurred.
The production launchers still execute the original official image; this
experiment must NEVER be used as a #665 repair PASS or as a reason to
weaken LAND/#700 tests.

## Executed Qt 6.5.3 adversarial method regression — 26 October 2026

A second, **separate** native C++/Qt experiment now qualifies bounded
behaviors of the **five original patched method definitions**, as opposed
to a reimplementation or a static text check.

- Generator in this PR: `qt_guarded_method_harness.py`. It extracts the
  method implementations verbatim from the **actually patched pinned Webots
  source**, then supplies minimal Qt-compatible mocks only for the adjacent
  `WbApplication` cancellation signal target and Windows dark-mode hook.
- Diagnostic [run 40320524036](https://github.com/djibian/webeeblocks/actions/runs/40320524036),
  exact evidence SHA `c7e0c2891620e17a0af455f3f5694b6da91672bb`,
  completed **success**; [archive 12648602612](https://github.com/djibian/webeeblocks/actions/runs/40320524036/artifacts/12648602612),
  ZIP SHA-256 `506e4fceae4b549ac2451003afd2ea143713ddb2633406af5c79a626429c88d3`.
  The archived log verifies successful baseline/patched C++ object compilations,
  the actual Qt xcb plugin loaded under Xvfb, and direct Qt 6.5.3 library
  identity. It is a NON-GATE experimental `push` workflow **only on its
  isolated evidence branch**, never an authorized workflow added to the PR.
- The method executable is linked against the existing exact Qt 6.5.3
  `libQt6Widgets`, `libQt6Gui`, and `libQt6Core` from the same pinned
  Webots official image. Building requires a **development-only image** with
  the native GL headers, Xvfb, xauth and xcb-cursor runtime dependency;
  `LD_LIBRARY_PATH` mirrors the genuine Webots Linux launcher.
- Observed executable assertions, without relying on mere non-crash:
  `retire_mid_setValue: callback=1 guarded=1 old_alive_inside=1
  old_alive_at_return=1 fresh_distinct=1
  old_destroyed_after_return=1 fresh_active=1 status_safe=1
  fresh_drained=1`;
  `retire_during_creation: callback=1 guarded=1 alive_after=1
  inactive=1 drained=1`;
  `retire_during_status: callback=1 guarded=1 alive_after=1 drained=1`;
  `cancel_preserved: before=0 after=1`.
  Verdict: **`QT665_GUARDED_METHODS_VERDICT=PASS`**.

**Reproduction:** in the *separate expendable R2025a checkout*, apply the
candidate patch; run
`python3 experiments/webots-qt-665/qt_guarded_method_harness.py
--patched-cpp /path/to/webots/src/webots/gui/WbMainWindow.cpp
--output qt665-guarded-methods.cpp`; compile this generated file with GCC
C++17 and the pinned Qt 6.5.3 headers/libraries and run under Webots' Qt
`xcb` platform and Xvfb. The diagnostic evidence branch holds the exact
reproducible workflow and command lines, including initial environment
failures. The initial `offscreen` plugin did not exist, and the native
`xcb` plugin needed the same `LD_LIBRARY_PATH` as the Webots launcher.
Those pre-execution failures are not source-patch failures.

**LIMITATION:** this is a **method-identical C++ test harness**, not the
linked Webots application, a real download callback in the full Webots
event graph, a production `webots-bin`, a patched image digest, or causal
modal native A/B inside real Webots. Window-parent destruction and
asynchronous callbacks across generations remain to falsify. No assertion
here implies that production/CI uses the corrected binary; the original
official image is still selected. Do **not** promote Ready, merge, close
#665, relax the canonical CI Gate or touch #637/#700 without all remaining
native and adoption proofs.

## Genuine Qt setValue call-stack discriminator — 26 October 2026 (METHOD-LEVEL PASS)

The already patched R2025a method implementations were extracted *verbatim*
to a C++ test executable linked against the **actual pinned Qt 6.5.3**
libraries and exercised under Xvfb/XCB/GDB 12.1. C++ noinline markers,
native stack frames, `QProgressBar::maximum()` address and Qt `destroyed`
signals establish ordered events, not just absence of a crash.

- [NON-GATE run 40351198213](https://github.com/djibian/webeeblocks/actions/runs/40351198213)
  `completed/success` at evidence HEAD `0f2ec488e5a367bddf7cc90cda85e5b36f61c54e`;
  [artifact 12663901155](https://github.com/djibian/webeeblocks/actions/runs/40351198213/artifacts/12663901155)
  ZIP SHA-256 `b2203217fb029b12ea0e28f791618b82f6817925c0d201d4fc867285b20dba0b`.
- **Positive stack:** old dialog/bar marker 10; callback marker 11 *inside*
  true `QProgressDialog::setValue` (Qt's own event dispatcher in stack);
  old detached but alive marker 12 in the same frame; subsequent
  `QProgressBar::maximum` on the **same old bar address**; protected
  return marker 13; old bar destructor marker 14 on deferred event
  *outside* `setValue`; drained marker 15.
- **Negative discriminator:** identical retirement under non-modal
  Qt is dispatched by the *outer* `WbMainWindow::setWorldLoadingProgress`
  `QApplication::processEvents`, *without* `QProgressDialog::setValue`
  in the callback's true stack; never accepted as modal causal PASS.
- **Discriminating precondition:** `show()` alone did not reliably
  establish Qt's internal `shownOnce` flag. The harness calls the
  *actual Qt metaobject* `forceShow` slot before arming the timer,
  rather than injecting private memory. The [earlier run 40350256406](https://github.com/djibian/webeeblocks/actions/runs/40350256406)
  correctly failed when the callback was served outside `setValue`.
  A pair of intermediate runs appearing successful but not loading
  the GDB Python script are INVALID; the final run executed the
  debugger and enforced the generated JSON `verdict=PASS`.
- **Reproducibility:** `qt665_causal_discriminator.py` and
  `qt665_causal_discriminator.gdb.py` live beside the original test
  generator. The exact pinning/compilation/GDB recipe is on the
  [isolated evidence branch](https://github.com/djibian/webeeblocks/tree/evidence/665-qt-causal-discriminator-20261026).
  Its diagnostic push-only workflow must NOT be copied to the PR.

**Bounded interpretation:** deterministic causal PASS on *real Qt* and
*verbatim Webots method definitions*, **not** on the complete linked
`webots-bin` executing a real asynchronous download callback. The
corrected full ELF (`d3140f65e361a109efd9ca3e7b5cac48594eb1fe87ccc35099a58ed117116fa9`)
was previously built, launched, and consumed in bounded unchanged native
runner tests (see PR comments 6419196331 and 6419384826). Its **internal
modal frame path** and parent-shutdown/stale-callback safety remain
unproven. Product CI Linux/Windows continues to use official unpatched
Webots. The unchanged `timeout-gate` oracle continues to fail BOTH
official and candidate binaries due to preceding `low-outside-zone`
(independent LAND at 210000 ms remains correct). No alteration of
oracles, LAND, RESET, worlds, AST or deadlines. Maintain **Draft**
and issue #665 **OPEN** pending actual consumer adoption, complete
qualification, Ready exact-head CI Gate and independent V5 GO.

## Reentrant PARENT shutdown: historical refutation and experimental repair — 26 Oct 2026

**Do not describe original patch as globally safe.** The initial source patch
guards ordinary retirement but not destruction of WbMainWindow during its
own nested modal `QProgressDialog::setValue` call.

- **Blocking counterexample on original patch:** NON-GATE
  [run 40352255637](https://github.com/djibian/webeeblocks/actions/runs/40352255637),
  parent GDB job 121675181950, `completed/success` as a DETECTOR:
  the bar was destroyed during the real Qt `setValue` frame and
  `QProgressBar::maximum` later read the exact **destroyed** address.
  `QT665_PARENT_COUNTEREXAMPLE=CONFIRMED`. The process exited normally;
  lack of SIGSEGV is not safety.
- **Experimental repair:** `repair_parent_shutdown.py` is a
  deterministic, fail-closed, SECOND source transformation applied after
  the original guarded patch to the same pinned upstream commit. The
  patch adds `WbWorldLoadingProgressLease`, shared by active calls,
  detaches dialogs during parent destruction and queues deferred deletion
  only after the last active protected method returns; all lambda accesses
  to WbMainWindow after reentrant Qt calls are QPointer guarded.
  This is a genuine new source variant, not the binary built earlier.
- **Two simultaneous pass results:** [run 40353966663](https://github.com/djibian/webeeblocks/actions/runs/40353966663),
  exact experimental HEAD `bc54874026b135d1cfaff9db7258dd7c21a074b2`,
  two `completed/success` jobs under *actual* Qt6.5.3/GDB. The modal
  retirement test still passes; the formerly failing parent counterprobe
  establishes parent deletion within `setValue`, same living bar accessed
  afterwards in `maximum`, survival through return, and deferred
  child destruction thereafter:
  `QT665_PARENT_LIVE_BAR_MAXIMUM_INSIDE_SET_VALUE=PASS`,
  `QT665_PARENT_DEFERRED_DELETE_AFTER_RETURN=PASS`,
  `QT665_PARENT_SHUTDOWN=PASS`.
  [Modal GDB archive 12665596162](https://github.com/djibian/webeeblocks/actions/runs/40353966663/artifacts/12665596162)
  ZIP SHA-256 `2ec4a77ea66e6158e05e7ab9be34214b9d5295c9b16200435cae596a5e4c7f68`;
  [parent shutdown archive 12664117768](https://github.com/djibian/webeeblocks/actions/runs/40353966663/artifacts/12664117768)
  ZIP SHA-256 `b585e95cff9445b198baf644f23418a76506b1b1c10384c4f4217986f7c8d5fe`.
- **Reproduction:** apply the original patch to a CLEAN pinned R2025a
  checkout, then run
  `python3 experiments/webots-qt-665/repair_parent_shutdown.py
  --webots-tree /path/to/patched-webots`.
  `qualify_source_patch.py` checks both transformations fail-closed and
  records their independent SHA-256 plus the resulting source blobs.
  `build_full_application.sh` compiles this COMPOSED source in a pinned
  native Webots toolchain and verifies the XCB launcher; the build is
  separately qualified and must NEVER reuse the former ELF hash.

**Status boundary:** this is a parent-shutdown METHOD-level PASS, not a
fully qualified Webots executable, genuine asynchronous WbDownloadManager
completion/cancellation, successive generations or packaged Windows Qt.
The new `build_full_application.sh` recipe must generate an authentic
new ELF and its native real-consumer matrix must pass before promotion.
Existing oracles, negative cases, LAND 210 s, RESET and all other
teams' Grand Prix changes remain untouched. Continue Draft/OPEN.

## Linux candidate consumption — fail-closed prototype, NOT product adoption

`attest_and_install_candidate.py` requires an **explicit full 64-character
SHA-256** for the newly linked Linux executable. It rejects incorrect
architecture/version, a binary equal to original R2025a, baseline ELF
mismatch, wrong exact Qt6 Widgets/Core bytes, missing XCB plugin, unresolved
native dependencies, and Qt libraries resolved outside this Webots runtime.
By default it only reports `VERIFIED_NOT_INSTALLED`; replacement requires
the conspicuous `--replace-disposable-installation` opt-in, intended
**only for an expendable experimental container**, not a classroom machine.
An audit JSON is always written. This helper does not certify provenance
of its container image by itself, make a new binary qualified, or turn a
Linux ELF into a Windows executable.

Reproducible execution after the NEW full-link artifact is qualified:

```bash
python3 experiments/webots-qt-665/attest_and_install_candidate.py \
  --runtime-home /usr/local/webots \
  --candidate /workspace/qt665-evidence/webots-bin \
  --expected-candidate-sha256 NEW_BINARY_SHA256_FROM_VERIFIED_ARTIFACT \
  --manifest /workspace/qt665-evidence/installation.json \
  --replace-disposable-installation
```

**Product integration NOT DONE.** Linux regular GP runner reads `IMAGE`
from `tools/ci/run_grand_prix_u_geometry.py`; other `.github/workflows`
invoke the original R2025a Docker tag. To consume a fully qualified fix
officially, pin an immutable corrected Linux image digest and verify
the ELF and Qt runtime identities **inside each real execution**.
Windows `packaging/windows/Launch-WebeeBlocks.ps1` searches the installed
Webots R2025a and currently validates the version, not this corrected
binary. It needs a separately built, independently checked patched
`webots-bin.exe` and exact Qt DLL closure; Linux sha256 evidence cannot
be transferred to Windows. No implicit image/tag/Qt fallback permitted.

## NEW full Webots R2025a ELF — parent-safe composed source (26 Oct 2026)

**Native full link and XCB launcher PASS, NOT product readiness.**
Isolated NON-GATE [run 40354624966](https://github.com/djibian/webeeblocks/actions/runs/40354624966)
completed/success at evidence HEAD `e5fa2d8c1409a1c97f63d9b14039683ffcfb0b05`;
[artifact 12666096845](https://github.com/djibian/webeeblocks/actions/runs/40354624966/artifacts/12666096845),
ZIP SHA-256 `5b831acea004ecbcd3ed301846c745fed5b64edb9a5261738ac43ffb3d0d05d0`.
The ELF digest was recomputed from the **actual artifact's 202081872 bytes**,
not copied from a former candidate:

- **Strengthened new Linux ELF SHA-256**:
  `e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545`.
- Historical weaker candidate (DO NOT ADOPT for parent protection):
  `d3140f65e361a109efd9ca3e7b5cac48594eb1fe87ccc35099a58ed117116fa9`.
- Official baseline from original image:
  `1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb`.
- Unchanged runtime Qt 6.5.3:
  Widgets `868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024`;
  Core `ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8`.
- Exact composite source: upstream
  `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`,
  initial patch SHA-256 `7a3603eaef1d6addc59175c6ed3363bc51497827fa39a699c8ee6af073280e94`,
  shutdown overlay SHA-256 `817f0ae4e9e9ec01da58ce23e228f44eb06f65e2da62b2c9db792d1abb0231db`;
  resulting WbMainWindow cpp Git blob `8451da9df169cf07439535f71451b3aed8b6f23f`,
  header blob `ac39c30fbfaf7cf2f0a042ee5a55cb2c9c156eb8`,
  WbApplication cpp blob `404ac1269f022ff4bde41801cdb79b2015c8ac65`.

The full build produced linked `webots-bin`, complete native dependency
closure (`ldd`: no unresolved entries), correct genuine Qt DLL/SO resolution
and **`QT665_LAUNCHER_VERSION=PASS`** with real Linux XCB/Xvfb,
showing `Webots version: R2025a`. It does not establish
completed genuine WebeeBlocks consumer tests, packaged Windows source
build or Windows Qt DLL fingerprint. Regular official consumers are
**not yet switched**. Never reuse the previous ELF SHA as proof of
this new variant.

The [isolated native consumer campaign](https://github.com/djibian/webeeblocks/actions/runs/40357331972)
uses the exact SHA, pinned original runtime, strict
`attest_and_install_candidate.py` and unchanged main native
`short`, `reset`, `wrong-landing`, `unavailable` tests; its outcome
must be checked before claiming those results.

### New parent-safe ELF exercised in real WebeeBlocks native GP consumers

**NON-GATE, NOT production adoption.** The fixed Linux ELF
`e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545`
was verified **inside** a disposable pinned R2025a Docker runtime and used
by unchanged native runners from main
`7ba59aca5047b5a1fa3b14ccb9724323130547c6`.

- [Consumer run 40357331972](https://github.com/djibian/webeeblocks/actions/runs/40357331972):
  exact experiment HEAD `1f44d0e29626c574ca53aad0ffcd56624024bfd1`,
  `completed/success` with **both matrix jobs success**.
- [Positive archive #12666691441](https://github.com/djibian/webeeblocks/actions/runs/40357331972/artifacts/12666691441),
  ZIP SHA-256 `b3066bbf5473e402ce418014a6fd8d6de3684ecd5355af777658de1e0a193977`;
  [negative archive #12666073656](https://github.com/djibian/webeeblocks/actions/runs/40357331972/artifacts/12666073656),
  ZIP SHA-256 `3cdf0460f0d03a552e97fe3111844caae27cce79b5ada03d44e89453584abd80`.
- `QT665_DISPOSABLE_LINUX_ADOPTION=PASS` in each native job, no arbitrary
  fallback to official baseline after checking the exact ELF and Qt identity.
- `short` PASS, expected `not-achieved / wrong-landing` at 13.736 sim sec;
  `reset` PASS, three crossings per attempt and `achieved` at
  163.936 sec / after genuine RESET 160.064 sec;
  `wrong-landing` PASS as negative at 159.56 sec;
  `unavailable` PASS as negative `not-achieved / runtime` at 8.808 sec.

**Explicit blockers:** The official Linux image selectors/CI have NOT
adopted this ELF; Windows does not have a qualified rebuilt `webots-bin.exe`.
A/B original/previous-patch `timeout-gate` still FAILs the existing
`low-outside-zone` outcome before the independent correct LAND deadline
210000 ms. Do not relax, omit or silently reinterpret this negative oracle.
True full-ELF modal retirement event stack, genuine late network callbacks,
all V5 suites, exact HEAD Ready canonical CI Gate, and independent GO remain
separate obligations. Preserve #701 Draft and #665 OPEN.

### Stale cancellation and successive dialog generations — true Qt regression

On the same **composed source** and true Webots Qt6.5.3,
[NON-GATE run 40358835107](https://github.com/djibian/webeeblocks/actions/runs/40358835107)
completed/success with both native GDB jobs. The causal generator now
also executes the controlled `qt665_late_cancel_generations` case:

- The canceled connection of generation 1 is disconnected before its
  previously live button receives a stale click (`old_alive=1`,
  `disconnected=1`, `unaffected=1`).
- Three distinct dialogs are created; generations 1 and 2 are drained
  only after deferred Qt processing, while generation 3 is live, remains
  active and later drains (`second_unique=1`, `third_unique=1`,
  `old_drained=1`, `fresh_alive=1`, `fresh_drained=1`).
- The modal frame and parent-shutdown genuine-Qt discriminators remain
  PASS; no method implementation is rewritten by the test generator.

Artifacts: [causal archive #12666343770](https://github.com/djibian/webeeblocks/actions/runs/40358835107/artifacts/12666343770),
ZIP sha256 `c78d8b240fdb817eb5fd5be0cf315f9dda768f95f452c5b53cf0670df53422de`;
[parent archive #12667302341](https://github.com/djibian/webeeblocks/actions/runs/40358835107/artifacts/12667302341),
ZIP sha256 `21539f083f357c7156635f862b813a21e0766eab5d5ee46e34e8d2566954e509`.

**Boundary:** this is a *mocked WbApplication canceled-slot* method-level
test, not proof of late in-flight `WbDownloadManager` replies or genuine
download request identity under complete Webots. No new official adoption
or V5 GO is implied.


## Runtime-process adoption attestation (experimental, NOT a deployment)

The new \`attest_running_consumer.py\` is an independently checkable **Linux
process identity probe**, not a runtime patch or a natural Qt callback witness.
Run it **inside the same container** while its real \`webots-bin\` PID is alive:

\`\`\`sh
python3 experiments/webots-qt-665/attest_running_consumer.py \
  --runtime-home /usr/local/webots --pid "$WEBOTS_PID" \
  --manifest ci-artifacts/qt665-running-consumer.json
\`\`\`

It rejects an official or historically refuted ELF, wrong R2025a, stale PID,
other executable, deleted or wrong Qt mappings, mismatched Qt binary digests
and a changed process starttime. It checks the actual Linux \`/proc/PID/exe\`
and \`/proc/PID/maps\` instead of inferring runtime adoption from a copied file,
\`ldd\`, image tag or install manifest. The isolated negative tests are
exercised from repository-hygiene CI. A positive result has **not yet been
obtained from any ordinary CI consumer**. It would prove exactly the inspected
running Linux process's ELF/Qt identity, not image supply-chain immutability,
all workloads, prevention of any UAF, Windows parity, or product deployment.
The existing official runtime paths still need deliberate correct adoption.
