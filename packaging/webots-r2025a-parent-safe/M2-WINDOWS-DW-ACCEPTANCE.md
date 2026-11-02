# M2 private Windows R2025a B — deterministic D/W acceptance

**Status: PROCEDURE ONLY — NOT TEST_REQUIRED, NOT A HUMAN PASS.** This test must bind the exact *current* immutable archive and candidate Git SHA. An old W1/W2 PASS or Qt methods-only PASS is not a substitute.

## Current release identity, independently attested

- Producing run: https://github.com/djibian/webeeblocks/actions/runs/41450732733 ; source `1cfefebf127cd70b90d2c14a8360fd8d978e6710`; artifact `13144826515` named `m2-windows-private-product-candidate`, inner `M2-private-product.zip`.
- **Exact ZIP SHA-256:** `dc614c04ca10115a85d76ce6e5150bd9e7551f0fe8cd3937f7b24563ec9b72c8`.
- **Immutable OCI copy:** `ghcr.io/djibian/webeeblocks-m2-private-windows-r2025a@sha256:ec0d516047bacf56aa536d29e6116636cec8632392d5bcf71992a3281e6e84fd`.
- Independent reconstruction: https://github.com/djibian/webeeblocks/actions/runs/41451536084 — identical inner ZIP SHA-256.
- Package retention/verified readback on an independent runner: https://github.com/djibian/webeeblocks/actions/runs/41451621194 — 11,366 private file SHA-256 checks, whole ZIP OCI roundtrip, constrained Windows PATH without separate Webots/MSYS2 SDK.
- Native Windows real-product READY, process ancestry, loaded Qt DLL identities: https://github.com/djibian/webeeblocks/actions/runs/41451726713 — `PASS_BOUNDED_NOT_DW`.
- Native Qt 6.11.2 method-only reentrancy/lease/Cancel/parent test: https://github.com/djibian/webeeblocks/actions/runs/41451726930 — **NOT** a full Webots application Q or natural-exit proof.
- Separate Linux parent-safe B full native U campaign: https://github.com/djibian/webeeblocks/actions/runs/41448884297 — **NOT** Linux default-selection evidence and **NOT** Windows D/W.
- Historical ZIP `9f3093082c5155ab3b77dfd902199350b7cecf9a67ceced139fcba03fb77194c` (run `41442076181`, OCI `b9785b1e...`) is retained only in `PROVENANCE.json.windows.historical_private_product`. **Never use its acceptance or artifact IDs for this checkpoint.**

## Deterministic host preparation and fail-closed checks

1. Record the Windows 11 machine's OS build, hardware class, GPU driver, account/session, browser and version, network status, and whether a global Webots installation exists.
2. Obtain the **inner ZIP** from the current digest-pinned OCI or artifact `13144826515`. Verify `(Get-FileHash -LiteralPath .\M2-private-product.zip -Algorithm SHA256).Hash.ToLowerInvariant()` equals **exactly** `dc614c04ca10115a85d76ce6e5150bd9e7551f0fe8cd3937f7b24563ec9b72c8`. Abort on drift; do not substitute a different ZIP or regenerate.
3. Extract to a local writable directory. Require `Webots/`, `controllers/`, `worlds/`, `MANIFEST.sha256`, `PRIVATE_RUNTIME.sha256`, `Launch-WebeeBlocks.cmd`, and `Launch-WebeeBlocks.ps1`. No separate Webots or MSYS2 installation is permitted for this candidate.
4. Run `Launch-WebeeBlocks.ps1 -ValidateOnly`. Require Webots `R2025a` and the launcher strictly under this private `Webots/msys64/mingw64/bin/webotsw.exe`. Global Webots, ambient SDK, or unverified DLL fallback => FAIL. Compare full private file manifest hashes.
5. On an expendable extracted **copy** only, temporarily remove a critical private Qt DLL; `-ValidateOnly` must fail. Restore exact original bytes and recheck manifest, then work on untouched extracted release.

## Interactive Windows D/W — real Webots 3D, same ZIP

6. Disable internet while preserving loopback. Run `Launch-WebeeBlocks.cmd` normally, **not** a mock/headless/manual SDK launcher. Observe live, visible, manipulable Webots 3D scene. Rotate/zoom/move camera; capture screen with real Webots and Blockly visible.
7. Require actual Robot Window `PRÊT`, Webots controller `READY`, and functional WWI handshake. Make a student-level Blockly edit, submit and observe genuine simulated Crazyflie motion and outcome in the live 3D scene.
8. Exercise `STOP`, `RESET` while active, `RESET` after completion, step-by-step, and `Continuer`. Check freshness (no stale request/ACK), neutral scene, no Qt crash, UAF or unowned process interference.
9. Start an activity template and `Enregistrer sous` a new `.wbb` to a school-like user folder. Edit, `Enregistrer`, close, `Ouvrir`, compare actual Blockly workspace/behavior and SHA; open an existing `.wbb`, edit and save to its bound path. **Real** file pickers only.
10. Verify Chrome or Firefox can coexist with Webots; file picker focus/foreground and file roundtrip work. Repeat a representative run/RESET/Open/Save cycle **offline**.
11. Close via the normal Webots window controls (no taskkill). Capture Webots launcher exit code, engine and controller PIDs/create times, child exit/EOF, no surviving owned processes, no Qt fatal and no closure of unrelated browser/foreign processes.
12. Repeat a bounded representative cycle on the low-end classroom reference machine using the same exact SHA.

**Evidence:** exact Git SHA and ZIP/OCI SHA; machine/browser/GPU; timestamps, screenshots, native process/module paths and exits, WWI/Blockly events, saved `.wbb` hash, logs, and explicit **PASS/FAIL/UNPROVEN** for each claim. A screenshot alone never proves child normal exit.

## Authorized V5 boundary

The existing `windows-low-end` GitHub profile prepares another product; it is forbidden for this exact ZIP. Request `TEST_REQUIRED` **only after** an exact-archive profile with deterministic immutable-digest preparation, required preflight tests, provenance/handling and deduplication is implemented and verified in the trusted GitHub checkpoint mechanism. Check that no unresolved request already exists. **Do not notify directly or record a human PASS in advance.**
